"""Los segmentos de YPF, trimestrales, desde la nota de segmentos de los 6-K.

Por qué importa acá: el caso pregunta por qué el mercado castigó a la acción
pese al balance récord, y esa respuesta no está en el consolidado. Un trimestre
récord puede ser shale creciendo, refino recuperando margen o el gas cobrando
un invierno; son tres negocios distintos, con tres múltiplos distintos, y el
consolidado los promedia hasta que no se ve ninguno.

La nota de segmentos —"Segment information", nota 5 o 6 según el año— abre
ingresos, resultado operativo, capex, depreciaciones y activos por segmento.
Como todo lo que se publica en un interino, viene acumulada desde enero, así
que el trimestre sale por diferencia de acumulados, con las mismas reglas que
el estado de flujo: restar en la moneda de origen y recién después convertir.

Entrada:  data/raw/financials/ypf/filings/*/   (los baja ingest/financials_ypf.py)
Salidas:  data/processed/segments_ypf.parquet  (largo: segmento-concepto-período)
          data/processed/segments_ypf.json     (resumen y cobertura)
"""

from __future__ import annotations

import io
import json
import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    PROCESSED,
    RAW,
    base_parser,
    human,
    log,
    record,
    rel,
    save_json,
    save_parquet,
)
from statements_ypf import (  # noqa: E402
    MESES,
    RE_FECHA,
    _cierre,
    _inicio_de,
    a_numero,
    fx_cierre,
    fx_promedio,
    limpiar,
    moneda_de,
)

FILINGS = RAW / "financials" / "ypf" / "filings"
OUT_LONG = PROCESSED / "segments_ypf.parquet"
OUT_JSON = PROCESSED / "segments_ypf.json"

# Los nombres cambiaron con el negocio: "Gas and Power" se fue en 2023 y
# aparecieron "LNG and Integrated Gas" y "New Energies" cuando la compañía
# reordenó su plan. Se conserva el nombre de cada época —renombrar hacia atrás
# sería inventar una serie que la compañía no reportó— y solo se traduce.
SEGMENTOS = {
    "upstream": "Upstream",
    "downstream": "Downstream",
    "industrialization": "Industrialización",
    "commercialization": "Comercialización",
    "midstream and downstream": "Midstream y Downstream",
    "gas and power": "Gas y energía",
    "gas & power": "Gas y energía",
    "gas and energy": "Gas y energía",
    "gas & energy": "Gas y energía",
    "lng and integrated gas": "GNL y gas integrado",
    "new energies": "Nuevas energías",
    "central administration and others": "Administración central y otros",
    "corporate and other": "Administración central y otros",
    "corporate and others": "Administración central y otros",
    "corporate & other": "Administración central y otros",
    "corporate & others": "Administración central y otros",
    "corporation and other": "Administración central y otros",
    "consolidation adjustments": "Ajustes de consolidación",
    "total": "Total",
}

# La compañía reordenó sus segmentos dos veces: en 2023 partió Downstream en
# Industrialización y Comercialización, y en 2025 rearmó todo alrededor de
# Midstream y Downstream, GNL y Nuevas energías. Un mismo trimestre aparece con
# la apertura vieja en el interino de su año y con la nueva en el comparativo
# del año siguiente. Se queda la más reciente: es la que la compañía usa hoy
# para contar su negocio.

# Las tres aperturas que convivieron. Lo que está en NUEVOS reemplaza a lo que
# está en VIEJOS, y "Industrialización" más "Comercialización" son el Downstream
# de 2023 partido en dos.
SEGMENTOS_NUEVOS = {"Midstream y Downstream", "GNL y gas integrado", "Nuevas energías"}
SEGMENTOS_PARTIDOS = {"Industrialización", "Comercialización"}
SEGMENTOS_VIEJOS = {"Downstream", "Gas y energía"} | SEGMENTOS_PARTIDOS

