"""Los tres estados contables de YPF, trimestrales, a partir de los 6-K y 20-F.

Por qué existe aparte de transform/financials_ypf.py: ese lee la tabla de
highlights del earnings release —revenues, EBITDA ajustado, capex, deuda neta—,
que es lo que hace falta para explicar la reacción del mercado. Acá se leen los
estados contables completos que YPF adjunta como Item 1 del 6-K: estado de
situación patrimonial, estado de resultados integrales y flujo de efectivo,
línea por línea y como los reporta la compañía.

Alcance y por qué: solo la era USD. YPF definió el dólar como moneda funcional
y de presentación, y los estados en pesos anteriores están reexpresados por
IAS 29 (inflación). Encadenar pesos ajustados con dólares daría una serie que
no significa nada. Los estados en USD arrancan con el 6-K del 1Q24, que trae
2023 como comparativo, así que la serie trimestral empieza en 1Q23.

Cómo se arma cada trimestre:
  - resultados: el interino publica el trimestre explícito ("three-month
    period"), salvo el 4T, que sale del anual menos los nueve meses;
  - flujo de efectivo: siempre acumulado del ejercicio, así que todo trimestre
    que no sea el primero se obtiene por diferencia con el acumulado anterior;
  - balance: es un stock, se toma a la fecha de cierre de cada trimestre.

Cuando un período aparece en más de una presentación se toma el de la más
reciente —es la versión reexpresada, la que la compañía sostiene hoy— y la
discrepancia con el primer reporte queda registrada en la salida para poder
auditarla.

Entrada:  data/raw/financials/ypf/filings/*/   (los baja ingest/financials_ypf.py)
Salidas:  data/processed/statements_ypf.parquet   (largo: línea-período-valor)
          data/processed/statements_ypf.json      (resumen + cobertura)
"""

from __future__ import annotations

import io
import json
import re
import sys
import unicodedata
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

FILINGS = RAW / "financials" / "ypf" / "filings"

OUT_LONG = PROCESSED / "statements_ypf.parquet"
OUT_JSON = PROCESSED / "statements_ypf.json"

# La era USD: antes de esto los estados vienen en pesos reexpresados por IAS 29.
MARCA_USD = "expressed in millions of united states dollars"

# Firmas para reconocer cada estado sin depender del título, que cambia de
# "CONSOLIDATED" a "CONDENSED INTERIM CONSOLIDATED" entre el anual y el interino.
FIRMAS = {
    "balance": ("total assets", "total liabilities"),
    "resultados": ("revenues", "gross profit"),
    "flujo": ("cash flows from operating activities", "cash and cash equivalents at the end"),
}

MESES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

RE_FECHA = re.compile(r"(" + "|".join(MESES) + r")\s+(\d{1,2}),?\s*(\d{4})", re.IGNORECASE)
RE_DURACION = re.compile(r"(three|six|nine|twelve)[\s-]month", re.IGNORECASE)
RE_ANUAL = re.compile(r"year[s]?\s+ended", re.IGNORECASE)
RE_ANIO = re.compile(r"^(19|20)\d{2}$")

MESES_DE = {"three": 3, "six": 6, "nine": 9, "twelve": 12}

# El 20-F repite los estados dos veces: primero como tablas resumen dentro del
# análisis de la gerencia y después como los estados auditados. Se toman los
# segundos, y la forma de distinguirlos es el encabezado formal: título del
# estado más la aclaración de moneda entre paréntesis.
RE_TITULO_ESTADO = re.compile(
    r"STATEMENTS?\s+OF\s+(FINANCIAL POSITION|COMPREHENSIVE INCOME|CASH FLOW)", re.IGNORECASE
)


def limpiar(texto) -> str:
    """Normaliza una celda: espacios raros de EDGAR, guiones tipográficos, NBSP."""
    if texto is None or (isinstance(texto, float) and np.isnan(texto)):
        return ""
    s = unicodedata.normalize("NFKC", str(texto))
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\ufffd", " ").replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return "" if s.lower() == "nan" else s


