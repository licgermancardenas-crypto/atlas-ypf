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
SALIDA = ROOT / "docs" / "YPF_estados_financieros.xlsx"

# La serie trimestral completa arranca cuando arrancan los estados en dólares.
# Antes hay balances de cierre de ejercicio, que van al bloque anual.
DESDE = "2023Q1"

HOJAS = {
    "resultados": "Resultados",
    "balance": "Balance",
    "flujo": "Flujo de efectivo",
}

# Ancho de la primera columna: las líneas del flujo de efectivo son largas.
ANCHO_ETIQUETA = 62
ANCHO_DATO = 11

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
def cargar() -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    datos = pd.read_parquet(ENTRADA)
    meta = json.loads(META.read_text(encoding="utf-8"))
    highlights = pd.read_parquet(HIGHLIGHTS) if HIGHLIGHTS.exists() else pd.DataFrame()
    return datos, meta, highlights


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
    return valores.reindex(columns=periodos), derivaciones.reindex(columns=periodos)


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
    hoja.write(fila_encabezado, 0, "En millones de dólares", fmt["encabezado_izq"])
    for i, periodo in enumerate(trimestres):
        columnas[periodo] = i + 1
        hoja.write(fila_encabezado, i + 1, periodo, fmt["encabezado"])
    inicio_anual = len(trimestres) + 2
    hoja.write(fila_encabezado, inicio_anual - 1, "", fmt["encabezado"])
    for i, anio in enumerate(anios):
        columnas[anio] = inicio_anual + i
        hoja.write(fila_encabezado, inicio_anual + i, f"FY{anio[-2:]}", fmt["encabezado"])

    valores, derivaciones = matriz(datos, estado, trimestres + anios)
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
            if es_total:
                formato = fmt["dato_total"]
            elif isinstance(derivacion, str) and derivacion != "reportado":
                formato = fmt["dato_derivado"]
            else:
                formato = fmt["dato"]
            hoja.write_number(fila, columna, float(valor), formato)
        filas[clave] = fila
        fila += 1

    hoja.write(
        fila + 1,
        0,
        "En bastardilla, los trimestres que la compañía no publica sueltos y salen por diferencia "
        "de acumulados (ver Portada).",
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
        "Antes de 2023 no hay serie comparable",
        "Hasta el ejercicio 2023 los estados interinos se presentaban en pesos reexpresados por "
        "IAS 29. Encadenar pesos ajustados por inflación con dólares no da una serie: da un "
        "gráfico. Los ejercicios 2020 a 2022 sí están, en dólares y anuales, porque el 20-F los "
        "presenta así.",
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
    hoja.write(2, 1, "Estados contables trimestrales — en millones de dólares", fmt["subtitulo"])

    fila = 4
    ficha = [
        ("Emisor", "YPF S.A. (NYSE: YPF), CIK 0000904851"),
        ("Fuente", "SEC EDGAR: estados contables adjuntos a los 6-K y a los 20-F"),
        ("Moneda y unidad", "Dólares estadounidenses, en millones. Resultado por acción, en dólares."),
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
        ("Análisis", "Márgenes, retornos, estructura de capital, liquidez, capital de trabajo y caja. Todo con fórmulas."),
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
def escribir_analisis(libro, fmt, mapas: dict, trimestres: list[str], anios: list[str]) -> None:
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

    fila_deuda_neta = fila + 1
    fila = escribir_formula(
        fila,
        "Deuda financiera bruta",
        con_dato(lambda c: deuda(c), lambda c: deuda(c)),
        fmt["dato"],
        "Préstamos corrientes y no corrientes. No incluye pasivos por arrendamiento.",
    )
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

    fila = fila_chequeo(fila, "Ingresos: suma de trimestres − ejercicio", suma_trimestres("resultados", "revenues"))
    fila = fila_chequeo(fila, "Resultado neto: suma de trimestres − ejercicio", suma_trimestres("resultados", "net profit"))
    fila = fila_chequeo(fila, "Flujo operativo: suma de trimestres − ejercicio",
                        suma_trimestres("flujo", "net cash flows from operating activities"))

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
                hoja.write_number(fila, columna, float(valor), fmt["dato"])
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
        ("Millones de USD", "valor_musd", 15),
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
                hoja.write_number(numero, i, float(valor), fmt["dato"])
            else:
                hoja.write(numero, i, "" if pd.isna(valor) else str(valor), fmt["etiqueta"])

    hoja.autofilter(0, 0, len(ordenado), len(columnas) - 1)
    hoja.freeze_panes(1, 0)


# --------------------------------------------------------------------------- #
def main() -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.parse_args()

    datos, meta, highlights = cargar()
    trimestres = sorted(p for p in datos.loc[datos["tipo"] == "trimestre", "periodo"].unique() if p >= DESDE)
    anios = sorted(datos.loc[datos["tipo"] == "anual", "periodo"].unique())

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    libro = xlsxwriter.Workbook(str(SALIDA), {"constant_memory": False})
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
        ("resultados", "Estado de resultados integrales", "Consolidado, en millones de dólares"),
        ("balance", "Estado de situación patrimonial", "Consolidado, en millones de dólares"),
        ("flujo", "Estado de flujo de efectivo", "Consolidado, en millones de dólares"),
    ]:
        _, filas, columnas = escribir_estado(libro, fmt, datos, estado, trimestres, anios, titulo, subtitulo)
        mapas[estado] = filas
        mapas["columnas"] = columnas

    escribir_analisis(libro, fmt, mapas, trimestres, anios)
    escribir_chequeos(libro, fmt, mapas, datos, highlights, trimestres, anios)
    escribir_datos(libro, fmt, datos)

    libro.close()
    tamanio = SALIDA.stat().st_size
    log(f"{rel(SALIDA)} ({human(tamanio)}) · {len(trimestres)} trimestres · {len(anios)} ejercicios")
    record(
        "export/excel",
        rows=int(len(datos)),
        bytes=int(tamanio),
        outputs=[rel(SALIDA)],
        source=rel(ENTRADA),
        note=f"{trimestres[0]}–{trimestres[-1]} trimestral y FY{anios[0]}–FY{anios[-1]}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