CONCEPTOS = [
    (r"^revenues from intersegment sales", "ingresos_intersegmento"),
    (r"^revenues", "ingresos"),  # aparece dos veces: externos y totales
    (r"^operating (profit|loss|income)", "resultado_operativo"),
    (r"^income from equity interests", "resultado_asociadas"),
    (r"^acquisitions of property", "capex_ppe"),
    (r"^acquisitions of right", "capex_derechos_uso"),
    (r"^increases from business combinations", "combinaciones_de_negocios"),
    (r"^depreciation of property", "depreciacion_ppe"),
    (r"^amortization of intangible", "amortizacion_intangibles"),
    (r"^depreciation of right", "depreciacion_derechos_uso"),
    (r"^inventories write", "deterioro_inventarios"),
    (r"^assets$", "activos"),
]

RE_PERIODO_FLUJO = re.compile(
    r"for the\s+(three|six|nine|twelve|year)[\s\-]*(month)?\s*(period|year)?s?\s+ended\s+(.+)",
    re.IGNORECASE,
)
RE_PERIODO_SALDO = re.compile(r"balance as of\s+(.+)", re.IGNORECASE)
MESES_DE = {"three": 3, "six": 6, "nine": 9, "twelve": 12, "year": 12}


RE_MONEDA_TABLA = re.compile(r"in millions of (u\.s\. )?dollars|in millions of pesos", re.IGNORECASE)


def moneda_de_tabla(texto: str) -> str | None:
    """La moneda de la nota de segmentos.

    La nota se publica dos veces en la misma tabla —dólares primero, pesos
    después, con dos columnas "Total"—, y el encabezado lo dice con tres
    redacciones distintas según el año. Si aparece el dólar, la tabla se lee en
    dólares: las columnas en pesos son las repetidas y se descartan.
    """
    marcas = [m.group(0).lower() for m in RE_MONEDA_TABLA.finditer(texto[:400])]
    if any("dollar" in m for m in marcas):
        return "USD"
    if marcas:
        return "ARS"
    return None


RE_CON_LLAMADA = re.compile(r"^(\(?[\d,.]+\)?)\((\d)\)$")


def numero_de_grupo(celdas: list[str]) -> float:
    """El valor de una celda de la nota, con o sin llamada al pie pegada.

    En la nota de segmentos la llamada al pie va pegada al número —"1,571 (3)"—
    y cae en la misma celda del grupo. Concatenado queda "1571(3)", que no es un
    número: así se perdía el resultado operativo de Upstream, justo el segmento
    del que trata el caso. El paréntesis de un negativo, en cambio, envuelve al
    número entero, y por eso los dos casos se distinguen.
    """
    texto = "".join(c for c in celdas if c).replace(" ", "")
    con_llamada = RE_CON_LLAMADA.match(texto)
    if con_llamada:
        return a_numero([con_llamada.group(1)])
    return a_numero(celdas)


def concepto_de(etiqueta: str) -> str | None:
    texto = re.sub(r"\(\d+\)", " ", etiqueta.lower())
    texto = re.sub(r"[\-\s]+", " ", texto).strip()
    for patron, nombre in CONCEPTOS:
        if re.search(patron, texto):
            return nombre
    return None


def periodo_de_fila(etiqueta: str) -> dict | None:
    """Las filas que anuncian un período: la nota mete varios en una tabla."""
    texto = re.sub(r"[\-\s]+", " ", etiqueta).strip()
    saldo = RE_PERIODO_SALDO.match(texto)
    if saldo:
        fecha = RE_FECHA.search(saldo.group(1))
        if fecha:
            return {
                "clase": "instante",
                "meses": None,
                "fin": pd.Timestamp(
                    year=int(fecha.group(3)), month=MESES[fecha.group(1).lower()], day=int(fecha.group(2))
                ),
            }
        return None

    flujo = RE_PERIODO_FLUJO.match(texto)
    if flujo:
        fecha = RE_FECHA.search(flujo.group(4))
        if fecha:
            return {
                "clase": "duracion",
                "meses": MESES_DE[flujo.group(1).lower()],
                "fin": pd.Timestamp(
                    year=int(fecha.group(3)), month=MESES[fecha.group(1).lower()], day=int(fecha.group(2))
                ),
            }
    return None