def a_numero(celdas: list[str]) -> float:
    """Primer número de un grupo de celdas. El negativo viene entre paréntesis
    y a veces partido: '(344' en una celda y ')' en la siguiente."""
    texto = "".join(celdas).strip()
    if not texto:
        return np.nan
    texto = texto.replace(",", "").replace("$", "").strip()
    if texto in {"-", "--", "—", "N/A", "n/a"}:
        return np.nan
    negativo = texto.startswith("(")
    texto = texto.strip("()").strip()
    if not re.fullmatch(r"\d+(\.\d+)?", texto):
        return np.nan
    valor = float(texto)
    return -valor if negativo else valor


# --------------------------------------------------------------------------- #
# Lectura de una tabla de estado contable
# --------------------------------------------------------------------------- #
def _encabezado_por_columna(tabla: pd.DataFrame, filas: int = 4) -> dict[int, str]:
    """Junta las primeras filas de cada columna en una sola etiqueta de período.

    El encabezado viene partido en dos niveles ("For the six-month periods
    ended June 30," arriba, "2026" abajo) y repetido en columnas contiguas.
    """
    etiquetas: dict[int, str] = {}
    for col in tabla.columns:
        partes = [limpiar(tabla.iloc[i][col]) for i in range(min(filas, len(tabla)))]
        etiquetas[col] = " ".join(p for p in partes if p)
    return etiquetas


def _titulo_de(contexto: str) -> str:
    """El título del estado, que es donde vive el período del anual.

    El contexto arrastra el pie de la página anterior —firmas, numeración—, y
    ahí aparecen fechas que no tienen nada que ver. Solo interesa desde el
    'STATEMENTS OF ...' para adelante.
    """
    posicion = contexto.upper().rfind("STATEMENTS OF")
    return contexto[posicion:] if posicion >= 0 else contexto[-200:]


def _anio_de(texto: str) -> int | None:
    """El año de una columna. Viene como '2025' y, cuando pandas lo leyó como
    número, también como '2025.0'."""
    anios = re.findall(r"(?:19|20)\d{2}", texto.replace(".0", ""))
    return int(anios[-1]) if anios else None


def _cierre_de(texto: str) -> tuple[int, int] | None:
    """Mes y día de cierre: 'June 30, 2026' o 'AS OF DECEMBER 31,' -> (6, 30)."""
    m = RE_FECHA.search(texto)
    if m:
        return MESES[m.group(1).lower()], int(m.group(2))
    m = re.search(r"(" + "|".join(MESES) + r")\s+(\d{1,2})", texto, re.IGNORECASE)
    if m:
        return MESES[m.group(1).lower()], int(m.group(2))
    return None


def _periodo_de_encabezado(texto: str, titulo: str, estado: str) -> dict | None:
    """Traduce el encabezado de una columna a un período.

    El interino repite el período completo en cada columna ('For the six-month
    periods ended June 30, 2026'); el anual deja solo el año y pone el resto en
    el título ('... AS OF DECEMBER 31, 2025, 2024 AND 2023'). Se lee primero la
    columna y se completa con el título.
    """
    anio = _anio_de(texto)
    # El rango es el de los datos del proyecto: cualquier año fuera de ahí sale
    # de una celda que no era un encabezado (una nota al pie, un número de
    # artículo) y arrastraría una columna fantasma.
    if anio is None or not 2015 <= anio <= 2035:
        return None

    cierre = _cierre_de(texto) or _cierre_de(titulo) or (12, 31)
    fin = pd.Timestamp(year=anio, month=cierre[0], day=cierre[1])

    # Que un estado sea de stock o de flujo lo define el estado, no la
    # redacción: YPF titula su estado de resultados anual "AS OF DECEMBER 31",
    # que suena a fecha de corte y es un ejercicio completo.
    if estado == "balance":
        return {"clase": "instante", "meses": None, "fin": fin}

    duracion = RE_DURACION.search(texto) or RE_DURACION.search(titulo)
    meses = MESES_DE[duracion.group(1).lower()] if duracion else 12
    return {"clase": "duracion", "meses": meses, "fin": fin}


