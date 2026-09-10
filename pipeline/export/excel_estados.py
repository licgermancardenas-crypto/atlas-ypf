"""Arma el Excel con los tres estados contables trimestrales de YPF.

Es la pieza para el lector de finanzas: el mismo dato que consume el sitio,
pero en el formato en el que un analista lo revisa, lo audita y lo usa de base
para su propio modelo. Sale de data/processed/statements_ypf.parquet, que a su
vez sale de los 6-K y 20-F de EDGAR.

Qué tiene el libro:

  Portada     alcance, unidades, método y las advertencias que hay que leer
              antes de usar un número;
  Resultados  estado de resultados integrales, trimestral y anual;
  Balance     estado de situación patrimonial;
  Flujo       estado de flujo de efectivo;
  Análisis    márgenes, retornos, estructura de capital, liquidez, capital de
              trabajo y generación de caja, todo con fórmulas vivas que apuntan
              a las hojas de estados;
  Chequeos    las identidades contables y el cruce contra los números que la
              compañía publica en su earnings release;
  Datos       la tabla larga con la derivación y la presentación de origen de
              cada número, para poder rastrearlo hasta el filing.

Las hojas de análisis y chequeos no traen valores pegados: traen fórmulas. Un
libro donde los ratios están calculados afuera y pegados como número no se
puede auditar ni reusar, que es justamente para lo que sirve un Excel.

Uso:
    python pipeline/export/excel_estados.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import xlsxwriter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "transform"))
from _common import PROCESSED, ROOT, base_parser, human, log, record, rel  # noqa: E402

ENTRADA = PROCESSED / "statements_ypf.parquet"
META = PROCESSED / "statements_ypf.json"
HIGHLIGHTS = PROCESSED / "financials_ypf.parquet"
SEGMENTOS_ENTRADA = PROCESSED / "segments_ypf.parquet"
SALIDA = ROOT / "docs" / "YPF_estados_financieros.xlsx"

# Seis ejercicios completos más lo que va del séptimo. Hacia atrás hay algunos
# trimestres sueltos de 2018 y 2019 —comparativos de presentaciones viejas— que
# quedan en la hoja Datos pero no en las de estados: media serie en una columna
# invita a comparar lo que no se puede.
DESDE = "2020Q1"

HOJAS = {
    "resultados": "Resultados",
    "balance": "Balance",
    "flujo": "Flujo de efectivo",
}

# Ancho de la primera columna: las líneas del flujo de efectivo son largas.
ANCHO_ETIQUETA = 62
ANCHO_DATO = 19

# La compañía reporta en millones de dólares. El libro muestra la cifra
# completa: 6.574 pasa a 6.574.000.000. No agrega precisión —el redondeo al
# millón es de la fuente y sigue estando— pero evita el error de leer un
# "6.574" como si fueran dólares, que en una planilla que se copia y se pega es
# más frecuente de lo que parece.
ESCALA = 1_000_000

AZUL = "#0054eb"
AZUL_OSCURO = "#00246b"
GRIS = "#5f7099"
BORDE = "#d5dcea"


# --------------------------------------------------------------------------- #
# Formatos
# --------------------------------------------------------------------------- #
def formatos(libro: xlsxwriter.Workbook) -> dict:
    base = {"font_name": "Calibri", "font_size": 10}
    # Los negativos entre paréntesis y el cero como raya: es la convención de
    # un estado contable, no un capricho tipográfico.
    numero = '#,##0;(#,##0);"–"'
    decimal = '#,##0.00;(#,##0.00);"–"'
    return {
        "titulo": libro.add_format({**base, "font_size": 16, "bold": True, "font_color": AZUL_OSCURO}),
        "subtitulo": libro.add_format({**base, "font_size": 10, "font_color": GRIS}),
        "seccion": libro.add_format({**base, "bold": True, "font_color": AZUL_OSCURO, "font_size": 11}),
        "encabezado": libro.add_format(
            {**base, "bold": True, "font_color": "white", "bg_color": AZUL, "align": "center", "bottom": 1}
        ),
        "encabezado_izq": libro.add_format(
            {**base, "bold": True, "font_color": "white", "bg_color": AZUL, "align": "left", "bottom": 1}
        ),
        "etiqueta": libro.add_format({**base, "indent": 1}),
        "etiqueta_total": libro.add_format({**base, "bold": True, "top": 1, "border_color": BORDE}),
        "etiqueta_ratio": libro.add_format({**base, "indent": 1}),
        "dato": libro.add_format({**base, "num_format": numero}),
        "dato_total": libro.add_format({**base, "num_format": numero, "bold": True, "top": 1, "border_color": BORDE}),
        "dato_derivado": libro.add_format({**base, "num_format": numero, "font_color": AZUL_OSCURO, "italic": True}),
        "dato_convertido": libro.add_format({**base, "num_format": numero, "font_color": "#8a6d3b"}),
        "dato_convertido_derivado": libro.add_format(
            {**base, "num_format": numero, "font_color": "#8a6d3b", "italic": True}
        ),
        "porcentaje": libro.add_format({**base, "num_format": '0.0%;(0.0%);"–"'}),
        "multiplo": libro.add_format({**base, "num_format": '0.00"x";(0.00"x");"–"'}),
        "dias": libro.add_format({**base, "num_format": '0.0;(0.0);"–"'}),
        "decimal": libro.add_format({**base, "num_format": decimal}),
        "texto": libro.add_format({**base, "text_wrap": True, "valign": "top"}),
        "texto_fuerte": libro.add_format({**base, "bold": True, "valign": "top"}),
        "nota": libro.add_format({**base, "font_size": 9, "font_color": GRIS, "text_wrap": True, "valign": "top"}),
        "ok": libro.add_format({**base, "num_format": numero, "font_color": "#2f7d5b"}),
        "alerta": libro.add_format({**base, "num_format": numero, "font_color": "#c0442a", "bold": True}),
    }


# --------------------------------------------------------------------------- #
# Datos
# --------------------------------------------------------------------------- #
def cargar() -> tuple[pd.DataFrame, dict, pd.DataFrame, pd.DataFrame]:
    datos = pd.read_parquet(ENTRADA)
    meta = json.loads(META.read_text(encoding="utf-8"))
    highlights = pd.read_parquet(HIGHLIGHTS) if HIGHLIGHTS.exists() else pd.DataFrame()
    segmentos = pd.read_parquet(SEGMENTOS_ENTRADA) if SEGMENTOS_ENTRADA.exists() else pd.DataFrame()
    return datos, meta, highlights, segmentos


SUFIJOS_SECCION = {
    "total non current assets": "no corriente",
    "total current assets": "corriente",
    "total non current liabilities": "no corriente",
    "total current liabilities": "corriente",
    "net cash flows from operating activities": "operativo",
    "net cash flows used in investing activities": "inversión",
    "net cash flows from financing activities": "financiación",
}

# Las tres veces que el estado de resultados repite las mismas dos líneas: es
# la atribución del resultado, la del otro resultado integral y la del
# resultado integral total, en ese orden.
ATRIBUCION = {
    "": "del resultado",
    "(2)": "de otro resultado integral",
    "(3)": "del resultado integral",
}


def etiqueta_legible(clave: str, etiqueta: str, repetida: bool, estado: str) -> str:
    """Le agrega a la línea lo que la distingue de su homónima.

    "Loans" aparece dos veces en el balance y "Non-controlling interest" tres
    veces en resultados. En el filing se distinguen por dónde están; en una
    planilla, donde el lector puede filtrar y ordenar, esa pista se pierde.
    """
    if not repetida:
        return etiqueta
    if " | " in clave:
        seccion = clave.rsplit(" | ", 1)[1]
        sufijo = SUFIJOS_SECCION.get(seccion)
        return f"{etiqueta} ({sufijo})" if sufijo else etiqueta
    if estado != "resultados":
        return etiqueta
    marca = clave[clave.rfind("(") :] if clave.endswith(")") else ""
    sufijo = ATRIBUCION.get(marca)
    return f"{etiqueta} ({sufijo})" if sufijo else etiqueta


def lineas_de(datos: pd.DataFrame, estado: str) -> list[tuple[str, str]]:
    """Las líneas de un estado, en el orden en que las presenta la compañía.

    El orden se toma de la presentación más reciente que tenga cada línea. Las
    que dejaron de publicarse quedan al final: no se las borra —son parte de la
    historia de la serie— pero tampoco se las intercala en un orden que hoy no
    existe.
    """
    sub = datos[datos["estado"] == estado]
    if sub.empty:
        return []
    ultimo = sub["presentado"].max()
    veces: dict[str, int] = {}
    for clave, grupo in sub.groupby("clave"):
        etiqueta = grupo.sort_values("presentado").iloc[-1]["etiqueta"]
        veces[etiqueta] = veces.get(etiqueta, 0) + 1

    filas = []
    for clave, grupo in sub.groupby("clave"):
        reciente = grupo.sort_values("presentado").iloc[-1]
        vigente = 0 if reciente["presentado"] == ultimo else 1
        etiqueta = etiqueta_legible(clave, reciente["etiqueta"], veces[reciente["etiqueta"]] > 1, estado)
        filas.append((vigente, int(reciente["orden"]), clave, etiqueta))
    filas.sort()

    # YPF imprime la variación de caja dos veces en el estado de flujo: como
    # subtotal de las tres secciones y de nuevo abajo de la conciliación de
    # saldos. Es el mismo número, no dos líneas: se deja una.
    series = sub.pivot_table(index="clave", columns="periodo", values="valor_musd", aggfunc="first")
    vistas: dict[str, str] = {}
    resultado = []
    for vigente, _, clave, etiqueta in filas:
        base = clave.rsplit(" (", 1)[0] if clave.endswith(")") and clave[-2].isdigit() else clave
        gemela = vistas.get(base)
        if gemela is not None and clave in series.index and gemela in series.index:
            if series.loc[clave].equals(series.loc[gemela]):
                continue
        vistas.setdefault(base, clave)
        resultado.append((clave, etiqueta, vigente))
    return resultado


def matriz(datos: pd.DataFrame, estado: str, periodos: list[str]) -> pd.DataFrame:
    sub = datos[(datos["estado"] == estado) & (datos["periodo"].isin(periodos))]
    valores = sub.pivot_table(index="clave", columns="periodo", values="valor_musd", aggfunc="first")
    derivaciones = sub.pivot_table(
        index="clave", columns="periodo", values="derivacion", aggfunc="first"
    )
    monedas = sub.pivot_table(
        index="clave", columns="periodo", values="moneda_origen", aggfunc="first"
    ) if "moneda_origen" in sub.columns else derivaciones * 0 + "USD"
    return (
        valores.reindex(columns=periodos),
        derivaciones.reindex(columns=periodos),
        monedas.reindex(columns=periodos),
    )


# --------------------------------------------------------------------------- #
# Hojas de estados
# --------------------------------------------------------------------------- #
def escribir_estado(
    libro: xlsxwriter.Workbook,
    fmt: dict,
    datos: pd.DataFrame,
    estado: str,
    trimestres: list[str],
    anios: list[str],
    titulo: str,
    subtitulo: str,
) -> tuple[str, dict[str, int], dict[str, str]]:
    """Escribe un estado contable y devuelve dónde quedó cada línea.

    El mapa de líneas a filas es lo que después le permite a la hoja de análisis
    apuntar con fórmulas en vez de repetir los números.
    """
    hoja = libro.add_worksheet(HOJAS[estado])
    hoja.hide_gridlines(2)
    hoja.set_column(0, 0, ANCHO_ETIQUETA)
    hoja.set_column(1, len(trimestres) + len(anios) + 2, ANCHO_DATO)
    hoja.set_tab_color(AZUL)

    hoja.write(0, 0, titulo, fmt["titulo"])
    hoja.write(1, 0, subtitulo, fmt["subtitulo"])

    columnas: dict[str, int] = {}
    fila_encabezado = 3
    hoja.write(fila_encabezado, 0, "En dólares", fmt["encabezado_izq"])
    for i, periodo in enumerate(trimestres):
        columnas[periodo] = i + 1
        hoja.write(fila_encabezado, i + 1, periodo, fmt["encabezado"])
    inicio_anual = len(trimestres) + 2
    hoja.write(fila_encabezado, inicio_anual - 1, "", fmt["encabezado"])
    for i, anio in enumerate(anios):
        columnas[anio] = inicio_anual + i
        hoja.write(fila_encabezado, inicio_anual + i, f"FY{anio[-2:]}", fmt["encabezado"])

    valores, derivaciones, monedas = matriz(datos, estado, trimestres + anios)
    filas: dict[str, int] = {}
    fila = fila_encabezado + 1
    historicas = False
    for clave, etiqueta, vigente in lineas_de(datos, estado):
        if clave not in valores.index:
            continue
        # Las líneas que la compañía dejó de publicar van al final, detrás de
        # su propio título: siguen siendo parte de la serie de los ejercicios
        # viejos, pero no son parte del estado de hoy.
        if vigente and not historicas:
            historicas = True
            fila += 1
            hoja.write(fila, 0, "Líneas de presentaciones anteriores", fmt["seccion"])
            fila += 1
        es_total = etiqueta.strip().lower().startswith("total")
        hoja.write(fila, 0, etiqueta, fmt["etiqueta_total"] if es_total else fmt["etiqueta"])
        for periodo, columna in columnas.items():
            valor = valores.at[clave, periodo] if periodo in valores.columns else None
            if valor is None or pd.isna(valor):
                continue
            derivacion = derivaciones.at[clave, periodo]
            moneda = monedas.at[clave, periodo] if periodo in monedas.columns else "USD"
            derivado = isinstance(derivacion, str) and derivacion != "reportado"
            convertido = moneda == "ARS"
            if es_total:
                formato = fmt["dato_total"]
            elif convertido and derivado:
                formato = fmt["dato_convertido_derivado"]
            elif convertido:
                formato = fmt["dato_convertido"]
            elif derivado:
                formato = fmt["dato_derivado"]
            else:
                formato = fmt["dato"]
            hoja.write_number(fila, columna, float(valor) * ESCALA, formato)
        filas[clave] = fila
        fila += 1

    hoja.write(
        fila + 1,
        0,
        "En bastardilla, los trimestres que la compañía no publica sueltos y salen por diferencia de "
        "acumulados. En marrón, los que la compañía presentó en pesos y acá vuelven a dólares por el "
        "tipo de cambio con el que se tradujeron. Ver Portada.",
        fmt["nota"],
    )
    hoja.freeze_panes(fila_encabezado + 1, 1)
    return HOJAS[estado], filas, columnas


# --------------------------------------------------------------------------- #
# Portada
# --------------------------------------------------------------------------- #
ADVERTENCIAS = [
    (
        "El cuarto trimestre no lo publica nadie",
        "YPF no emite un reporte de 4T: emite el ejercicio completo. El 4T de resultados y de "
        "flujo de efectivo de este libro sale del ejercicio menos los nueve meses. Es aritmética "
        "exacta, no una estimación, pero hereda cualquier reexpresión que la compañía haya hecho "
        "entre el 3T y el cierre: si algo se reclasificó, el ajuste cae entero en el 4T.",
    ),
    (
        "El flujo de efectivo trimestral es una diferencia",
        "El estado de flujo de efectivo se publica siempre acumulado desde el 1 de enero. Cada "
        "trimestre que no sea el primero es la resta de dos acumulados, y esos dos acumulados "
        "vienen de dos presentaciones distintas.",
    ),
    (
        "El balance empieza en el 4T23",
        "Los estados en dólares arrancan con el 6-K del 1T24, que trae 2023 como comparativo. Del "
        "estado de situación patrimonial, un interino solo muestra dos fechas: el cierre del "
        "trimestre y el diciembre anterior. Por eso hay resultados y flujo de todo 2023 pero no "
        "balance del 1T, 2T y 3T de ese año: en dólares, esas tres fechas no existen publicadas.",
    ),
    (
        "Hasta 2022 los estados venían en pesos, y acá están traducidos",
        "La moneda funcional de YPF es el dólar: los estados en pesos de esos años son esa misma "
        "contabilidad traducida según la NIC 21, con tipo de cambio de cierre para los saldos y "
        "promedio del período para los flujos. No son pesos reexpresados por inflación —se nota en "
        "que los comparativos no cambian de una presentación a la otra—, así que deshacer la "
        "traducción es dividir por el mismo tipo de cambio. Esos números van en marrón. El "
        "chequeo de que el camino de vuelta funciona está en la hoja Chequeos: el activo de "
        "diciembre de 2022 vuelve a dar los 25.912 millones que la compañía publicó en dólares, y "
        "el resultado neto de cada trimestre de 2020 a 2022 vuelve con menos de un millón de "
        "diferencia contra el que anunció en su earnings release.",
    ),
    (
        "El residuo de la traducción está en los ingresos de 2022",
        "La compañía traduce transacción por transacción y acá se usa el promedio de la cotización "
        "diaria del período. Cuando el tipo de cambio se mueve rápido, las dos cosas dejan de ser "
        "lo mismo: en 2022, con el peso perdiendo 72%, los ingresos trimestrales quedan entre 4 y "
        "6% por encima de los del release. En 2020 y 2021 la diferencia es menor a 2%.",
    ),
    (
        "Restar en pesos, convertir después",
        "El trimestre que sale de restar dos acumulados se arma antes de convertir. Restar dos "
        "números ya pasados a dólares con tipos de cambio distintos —el del semestre y el del "
        "trimestre— metería esa diferencia adentro del resultado.",
    ),
    (
        "Cuando un acumulado tiene dos versiones, se usan las que convivieron",
        "Un acumulado aparece en varias presentaciones y entre 2021 y 2023 la compañía reexpresó "
        "algunos comparativos. Restar un ejercicio reexpresado de un acumulado que no lo fue "
        "cargaba trece puntos de ingresos en el cuarto trimestre de 2020. Las dos puntas de cada "
        "resta se toman de las presentaciones más cercanas entre sí.",
    ),
    (
        "Cuando un número cambia, gana el último",
        "Un mismo período aparece en varias presentaciones: primero como período titular y "
        "después como comparativo, a veces reexpresado. Este libro toma la versión más reciente. "
        "La hoja Datos deja registrada la presentación de la que salió cada número.",
    ),
    (
        "EBITDA no es el de la compañía",
        "El EBITDA de la hoja Análisis es resultado operativo más depreciaciones y amortizaciones "
        "del estado de flujo. El 'EBITDA ajustado' que YPF publica en su earnings release además "
        "excluye partidas que la compañía considera no recurrentes. Los dos números están "
        "cruzados en la hoja Chequeos: la diferencia es el ajuste, no un error.",
    ),
]


def presentaciones(datos: pd.DataFrame, meta: dict) -> pd.DataFrame:
    """Las presentaciones que alimentaron el libro, sin repetir.

    Un trimestre derivado guarda las dos presentaciones de las que salió, en un
    campo del tipo "acc1 - acc2". Contarlas como están daría más presentaciones
    que las que existen.
    """
    fichas = meta.get("presentaciones") or []
    if fichas:
        return pd.DataFrame(fichas).sort_values("presentado")
    # Sin la ficha del transform queda el camino largo: las presentaciones que
    # aparecen en la columna de fuentes, que en un trimestre derivado son dos.
    filas = []
    for fuentes, fecha in zip(datos["fuentes"], datos["presentado"]):
        for accession in str(fuentes).split(" - "):
            filas.append({"accession": accession.strip(), "form": "", "presentado": fecha})
    return pd.DataFrame(filas).drop_duplicates("accession").sort_values("accession")


def escribir_portada(libro, fmt, meta: dict, datos: pd.DataFrame, trimestres: list[str], anios: list[str]) -> None:
    hoja = libro.add_worksheet("Portada")
    hoja.hide_gridlines(2)
    hoja.set_column(0, 0, 3)
    hoja.set_column(1, 1, 30)
    hoja.set_column(2, 2, 92)
    hoja.set_tab_color(AZUL_OSCURO)

    hoja.write(1, 1, "YPF Sociedad Anónima", fmt["titulo"])
    hoja.write(2, 1, "Estados contables trimestrales — en dólares", fmt["subtitulo"])

    fila = 4
    ficha = [
        ("Emisor", "YPF S.A. (NYSE: YPF), CIK 0000904851"),
        ("Fuente", "SEC EDGAR: estados contables adjuntos a los 6-K y a los 20-F"),
        ("Moneda y unidad", "Dólares estadounidenses, cifras completas. La compañía reporta redondeada al millón, así que "
                            "en la era dólar los últimos seis dígitos son cero: es el redondeo de la fuente, no una precisión "
                            "falsa. Los trimestres traducidos desde pesos no terminan en ceros porque el redondeo de origen es "
                            "al millón de pesos, que son unos pocos miles de dólares."),
        ("Split", "En 2026 el valor nominal pasó de $10 a $1: por cada acción vieja hay diez nuevas. El ADR de NYSE "
                  "pasó a representar diez acciones, así que la cantidad de ADR y su precio no cambiaron. La valuación "
                  "razona en ADR por eso. El resultado por acción de los estados, en cambio, cambia de base con el split."),
        ("Norma contable", "NIIF (IFRS) tal como las emite el IASB"),
        ("Cobertura trimestral", f"{trimestres[0]} a {trimestres[-1]} ({len(trimestres)} trimestres)"),
        ("Cobertura anual", f"FY{anios[0]} a FY{anios[-1]}"),
        ("Presentaciones usadas", f"{len(presentaciones(datos, meta))} entre 6-K y 20-F, listadas al pie"),
        ("Generado", meta.get("generado", "")),
    ]
    for etiqueta, valor in ficha:
        hoja.write(fila, 1, etiqueta, fmt["texto_fuerte"])
        hoja.write(fila, 2, valor, fmt["texto"])
        fila += 1

    fila += 1
    hoja.write(fila, 1, "Cómo se arma cada trimestre", fmt["seccion"])
    fila += 1
    metodo = [
        ("Resultados", "El interino publica el trimestre explícito para el 1T, 2T y 3T. El 4T sale del ejercicio menos los nueve meses."),
        ("Balance", "Es un stock: se toma tal cual a la fecha de cierre de cada trimestre."),
        ("Flujo de efectivo", "Se publica acumulado. 1T tal cual; 2T = 6M menos 3M; 3T = 9M menos 6M; 4T = ejercicio menos 9M."),
        ("Saldos de caja", "El saldo al cierre no se resta: es el saldo del acumulado que termina en ese trimestre. La apertura del trimestre es el cierre del anterior."),
        ("Resultado por acción", "Solo cuando la compañía lo publica para el trimestre. Restar acumulados de un ratio por acción no da el ratio del período."),
        ("Traducción de pesos", "Saldos al tipo de cambio de cierre; flujos al promedio del período. La resta de acumulados se hace en pesos y se convierte después."),
    ]
    for etiqueta, valor in metodo:
        hoja.write(fila, 1, etiqueta, fmt["texto_fuerte"])
        hoja.write(fila, 2, valor, fmt["texto"])
        fila += 1

    fila += 1
    hoja.write(fila, 1, "Lo que hay que saber antes de usar un número", fmt["seccion"])
    fila += 1
    for titulo, cuerpo in ADVERTENCIAS:
        hoja.write(fila, 1, titulo, fmt["texto_fuerte"])
        hoja.write(fila, 2, cuerpo, fmt["texto"])
        hoja.set_row(fila, 46)
        fila += 1

    fila += 1
    hoja.write(fila, 1, "Hojas", fmt["seccion"])
    fila += 1
    for nombre, que in [
        ("Resultados", "Estado de resultados integrales, trimestral y anual."),
        ("Balance", "Estado de situación patrimonial."),
        ("Flujo de efectivo", "Estado de flujo de efectivo."),
        ("Segmentos", "Ingresos, resultado operativo, capex y activos por negocio, con el margen de cada uno."),
        ("Operativo", "Producción, precios de realización y las métricas por barril que salen de cruzarlos con los estados."),
        ("Análisis", "Márgenes, retornos, estructura de capital, liquidez, capital de trabajo y caja. Todo con fórmulas."),
        ("Valuación", "Cuatro métodos —descontado, múltiplo, reservas y valor libro— sobre supuestos editables."),
        ("Comparables", "YPF contra Vista y Pampa: márgenes, apalancamiento y múltiplos, del XBRL de sus 20-F."),
        ("Chequeos", "Identidades contables y cruce contra el earnings release de la compañía."),
        ("Datos", "Tabla larga: cada número con su derivación y la presentación de la que salió."),
    ]:
        hoja.write(fila, 1, nombre, fmt["texto_fuerte"])
        hoja.write(fila, 2, que, fmt["texto"])
        fila += 1

    fila += 1
    hoja.write(fila, 1, "Presentaciones usadas", fmt["seccion"])
    fila += 1
    hoja.write(fila, 1, "Accession de EDGAR", fmt["texto_fuerte"])
    hoja.write(fila, 2, "Se consulta en sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000904851", fmt["texto"])
    fila += 1
    for registro in presentaciones(datos, meta).itertuples():
        hoja.write(fila, 1, registro.accession, fmt["texto"])
        hoja.write(fila, 2, f"{registro.form}, presentada el {registro.presentado}", fmt["texto"])
        fila += 1

    fila += 1
    hoja.write(
        fila,
        1,
        "Este libro se genera con pipeline/export/excel_estados.py. No editar a mano: "
        "la próxima corrida lo pisa.",
        fmt["nota"],
    )


# --------------------------------------------------------------------------- #
# Análisis
# --------------------------------------------------------------------------- #
def escribir_analisis(libro, fmt, mapas: dict, trimestres: list[str], anios: list[str]) -> dict:
    hoja = libro.add_worksheet("Análisis")
    hoja.hide_gridlines(2)
    hoja.set_column(0, 0, ANCHO_ETIQUETA)
    hoja.set_column(1, len(trimestres) + len(anios) + 2, ANCHO_DATO)
    hoja.set_tab_color(AZUL)

    hoja.write(0, 0, "Análisis", fmt["titulo"])
    hoja.write(1, 0, "Todo calculado con fórmulas sobre las hojas de estados: se puede seguir cada celda hasta la línea que la origina.", fmt["subtitulo"])

    columnas = mapas["columnas"]
    fila_encabezado = 3
    hoja.write(fila_encabezado, 0, "", fmt["encabezado_izq"])
    for periodo, columna in columnas.items():
        hoja.write(fila_encabezado, columna, periodo if periodo in trimestres else f"FY{periodo[-2:]}", fmt["encabezado"])

    def ref(estado: str, clave: str, columna: int) -> str | None:
        filas = mapas[estado]
        if clave not in filas:
            return None
        hoja_nombre = HOJAS[estado]
        letra = xlsxwriter.utility.xl_col_to_name(columna)
        return f"'{hoja_nombre}'!{letra}{filas[clave] + 1}"

    def escribir_formula(fila: int, etiqueta: str, armar, formato, nota: str = "") -> int:
        hoja.write(fila, 0, etiqueta, fmt["etiqueta_ratio"])
        for periodo, columna in columnas.items():
            formula = armar(columna, periodo)
            if formula:
                hoja.write_formula(fila, columna, formula, formato, "")
        if nota:
            hoja.write(fila, max(columnas.values()) + 2, nota, fmt["nota"])
        return fila + 1

    def division(numerador, denominador):
        def armar(columna: int, periodo: str) -> str | None:
            arriba = numerador(columna) if callable(numerador) else numerador
            abajo = denominador(columna) if callable(denominador) else denominador
            if not arriba or not abajo:
                return None
            return f"=IFERROR({arriba}/{abajo},\"\")"
        return armar

    R = lambda clave: (lambda c: ref("resultados", clave, c))  # noqa: E731
    B = lambda clave: (lambda c: ref("balance", clave, c))  # noqa: E731
    F = lambda clave: (lambda c: ref("flujo", clave, c))  # noqa: E731

    def suma(partes):
        def armar(columna: int) -> str | None:
            celdas = [p(columna) for p in partes]
            celdas = [c for c in celdas if c]
            if not celdas:
                return None
            return "(" + "+".join(celdas) + ")"
        return armar

    ingresos = R("revenues")
    resultado_operativo = R("operating profit")
    resultado_neto = R("net profit")
    depreciaciones = suma([
        F("depreciation of property plant and equipment | net cash flows from operating activities"),
        F("amortization of intangible assets | net cash flows from operating activities"),
        F("depreciation of right of use assets | net cash flows from operating activities"),
    ])
    ebitda = suma([resultado_operativo, depreciaciones])
    caja = B("cash and cash equivalents | total current assets")
    inversiones_corrientes = B("investments in financial assets | total current assets")
    deuda = suma([
        B("loans | total non current liabilities"),
        B("loans | total current liabilities"),
    ])
    arrendamientos = suma([
        B("lease liabilities | total non current liabilities"),
        B("lease liabilities | total current liabilities"),
    ])
    patrimonio = B("total shareholders equity")
    activo = B("total assets")
    activo_corriente = B("total current assets")
    pasivo_corriente = B("total current liabilities")
    inventarios = B("inventories | total current assets")
    creditos = B("trade receivables | total current assets")
    proveedores = B("accounts payable | total current liabilities")
    cfo = F("net cash flows from operating activities")
    capex = F("acquisition of property plant and equipment and intangible assets | net cash flows used in investing activities")

    fila = fila_encabezado + 1
    hoja.write(fila, 0, "Rentabilidad", fmt["seccion"])
    fila += 1
    fila = escribir_formula(fila, "Margen bruto", division(R("gross profit"), ingresos), fmt["porcentaje"])
    fila = escribir_formula(fila, "Margen operativo", division(resultado_operativo, ingresos), fmt["porcentaje"])
    fila = escribir_formula(fila, "Margen EBITDA", division(ebitda, ingresos), fmt["porcentaje"])
    fila = escribir_formula(fila, "Margen neto", division(resultado_neto, ingresos), fmt["porcentaje"])
    fila = escribir_formula(
        fila,
        "Tasa efectiva de impuesto",
        division(lambda c: f"-{R('income tax')(c)}" if R("income tax")(c) else None, R("net profit before income tax")),
        fmt["porcentaje"],
        "Impuesto sobre resultado antes de impuesto. Con resultado negativo, el signo se invierte y el ratio no dice nada.",
    )

    fila += 1
    hoja.write(fila, 0, "Absolutos calculados", fmt["seccion"])
    fila += 1
    fila_ebitda = fila
    fila = escribir_formula(fila, "EBITDA (resultado operativo + D&A)", lambda c, p: f"={ebitda(c)}" if ebitda(c) else None, fmt["dato"])
    fila = escribir_formula(fila, "Depreciaciones y amortizaciones", lambda c, p: f"={depreciaciones(c)}" if depreciaciones(c) else None, fmt["dato"])
    fila_fcf = fila
    fila = escribir_formula(
        fila,
        "Flujo de caja libre (operativo − capex)",
        lambda c, p: f"={cfo(c)}+{capex(c)}" if cfo(c) and capex(c) else None,
        fmt["dato"],
        "El capex viene con signo negativo en el estado de flujo, así que se suma.",
    )
    def con_dato(referencia, expresion):
        """Sin el dato de base, la celda va vacía.

        Una suma de celdas vacías da cero, y un cero en una serie de deuda se
        lee como que la compañía no debía nada. En los trimestres de 2023 sin
        balance publicado en dólares, la respuesta correcta es el silencio.
        """
        def armar(columna: int, periodo: str) -> str | None:
            base = referencia(columna)
            cuerpo = expresion(columna)
            if not base or not cuerpo:
                return None
            return f"=IF(COUNT({base})=0,\"\",{cuerpo})"
        return armar

    fila_deuda_bruta = fila
    fila = escribir_formula(
        fila,
        "Deuda financiera bruta",
        con_dato(lambda c: deuda(c), lambda c: deuda(c)),
        fmt["dato"],
        "Préstamos corrientes y no corrientes. No incluye pasivos por arrendamiento.",
    )
    fila_deuda_neta = fila
    fila = escribir_formula(
        fila,
        "Deuda financiera neta",
        con_dato(caja, lambda c: f"{deuda(c)}-{caja(c)}-{inversiones_corrientes(c)}" if deuda(c) and caja(c) else None),
        fmt["dato"],
        "Neta de caja y de inversiones financieras corrientes.",
    )
    fila = escribir_formula(
        fila,
        "Deuda financiera neta + arrendamientos",
        con_dato(
            caja,
            lambda c: f"{deuda(c)}+{arrendamientos(c)}-{caja(c)}-{inversiones_corrientes(c)}"
            if deuda(c) and arrendamientos(c) and caja(c)
            else None,
        ),
        fmt["dato"],
    )
    fila = escribir_formula(
        fila,
        "Capital invertido (deuda neta + patrimonio)",
        con_dato(
            caja,
            lambda c: f"{deuda(c)}-{caja(c)}-{inversiones_corrientes(c)}+{patrimonio(c)}"
            if deuda(c) and caja(c) and patrimonio(c)
            else None,
        ),
        fmt["dato"],
    )
    fila_capital = fila - 1

    fila += 1
    hoja.write(fila, 0, "Últimos doce meses", fmt["seccion"])
    fila += 1

    def ltm(constructor):
        """Suma los cuatro trimestres que terminan en cada columna."""
        def armar(columna: int, periodo: str) -> str | None:
            if periodo not in trimestres:
                return None
            posicion = trimestres.index(periodo)
            if posicion < 3:
                return None
            celdas = [constructor(columnas[trimestres[posicion - i]]) for i in range(4)]
            if any(c is None for c in celdas):
                return None
            return "=" + "+".join(celdas)
        return armar

    fila_ltm_ebitda = fila
    fila = escribir_formula(fila, "EBITDA UDM", ltm(ebitda), fmt["dato"])
    fila_ltm_neto = fila
    fila = escribir_formula(fila, "Resultado neto UDM", ltm(resultado_neto), fmt["dato"])
    fila_ltm_cfo = fila
    fila = escribir_formula(fila, "Flujo operativo UDM", ltm(cfo), fmt["dato"])
    fila_ltm_ingresos = fila
    fila = escribir_formula(fila, "Ingresos UDM", ltm(ingresos), fmt["dato"])
    fila_ltm_ebit = fila
    fila = escribir_formula(fila, "Resultado operativo UDM", ltm(resultado_operativo), fmt["dato"])
    fila_ltm_antes = fila
    fila = escribir_formula(fila, "Resultado antes de impuesto UDM", ltm(R("net profit before income tax")), fmt["dato"])
    fila_ltm_impuesto = fila
    fila = escribir_formula(fila, "Impuesto a las ganancias UDM", ltm(R("income tax")), fmt["dato"])
    fila_ltm_capex = fila
    fila = escribir_formula(fila, "Capex UDM", ltm(capex), fmt["dato"])
    fila_ltm_costo_fin = fila
    fila = escribir_formula(fila, "Costos financieros UDM", ltm(R("financial costs")), fmt["dato"])

    def celda_local(fila_local: int):
        def armar(columna: int) -> str:
            return f"{xlsxwriter.utility.xl_col_to_name(columna)}{fila_local + 1}"
        return armar

    fila += 1
    hoja.write(fila, 0, "Retornos", fmt["seccion"])
    fila += 1

    def promedio_balance(constructor):
        """Promedio del stock entre el cierre actual y el de cuatro trimestres antes."""
        def armar(columna: int, periodo: str) -> str | None:
            if periodo not in trimestres:
                return None
            posicion = trimestres.index(periodo)
            if posicion < 4:
                return None
            ahora = constructor(columna)
            antes = constructor(columnas[trimestres[posicion - 4]])
            if not ahora or not antes:
                return None
            return f"AVERAGE({ahora},{antes})"
        return armar

    def retorno(fila_numerador: int, denominador, constructor):
        """Retorno sobre un stock promedio, solo cuando las dos puntas existen.

        AVERAGE ignora las celdas vacías, así que un promedio con una sola
        punta devolvería un denominador que es un cierre y no un promedio, sin
        avisar. El COUNT es lo que impide ese número silenciosamente mal.
        """
        def armar(columna: int, periodo: str) -> str | None:
            abajo = denominador(columna, periodo)
            if not abajo or periodo not in trimestres:
                return None
            posicion = trimestres.index(periodo)
            if posicion < 4:
                return None
            puntas = f"{constructor(columna)},{constructor(columnas[trimestres[posicion - 4]])}"
            arriba = celda_local(fila_numerador)(columna)
            return f"=IF(COUNT({puntas})<2,\"\",IFERROR({arriba}/{abajo},\"\"))"
        return armar

    fila = escribir_formula(fila, "ROE (UDM sobre patrimonio promedio)",
                            retorno(fila_ltm_neto, promedio_balance(patrimonio), patrimonio), fmt["porcentaje"])
    fila = escribir_formula(fila, "ROA (UDM sobre activo promedio)",
                            retorno(fila_ltm_neto, promedio_balance(activo), activo), fmt["porcentaje"])

    def roic(columna: int, periodo: str) -> str | None:
        """NOPAT sobre capital invertido promedio.

        El NOPAT usa la tasa efectiva de los últimos doce meses y no la del
        trimestre: con un trimestre de resultado negativo, la tasa efectiva
        puntual es un número sin sentido económico.
        """
        if periodo not in trimestres or trimestres.index(periodo) < 4:
            return None
        posicion = trimestres.index(periodo)
        capital_hoy = celda_local(fila_capital)(columna)
        capital_antes = celda_local(fila_capital)(columnas[trimestres[posicion - 4]])
        ebit = celda_local(fila_ltm_ebit)(columna)
        antes = celda_local(fila_ltm_antes)(columna)
        impuesto = celda_local(fila_ltm_impuesto)(columna)
        # La tasa efectiva se acota entre 0 y 60%: con un resultado antes de
        # impuesto cercano a cero, el cociente se dispara —en 2025 dio 26 veces
        # el resultado— y arrastra el NOPAT a un número que no existe.
        tasa = f"MIN(MAX(IF({antes}<=0,0.35,-{impuesto}/{antes}),0),0.6)"
        return (
            f"=IF(COUNT({capital_hoy},{capital_antes})<2,\"\","
            f"IFERROR({ebit}*(1-{tasa})/AVERAGE({capital_hoy},{capital_antes}),\"\"))"
        )

    fila = escribir_formula(
        fila,
        "ROIC (NOPAT UDM sobre capital invertido promedio)",
        roic,
        fmt["porcentaje"],
        "Tasa efectiva de los últimos doce meses, acotada entre 0% y 60%. Con resultado antes de impuesto "
        "negativo se usa 35%, la tasa societaria argentina.",
    )

    fila += 1
    hoja.write(fila, 0, "Estructura de capital", fmt["seccion"])
    fila += 1

    def sobre_ltm_ebitda(constructor):
        def armar(columna: int, periodo: str) -> str | None:
            if periodo not in trimestres or trimestres.index(periodo) < 3:
                return None
            arriba = constructor(columna)
            if not arriba:
                return None
            return f"=IFERROR({arriba}/{celda_local(fila_ltm_ebitda)(columna)},\"\")"
        return armar

    fila = escribir_formula(
        fila,
        "Deuda neta / EBITDA UDM",
        sobre_ltm_ebitda(lambda c: f"({deuda(c)}-{caja(c)}-{inversiones_corrientes(c)})" if deuda(c) and caja(c) else None),
        fmt["multiplo"],
    )
    fila = escribir_formula(fila, "Deuda bruta / patrimonio", division(deuda, patrimonio), fmt["multiplo"])
    fila = escribir_formula(fila, "Pasivo / activo", division(B("total liabilities"), activo), fmt["porcentaje"])
    fila = escribir_formula(
        fila,
        "Cobertura de intereses (EBIT / costos financieros)",
        division(resultado_operativo, lambda c: f"-{R('financial costs')(c)}" if R("financial costs")(c) else None),
        fmt["multiplo"],
        "Costos financieros totales del estado de resultados, no solo intereses de deuda.",
    )

    fila += 1
    hoja.write(fila, 0, "Liquidez y capital de trabajo", fmt["seccion"])
    fila += 1
    fila = escribir_formula(fila, "Liquidez corriente", division(activo_corriente, pasivo_corriente), fmt["multiplo"])
    fila = escribir_formula(
        fila,
        "Prueba ácida",
        division(lambda c: f"({activo_corriente(c)}-{inventarios(c)})" if activo_corriente(c) and inventarios(c) else None, pasivo_corriente),
        fmt["multiplo"],
    )
    fila = escribir_formula(
        fila,
        "Días de cobranza (DSO)",
        division(lambda c: f"{creditos(c)}*91.25" if creditos(c) else None, ingresos),
        fmt["dias"],
        "Sobre los ingresos del trimestre anualizados a 365 días.",
    )
    fila = escribir_formula(
        fila,
        "Días de inventario (DIO)",
        division(lambda c: f"{inventarios(c)}*91.25" if inventarios(c) else None, lambda c: f"-{R('costs')(c)}" if R("costs")(c) else None),
        fmt["dias"],
    )
    fila = escribir_formula(
        fila,
        "Días de pago (DPO)",
        division(lambda c: f"{proveedores(c)}*91.25" if proveedores(c) else None, lambda c: f"-{R('costs')(c)}" if R("costs")(c) else None),
        fmt["dias"],
    )

    fila += 1
    hoja.write(fila, 0, "Generación de caja", fmt["seccion"])
    fila += 1
    fila = escribir_formula(fila, "Flujo operativo / ingresos", division(cfo, ingresos), fmt["porcentaje"])
    fila = escribir_formula(
        fila,
        "Capex / D&A",
        division(lambda c: f"-{capex(c)}" if capex(c) else None, depreciaciones),
        fmt["multiplo"],
        "Arriba de 1 la compañía está invirtiendo más de lo que consume su base de activos.",
    )
    fila = escribir_formula(
        fila,
        "Flujo de caja libre / EBITDA",
        division(lambda c: f"({cfo(c)}+{capex(c)})" if cfo(c) and capex(c) else None, ebitda),
        fmt["porcentaje"],
    )

    fila += 1
    hoja.write(fila, 0, "Crecimiento interanual", fmt["seccion"])
    fila += 1

    def interanual(constructor):
        """Contra el mismo trimestre del año anterior: el negocio es estacional."""
        def armar(columna: int, periodo: str) -> str | None:
            if periodo not in trimestres:
                return None
            posicion = trimestres.index(periodo)
            if posicion < 4:
                return None
            ahora = constructor(columna)
            antes = constructor(columnas[trimestres[posicion - 4]])
            if not ahora or not antes:
                return None
            return f"=IFERROR({ahora}/{antes}-1,\"\")"
        return armar

    fila = escribir_formula(fila, "Ingresos", interanual(ingresos), fmt["porcentaje"])
    fila = escribir_formula(fila, "EBITDA", interanual(ebitda), fmt["porcentaje"])
    fila = escribir_formula(fila, "Flujo operativo", interanual(cfo), fmt["porcentaje"])

    fila += 1
    hoja.write(fila, 0, "Estructura del resultado (sobre ingresos)", fmt["seccion"])
    fila += 1
    for etiqueta, clave in [
        ("Costos", "costs"),
        ("Gastos de comercialización", "selling expenses"),
        ("Gastos de administración", "administrative expenses"),
        ("Gastos de exploración", "exploration expenses"),
        ("Otros resultados operativos", "other net operating results"),
        ("Resultados financieros netos", "net financial results"),
        ("Impuesto a las ganancias", "income tax"),
    ]:
        fila = escribir_formula(fila, etiqueta, division(R(clave), ingresos), fmt["porcentaje"])

    hoja.freeze_panes(fila_encabezado + 1, 1)
    return {
        "hoja": "Análisis",
        "ebitda": fila_ebitda,
        "fcf": fila_fcf,
        "deuda_bruta": fila_deuda_bruta,
        "deuda_neta": fila_deuda_neta,
        "capital": fila_capital,
        "ltm_ebitda": fila_ltm_ebitda,
        "ltm_neto": fila_ltm_neto,
        "ltm_cfo": fila_ltm_cfo,
        "ltm_ingresos": fila_ltm_ingresos,
        "ltm_ebit": fila_ltm_ebit,
        "ltm_antes": fila_ltm_antes,
        "ltm_impuesto": fila_ltm_impuesto,
        "ltm_capex": fila_ltm_capex,
        "ltm_costo_fin": fila_ltm_costo_fin,
    }


# --------------------------------------------------------------------------- #
# Chequeos
# --------------------------------------------------------------------------- #
def escribir_chequeos(libro, fmt, mapas: dict, datos: pd.DataFrame, highlights: pd.DataFrame,
                      trimestres: list[str], anios: list[str]) -> None:
    """Las identidades que tienen que dar cero y el cruce contra la compañía.

    Un estado armado a mano desde HTML puede estar mal de mil maneras, y casi
    todas se ven acá: si el activo no cierra contra pasivo más patrimonio, si la
    caja del flujo no es la del balance, si los cuatro trimestres no suman el
    ejercicio. Que estén a la vista y como fórmula —no como afirmación en la
    portada— es lo que hace que el libro se pueda auditar.
    """
    hoja = libro.add_worksheet("Chequeos")
    hoja.hide_gridlines(2)
    hoja.set_column(0, 0, ANCHO_ETIQUETA)
    hoja.set_column(1, len(trimestres) + len(anios) + 2, ANCHO_DATO)
    hoja.set_tab_color(AZUL_OSCURO)

    hoja.write(0, 0, "Chequeos", fmt["titulo"])
    hoja.write(1, 0, "Las identidades contables tienen que dar cero. El cruce contra el earnings release no: ahí la diferencia es el ajuste de la compañía.", fmt["subtitulo"])

    columnas = mapas["columnas"]
    fila_encabezado = 3
    hoja.write(fila_encabezado, 0, "", fmt["encabezado_izq"])
    for periodo, columna in columnas.items():
        hoja.write(fila_encabezado, columna, periodo if periodo in trimestres else f"FY{periodo[-2:]}", fmt["encabezado"])

    def ref(estado: str, clave: str, columna: int) -> str | None:
        filas = mapas[estado]
        if clave not in filas:
            return None
        letra = xlsxwriter.utility.xl_col_to_name(columna)
        return f"'{HOJAS[estado]}'!{letra}{filas[clave] + 1}"

    def fila_chequeo(fila: int, etiqueta: str, armar) -> int:
        hoja.write(fila, 0, etiqueta, fmt["etiqueta_ratio"])
        for periodo, columna in columnas.items():
            formula = armar(columna, periodo)
            if formula:
                hoja.write_formula(fila, columna, formula, fmt["dato"], "")
        # El formato condicional pinta el desvío: verde en cero, rojo si no.
        hoja.conditional_format(
            fila, 1, fila, max(columnas.values()),
            {"type": "cell", "criteria": "between", "minimum": -0.5, "maximum": 0.5,
             "format": libro.add_format({"font_color": "#2f7d5b"})},
        )
        hoja.conditional_format(
            fila, 1, fila, max(columnas.values()),
            {"type": "cell", "criteria": "not between", "minimum": -0.5, "maximum": 0.5,
             "format": libro.add_format({"font_color": "#c0442a", "bold": True})},
        )
        return fila + 1

    def resta(izquierda, derecha):
        def armar(columna: int, periodo: str) -> str | None:
            a = izquierda(columna)
            b = derecha(columna)
            if not a or not b:
                return None
            return f"={a}-({b})"
        return armar

    B = lambda clave: (lambda c: ref("balance", clave, c))  # noqa: E731
    R = lambda clave: (lambda c: ref("resultados", clave, c))  # noqa: E731
    F = lambda clave: (lambda c: ref("flujo", clave, c))  # noqa: E731

    def mas(partes):
        def armar(columna: int) -> str | None:
            celdas = [p(columna) for p in partes]
            if any(c is None for c in celdas):
                return None
            return "+".join(celdas)
        return armar

    fila = fila_encabezado + 1
    hoja.write(fila, 0, "Identidades del balance", fmt["seccion"])
    fila += 1
    fila = fila_chequeo(fila, "Activo − (pasivo + patrimonio)",
                        resta(B("total assets"), mas([B("total liabilities"), B("total shareholders equity")])))
    fila = fila_chequeo(fila, "Activo − (corriente + no corriente)",
                        resta(B("total assets"), mas([B("total current assets"), B("total non current assets")])))
    fila = fila_chequeo(fila, "Pasivo − (corriente + no corriente)",
                        resta(B("total liabilities"), mas([B("total current liabilities"), B("total non current liabilities")])))

    fila += 1
    hoja.write(fila, 0, "Identidades del estado de resultados", fmt["seccion"])
    fila += 1
    fila = fila_chequeo(fila, "Resultado bruto − (ingresos + costos)",
                        resta(R("gross profit"), mas([R("revenues"), R("costs")])))
    fila = fila_chequeo(fila, "Resultado neto − (antes de impuesto + impuesto)",
                        resta(R("net profit"), mas([R("net profit before income tax"), R("income tax")])))
    fila = fila_chequeo(fila, "Resultado neto − (controlante + no controlante)",
                        resta(R("net profit"), mas([R("shareholders of the parent company"), R("non controlling interest")])))

    fila += 1
    hoja.write(fila, 0, "Articulación entre estados", fmt["seccion"])
    fila += 1
    fila = fila_chequeo(
        fila,
        "Caja del flujo − caja del balance",
        resta(F("cash and cash equivalents at the end of the period"),
              B("cash and cash equivalents | total current assets")),
    )
    fila = fila_chequeo(
        fila,
        "(Operativo + inversión + financiación + tipo de cambio) − variación de caja",
        resta(
            mas([
                F("net cash flows from operating activities"),
                F("net cash flows used in investing activities"),
                F("net cash flows from financing activities"),
                F("effect of changes in exchange rates on cash and cash equivalents"),
            ]),
            F("increase in cash and cash equivalents"),
        ),
    )
    fila = fila_chequeo(
        fila,
        "Resultado neto del flujo − resultado neto del estado de resultados",
        resta(F("net profit | net cash flows from operating activities"), R("net profit")),
    )

    fila += 1
    hoja.write(fila, 0, "Los cuatro trimestres contra el ejercicio", fmt["seccion"])
    fila += 1

    def suma_trimestres(estado: str, clave: str):
        def armar(columna: int, periodo: str) -> str | None:
            if periodo in trimestres:
                return None
            trimestres_del_anio = [t for t in trimestres if t.startswith(periodo)]
            if len(trimestres_del_anio) != 4:
                return None
            celdas = [ref(estado, clave, columnas[t]) for t in trimestres_del_anio]
            anual = ref(estado, clave, columna)
            if any(c is None for c in celdas) or anual is None:
                return None
            return "=" + "+".join(celdas) + f"-{anual}"
        return armar

    hoja.write(
        fila - 1,
        max(columnas.values()) + 2,
        "En los ejercicios en dólares esto tiene que dar cero. Hasta 2022 no: ahí los trimestres vuelven "
        "de pesos con el tipo de cambio promedio de cada período y el ejercicio es el que la compañía "
        "publicó en dólares en su 20-F. La diferencia es el residuo de la traducción, medido abajo.",
        fmt["nota"],
    )
    fila = fila_chequeo(fila, "Ingresos: suma de trimestres − ejercicio", suma_trimestres("resultados", "revenues"))
    fila = fila_chequeo(fila, "Resultado neto: suma de trimestres − ejercicio", suma_trimestres("resultados", "net profit"))
    fila = fila_chequeo(fila, "Flujo operativo: suma de trimestres − ejercicio",
                        suma_trimestres("flujo", "net cash flows from operating activities"))

    fila += 1
    hoja.write(fila, 0, "Cuánto cuesta la conversión desde pesos", fmt["seccion"])
    hoja.write(
        fila,
        max(columnas.values()) + 2,
        "La compañía traduce cada transacción a su propio tipo de cambio; acá se usa el promedio diario del "
        "período. En un año de salto cambiario las dos cosas se separan, y esta fila mide cuánto.",
        fmt["nota"],
    )
    fila += 1

    def brecha(estado: str, clave: str):
        def armar(columna: int, periodo: str) -> str | None:
            if periodo in trimestres:
                return None
            trimestres_del_anio = [t for t in trimestres if t.startswith(periodo)]
            if len(trimestres_del_anio) != 4:
                return None
            celdas = [ref(estado, clave, columnas[t]) for t in trimestres_del_anio]
            anual = ref(estado, clave, columna)
            if any(c is None for c in celdas) or anual is None:
                return None
            suma = "+".join(celdas)
            return f"=IFERROR(({suma})/{anual}-1,\"\")"
        return armar

    for etiqueta, estado, clave in [
        ("Ingresos, brecha en %", "resultados", "revenues"),
        ("Resultado neto, brecha en %", "resultados", "net profit"),
        ("Flujo operativo, brecha en %", "flujo", "net cash flows from operating activities"),
    ]:
        hoja.write(fila, 0, etiqueta, fmt["etiqueta_ratio"])
        armar = brecha(estado, clave)
        for periodo, columna in columnas.items():
            formula = armar(columna, periodo)
            if formula:
                hoja.write_formula(fila, columna, formula, fmt["porcentaje"], "")
        fila += 1

    if not highlights.empty:
        fila += 1
        hoja.write(fila, 0, "Contra el earnings release de la compañía", fmt["seccion"])
        fila += 1
        hoja.write(fila - 1, max(columnas.values()) + 2,
                   "Los números del release salen de la tabla de highlights del 6-K; los del estado, de los estados contables del mismo 6-K.",
                   fmt["nota"])
        indexado = highlights.set_index("trimestre")
        cruces = [
            ("Ingresos, release", "revenues_musd", "resultados", "revenues", True),
            ("Resultado neto, release", "net_result_musd", "resultados", "net profit", True),
            ("EBITDA ajustado, release", "adj_ebitda_musd", None, None, False),
            ("Deuda neta, release", "net_debt_musd", None, None, False),
        ]
        for etiqueta, campo, estado, clave, comparar in cruces:
            if campo not in indexado.columns:
                continue
            hoja.write(fila, 0, etiqueta, fmt["etiqueta_ratio"])
            for periodo, columna in columnas.items():
                if periodo not in indexado.index:
                    continue
                valor = indexado.at[periodo, campo]
                if pd.isna(valor):
                    continue
                hoja.write_number(fila, columna, float(valor) * ESCALA, fmt["dato"])
            fila_release = fila
            fila += 1
            if comparar:
                hoja.write(fila, 0, f"   diferencia contra el estado contable", fmt["etiqueta_ratio"])
                for periodo, columna in columnas.items():
                    celda_estado = ref(estado, clave, columna)
                    if celda_estado is None or periodo not in indexado.index:
                        continue
                    if pd.isna(indexado.at[periodo, campo]):
                        continue
                    letra = xlsxwriter.utility.xl_col_to_name(columna)
                    hoja.write_formula(
                        fila, columna, f"={letra}{fila_release + 1}-{celda_estado}", fmt["dato"], ""
                    )
                fila += 1

    hoja.freeze_panes(fila_encabezado + 1, 1)


# --------------------------------------------------------------------------- #
# Datos
# --------------------------------------------------------------------------- #
def escribir_datos(libro, fmt, datos: pd.DataFrame) -> None:
    hoja = libro.add_worksheet("Datos")
    hoja.hide_gridlines(2)
    hoja.set_tab_color(GRIS)

    columnas = [
        ("Estado", "estado", 14),
        ("Línea", "etiqueta", 58),
        ("Clave", "clave", 46),
        ("Período", "periodo", 10),
        ("Tipo", "tipo", 11),
        ("Dólares", "valor_musd", 20),
        ("Derivación", "derivacion", 34),
        ("Presentación", "fuentes", 44),
        ("Fecha de presentación", "presentado", 18),
    ]
    for i, (titulo, _, ancho) in enumerate(columnas):
        hoja.write(0, i, titulo, fmt["encabezado"])
        hoja.set_column(i, i, ancho)

    ordenado = datos.sort_values(["estado", "periodo", "orden"])
    for numero, (_, registro) in enumerate(ordenado.iterrows(), start=1):
        for i, (_, campo, _) in enumerate(columnas):
            valor = registro[campo]
            if campo == "valor_musd":
                hoja.write_number(numero, i, float(valor) * ESCALA, fmt["dato"])
            else:
                hoja.write(numero, i, "" if pd.isna(valor) else str(valor), fmt["etiqueta"])

    hoja.autofilter(0, 0, len(ordenado), len(columnas) - 1)
    hoja.freeze_panes(1, 0)




# --------------------------------------------------------------------------- #
# Valuación
# --------------------------------------------------------------------------- #
# El split de 2026 cambió el valor nominal de $10 a $1 por acción: por cada
# acción vieja hay diez nuevas. El ADR de NYSE pasó a representar diez acciones
# ordinarias, así que la cantidad de ADR no cambió y su precio tampoco. Todo el
# libro razona en ADR justamente por eso: es la única unidad que no se corta al
# medio de la serie.
ADRS = 393_312_793
ACCIONES_POR_ADR = 10

# Insumos de mercado que no salen de los estados contables. Se dejan como
# supuesto editable en la hoja, con el valor que tenían al generarse el libro.
TASA_LIBRE = 0.0425      # bono del Tesoro de EE.UU. a 10 años
PRIMA_MERCADO = 0.055    # prima histórica de acciones sobre bonos
BETA = 1.10              # beta de YPF contra el S&P 500
TASA_IMPUESTO = 0.35     # alícuota societaria argentina
CRECIMIENTO_EXPLICITO = 0.04
CRECIMIENTO_PERPETUO = 0.02
ANIOS_PROYECCION = 5


def datos_de_mercado(trimestres: list[str]) -> dict:
    """Precio del ADR por trimestre, riesgo país y reservas probadas."""
    from _common import RAW, serie_yahoo

    precios = serie_yahoo(RAW / "market" / "stock" / "YPF.json", "ypf")
    por_trimestre = {}
    for periodo in trimestres:
        anio, trimestre = int(periodo[:4]), int(periodo[-1])
        cierre = pd.Period(f"{anio}Q{trimestre}", freq="Q").end_time
        previos = precios[precios.index <= cierre]
        if len(previos):
            por_trimestre[periodo] = float(previos.iloc[-1])

    riesgo_pais = None
    ruta_embi = RAW / "macro" / "country-risk" / "embi.json"
    if ruta_embi.exists():
        embi = json.loads(ruta_embi.read_text(encoding="utf-8"))
        serie = embi.get("serie") if isinstance(embi, dict) else embi
        if serie:
            ultimo = serie[-1]
            riesgo_pais = float(ultimo.get("valor") or ultimo.get("value") or 0)

    reservas = None
    ruta_reservas = PROCESSED / "reserves.json"
    if ruta_reservas.exists():
        datos_reservas = json.loads(ruta_reservas.read_text(encoding="utf-8"))
        ultimo_anio = datos_reservas.get("ultimo_anio")
        for fila in datos_reservas.get("por_operador", []):
            if fila.get("anio") == ultimo_anio and str(fila.get("operador", "")).upper().startswith("YPF"):
                # La fuente viene en miles de boe; el libro razona en millones.
                reservas = {
                    "anio": ultimo_anio,
                    "comprobadas_mmboe": float(fila["comprobadas_mboe"]) / 1000,
                    "vida": fila.get("vida_reservas"),
                }
                break

    # El valor por boe no se inventa: sale del NPV mediano de un pozo de YPF
    # dividido por su EUR, los dos del modelo de economia de pozo del proyecto.
    # Es valor después de capex, que es lo que corresponde para una reserva que
    # todavía hay que desarrollar.
    valor_boe = None
    ruta_economia = PROCESSED / "well_economics.json"
    if ruta_economia.exists():
        economia = json.loads(ruta_economia.read_text(encoding="utf-8"))
        for fila in economia.get("por_operador", []):
            if str(fila.get("operador", "")).upper().startswith("YPF") and fila.get("eur_bbl_mediana"):
                valor_boe = float(fila["npv_musd_mediano"]) * 1_000_000 / float(fila["eur_bbl_mediana"])
                break

    return {
        "precios": por_trimestre,
        "valor_boe": valor_boe,
        "ultimo_precio": float(precios.iloc[-1]),
        "fecha_precio": precios.index[-1].date().isoformat(),
        "riesgo_pais": riesgo_pais,
        "reservas": reservas,
    }


def escribir_valuacion(libro, fmt, mapas: dict, analisis: dict, mercado: dict,
                       trimestres: list[str], anios: list[str]) -> None:
    """Cuatro maneras de ponerle precio a la misma compañía.

    Ninguna de las cuatro es la respuesta: la respuesta es el rango que arman
    entre las cuatro, y sobre todo qué supuesto hay que creerse para llegar al
    precio al que la acción efectivamente cotiza. Por eso los supuestos están
    arriba, en celdas editables, y todo lo de abajo son fórmulas: el libro sirve
    para discutir el supuesto, no para defender el número.
    """
    hoja = libro.add_worksheet("Valuación")
    hoja.hide_gridlines(2)
    hoja.set_column(0, 0, ANCHO_ETIQUETA)
    hoja.set_column(1, len(trimestres) + len(anios) + 3, ANCHO_DATO)
    hoja.set_tab_color("#f0a830")

    columnas = mapas["columnas"]
    ultimo = trimestres[-1]
    col_ultimo = columnas[ultimo]
    letra_ultimo = xlsxwriter.utility.xl_col_to_name(col_ultimo)

    editable = libro.add_format(
        {"font_name": "Calibri", "font_size": 10, "num_format": '#,##0.00', "bg_color": "#fff6e5",
         "border": 1, "border_color": "#f0a830"}
    )
    editable_pct = libro.add_format(
        {"font_name": "Calibri", "font_size": 10, "num_format": '0.00%', "bg_color": "#fff6e5",
         "border": 1, "border_color": "#f0a830"}
    )
    editable_entero = libro.add_format(
        {"font_name": "Calibri", "font_size": 10, "num_format": '#,##0', "bg_color": "#fff6e5",
         "border": 1, "border_color": "#f0a830"}
    )

    hoja.write(0, 0, "Valuación", fmt["titulo"])
    hoja.write(1, 0, "Múltiplos, flujo de fondos descontado y valor de reservas. Las celdas naranjas son supuestos: cambiarlas recalcula todo lo demás.", fmt["subtitulo"])

    def ref_analisis(clave: str, columna: int | None = None) -> str:
        columna = col_ultimo if columna is None else columna
        return f"'Análisis'!{xlsxwriter.utility.xl_col_to_name(columna)}{analisis[clave] + 1}"

    def ref_balance(clave: str, columna: int | None = None) -> str:
        columna = col_ultimo if columna is None else columna
        fila = mapas["balance"][clave]
        return f"'Balance'!{xlsxwriter.utility.xl_col_to_name(columna)}{fila + 1}"

    def local(fila: int, columna: int = 1) -> str:
        return f"${xlsxwriter.utility.xl_col_to_name(columna)}${fila + 1}"

    def dato(fila: int, etiqueta: str, valor, formato, nota: str = "") -> int:
        hoja.write(fila, 0, etiqueta, fmt["etiqueta_ratio"])
        if isinstance(valor, str):
            hoja.write_formula(fila, 1, valor, formato, "")
        else:
            hoja.write_number(fila, 1, valor, formato)
        if nota:
            hoja.write(fila, 3, nota, fmt["nota"])
        return fila + 1

    # --- supuestos ---------------------------------------------------------
    fila = 3
    hoja.write(fila, 0, "Supuestos", fmt["seccion"])
    fila += 1
    f_adrs = fila
    fila = dato(fila, "ADR en circulación", ADRS, editable_entero,
                f"Cada ADR representa {ACCIONES_POR_ADR} acciones ordinarias desde el split de 2026. Antes del split representaba una.")
    f_precio = fila
    fila = dato(fila, "Precio del ADR (USD)", mercado["ultimo_precio"], editable,
                f"Cierre del {mercado['fecha_precio']} en NYSE.")
    f_libre = fila
    fila = dato(fila, "Tasa libre de riesgo", TASA_LIBRE, editable_pct,
                "Tesoro de EE.UU. a 10 años. No sale del pipeline: es un supuesto que conviene actualizar.")
    f_pais = fila
    riesgo = (mercado["riesgo_pais"] or 700) / 10000
    fila = dato(fila, "Riesgo país", riesgo, editable_pct,
                "EMBI+ Argentina, el último del pipeline, pasado a tasa.")
    f_beta = fila
    fila = dato(fila, "Beta", BETA, editable, "Beta de YPF contra el S&P 500. Supuesto.")
    f_prima = fila
    fila = dato(fila, "Prima de riesgo de mercado", PRIMA_MERCADO, editable_pct, "Supuesto.")
    f_impuesto = fila
    fila = dato(fila, "Tasa de impuesto", TASA_IMPUESTO, editable_pct, "Alícuota societaria argentina.")
    f_crecimiento = fila
    fila = dato(fila, "Crecimiento del flujo, años 1 a 5", CRECIMIENTO_EXPLICITO, editable_pct,
                "Vaca Muerta viene creciendo bastante más que esto; el supuesto es deliberadamente conservador.")
    f_perpetuo = fila
    fila = dato(fila, "Crecimiento perpetuo", CRECIMIENTO_PERPETUO, editable_pct,
                "A perpetuidad no se le puede pedir más que la inflación de largo plazo del dólar.")
    f_valor_boe = fila
    fila = dato(fila, "Valor por boe de reserva probada (USD)", mercado.get("valor_boe") or 6.0, editable,
                "Del modelo de economía de pozo del proyecto: NPV mediano de un pozo de YPF sobre su EUR, "
                "o sea valor después de capex. Comparar contra el EV por boe de arriba, que es lo que paga hoy el mercado.")

    # --- mercado y capital -------------------------------------------------
    fila += 1
    hoja.write(fila, 0, "Mercado y capital", fmt["seccion"])
    fila += 1
    f_cap = fila
    fila = dato(fila, "Capitalización bursátil", f"={local(f_adrs)}*{local(f_precio)}", fmt["dato"])
    f_deuda_neta = fila
    fila = dato(fila, "Deuda financiera neta", f"={ref_analisis('deuda_neta')}", fmt["dato"],
                "De la hoja Análisis, al último trimestre.")
    f_ev = fila
    fila = dato(fila, "Valor de la empresa (EV)", f"={local(f_cap)}+{local(f_deuda_neta)}", fmt["dato"])
    fila = dato(fila, "EV / EBITDA UDM", f"=IFERROR({local(f_ev)}/{ref_analisis('ltm_ebitda')},\"\")", fmt["multiplo"])
    fila = dato(fila, "EV / ingresos UDM", f"=IFERROR({local(f_ev)}/{ref_analisis('ltm_ingresos')},\"\")", fmt["multiplo"])
    fila = dato(fila, "Precio / utilidad UDM", f"=IFERROR({local(f_cap)}/{ref_analisis('ltm_neto')},\"\")", fmt["multiplo"],
                "Con resultado negativo el múltiplo no significa nada; queda a la vista igual.")
    fila = dato(fila, "Precio / valor libro",
                f"=IFERROR({local(f_cap)}/{ref_balance('total shareholders equity')},\"\")", fmt["multiplo"])
    if mercado["reservas"]:
        f_reservas = fila
        fila = dato(fila, f"Reservas probadas ({mercado['reservas']['anio']}, millones de boe)",
                    mercado["reservas"]["comprobadas_mmboe"], editable,
                    "Secretaría de Energía. Son las reservas de los bloques que YPF opera.")
        fila = dato(fila, "EV / boe de reserva probada (USD)",
                    f"=IFERROR({local(f_ev)}/({local(f_reservas)}*1000000),\"\")", fmt["decimal"])
    else:
        f_reservas = None

    # --- múltiplos históricos ---------------------------------------------
    fila += 1
    hoja.write(fila, 0, "Múltiplo histórico por trimestre", fmt["seccion"])
    fila += 1
    encabezado_hist = fila
    hoja.write(fila, 0, "", fmt["encabezado_izq"])
    for periodo in trimestres:
        hoja.write(fila, columnas[periodo], periodo, fmt["encabezado"])
    col_resumen = max(columnas.values()) + 2
    hoja.write(fila, col_resumen, "Promedio", fmt["encabezado"])
    hoja.write(fila, col_resumen + 1, "Mediana", fmt["encabezado"])
    fila += 1

    f_precio_hist = fila
    hoja.write(fila, 0, "Precio del ADR al cierre del trimestre", fmt["etiqueta_ratio"])
    for periodo, precio in mercado["precios"].items():
        hoja.write_number(fila, columnas[periodo], precio, fmt["decimal"])
    fila += 1

    f_cap_hist = fila
    hoja.write(fila, 0, "Capitalización bursátil", fmt["etiqueta_ratio"])
    for periodo in trimestres:
        if periodo not in mercado["precios"]:
            continue
        celda_precio = f"{xlsxwriter.utility.xl_col_to_name(columnas[periodo])}{f_precio_hist + 1}"
        hoja.write_formula(fila, columnas[periodo], f"={celda_precio}*{local(f_adrs)}", fmt["dato"], "")
    fila += 1

    f_ev_hist = fila
    hoja.write(fila, 0, "Valor de la empresa (EV)", fmt["etiqueta_ratio"])
    for periodo in trimestres:
        if periodo not in mercado["precios"]:
            continue
        columna = columnas[periodo]
        celda_cap = f"{xlsxwriter.utility.xl_col_to_name(columna)}{f_cap_hist + 1}"
        hoja.write_formula(
            fila, columna,
            f"=IF(COUNT({ref_analisis('deuda_neta', columna)})=0,\"\",{celda_cap}+{ref_analisis('deuda_neta', columna)})",
            fmt["dato"], "",
        )
    fila += 1

    f_ev_ebitda_hist = fila
    hoja.write(fila, 0, "EV / EBITDA UDM", fmt["etiqueta_ratio"])
    for periodo in trimestres:
        if periodo not in mercado["precios"]:
            continue
        columna = columnas[periodo]
        celda_ev = f"{xlsxwriter.utility.xl_col_to_name(columna)}{f_ev_hist + 1}"
        hoja.write_formula(
            fila, columna, f"=IFERROR({celda_ev}/{ref_analisis('ltm_ebitda', columna)},\"\")", fmt["multiplo"], ""
        )
    primera = xlsxwriter.utility.xl_col_to_name(min(columnas[t] for t in trimestres))
    ultima = xlsxwriter.utility.xl_col_to_name(max(columnas[t] for t in trimestres))
    hoja.write_formula(fila, col_resumen, f"=IFERROR(AVERAGE({primera}{fila + 1}:{ultima}{fila + 1}),\"\")", fmt["multiplo"], "")
    hoja.write_formula(fila, col_resumen + 1, f"=IFERROR(MEDIAN({primera}{fila + 1}:{ultima}{fila + 1}),\"\")", fmt["multiplo"], "")
    f_mediana_multiplo = (fila, col_resumen + 1)
    fila += 1

    f_pb_hist = fila
    hoja.write(fila, 0, "Precio / valor libro", fmt["etiqueta_ratio"])
    for periodo in trimestres:
        if periodo not in mercado["precios"]:
            continue
        columna = columnas[periodo]
        celda_cap = f"{xlsxwriter.utility.xl_col_to_name(columna)}{f_cap_hist + 1}"
        hoja.write_formula(
            fila, columna, f"=IFERROR({celda_cap}/{ref_balance('total shareholders equity', columna)},\"\")",
            fmt["multiplo"], "",
        )
    hoja.write_formula(fila, col_resumen, f"=IFERROR(AVERAGE({primera}{fila + 1}:{ultima}{fila + 1}),\"\")", fmt["multiplo"], "")
    hoja.write_formula(fila, col_resumen + 1, f"=IFERROR(MEDIAN({primera}{fila + 1}:{ultima}{fila + 1}),\"\")", fmt["multiplo"], "")
    fila += 1

    # --- costo del capital -------------------------------------------------
    fila += 1
    hoja.write(fila, 0, "Costo del capital", fmt["seccion"])
    fila += 1
    f_ke = fila
    fila = dato(fila, "Costo del patrimonio (CAPM + riesgo país)",
                f"={local(f_libre)}+{local(f_pais)}+{local(f_beta)}*{local(f_prima)}", fmt["porcentaje"],
                "Se suma el riesgo país entero al costo del patrimonio: es el ajuste más común para un emisor argentino, y también el más discutible.")
    f_kd = fila
    fila = dato(fila, "Costo de la deuda (implícito)",
                f"=IFERROR(-{ref_analisis('ltm_costo_fin')}/{ref_analisis('deuda_bruta')},\"\")", fmt["porcentaje"],
                "Costos financieros de los últimos doce meses sobre deuda bruta. Incluye cargos que no son intereses, así que queda alto.")
    f_kd_neto = fila
    fila = dato(fila, "Costo de la deuda después de impuestos",
                f"={local(f_kd)}*(1-{local(f_impuesto)})", fmt["porcentaje"])
    f_peso_deuda = fila
    fila = dato(fila, "Peso de la deuda",
                f"=IFERROR({ref_analisis('deuda_neta')}/({ref_analisis('deuda_neta')}+{local(f_cap)}),\"\")", fmt["porcentaje"],
                "A valor de mercado del patrimonio, no a valor libro.")
    f_wacc = fila
    fila = dato(fila, "WACC",
                f"={local(f_ke)}*(1-{local(f_peso_deuda)})+{local(f_kd_neto)}*{local(f_peso_deuda)}", fmt["porcentaje"])

    # --- flujo de fondos descontado ---------------------------------------
    fila += 1
    hoja.write(fila, 0, "Método 1 — flujo de fondos descontado (FCFF)", fmt["seccion"])
    fila += 1
    f_fcff_base = fila
    fila = dato(
        fila,
        "Flujo libre para la firma, UDM",
        f"={ref_analisis('ltm_cfo')}+(-{ref_analisis('ltm_costo_fin')})*(1-{local(f_impuesto)})+{ref_analisis('ltm_capex')}",
        fmt["dato"],
        "Operativo, más los intereses después de impuestos que ya se pagaron, menos el capex. El capex viene negativo del estado de flujo.",
    )

    encabezado_dcf = fila
    hoja.write(fila, 0, "", fmt["encabezado_izq"])
    for i in range(ANIOS_PROYECCION):
        hoja.write(fila, 1 + i, f"Año {i + 1}", fmt["encabezado"])
    hoja.write(fila, 1 + ANIOS_PROYECCION, "Terminal", fmt["encabezado"])
    fila += 1

    f_fcff_proy = fila
    hoja.write(fila, 0, "Flujo proyectado", fmt["etiqueta_ratio"])
    for i in range(ANIOS_PROYECCION):
        anterior = local(f_fcff_base) if i == 0 else f"{xlsxwriter.utility.xl_col_to_name(i)}{fila + 1}"
        hoja.write_formula(fila, 1 + i, f"={anterior}*(1+{local(f_crecimiento)})", fmt["dato"], "")
    celda_ultimo_flujo = f"{xlsxwriter.utility.xl_col_to_name(ANIOS_PROYECCION)}{fila + 1}"
    hoja.write_formula(
        fila, 1 + ANIOS_PROYECCION,
        f"=IFERROR({celda_ultimo_flujo}*(1+{local(f_perpetuo)})/({local(f_wacc)}-{local(f_perpetuo)}),\"\")",
        fmt["dato"], "",
    )
    fila += 1

    f_valor_presente = fila
    hoja.write(fila, 0, "Valor presente", fmt["etiqueta_ratio"])
    for i in range(ANIOS_PROYECCION + 1):
        columna = 1 + i
        celda = f"{xlsxwriter.utility.xl_col_to_name(columna)}{f_fcff_proy + 1}"
        exponente = min(i + 1, ANIOS_PROYECCION)
        hoja.write_formula(
            fila, columna, f"=IFERROR({celda}/(1+{local(f_wacc)})^{exponente},\"\")", fmt["dato"], ""
        )
    fila += 1

    f_ev_dcf = fila
    primera_vp = xlsxwriter.utility.xl_col_to_name(1)
    ultima_vp = xlsxwriter.utility.xl_col_to_name(1 + ANIOS_PROYECCION)
    fila = dato(fila, "Valor de la empresa por descuento",
                f"=SUM({primera_vp}{f_valor_presente + 1}:{ultima_vp}{f_valor_presente + 1})", fmt["dato"])
    celda_terminal = f"{xlsxwriter.utility.xl_col_to_name(1 + ANIOS_PROYECCION)}{f_valor_presente + 1}"
    fila = dato(fila, "Peso del valor terminal", f"=IFERROR({celda_terminal}/{local(f_ev_dcf)},\"\")", fmt["porcentaje"],
                "Arriba de dos tercios, el descontado está diciendo más sobre la tasa y el crecimiento perpetuo que sobre los próximos cinco años.")
    f_equity_dcf = fila
    fila = dato(fila, "Valor del patrimonio", f"={local(f_ev_dcf)}-{local(f_deuda_neta)}", fmt["dato"])
    f_adr_dcf = fila
    fila = dato(fila, "Valor por ADR", f"=IFERROR({local(f_equity_dcf)}/{local(f_adrs)},\"\")", fmt["decimal"])

    # --- sensibilidad ------------------------------------------------------
    fila += 1
    hoja.write(fila, 0, "Sensibilidad del valor por ADR (WACC contra crecimiento perpetuo)", fmt["seccion"])
    fila += 1
    encabezado_sens = fila
    hoja.write(fila, 0, "WACC \\ g", fmt["encabezado_izq"])
    pasos_g = [-0.01, -0.005, 0.0, 0.005, 0.01]
    pasos_wacc = [-0.02, -0.01, 0.0, 0.01, 0.02]
    for j, paso in enumerate(pasos_g):
        hoja.write_formula(fila, 1 + j, f"={local(f_perpetuo)}+{paso}", fmt["porcentaje"], "")
    fila += 1
    for paso_w in pasos_wacc:
        hoja.write_formula(fila, 0, f"={local(f_wacc)}+{paso_w}", fmt["porcentaje"], "")
        for j, paso_g in enumerate(pasos_g):
            w = f"({local(f_wacc)}+{paso_w})"
            g = f"({local(f_perpetuo)}+{paso_g})"
            partes = []
            for i in range(ANIOS_PROYECCION):
                celda = f"{xlsxwriter.utility.xl_col_to_name(1 + i)}{f_fcff_proy + 1}"
                partes.append(f"{celda}/(1+{w})^{i + 1}")
            ultimo_flujo = f"{xlsxwriter.utility.xl_col_to_name(ANIOS_PROYECCION)}{f_fcff_proy + 1}"
            terminal = f"{ultimo_flujo}*(1+{g})/({w}-{g})/(1+{w})^{ANIOS_PROYECCION}"
            expresion = "+".join(partes) + "+" + terminal
            hoja.write_formula(
                fila, 1 + j,
                f"=IFERROR((({expresion})-{local(f_deuda_neta)})/{local(f_adrs)},\"\")",
                fmt["decimal"], "",
            )
        fila += 1

    # --- múltiplo y activos ------------------------------------------------
    fila += 1
    hoja.write(fila, 0, "Método 2 — múltiplo histórico", fmt["seccion"])
    fila += 1
    celda_mediana = f"${xlsxwriter.utility.xl_col_to_name(f_mediana_multiplo[1])}${f_mediana_multiplo[0] + 1}"
    f_ev_multiplo = fila
    fila = dato(fila, "EV a la mediana histórica de EV/EBITDA",
                f"=IFERROR({celda_mediana}*{ref_analisis('ltm_ebitda')},\"\")", fmt["dato"],
                "La mediana del propio papel, no la de un panel de comparables: Vista y Pampa cotizan otra combinación de negocios.")
    f_equity_multiplo = fila
    fila = dato(fila, "Valor del patrimonio", f"={local(f_ev_multiplo)}-{local(f_deuda_neta)}", fmt["dato"])
    f_adr_multiplo = fila
    fila = dato(fila, "Valor por ADR", f"=IFERROR({local(f_equity_multiplo)}/{local(f_adrs)},\"\")", fmt["decimal"])

    f_adr_nav = None
    if f_reservas is not None:
        fila += 1
        hoja.write(fila, 0, "Método 3 — valor de los activos (NAV por reservas)", fmt["seccion"])
        fila += 1
        f_activos = fila
        fila = dato(fila, "Valor de las reservas probadas",
                    f"={local(f_reservas)}*1000000*{local(f_valor_boe)}", fmt["dato"],
                    "Reservas probadas por el valor unitario del supuesto. Es un piso por dos motivos: ignora los recursos "
                    "no desarrollados y el negocio de refino y comercialización, que en YPF no es menor.")
        f_equity_nav = fila
        fila = dato(fila, "Valor del patrimonio", f"={local(f_activos)}-{local(f_deuda_neta)}", fmt["dato"])
        f_adr_nav = fila
        fila = dato(fila, "Valor por ADR", f"=IFERROR({local(f_equity_nav)}/{local(f_adrs)},\"\")", fmt["decimal"])

    fila += 1
    hoja.write(fila, 0, "Método 4 — valor libro", fmt["seccion"])
    fila += 1
    f_adr_libro = fila
    fila = dato(fila, "Patrimonio por ADR",
                f"=IFERROR({ref_balance('total shareholders equity')}/{local(f_adrs)},\"\")", fmt["decimal"],
                "El piso contable. Para una petrolera con activos amortizados a costo histórico, suele quedar por debajo del valor económico.")

    # --- resumen -----------------------------------------------------------
    fila += 1
    hoja.write(fila, 0, "Resumen", fmt["seccion"])
    fila += 1
    hoja.write(fila, 0, "", fmt["encabezado_izq"])
    hoja.write(fila, 1, "Valor por ADR", fmt["encabezado"])
    hoja.write(fila, 2, "Contra el precio", fmt["encabezado"])
    fila += 1
    metodos = [("Flujo de fondos descontado", f_adr_dcf), ("Múltiplo histórico", f_adr_multiplo)]
    if f_adr_nav is not None:
        metodos.append(("Valor de reservas", f_adr_nav))
    metodos.append(("Valor libro", f_adr_libro))
    for etiqueta, fila_metodo in metodos:
        hoja.write(fila, 0, etiqueta, fmt["etiqueta_ratio"])
        hoja.write_formula(fila, 1, f"={local(fila_metodo)}", fmt["decimal"], "")
        hoja.write_formula(fila, 2, f"=IFERROR({local(fila_metodo)}/{local(f_precio)}-1,\"\")", fmt["porcentaje"], "")
        fila += 1
    hoja.write(fila, 0, "Precio de mercado", fmt["etiqueta_total"])
    hoja.write_formula(fila, 1, f"={local(f_precio)}", fmt["decimal"], "")
    fila += 2

    hoja.write(
        fila,
        0,
        "Las cuatro no son cuatro respuestas: son cuatro maneras de equivocarse distinto. El descontado "
        "depende del WACC, que en un emisor argentino es casi todo riesgo país; el múltiplo depende de que "
        "el pasado del papel siga siendo una referencia; el de reservas ignora el negocio de refino y "
        "comercialización; el valor libro ignora que los activos están a costo histórico. Lo que hay que "
        "mirar es el rango, y qué supuesto habría que creerse para justificar el precio de la pantalla.",
        fmt["nota"],
    )
    hoja.set_row(fila, 60)
    hoja.freeze_panes(3, 1)




# --------------------------------------------------------------------------- #
# Segmentos
# --------------------------------------------------------------------------- #
# El orden en el que la compañía los presenta, y en el que se leen: primero de
# dónde sale el petróleo, después qué se hace con él, y al final lo que ajusta.
ORDEN_SEGMENTOS = [
    "Upstream",
    "Midstream y Downstream",
    "Downstream",
    "Industrialización",
    "Comercialización",
    "Gas y energía",
    "GNL y gas integrado",
    "Nuevas energías",
    "Administración central y otros",
    "Ajustes de consolidación",
    "Total",
]

BLOQUES_SEGMENTO = [
    ("ingresos_totales", "Ingresos", "dato"),
    ("resultado_operativo", "Resultado operativo", "dato"),
    ("capex_ppe", "Capex en bienes de uso", "dato"),
    ("depreciacion_ppe", "Depreciación de bienes de uso", "dato"),
    ("activos", "Activos", "dato"),
]


def escribir_segmentos(libro, fmt, segmentos: pd.DataFrame, trimestres: list[str],
                       anios: list[str], columnas: dict) -> dict:
    """Los segmentos, que es donde el consolidado deja de promediar.

    Un trimestre récord puede ser shale creciendo, refino recuperando margen o
    el gas cobrando un invierno. Son tres negocios con tres múltiplos distintos
    y el consolidado los suma hasta que no se distingue ninguno.
    """
    hoja = libro.add_worksheet("Segmentos")
    hoja.hide_gridlines(2)
    hoja.set_column(0, 0, ANCHO_ETIQUETA)
    hoja.set_column(1, len(trimestres) + len(anios) + 3, ANCHO_DATO)
    hoja.set_tab_color(AZUL)

    hoja.write(0, 0, "Segmentos", fmt["titulo"])
    hoja.write(
        1, 0,
        "De la nota de segmentos de cada 6-K. La compañía la publica acumulada, así que el trimestre "
        "sale por diferencia; cuando cambió la apertura, el trimestre del cambio queda vacío.",
        fmt["subtitulo"],
    )

    fila_encabezado = 3
    hoja.write(fila_encabezado, 0, "En dólares", fmt["encabezado_izq"])
    for periodo, columna in columnas.items():
        hoja.write(fila_encabezado, columna, periodo if periodo in trimestres else f"FY{periodo[-2:]}", fmt["encabezado"])

    presentes = [s for s in ORDEN_SEGMENTOS if s in set(segmentos["segmento"])]
    filas_por_bloque: dict[tuple[str, str], int] = {}
    fila = fila_encabezado + 1

    for concepto, titulo, formato in BLOQUES_SEGMENTO:
        datos_bloque = segmentos[segmentos["concepto"] == concepto]
        if datos_bloque.empty:
            continue
        matriz_bloque = datos_bloque.pivot_table(
            index="segmento", columns="periodo", values="valor_musd", aggfunc="first"
        )
        hoja.write(fila, 0, titulo, fmt["seccion"])
        fila += 1
        for segmento in presentes:
            if segmento not in matriz_bloque.index:
                continue
            es_total = segmento == "Total"
            hoja.write(fila, 0, segmento, fmt["etiqueta_total"] if es_total else fmt["etiqueta"])
            for periodo, columna in columnas.items():
                if periodo not in matriz_bloque.columns:
                    continue
                valor = matriz_bloque.at[segmento, periodo]
                if pd.isna(valor):
                    continue
                hoja.write_number(
                    fila, columna, float(valor) * ESCALA,
                    fmt["dato_total"] if es_total else fmt[formato],
                )
            filas_por_bloque[(concepto, segmento)] = fila
            fila += 1

        # El control que importa: las partes tienen que dar el todo.
        if "Total" in matriz_bloque.index:
            hoja.write(fila, 0, "Suma de segmentos − total", fmt["nota"])
            for periodo, columna in columnas.items():
                partes = [
                    filas_por_bloque[(concepto, s)]
                    for s in presentes
                    if s != "Total" and (concepto, s) in filas_por_bloque
                ]
                if not partes or (concepto, "Total") not in filas_por_bloque:
                    continue
                letra = xlsxwriter.utility.xl_col_to_name(columna)
                celdas = [f"{letra}{f + 1}" for f in partes]
                suma = "+".join(celdas)
                total = f"{letra}{filas_por_bloque[(concepto, 'Total')] + 1}"
                # Con un solo segmento sin publicar, la resta deja de medir un
                # descuadre y pasa a medir el hueco: ahí no se muestra nada.
                completo = f"COUNT({','.join(celdas)})={len(celdas)}"
                hoja.write_formula(
                    fila, columna,
                    f"=IF(AND(COUNT({total})=1,{completo}),({suma})-{total},\"\")",
                    fmt["dato"], "",
                )
            fila += 1
        fila += 1

    # Márgenes: el número por el que existe la hoja.
    hoja.write(fila, 0, "Margen operativo por segmento", fmt["seccion"])
    fila += 1
    for segmento in presentes:
        if ("resultado_operativo", segmento) not in filas_por_bloque:
            continue
        if ("ingresos_totales", segmento) not in filas_por_bloque:
            continue
        hoja.write(fila, 0, segmento, fmt["etiqueta_ratio"])
        for periodo, columna in columnas.items():
            letra = xlsxwriter.utility.xl_col_to_name(columna)
            arriba = f"{letra}{filas_por_bloque[('resultado_operativo', segmento)] + 1}"
            abajo = f"{letra}{filas_por_bloque[('ingresos_totales', segmento)] + 1}"
            hoja.write_formula(fila, columna, f"=IFERROR({arriba}/{abajo},\"\")", fmt["porcentaje"], "")
        fila += 1

    hoja.freeze_panes(fila_encabezado + 1, 1)
    return filas_por_bloque


# --------------------------------------------------------------------------- #
# Operativo: el puente entre los barriles y los dólares
# --------------------------------------------------------------------------- #
KPI_OPERATIVOS = [
    ("produccion_kboed", "Producción total (kboe/d)", "dias"),
    ("petroleo_kbbld", "Petróleo (kbbl/d)", "dias"),
    ("shale_oil_kbbld", "Petróleo shale (kbbl/d)", "dias"),
    ("gas_mm3d", "Gas (Mm³/d)", "dias"),
    ("crudo_procesado_kbbld", "Crudo procesado (kbbl/d)", "dias"),
    ("precio_crudo_usd_bbl", "Precio de realización del crudo (USD/bbl)", "decimal"),
    ("precio_gas_usd_mbtu", "Precio de realización del gas (USD/MBTU)", "decimal"),
    ("lifting_cost_usd_boe", "Lifting cost (USD/boe)", "decimal"),
]

DIAS_POR_TRIMESTRE = {1: 90.25, 2: 91, 3: 92, 4: 92}


def escribir_operativo(libro, fmt, highlights: pd.DataFrame, mapas: dict, analisis: dict,
                       filas_segmento: dict, trimestres: list[str], anios: list[str]) -> None:
    """Los barriles al lado de los dólares.

    Una petrolera no se compara por margen sino por lo que le saca a cada barril
    y lo que le cuesta ponerlo arriba. Esta hoja divide las dos cosas: arriba lo
    que publica la compañía en su release, abajo lo que sale de dividir los
    estados por la producción del trimestre.
    """
    hoja = libro.add_worksheet("Operativo")
    hoja.hide_gridlines(2)
    hoja.set_column(0, 0, ANCHO_ETIQUETA)
    hoja.set_column(1, len(trimestres) + len(anios) + 3, ANCHO_DATO)
    hoja.set_tab_color("#3fb98a")

    hoja.write(0, 0, "Operativo", fmt["titulo"])
    hoja.write(
        1, 0,
        "Producción y precios del earnings release; las métricas por barril salen de cruzarlos con los estados.",
        fmt["subtitulo"],
    )

    columnas = mapas["columnas"]
    fila_encabezado = 3
    hoja.write(fila_encabezado, 0, "", fmt["encabezado_izq"])
    for periodo, columna in columnas.items():
        hoja.write(fila_encabezado, columna, periodo if periodo in trimestres else f"FY{periodo[-2:]}", fmt["encabezado"])

    indexado = highlights.set_index("trimestre") if not highlights.empty else pd.DataFrame()
    fila = fila_encabezado + 1
    hoja.write(fila, 0, "Lo que publica la compañía", fmt["seccion"])
    fila += 1
    filas_kpi: dict[str, int] = {}
    for campo, etiqueta, formato in KPI_OPERATIVOS:
        if indexado.empty or campo not in indexado.columns:
            continue
        hoja.write(fila, 0, etiqueta, fmt["etiqueta"])
        for periodo, columna in columnas.items():
            if periodo not in indexado.index:
                continue
            valor = indexado.at[periodo, campo]
            if pd.isna(valor):
                continue
            hoja.write_number(fila, columna, float(valor), fmt["decimal"])
        filas_kpi[campo] = fila
        fila += 1

    if "produccion_kboed" not in filas_kpi:
        hoja.freeze_panes(fila_encabezado + 1, 1)
        return

    fila += 1
    hoja.write(fila, 0, "Producción del período", fmt["seccion"])
    fila += 1
    fila_dias = fila
    hoja.write(fila, 0, "Días del período", fmt["etiqueta"])
    for periodo, columna in columnas.items():
        dias = DIAS_POR_TRIMESTRE[int(periodo[-1])] if periodo in trimestres else 365
        hoja.write_number(fila, columna, dias, fmt["dias"])
    fila += 1

    fila_boe = fila
    hoja.write(fila, 0, "Producción del período (Mboe)", fmt["etiqueta"])
    for periodo, columna in columnas.items():
        letra = xlsxwriter.utility.xl_col_to_name(columna)
        produccion = f"{letra}{filas_kpi['produccion_kboed'] + 1}"
        hoja.write_formula(
            fila, columna, f"=IFERROR({produccion}*{letra}{fila_dias + 1}/1000,\"\")", fmt["decimal"], ""
        )
    fila += 1

    def por_boe(etiqueta: str, referencia, formato_celda, nota: str = "") -> int:
        nonlocal fila
        hoja.write(fila, 0, etiqueta, fmt["etiqueta_ratio"])
        for periodo, columna in columnas.items():
            celda = referencia(columna)
            if not celda:
                continue
            letra = xlsxwriter.utility.xl_col_to_name(columna)
            hoja.write_formula(
                fila, columna,
                f"=IFERROR({celda}/({letra}{fila_boe + 1}*1000000),\"\")",
                formato_celda, "",
            )
        if nota:
            hoja.write(fila, max(columnas.values()) + 2, nota, fmt["nota"])
        fila += 1
        return fila - 1

    hoja.write(fila, 0, "Por barril equivalente", fmt["seccion"])
    fila += 1

    def ref_analisis(clave: str):
        return lambda columna: f"'Análisis'!{xlsxwriter.utility.xl_col_to_name(columna)}{analisis[clave] + 1}"

    def ref_segmento(concepto: str, segmento: str):
        fila_segmento = filas_segmento.get((concepto, segmento))
        if fila_segmento is None:
            return lambda columna: None
        return lambda columna: f"'Segmentos'!{xlsxwriter.utility.xl_col_to_name(columna)}{fila_segmento + 1}"

    por_boe("EBITDA por boe", ref_analisis("ebitda"), fmt["decimal"],
            "EBITDA consolidado sobre producción: incluye el aporte de refino, que no produce barriles.")
    por_boe("Ingresos de Upstream por boe", ref_segmento("ingresos_totales", "Upstream"), fmt["decimal"],
            "Incluye las ventas intersegmento, que es como el crudo llega a la refinería propia.")
    por_boe("Resultado operativo de Upstream por boe", ref_segmento("resultado_operativo", "Upstream"), fmt["decimal"])
    por_boe("Capex de Upstream por boe", ref_segmento("capex_ppe", "Upstream"), fmt["decimal"])
    por_boe("Depreciación de Upstream por boe", ref_segmento("depreciacion_ppe", "Upstream"), fmt["decimal"],
            "Es el costo de agotamiento del yacimiento: contra el resultado operativo por boe dice cuánto del margen es caja.")
    fila_cfo = mapas["flujo"].get("net cash flows from operating activities")
    if fila_cfo is not None:
        por_boe(
            "Flujo operativo por boe",
            lambda columna: f"'{HOJAS['flujo']}'!{xlsxwriter.utility.xl_col_to_name(columna)}{fila_cfo + 1}",
            fmt["decimal"],
            "Consolidado: el flujo de refino y comercialización también está adentro.",
        )

    hoja.freeze_panes(fila_encabezado + 1, 1)




# --------------------------------------------------------------------------- #
# Comparables
# --------------------------------------------------------------------------- #
PEERS = PROCESSED / "peers.parquet"
PEERS_META = PROCESSED / "peers.json"


def datos_de_comparables() -> dict:
    """Los comparables y sus precios, listos para la hoja."""
    from _common import RAW, serie_yahoo

    if not PEERS.exists() or not PEERS_META.exists():
        return {}

    tabla = pd.read_parquet(PEERS)
    meta = json.loads(PEERS_META.read_text(encoding="utf-8"))
    fichas = {ficha["ticker"]: ficha for ficha in meta.get("emisores", [])}

    precios = {}
    for ticker in fichas:
        ruta = RAW / "market" / "stock" / f"{ticker}.json"
        if ruta.exists():
            serie = serie_yahoo(ruta, ticker)
            precios[ticker] = {"precio": float(serie.iloc[-1]), "fecha": serie.index[-1].date().isoformat()}

    valores = {
        (fila.ticker, fila.concepto, int(fila.anio)): float(fila.valor_usd)
        for fila in tabla.itertuples()
    }
    anios = sorted({int(a) for _, _, a in valores})
    return {"valores": valores, "fichas": fichas, "precios": precios, "anios": anios, "meta": meta}


def escribir_comparables(libro, fmt, mapas: dict, analisis: dict, mercado: dict, comparables: dict,
                         trimestres: list[str], anios: list[str]) -> None:
    """YPF al lado de los dos que se le parecen.

    Vista es shale puro: sirve para aislar cuánto del múltiplo de YPF es Vaca
    Muerta y cuánto es todo lo demás. Pampa mezcla upstream con generación
    eléctrica, que es el otro extremo del mismo país. Los tres presentan ante la
    SEC, así que las líneas son comparables de verdad y no una traducción de
    tres criterios contables distintos.

    Los dos comparables van al último ejercicio con XBRL publicado; YPF va con
    esos mismos ejercicios y además con los últimos doce meses, que es lo que
    cotiza hoy. La diferencia de fechas está a la vista en el encabezado: es
    preferible a emparejar por la fuerza dos cosas que no son iguales.
    """
    if not comparables:
        return

    hoja = libro.add_worksheet("Comparables")
    hoja.hide_gridlines(2)
    hoja.set_column(0, 0, ANCHO_ETIQUETA)
    hoja.set_column(1, 12, ANCHO_DATO)
    hoja.set_tab_color("#f0a830")

    hoja.write(0, 0, "Comparables", fmt["titulo"])
    hoja.write(
        1, 0,
        "YPF contra Vista Energy y Pampa Energía, las dos únicas argentinas con disclosure equiparable ante la SEC.",
        fmt["subtitulo"],
    )

    valores = comparables["valores"]
    fichas = comparables["fichas"]
    precios = comparables["precios"]
    anios_peer = [a for a in comparables["anios"] if a >= 2023]
    ultimo_trimestre = trimestres[-1]

    # Las columnas: YPF con sus ejercicios y sus últimos doce meses, y cada
    # comparable con los ejercicios que tenga publicados.
    columnas: list[dict] = []
    for anio in [a for a in anios if int(a) >= 2023]:
        columnas.append({"clase": "ypf_fy", "anio": anio, "titulo": f"YPF FY{anio[-2:]}"})
    columnas.append({"clase": "ypf_udm", "titulo": f"YPF UDM {ultimo_trimestre}"})
    for ticker in sorted(fichas):
        for anio in anios_peer:
            if (ticker, "ingresos", anio) in valores:
                columnas.append({"clase": "peer", "ticker": ticker, "anio": anio, "titulo": f"{ticker} FY{str(anio)[-2:]}"})

    fila_encabezado = 3
    hoja.write(fila_encabezado, 0, "En dólares", fmt["encabezado_izq"])
    for i, columna in enumerate(columnas):
        columna["col"] = i + 1
        hoja.write(fila_encabezado, columna["col"], columna["titulo"], fmt["encabezado"])

    def celda_ypf(estado: str, clave: str, anio: str) -> str | None:
        fila_clave = mapas[estado].get(clave)
        if fila_clave is None or anio not in mapas["columnas"]:
            return None
        letra = xlsxwriter.utility.xl_col_to_name(mapas["columnas"][anio])
        return f"'{HOJAS[estado]}'!{letra}{fila_clave + 1}"

    def celda_analisis(clave: str) -> str:
        letra = xlsxwriter.utility.xl_col_to_name(mapas["columnas"][ultimo_trimestre])
        return f"'Análisis'!{letra}{analisis[clave] + 1}"

    filas_metrica: dict[str, int] = {}

    def escribir_metrica(nombre: str, etiqueta: str, ypf_fy, ypf_udm, concepto_peer,
                         formato=None, nota: str = "") -> None:
        nonlocal fila
        formato = formato or fmt["dato"]
        hoja.write(fila, 0, etiqueta, fmt["etiqueta"])
        for columna in columnas:
            destino = columna["col"]
            if columna["clase"] == "ypf_fy" and ypf_fy:
                formula = ypf_fy(columna["anio"])
                if formula:
                    hoja.write_formula(fila, destino, formula, formato, "")
            elif columna["clase"] == "ypf_udm" and ypf_udm:
                formula = ypf_udm()
                if formula:
                    hoja.write_formula(fila, destino, formula, formato, "")
            elif columna["clase"] == "peer" and concepto_peer:
                valor = concepto_peer(columna["ticker"], columna["anio"])
                if valor is not None:
                    hoja.write_number(fila, destino, valor, formato)
        if nota:
            hoja.write(fila, len(columnas) + 2, nota, fmt["nota"])
        filas_metrica[nombre] = fila
        fila += 1

    def peer(concepto: str, signo: float = 1.0):
        def leer(ticker: str, anio: int) -> float | None:
            valor = valores.get((ticker, concepto, anio))
            return None if valor is None else valor * signo
        return leer

    def peer_suma(*conceptos: str):
        def leer(ticker: str, anio: int) -> float | None:
            partes = [valores.get((ticker, c, anio)) for c in conceptos]
            if any(p is None for p in partes):
                return None
            return float(sum(partes))
        return leer

    fila = fila_encabezado + 1
    hoja.write(fila, 0, "Resultados y caja", fmt["seccion"])
    fila += 1

    escribir_metrica(
        "ingresos", "Ingresos",
        lambda anio: (c := celda_ypf("resultados", "revenues", anio)) and f"={c}",
        lambda: f"={celda_analisis('ltm_ingresos')}",
        peer("ingresos"),
    )
    escribir_metrica(
        "ebitda", "EBITDA",
        lambda anio: (
            f"={celda_ypf('resultados', 'operating profit', anio)}"
            f"+{celda_ypf('flujo', 'depreciation of property plant and equipment | net cash flows from operating activities', anio)}"
            f"+{celda_ypf('flujo', 'amortization of intangible assets | net cash flows from operating activities', anio)}"
            f"+{celda_ypf('flujo', 'depreciation of right of use assets | net cash flows from operating activities', anio)}"
        ) if celda_ypf("resultados", "operating profit", anio) else None,
        lambda: f"={celda_analisis('ltm_ebitda')}",
        peer_suma("resultado_operativo", "depreciacion_y_amortizacion"),
        nota="Resultado operativo más depreciaciones y amortizaciones, para los tres igual.",
    )
    escribir_metrica(
        "operativo", "Resultado operativo",
        lambda anio: (c := celda_ypf("resultados", "operating profit", anio)) and f"={c}",
        lambda: f"={celda_analisis('ltm_ebit')}",
        peer("resultado_operativo"),
    )
    escribir_metrica(
        "neto", "Resultado neto",
        lambda anio: (c := celda_ypf("resultados", "net profit", anio)) and f"={c}",
        lambda: f"={celda_analisis('ltm_neto')}",
        peer("resultado_neto"),
    )
    escribir_metrica(
        "cfo", "Flujo operativo",
        lambda anio: (c := celda_ypf("flujo", "net cash flows from operating activities", anio)) and f"={c}",
        lambda: f"={celda_analisis('ltm_cfo')}",
        peer("flujo_operativo"),
    )
    escribir_metrica(
        "capex", "Capex",
        lambda anio: (c := celda_ypf(
            "flujo",
            "acquisition of property plant and equipment and intangible assets | net cash flows used in investing activities",
            anio,
        )) and f"=-{c}",
        lambda: f"=-{celda_analisis('ltm_capex')}",
        peer("capex"),
        nota="En positivo para los tres: en el estado de flujo de YPF viene con signo negativo.",
    )

    fila += 1
    hoja.write(fila, 0, "Balance", fmt["seccion"])
    fila += 1
    escribir_metrica(
        "activos", "Activos",
        lambda anio: (c := celda_ypf("balance", "total assets", anio)) and f"={c}",
        lambda: (c := celda_ypf("balance", "total assets", ultimo_trimestre)) and f"={c}",
        peer("activos"),
    )
    escribir_metrica(
        "patrimonio", "Patrimonio neto",
        lambda anio: (c := celda_ypf("balance", "total shareholders equity", anio)) and f"={c}",
        lambda: (c := celda_ypf("balance", "total shareholders equity", ultimo_trimestre)) and f"={c}",
        peer("patrimonio"),
    )
    escribir_metrica(
        "deuda", "Deuda financiera bruta",
        lambda anio: (
            f"={celda_ypf('balance', 'loans | total non current liabilities', anio)}"
            f"+{celda_ypf('balance', 'loans | total current liabilities', anio)}"
        ) if celda_ypf("balance", "loans | total non current liabilities", anio) else None,
        lambda: (
            f"={celda_ypf('balance', 'loans | total non current liabilities', ultimo_trimestre)}"
            f"+{celda_ypf('balance', 'loans | total current liabilities', ultimo_trimestre)}"
        ),
        peer("deuda_financiera"),
    )
    escribir_metrica(
        "caja", "Caja",
        lambda anio: (c := celda_ypf("balance", "cash and cash equivalents | total current assets", anio)) and f"={c}",
        lambda: (c := celda_ypf("balance", "cash and cash equivalents | total current assets", ultimo_trimestre)) and f"={c}",
        peer("caja"),
    )

    def local(fila_metrica: str, columna: int) -> str:
        return f"{xlsxwriter.utility.xl_col_to_name(columna)}{filas_metrica[fila_metrica] + 1}"

    fila_deuda_neta = fila
    hoja.write(fila, 0, "Deuda financiera neta", fmt["etiqueta"])
    for columna in columnas:
        destino = columna["col"]
        hoja.write_formula(
            fila, destino,
            f"=IFERROR({local('deuda', destino)}-{local('caja', destino)},\"\")",
            fmt["dato"], "",
        )
    filas_metrica["deuda_neta"] = fila
    fila += 1

    fila += 1
    hoja.write(fila, 0, "Mercado", fmt["seccion"])
    fila += 1
    hoja.write(fila, len(columnas) + 2,
               "El precio es el último de cada papel, aunque el balance sea de distinta fecha: "
               "es el precio al que cotizan hoy esos números.", fmt["nota"])

    hoja.write(fila, 0, "Precio del ADR (USD)", fmt["etiqueta"])
    for columna in columnas:
        if columna["clase"] == "peer":
            precio = precios.get(columna["ticker"], {}).get("precio")
        else:
            precio = mercado["ultimo_precio"]
        if precio is not None:
            hoja.write_number(fila, columna["col"], precio, fmt["decimal"])
    filas_metrica["precio"] = fila
    fila += 1

    hoja.write(fila, 0, "ADR equivalentes", fmt["etiqueta"])
    for columna in columnas:
        if columna["clase"] == "peer":
            ficha = fichas[columna["ticker"]]
            acciones = ficha.get("acciones")
            por_ads = ficha.get("acciones_por_ads") or 1
            cantidad = acciones / por_ads if acciones else None
        else:
            cantidad = ADRS
        if cantidad:
            hoja.write_number(fila, columna["col"], cantidad, fmt["dato"])
    filas_metrica["adrs"] = fila
    hoja.write(fila, len(columnas) + 2,
               "Acciones en circulación dividido las que representa cada ADR, de la portada del 20-F: "
               "en Pampa son 25 por ADR y en Vista una.", fmt["nota"])
    fila += 1

    for nombre, etiqueta, formula in [
        ("capitalizacion", "Capitalización bursátil", lambda c: f"={local('precio', c)}*{local('adrs', c)}"),
        ("ev", "Valor de la empresa (EV)", lambda c: f"=IFERROR({local('capitalizacion', c)}+{local('deuda_neta', c)},\"\")"),
    ]:
        hoja.write(fila, 0, etiqueta, fmt["etiqueta"])
        for columna in columnas:
            hoja.write_formula(fila, columna["col"], formula(columna["col"]), fmt["dato"], "")
        filas_metrica[nombre] = fila
        fila += 1

    fila += 1
    hoja.write(fila, 0, "Márgenes y retornos", fmt["seccion"])
    fila += 1
    for etiqueta, arriba, abajo, formato in [
        ("Margen EBITDA", "ebitda", "ingresos", "porcentaje"),
        ("Margen operativo", "operativo", "ingresos", "porcentaje"),
        ("Margen neto", "neto", "ingresos", "porcentaje"),
        ("Flujo operativo / ingresos", "cfo", "ingresos", "porcentaje"),
        ("Capex / EBITDA", "capex", "ebitda", "porcentaje"),
        ("Resultado neto / patrimonio", "neto", "patrimonio", "porcentaje"),
    ]:
        hoja.write(fila, 0, etiqueta, fmt["etiqueta_ratio"])
        for columna in columnas:
            destino = columna["col"]
            hoja.write_formula(
                fila, destino,
                f"=IFERROR({local(arriba, destino)}/{local(abajo, destino)},\"\")",
                fmt[formato], "",
            )
        fila += 1

    fila += 1
    hoja.write(fila, 0, "Múltiplos", fmt["seccion"])
    fila += 1
    for etiqueta, arriba, abajo, formato in [
        ("EV / EBITDA", "ev", "ebitda", "multiplo"),
        ("EV / ingresos", "ev", "ingresos", "multiplo"),
        ("Precio / utilidad", "capitalizacion", "neto", "multiplo"),
        ("Precio / valor libro", "capitalizacion", "patrimonio", "multiplo"),
        ("Deuda neta / EBITDA", "deuda_neta", "ebitda", "multiplo"),
    ]:
        hoja.write(fila, 0, etiqueta, fmt["etiqueta_ratio"])
        for columna in columnas:
            destino = columna["col"]
            hoja.write_formula(
                fila, destino,
                f"=IFERROR({local(arriba, destino)}/{local(abajo, destino)},\"\")",
                fmt[formato], "",
            )
        fila += 1

    fila += 2
    fechas = ", ".join(
        f"{ticker}: 20-F de {fichas[ticker].get('ultimo_20f', '?')}" for ticker in sorted(fichas)
    )
    hoja.write(
        fila, 0,
        "Los comparables salen del XBRL de sus 20-F, que la SEC publica estructurado y en dólares "
        f"({fechas}). El último ejercicio con XBRL disponible es 2024: el 20-F siguiente ya está "
        "presentado pero sus estados todavía no aparecen en la API de datos estructurados. YPF, en "
        "cambio, está al último trimestre, porque sus estados los arma este pipeline desde el filing.",
        fmt["nota"],
    )
    hoja.set_row(fila, 42)
    hoja.freeze_panes(fila_encabezado + 1, 1)


# --------------------------------------------------------------------------- #
def main() -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.parse_args()

    datos, meta, highlights, segmentos = cargar()
    trimestres = sorted(p for p in datos.loc[datos["tipo"] == "trimestre", "periodo"].unique() if p >= DESDE)
    # Los ejercicios anteriores a 2019 existen en la hoja Datos —salen de los
    # comparativos de presentaciones viejas— pero no entran a las hojas de
    # estados: no hay trimestres que los acompañen y ensanchan la planilla sin
    # agregar lectura.
    anios = sorted(a for a in datos.loc[datos["tipo"] == "anual", "periodo"].unique() if a >= "2019")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    # Se escribe primero a un temporal y después se reemplaza. Si el libro está
    # abierto en Excel, Windows no deja pisarlo: sin esto, la corrida termina
    # con un "Permission denied" a mitad de camino y deja el archivo roto.
    provisorio = SALIDA.with_suffix(".tmp.xlsx")
    libro = xlsxwriter.Workbook(str(provisorio), {"constant_memory": False})
    libro.set_properties(
        {
            "title": "YPF — estados contables trimestrales",
            "subject": "Estados contables consolidados en dólares, armados desde SEC EDGAR",
            "author": "ATLAS-YPF",
            "company": "ATLAS-YPF",
            "comments": "Generado por pipeline/export/excel_estados.py",
        }
    )
    fmt = formatos(libro)

    escribir_portada(libro, fmt, meta, datos, trimestres, anios)

    mapas: dict = {}
    for estado, titulo, subtitulo in [
        ("resultados", "Estado de resultados integrales", "Consolidado, en dólares (la compañía reporta redondeado al millón)"),
        ("balance", "Estado de situación patrimonial", "Consolidado, en dólares (la compañía reporta redondeado al millón)"),
        ("flujo", "Estado de flujo de efectivo", "Consolidado, en dólares (la compañía reporta redondeado al millón)"),
    ]:
        _, filas, columnas = escribir_estado(libro, fmt, datos, estado, trimestres, anios, titulo, subtitulo)
        mapas[estado] = filas
        mapas["columnas"] = columnas

    filas_analisis = escribir_analisis(libro, fmt, mapas, trimestres, anios)
    filas_segmento: dict = {}
    if not segmentos.empty:
        filas_segmento = escribir_segmentos(
            libro, fmt, segmentos, trimestres, anios, mapas["columnas"]
        )
    escribir_operativo(libro, fmt, highlights, mapas, filas_analisis, filas_segmento, trimestres, anios)
    mercado = datos_de_mercado(trimestres)
    escribir_valuacion(libro, fmt, mapas, filas_analisis, mercado, trimestres, anios)
    escribir_comparables(
        libro, fmt, mapas, filas_analisis, mercado, datos_de_comparables(), trimestres, anios
    )
    escribir_chequeos(libro, fmt, mapas, datos, highlights, trimestres, anios)
    escribir_datos(libro, fmt, datos)

    libro.close()
    try:
        provisorio.replace(SALIDA)
        destino = SALIDA
    except PermissionError:
        destino = SALIDA.with_name(f"{SALIDA.stem} (nuevo){SALIDA.suffix}")
        provisorio.replace(destino)
        log(
            f"{rel(SALIDA)} está abierto en Excel y no se pudo reemplazar; "
            f"el libro nuevo quedó en {rel(destino)}"
        )
    tamanio = destino.stat().st_size
    log(f"{rel(destino)} ({human(tamanio)}) · {len(trimestres)} trimestres · {len(anios)} ejercicios")
    record(
        "export/excel",
        rows=int(len(datos)),
        bytes=int(tamanio),
        outputs=[rel(destino)],
        source=rel(ENTRADA),
        note=f"{trimestres[0]}–{trimestres[-1]} trimestral y FY{anios[0]}–FY{anios[-1]}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