def _columnas_de_segmento(tabla: pd.DataFrame) -> list[tuple[str, list]]:
    """Agrupa las columnas por segmento, según la fila que trae los nombres."""
    fila_encabezado = None
    for i in range(min(4, len(tabla))):
        textos = " ".join(limpiar(v) for v in tabla.iloc[i]).lower()
        if "upstream" in textos:
            fila_encabezado = i
            break
    if fila_encabezado is None:
        return []

    grupos: list[tuple[str, list]] = []
    actual, columnas = None, []
    for columna in tabla.columns:
        texto = limpiar(tabla.iloc[fila_encabezado][columna])
        if texto and texto != actual:
            if actual is not None:
                grupos.append((actual, columnas))
            actual, columnas = texto, [columna]
        elif actual is not None:
            columnas.append(columna)
    if actual is not None:
        grupos.append((actual, columnas))

    resueltos = []
    vistos = set()
    for nombre, columnas in grupos:
        clave = re.sub(r"\(\d+\)", " ", nombre.lower())
        clave = re.sub(r"[\-\s]+", " ", clave).strip()
        segmento = SEGMENTOS.get(clave)
        if segmento is None:
            continue
        # La tabla del interino repite el total en pesos al final. El primero es
        # el de dólares y es el que vale; el segundo se descarta.
        if segmento in vistos:
            continue
        vistos.add(segmento)
        resueltos.append((segmento, columnas))
    return resueltos


def _recortar_en_pesos(tabla: pd.DataFrame) -> pd.DataFrame:
    """Corta la mitad en pesos de la nota, cuando la trae al lado de la de dólares.

    La tabla arranca con "In millions of U.S. dollars" y a mitad de camino dice
    "In millions of pesos": son los mismos segmentos dos veces, con dos columnas
    "Total" seguidas. Sin cortar, las dos columnas de total se leen como una y
    el total del segmento queda siendo la concatenación de un número en dólares
    con otro en pesos.
    """
    for i in range(min(3, len(tabla))):
        dolar = None
        for columna in tabla.columns:
            texto = limpiar(tabla.iloc[i][columna]).lower()
            if not texto:
                continue
            if "dollar" in texto:
                dolar = columna
            elif "peso" in texto and dolar is not None:
                return tabla.loc[:, [c for c in tabla.columns if c < columna]]
    return tabla


def leer_tabla(tabla: pd.DataFrame) -> list[dict]:
    """Las filas de una nota de segmentos, con el período que las encabeza."""
    tabla = _recortar_en_pesos(tabla.dropna(axis=1, how="all"))
    grupos = _columnas_de_segmento(tabla)
    if not grupos:
        return []

    primera = tabla.columns[0]
    filas: list[dict] = []
    periodo = None
    apariciones: dict[str, int] = {}
    for i in range(len(tabla)):
        etiqueta = limpiar(tabla.iloc[i][primera])
        if not etiqueta:
            continue

        nuevo = periodo_de_fila(etiqueta)
        if nuevo:
            periodo = nuevo
            apariciones = {}
            continue
        if periodo is None:
            continue

        concepto = concepto_de(etiqueta)
        if concepto is None:
            continue

        valores = {
            segmento: numero_de_grupo([limpiar(tabla.iloc[i][c]) for c in columnas])
            for segmento, columnas in grupos
        }
        if all(np.isnan(v) for v in valores.values()):
            continue

        apariciones[concepto] = apariciones.get(concepto, 0) + 1
        # "Revenues" aparece dos veces: arriba las ventas a terceros y abajo,
        # después de las intersegmento, el total del segmento.
        if concepto == "ingresos":
            concepto = "ingresos_externos" if apariciones[concepto] == 1 else "ingresos_totales"

        for segmento, valor in valores.items():
            if np.isnan(valor) or abs(valor) > 1e8:
                continue
            filas.append(
                {
                    "segmento": segmento,
                    "concepto": concepto,
                    "clase": periodo["clase"],
                    "meses": periodo["meses"],
                    "fin": periodo["fin"],
                    "valor": valor,
                }
            )
    return filas