def _grupos_de_periodo(tabla: pd.DataFrame, titulo: str, estado: str) -> list[tuple[dict, list]]:
    """Columnas contiguas que corresponden al mismo período, con su período."""
    etiquetas = _encabezado_por_columna(tabla)
    grupos: list[tuple[dict, list]] = []
    actual_texto, actual_cols = None, []
    for col in tabla.columns:
        texto = etiquetas[col]
        if texto and texto != actual_texto:
            if actual_texto is not None:
                grupos.append((actual_texto, actual_cols))
            actual_texto, actual_cols = texto, [col]
        elif actual_texto is not None and (not texto or texto == actual_texto):
            actual_cols.append(col)
    if actual_texto is not None:
        grupos.append((actual_texto, actual_cols))

    resueltos = []
    for texto, cols in grupos:
        periodo = _periodo_de_encabezado(texto, titulo, estado)
        if periodo:
            resueltos.append((periodo, cols))
    return resueltos


def _primera_fila_de_datos(tabla: pd.DataFrame, grupos: list) -> int:
    """La primera fila donde la primera columna trae una etiqueta de línea."""
    primera = tabla.columns[0]
    for i in range(len(tabla)):
        if limpiar(tabla.iloc[i][primera]):
            return i
    return 0


# El subtotal que cierra cada bloque: es lo que le da sección a las líneas que
# vienen arriba. En el balance "Loans" aparece dos veces —no corriente y
# corriente— y son dos líneas distintas; contar apariciones no alcanza, porque
# en un trimestre donde la de arriba no existe la de abajo pasaría a ser la
# primera y se mezclarían dos series.
RE_SUBTOTAL = {
    "balance": re.compile(r"^total(?![a-z])", re.IGNORECASE),
    "flujo": re.compile(r"^net cash flows(?![a-z])", re.IGNORECASE),
    "resultados": re.compile(r"(?!)"),  # el estado de resultados no lleva seccion
}


def _secciones(etiquetas: list[str], estado: str) -> list[str]:
    """Para cada línea, el subtotal que la cierra."""
    patron = RE_SUBTOTAL[estado]
    seccion = [""] * len(etiquetas)
    pendientes: list[int] = []
    for i, etiqueta in enumerate(etiquetas):
        pendientes.append(i)
        if patron.match(etiqueta.strip()):
            for j in pendientes:
                seccion[j] = normalizar_clave(etiqueta)
            pendientes = []
    return seccion


def leer_estado(tabla: pd.DataFrame, estado: str, contexto: str = "") -> list[dict]:
    """Las líneas de un estado contable: etiqueta, período y valor."""
    tabla = tabla.dropna(axis=1, how="all")
    if tabla.empty:
        return []
    titulo = _titulo_de(contexto)
    grupos = _grupos_de_periodo(tabla, titulo, estado)
    if not grupos:
        return []

    primera_col = tabla.columns[0]
    inicio = _primera_fila_de_datos(tabla, grupos)
    filas: list[dict] = []
    # "Shareholders of the parent company" y "Non-controlling interest"
    # aparecen dos veces en el estado de resultados: una abre el resultado del
    # período y otra el resultado integral. Se las distingue por orden de
    # aparición o se pisan entre ellas.
    apariciones: dict[str, int] = {}
    for orden, i in enumerate(range(inicio, len(tabla))):
        etiqueta = limpiar(tabla.iloc[i][primera_col])
        if not etiqueta:
            continue
        valores = {}
        for periodo, cols in grupos:
            valores[id(periodo)] = a_numero([limpiar(tabla.iloc[i][c]) for c in cols])

        # El título de la columna cae en la misma fila que la primera etiqueta
        # ("Net income" arriba de todo, con los años al lado). Si cada valor de
        # la fila es el año de su propia columna, la fila es el encabezado.
        años = [
            valores[id(periodo)] == periodo["fin"].year
            for periodo, _ in grupos
            if not np.isnan(valores[id(periodo)])
        ]
        if años and all(años):
            continue

        if not any(not np.isnan(v) for v in valores.values()):
            continue
        apariciones[etiqueta] = apariciones.get(etiqueta, 0) + 1
        aparicion = apariciones[etiqueta]

        for periodo, cols in grupos:
            valor = valores[id(periodo)]
            if np.isnan(valor):
                continue
            # Los estados están en millones: nada legítimo llega al billón. Un
            # número así es la concatenación de dos celdas del encabezado.
            if abs(valor) > 1e6:
                continue
            filas.append(
                {
                    "estado": estado,
                    "etiqueta": etiqueta,
                    "fila": i,
                    "aparicion": aparicion,
                    "orden": orden,
                    "clase": periodo["clase"],
                    "meses": periodo.get("meses"),
                    "fin": periodo["fin"],
                    "valor_musd": valor,
                }
            )

    # La sección se resuelve al final, cuando ya se sabe qué subtotal viene
    # después de cada línea.
    orden_filas = sorted({f["fila"] for f in filas})
    etiquetas_ordenadas = []
    for numero in orden_filas:
        etiquetas_ordenadas.append(next(f["etiqueta"] for f in filas if f["fila"] == numero))
    secciones = dict(zip(orden_filas, _secciones(etiquetas_ordenadas, estado)))
    for f in filas:
        f["seccion"] = secciones.get(f["fila"], "")
    return filas