def _texto_previo(tabla, limite: int = 2500) -> str:
    partes: list[str] = []
    nodo = tabla
    while nodo is not None and sum(len(p) for p in partes) < limite:
        nodo = nodo.find_previous(string=True)
        if nodo is None:
            break
        texto = limpiar(nodo)
        if texto:
            partes.append(texto)
    return " ".join(reversed(partes))


def leer_filing(carpeta: Path) -> list[dict]:
    from bs4 import BeautifulSoup

    meta = json.loads((carpeta / "_meta.json").read_text(encoding="utf-8"))
    salida: list[dict] = []

    for doc in sorted(carpeta.glob("*.htm"), key=lambda p: p.stat().st_size, reverse=True):
        if doc.stat().st_size < 300_000:
            continue
        sopa = BeautifulSoup(doc.read_text(encoding="utf-8", errors="replace"), "lxml")
        # La moneda de la nota no siempre está en la tabla ni cerca: en los
        # interinos viejos se declara una vez, arriba de todas las notas. Se
        # toma la del documento y, si el documento trae las dos —los interinos
        # nuevos publican la nota en dólares y de nuevo en pesos—, manda el
        # dólar: la tabla en pesos viene después y se descarta por repetida.
        moneda_documento = moneda_de(limpiar(sopa.get_text(" "))) or "USD"
        vistos: set[tuple] = set()
        for tabla_html in sopa.find_all("table"):
            texto = limpiar(tabla_html.get_text(" "))
            if "Upstream" not in texto or not re.search(r"operating (profit|loss|income)", texto, re.I):
                continue
            # La misma nota se publica dos veces, en dólares y en pesos. La
            # moneda sale del encabezado de la tabla o del texto que la precede.
            moneda = moneda_de_tabla(texto) or moneda_de(_texto_previo(tabla_html))
            if moneda is None:
                # Un 20-F puede traer los estados en dólares y la nota de
                # segmentos en pesos. Cuando ni la tabla ni lo que la precede lo
                # dicen, lo dice la magnitud: en millones de dólares los
                # ingresos de un trimestre de YPF no llegan a cien mil.
                mayor = max(
                    (abs(v) for v in (a_numero([x]) for x in re.findall(r"[\d,]{4,}", texto)) if not np.isnan(v)),
                    default=0,
                )
                moneda = "ARS" if mayor > 200_000 else moneda_documento
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    marcos = pd.read_html(io.StringIO(str(tabla_html)), flavor="lxml")
                except ValueError:
                    continue
            if not marcos:
                continue
            for fila in leer_tabla(marcos[0]):
                clave = (fila["segmento"], fila["concepto"], fila["clase"], fila["meses"], fila["fin"])
                if clave in vistos:
                    continue
                vistos.add(clave)
                fila.update(
                    {
                        "moneda": moneda,
                        "accession": meta["accession"],
                        "form": meta["form"],
                        "presentado": meta["filing_date"],
                    }
                )
                salida.append(fila)
    return salida


def recolectar() -> pd.DataFrame:
    registros: list[dict] = []
    for carpeta in sorted(p for p in FILINGS.iterdir() if (p / "_meta.json").exists()):
        filas = leer_filing(carpeta)
        if filas:
            periodos = sorted({str(pd.Timestamp(f["fin"]).date()) for f in filas})
            log(f"{carpeta.name}: {len(filas)} filas ({periodos[0]} a {periodos[-1]})")
            registros.extend(filas)
    if not registros:
        raise SystemExit("no se encontró ninguna nota de segmentos")
    return pd.DataFrame(registros)


# --------------------------------------------------------------------------- #
# De pesos a dólares y de acumulados a trimestres
# --------------------------------------------------------------------------- #
def convertir(df: pd.DataFrame) -> pd.DataFrame:
    """Mismo criterio que en los estados: saldos al cierre, flujos al promedio.

    La nota de segmentos de la era peso es parte de los mismos estados
    traducidos, así que se deshace la traducción igual que en statements_ypf.
    """
    df = df.copy()
    df["valor_origen"] = df["valor"]
    pesos = df["moneda"] == "ARS"
    if not pesos.any():
        return df

    def tipo(fila) -> float:
        fin = pd.Timestamp(fila["fin"])
        if fila["clase"] == "instante":
            return fx_cierre(fin)
        return fx_promedio(_inicio_de(fin, int(fila["meses"])), fin)

    df.loc[pesos, "fx_usado"] = df.loc[pesos].apply(tipo, axis=1)
    df.loc[pesos, "valor"] = df.loc[pesos, "valor_origen"] / df.loc[pesos, "fx_usado"]
    return df


def _par_mas_cercano(acumulados, previos, misma_apertura: bool = True):
    if not acumulados or not previos:
        return None
    if misma_apertura:
        acumulados = [a for a in acumulados if any(a["apertura"] == p["apertura"] for p in previos)]
        previos = [p for p in previos if any(a["apertura"] == p["apertura"] for a in acumulados)]
        if not acumulados or not previos:
            return None
    return min(
        ((a, p) for a in acumulados for p in previos),
        key=lambda par: (
            abs((par[0]["presentado"] - par[1]["presentado"]).days),
            -par[0]["presentado"].value,
            -par[1]["presentado"].value,
        ),
    )