# --------------------------------------------------------------------------- #
# Recorrido de las presentaciones
# --------------------------------------------------------------------------- #
def _texto_previo(tabla, limite: int = 600) -> str:
    """El texto que precede a una tabla: ahí está el título del estado."""
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


def _estado_de(texto_tabla: str) -> str | None:
    bajo = texto_tabla.lower()
    for estado, firmas in FIRMAS.items():
        if all(f in bajo for f in firmas):
            return estado
    return None


def leer_filing(carpeta: Path) -> list[dict]:
    """Los tres estados de una presentación, si están y si vienen en dólares."""
    from bs4 import BeautifulSoup

    meta = json.loads((carpeta / "_meta.json").read_text(encoding="utf-8"))
    salida: list[dict] = []

    for doc in sorted(carpeta.glob("*.htm"), key=lambda p: p.stat().st_size, reverse=True):
        if doc.stat().st_size < 300_000:
            continue
        html = doc.read_text(encoding="utf-8", errors="replace")
        sopa = BeautifulSoup(html, "lxml")
        # El marcador de moneda se busca sobre el texto y no sobre el HTML: en
        # el crudo la frase viene cortada por tags de estilo cada dos palabras.
        if MARCA_USD not in limpiar(sopa.get_text(" ")).lower():
            continue
        vistos: set[str] = set()
        for tabla_html in sopa.find_all("table"):
            texto = limpiar(tabla_html.get_text(" "))
            estado = _estado_de(texto)
            if estado is None or estado in vistos:
                continue
            contexto = _texto_previo(tabla_html)
            titulo = _titulo_de(contexto)
            if not RE_TITULO_ESTADO.search(titulo) or MARCA_USD not in titulo.lower():
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    marcos = pd.read_html(io.StringIO(str(tabla_html)), flavor="lxml")
                except ValueError:
                    continue
            if not marcos:
                continue
            filas = leer_estado(marcos[0], estado, contexto)
            if not filas:
                continue
            vistos.add(estado)
            for fila in filas:
                fila.update(
                    {
                        "accession": meta["accession"],
                        "form": meta["form"],
                        "presentado": meta["filing_date"],
                        "documento": doc.name,
                    }
                )
            salida.extend(filas)
        if len(vistos) == len(FIRMAS):
            break

    return salida


def recolectar() -> pd.DataFrame:
    """Recorre todas las presentaciones y devuelve las líneas en formato largo."""
    registros: list[dict] = []
    carpetas = sorted(p for p in FILINGS.iterdir() if (p / "_meta.json").exists())
    for carpeta in carpetas:
        filas = leer_filing(carpeta)
        if filas:
            estados = sorted({f["estado"] for f in filas})
            log(f"{carpeta.name}: {len(filas)} líneas ({', '.join(estados)})")
            registros.extend(filas)
    if not registros:
        raise SystemExit("no se encontró ningún estado contable en dólares")
    return pd.DataFrame(registros)


# --------------------------------------------------------------------------- #
# Normalización de líneas
# --------------------------------------------------------------------------- #
# La misma línea cambia de redacción entre el interino y el anual ("Net profit
# for the period" / "Net (loss) / profit for the year") y, en dos casos, entre
# ejercicios. Se normaliza lo mecánico y el resto va como alias explícito: son
# pocos y prefiero que se vean a que un regex los junte de casualidad.
ALIAS = {
    # El mismo renglón, redactado según el signo que le tocó ese año: cuando el
    # cargo por deterioro vuelve, la línea pasa de "Impairment" a "Reversal".
    "inventories write down and reversal of impairment losses of property plant and equipment":
        "impairment reversal of ppe and inventories write down",
    "reversal impairment of property plant and equipment and inventories write down":
        "impairment reversal of ppe and inventories write down",
    "impairment of property plant and equipment and inventories write down":
        "impairment reversal of ppe and inventories write down",
    "reversal impairment of property plant and equipment":
        "impairment reversal of ppe and inventories write down",
    "impairment of property plant and equipment":
        "impairment reversal of ppe and inventories write down",
    # Financiación y variación de caja: cambian de orden según el signo del año.
    "net cash flows from used in financing activities": "net cash flows from financing activities",
    "net cash flows used in from financing activities": "net cash flows from financing activities",
    "net cash flows used in financing activities": "net cash flows from financing activities",
    "increase decrease in cash and cash equivalents": "increase in cash and cash equivalents",
    "decrease increase in cash and cash equivalents": "increase in cash and cash equivalents",
    "decrease in cash and cash equivalents": "increase in cash and cash equivalents",
    "net increase decrease in cash and cash equivalents": "increase in cash and cash equivalents",
    "net increase in cash and cash equivalents": "increase in cash and cash equivalents",
    "cash and cash equivalents at the end of the fiscal year": "cash and cash equivalents at the end of the period",
    # El anual de 2022 escribe "Net profit or loss" donde el nuevo pone
    # "Net profit / (loss)": misma línea, otra tipografía del signo. No se
    # generaliza con un regex porque "reclassified to profit or loss" es otra
    # cosa y ahí "or loss" no sobra.
    "net profit or loss": "net profit",
    "operating profit or loss": "operating profit",
    "net profit or loss before income tax": "net profit before income tax",
    # Plurales y sinónimos sueltos.
    "taxes payables": "taxes payable",
    "account overdrafts net": "account overdraft net",
    "investment in financial assets": "investments in financial assets",
    "assets held for disposal": "assets held for sale",
}

# Saldos que viajan adentro del estado de flujo: no son flujos del período y
# restarle el acumulado anterior no da nada. El cierre se toma tal cual del
# acumulado que termina en ese trimestre; la apertura es el cierre del anterior.
SALDO_CIERRE = "cash and cash equivalents at the end of the period"
SALDO_APERTURA = "cash and cash equivalents at the beginning of the fiscal year"

# Por acción: sumar o restar acumulados de un ratio no da el ratio del período.
# Solo se publica el trimestre cuando la compañía lo publica.
SOLO_REPORTADO = {"basic and diluted"}