def serie_trimestral(crudo: pd.DataFrame) -> pd.DataFrame:
    """Trimestres y ejercicios por segmento, con la derivación a la vista."""
    crudo = crudo.copy()
    crudo["presentado"] = pd.to_datetime(crudo["presentado"])

    # Con qué segmentos se publicó cada tabla. Dos acumulados con aperturas
    # distintas no se pueden restar: el "Downstream" de septiembre y la suma de
    # "Industrialización" más "Comercialización" de diciembre son el mismo
    # negocio contado distinto, y la resta línea por línea da cualquier cosa.
    aperturas: dict[tuple, set] = {}

    def clave_apertura(fila) -> tuple:
        # Los saldos no tienen meses y NaN no sirve de clave.
        meses = -1 if fila.clase == "instante" else int(fila.meses)
        return (fila.accession, fila.concepto, meses, pd.Timestamp(fila.fin))

    for fila in crudo.itertuples():
        aperturas.setdefault(clave_apertura(fila), set()).add(fila.segmento)

    versiones: dict[tuple, list[dict]] = {}
    instantes: dict[tuple, list[dict]] = {}
    for fila in crudo.itertuples():
        registro = {
            "valor": fila.valor,
            "origen": fila.valor_origen,
            "accession": fila.accession,
            "presentado": pd.Timestamp(fila.presentado),
            "apertura": frozenset(aperturas[clave_apertura(fila)]),
        }
        fin = pd.Timestamp(fila.fin)
        if fila.clase == "instante":
            instantes.setdefault((fila.segmento, fila.concepto, fin, fila.moneda), []).append(registro)
        else:
            versiones.setdefault(
                (fila.segmento, fila.concepto, int(fila.meses), fin, fila.moneda), []
            ).append(registro)

    def ultimo(opciones):
        return max(opciones, key=lambda r: r["presentado"]) if opciones else None

    filas: list[dict] = []
    pares = sorted({(fila.segmento, fila.concepto) for fila in crudo.itertuples()})
    anios = sorted({pd.Timestamp(f).year for f in crudo["fin"]})

    for segmento, concepto in pares:
        for anio in anios:
            for trimestre in (1, 2, 3, 4):
                fin = _cierre(anio, trimestre)

                # Los activos son un stock: se toman a la fecha, sin restar.
                saldo = None
                for moneda in ("USD", "ARS"):
                    saldo = ultimo(instantes.get((segmento, concepto, fin, moneda)))
                    if saldo:
                        filas.append(
                            {
                                "segmento": segmento,
                                "concepto": concepto,
                                "periodo": f"{anio}Q{trimestre}",
                                "anio": anio,
                                "trimestre": trimestre,
                                "tipo": "trimestre",
                                "valor_musd": saldo["valor"],
                                "derivacion": "reportado",
                                "moneda_origen": moneda,
                                "fuentes": saldo["accession"],
                                "presentado": saldo["presentado"],
                            }
                        )
                        break
                if saldo:
                    continue

                armado = None
                for moneda in ("USD", "ARS"):
                    directo = ultimo(versiones.get((segmento, concepto, 3, fin, moneda)))
                    if directo:
                        armado = (
                            directo["valor"],
                            directo["accession"],
                            "reportado",
                            moneda,
                            directo["presentado"],
                        )
                        break
                    if trimestre == 1:
                        continue
                    par = _par_mas_cercano(
                        versiones.get((segmento, concepto, 3 * trimestre, fin, moneda)),
                        versiones.get((segmento, concepto, 3 * (trimestre - 1), _cierre(anio, trimestre - 1), moneda)),
                        misma_apertura=segmento != "Total",
                    )
                    if not par:
                        continue
                    acumulado, previo = par
                    if moneda == "USD":
                        valor = acumulado["valor"] - previo["valor"]
                    else:
                        # En pesos, la resta va antes de convertir.
                        tipo = fx_promedio(_inicio_de(fin, 3), fin)
                        if not tipo or np.isnan(tipo):
                            continue
                        valor = (acumulado["origen"] - previo["origen"]) / tipo
                    armado = (
                        valor,
                        f"{acumulado['accession']} - {previo['accession']}",
                        f"{3 * trimestre}M menos {3 * (trimestre - 1)}M",
                        moneda,
                        max(acumulado["presentado"], previo["presentado"]),
                    )
                    break

                if armado is None:
                    continue
                valor, fuentes, derivacion, moneda, presentado = armado
                filas.append(
                    {
                        "segmento": segmento,
                        "concepto": concepto,
                        "periodo": f"{anio}Q{trimestre}",
                        "anio": anio,
                        "trimestre": trimestre,
                        "tipo": "trimestre",
                        "valor_musd": valor,
                        "derivacion": derivacion,
                        "moneda_origen": moneda,
                        "fuentes": fuentes,
                        "presentado": presentado,
                    }
                )

            for moneda in ("USD", "ARS"):
                anual = ultimo(versiones.get((segmento, concepto, 12, _cierre(anio, 4), moneda)))
                if anual:
                    filas.append(
                        {
                            "segmento": segmento,
                            "concepto": concepto,
                            "periodo": str(anio),
                            "anio": anio,
                            "trimestre": 0,
                            "tipo": "anual",
                            "valor_musd": anual["valor"],
                            "derivacion": "reportado",
                            "moneda_origen": moneda,
                            "fuentes": anual["accession"],
                            "presentado": anual["presentado"],
                        }
                    )
                    break

    serie = pd.DataFrame(filas)
    if serie.empty:
        return serie

    # Un trimestre puede estar dos veces: con la apertura vigente ese año y con
    # la que la compañía estrenó después, en el comparativo. Sumar las dos
    # cuenta el mismo negocio dos veces. Se descarta la apertura vieja, pero
    # solo la parte que efectivamente cambió: Upstream, la administración
    # central y los ajustes son los mismos en las tres aperturas y se quedan
    # aunque vengan de una presentación anterior.
    serie = serie.sort_values("presentado").drop_duplicates(
        ["concepto", "periodo", "segmento"], keep="last"
    )

    # Cada tabla trae la apertura completa de su período, así que la mezcla de
    # dos presentaciones es siempre un error: o los negocios se cuentan dos
    # veces —"Downstream" de un lado, "Industrialización" más
    # "Comercialización" del otro— o falta uno. Se elige una sola presentación
    # por período: la más reciente que traiga la apertura entera.
    # De todas las presentaciones que abren un mismo período, se elige la que
    # cierra: aquella cuyas partes suman su total. Es un criterio y una
    # verificación a la vez —si una apertura quedó incompleta o mezclada, no
    # cierra y pierde—, y desempata la más reciente.
    conservar = []
    for _, grupo in serie.groupby(["concepto", "periodo"]):
        totales = grupo[grupo["segmento"] == "Total"]
        partes = grupo[grupo["segmento"] != "Total"]
        referencia = float(totales["valor_musd"].iloc[-1]) if len(totales) else None

        mejor, mejor_puntaje = None, None
        for fecha, bloque in partes.groupby("presentado"):
            propio = totales[totales["presentado"] == fecha]
            objetivo = float(propio["valor_musd"].iloc[0]) if len(propio) else referencia
            if objetivo is None or abs(objetivo) < 1:
                error = float("inf")
            else:
                error = abs(float(bloque["valor_musd"].sum()) - objetivo) / abs(objetivo)
            puntaje = (round(error, 4), -fecha.value)
            if mejor_puntaje is None or puntaje < mejor_puntaje:
                mejor, mejor_puntaje = fecha, puntaje

        if mejor is not None:
            conservar.extend(partes[partes["presentado"] == mejor].index)
            propio = totales[totales["presentado"] == mejor]
            conservar.extend(
                (propio if len(propio) else totales.tail(1)).index
            )
        elif len(totales):
            conservar.extend(totales.tail(1).index)

    serie = serie.loc[sorted(set(conservar))]

    # El formato de la nota antes de 2019 es otro y el parseo no lo lee bien:
    # las partes no dan el total ni de casualidad. Se corta ahí en vez de
    # publicar una serie que no cierra.
    return serie[serie["anio"] >= 2019].reset_index(drop=True)