def normalizar_clave(etiqueta: str) -> str:
    """Clave de comparación de una línea entre presentaciones."""
    s = etiqueta.lower()
    s = re.sub(r"\(\d+\)", " ", s)                     # llamadas al pie
    s = re.sub(r"\bfor the (year|period)s?\b", " ", s)  # "for the year" / "for the period"
    s = s.replace("(loss)", " ").replace("(losses)", " ").replace("(impairment)", "impairment")
    s = s.replace("/", " ").replace("’", "'").replace("'", "")
    s = re.sub(r"[^a-z ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return ALIAS.get(s, s)


def consolidar(df: pd.DataFrame) -> pd.DataFrame:
    """Un valor por línea y período: el de la presentación más reciente.

    Un mismo período aparece en varias presentaciones —como período titular y
    después como comparativo— y los comparativos pueden venir reexpresados. Se
    toma el más reciente, que es la versión que la compañía sostiene hoy, y se
    guarda cuántas versiones hubo y cuánto se movió el número, que es lo que
    permite auditar una reexpresión en vez de que pase inadvertida.
    """
    df = df.copy()
    df["clave"] = df["etiqueta"].map(normalizar_clave)
    # En balance y flujo la sección desempata; en resultados, donde la
    # atribución del resultado y la del resultado integral repiten las mismas
    # dos líneas seguidas, desempata el orden de aparición.
    con_seccion = df["estado"].isin(["balance", "flujo"]) & (df["seccion"] != "") & (df["clave"] != df["seccion"])
    df.loc[con_seccion, "clave"] = df.loc[con_seccion, "clave"] + " | " + df.loc[con_seccion, "seccion"]
    repetida = (~con_seccion) & (df["aparicion"] > 1)
    df.loc[repetida, "clave"] = df.loc[repetida, "clave"] + " (" + df.loc[repetida, "aparicion"].astype(str) + ")"
    df["presentado"] = pd.to_datetime(df["presentado"])
    llave = ["estado", "clave", "clase", "meses", "fin"]

    df = df.sort_values("presentado")
    agrupado = df.groupby(llave, dropna=False)
    resumen = agrupado.agg(
        valor_musd=("valor_musd", "last"),
        etiqueta=("etiqueta", "last"),
        orden=("orden", "last"),
        accession=("accession", "last"),
        form=("form", "last"),
        presentado=("presentado", "last"),
        versiones=("valor_musd", "size"),
        valor_primero=("valor_musd", "first"),
        presentado_primero=("presentado", "first"),
    ).reset_index()
    resumen["reexpresado_musd"] = resumen["valor_musd"] - resumen["valor_primero"]
    return resumen


# --------------------------------------------------------------------------- #
# Armado de la serie trimestral
# --------------------------------------------------------------------------- #
CIERRES = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}


def _cierre(anio: int, trimestre: int) -> pd.Timestamp:
    mes, dia = CIERRES[trimestre]
    return pd.Timestamp(year=anio, month=mes, day=dia)