def construir_json(serie: pd.DataFrame) -> dict:
    trimestres = sorted(serie.loc[serie["tipo"] == "trimestre", "periodo"].unique())
    por_segmento = {
        segmento: sorted(grupo.loc[grupo["tipo"] == "trimestre", "periodo"].unique())
        for segmento, grupo in serie.groupby("segmento")
    }
    return {
        "generado": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "moneda": "USD",
        "unidad": "millones",
        "trimestres": trimestres,
        "segmentos": sorted(serie["segmento"].unique()),
        "conceptos": sorted(serie["concepto"].unique()),
        "cobertura": por_segmento,
        "nota": (
            "La nota de segmentos se publica acumulada desde enero: el trimestre sale "
            "por diferencia de acumulados, y en la era peso la resta se hace en pesos "
            "y se convierte después."
        ),
    }


def main() -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.parse_args()

    crudo = convertir(recolectar())
    serie = serie_trimestral(crudo).sort_values(["segmento", "concepto", "periodo"])

    bytes_parquet = save_parquet(serie.reset_index(drop=True), OUT_LONG)
    bytes_json = save_json(construir_json(serie), OUT_JSON, indent=2)

    trimestres = sorted(serie.loc[serie["tipo"] == "trimestre", "periodo"].unique())
    log(
        f"{len(serie)} filas · {serie['segmento'].nunique()} segmentos · "
        f"{len(trimestres)} trimestres ({trimestres[0]}–{trimestres[-1]})"
    )
    record(
        "transform/segmentos",
        rows=int(len(serie)),
        bytes=int(bytes_parquet + bytes_json),
        outputs=[rel(OUT_LONG), rel(OUT_JSON)],
        source=rel(FILINGS),
        note=f"{trimestres[0]}–{trimestres[-1]}; el trimestre sale de la diferencia de acumulados",
    )
    log(f"{rel(OUT_LONG)} ({human(bytes_parquet)}) · {rel(OUT_JSON)} ({human(bytes_json)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