def serie_trimestral(cons: pd.DataFrame) -> pd.DataFrame:
    """Trimestres, acumulados y ejercicios completos, con su derivación.

    El balance es un stock y se toma a la fecha. Resultados y flujo son flujos:
    el interino publica el trimestre de resultados explícito, pero el flujo de
    efectivo siempre viene acumulado del ejercicio, así que salvo el primer
    trimestre todo sale por diferencia de acumulados. El cuarto trimestre nunca
    se publica solo —no hay reporte de 4T— y sale del ejercicio menos los nueve
    meses, en los dos estados.
    """
    filas: list[dict] = []

    # --- balance: instantes -------------------------------------------------
    balance = cons[cons["clase"] == "instante"]
    for fila in balance.itertuples():
        fin = pd.Timestamp(fila.fin)
        trimestre = (fin.month - 1) // 3 + 1
        if (fin.month, fin.day) != CIERRES[trimestre]:
            continue
        filas.append(
            {
                "estado": fila.estado,
                "clave": fila.clave,
                "etiqueta": fila.etiqueta,
                "orden": fila.orden,
                "periodo": f"{fin.year}Q{trimestre}",
                "anio": fin.year,
                "trimestre": trimestre,
                "tipo": "trimestre",
                "valor_musd": fila.valor_musd,
                "derivacion": "reportado",
                "fuentes": fila.accession,
                "presentado": pd.Timestamp(fila.presentado).date().isoformat(),
                "reexpresado_musd": fila.reexpresado_musd,
            }
        )

    # --- resultados y flujo: duraciones ------------------------------------
    flujos = cons[cons["clase"] == "duracion"]
    indice: dict[tuple, tuple[float, str]] = {}
    cubiertos: set[tuple[str, int, pd.Timestamp]] = set()
    for fila in flujos.itertuples():
        fin = pd.Timestamp(fila.fin)
        indice[(fila.estado, fila.clave, int(fila.meses), fin)] = (fila.valor_musd, fila.accession)
        cubiertos.add((fila.estado, int(fila.meses), fin))

    # La etiqueta y el orden de presentación se toman de la presentación más
    # reciente que tenga esa línea: es la redacción vigente.
    recientes = flujos.sort_values("presentado").groupby(["estado", "clave"]).last()
    anios = sorted({pd.Timestamp(f).year for f in flujos["fin"]})

    for (estado, clave), fila in recientes.iterrows():
        for anio in anios:
            computados: dict[int, float] = {}
            for trimestre in (1, 2, 3, 4):
                fin = _cierre(anio, trimestre)
                # Sin un estado que cierre en esa fecha no hay trimestre que
                # armar: sin esto, una línea de saldo se arrastraría hacia
                # trimestres que todavía no se publicaron.
                ventanas = {3, 3 * trimestre} | ({12} if trimestre == 4 else set())
                if not any((estado, meses, fin) in cubiertos for meses in ventanas):
                    continue
                directo = indice.get((estado, clave, 3, fin))
                if directo is not None:
                    valor, fuentes, derivacion = directo[0], directo[1], "reportado"
                elif clave in SOLO_REPORTADO:
                    continue
                elif clave == SALDO_CIERRE:
                    saldo = indice.get((estado, clave, 3 * trimestre, fin))
                    if saldo is None:
                        continue
                    valor, fuentes, derivacion = saldo[0], saldo[1], "saldo al cierre"
                elif clave == SALDO_APERTURA:
                    # La apertura del trimestre es el cierre del anterior; la del
                    # primero es la apertura del ejercicio, que sí viene publicada.
                    if trimestre == 1:
                        saldo = indice.get((estado, clave, 3, fin))
                    else:
                        anterior = _cierre(anio, trimestre - 1)
                        saldo = indice.get((estado, SALDO_CIERRE, 3 * (trimestre - 1), anterior))
                    if saldo is None:
                        continue
                    valor, fuentes, derivacion = saldo[0], saldo[1], "saldo al cierre del trimestre anterior"
                else:
                    acumulado = indice.get((estado, clave, 3 * trimestre, fin))
                    if acumulado is None:
                        continue
                    if trimestre == 1:
                        valor, fuentes, derivacion = acumulado[0], acumulado[1], "reportado"
                    else:
                        previo = indice.get((estado, clave, 3 * (trimestre - 1), _cierre(anio, trimestre - 1)))
                        if previo is not None:
                            valor = acumulado[0] - previo[0]
                            fuentes = f"{acumulado[1]} - {previo[1]}"
                            derivacion = f"{3 * trimestre}M menos {3 * (trimestre - 1)}M"
                        elif all(t in computados for t in range(1, trimestre)):
                            # Una línea puede faltar en el acumulado anterior
                            # —la compañía no la abrió ese trimestre— y estar en
                            # el ejercicio. Ahí el trimestre sale de restarle al
                            # acumulado los trimestres que ya se armaron, que es
                            # aritméticamente lo mismo cuando los dos existen.
                            valor = acumulado[0] - sum(computados[t] for t in range(1, trimestre))
                            fuentes = acumulado[1]
                            derivacion = f"{3 * trimestre}M menos los trimestres anteriores"
                        else:
                            continue
                if derivacion != "saldo al cierre del trimestre anterior":
                    computados[trimestre] = valor
                filas.append(
                    {
                        "estado": estado,
                        "clave": clave,
                        "etiqueta": fila.etiqueta,
                        "orden": fila.orden,
                        "periodo": f"{anio}Q{trimestre}",
                        "anio": anio,
                        "trimestre": trimestre,
                        "tipo": "trimestre",
                        "valor_musd": valor,
                        "derivacion": derivacion,
                        "fuentes": fuentes,
                        "presentado": pd.Timestamp(fila.presentado).date().isoformat(),
                        "reexpresado_musd": np.nan,
                    }
                )

            anual = indice.get((estado, clave, 12, _cierre(anio, 4)))
            if anual is not None:
                filas.append(
                    {
                        "estado": estado,
                        "clave": clave,
                        "etiqueta": fila.etiqueta,
                        "orden": fila.orden,
                        "periodo": str(anio),
                        "anio": anio,
                        "trimestre": 0,
                        "tipo": "anual",
                        "valor_musd": anual[0],
                        "derivacion": "reportado",
                        "fuentes": anual[1],
                        "presentado": pd.Timestamp(fila.presentado).date().isoformat(),
                        "reexpresado_musd": np.nan,
                    }
                )

    # El balance anual es el cierre de diciembre: la misma fila, con la etiqueta
    # de ejercicio, para que la hoja anual no tenga un hueco donde va el stock.
    for fila in [f for f in filas if f["estado"] == "balance" and f["trimestre"] == 4]:
        anual = dict(fila)
        anual.update({"periodo": str(fila["anio"]), "trimestre": 0, "tipo": "anual"})
        filas.append(anual)

    return pd.DataFrame(filas)


def construir_json(serie: pd.DataFrame, cons: pd.DataFrame, crudo: pd.DataFrame) -> dict:
    """Resumen de cobertura: qué períodos quedaron y de dónde salieron."""
    trimestres = sorted(serie.loc[serie["tipo"] == "trimestre", "periodo"].unique())
    por_estado = {
        estado: sorted(grupo.loc[grupo["tipo"] == "trimestre", "periodo"].unique())
        for estado, grupo in serie.groupby("estado")
    }
    reexpresiones = cons[cons["reexpresado_musd"].abs() > 0.5]
    # La ficha de cada presentacion: la fecha es la del filing, no la de la
    # linea, que puede venir de una presentacion posterior que la reexpreso.
    fichas = (
        crudo.drop_duplicates("accession")
        .sort_values("presentado")[["accession", "form", "presentado"]]
        .to_dict("records")
    )
    return {
        "generado": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "moneda": "USD",
        "unidad": "millones",
        "trimestres": trimestres,
        "cobertura": por_estado,
        "anios": sorted(serie.loc[serie["tipo"] == "anual", "periodo"].unique()),
        "presentaciones": fichas,
        "lineas_reexpresadas": int(len(reexpresiones)),
        "nota": (
            "Estados en dólares. Los trimestres del flujo de efectivo salen por "
            "diferencia de acumulados; el 4T de resultados y de flujo, del "
            "ejercicio menos los nueve meses."
        ),
    }


def main() -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.parse_args()

    crudo = recolectar()
    cons = consolidar(crudo)
    serie = serie_trimestral(cons)

    salida = serie.sort_values(["estado", "periodo", "orden"]).reset_index(drop=True)
    bytes_parquet = save_parquet(salida, OUT_LONG)
    bytes_json = save_json(construir_json(serie, cons, crudo), OUT_JSON, indent=2)

    trimestres = sorted(salida.loc[salida["tipo"] == "trimestre", "periodo"].unique())
    log(
        f"{len(salida)} líneas · {len(trimestres)} trimestres "
        f"({trimestres[0]}–{trimestres[-1]}) · {crudo['accession'].nunique()} presentaciones"
    )
    record(
        "transform/statements",
        rows=int(len(salida)),
        bytes=int(bytes_parquet + bytes_json),
        outputs=[rel(OUT_LONG), rel(OUT_JSON)],
        source=rel(FILINGS),
        note=f"{trimestres[0]}–{trimestres[-1]} en USD; el 4T sale del anual menos nueve meses",
    )
    log(f"{rel(OUT_LONG)} ({human(bytes_parquet)}) · {rel(OUT_JSON)} ({human(bytes_json)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
