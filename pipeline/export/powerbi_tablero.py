"""El tablero del Excel, como proyecto de Power BI (PBIP).

Por qué un generador y no un .pbix: el proyecto de Power BI en formato PBIP es
texto —el modelo en TMDL, el reporte en JSON por visual—, así que se puede
versionar, revisar en un diff y regenerar igual que el Excel. Este script lo
escribe entero en powerbi/; Power BI Desktop lo abre con doble clic en el .pbip.

Lo mismo que rige para el Excel rige acá: el modelo lee solo data/processed/ y
no calcula nada que no esté en un transform. Las medidas DAX son las mismas
cuentas de presentación que las fórmulas del tablero de Excel: elegir un
trimestre, desplazarlo, dividir, sumar lo que va del año.

Cómo está armado el modelo, porque condiciona todas las medidas:

  - no hay relaciones. Cada tabla de hechos trae la columna Orden (1 = primer
    trimestre de la serie) y las medidas filtran por Orden a mano;
  - Trimestres alimenta la lista del trimestre elegido; Eje es una copia
    desconectada que hace de eje de los gráficos, así el gráfico muestra doce
    trimestres aunque el filtro tenga elegido uno;
  - Desfase es una tabla de 0 a 15: una medida evaluada con Desfase[N] = 4
    devuelve su valor de cuatro trimestres antes. Así se arman la comparación
    y el acumulado del año sin repetir cada medida.

Salida: powerbi/YPF_Atlas.pbip y sus carpetas .SemanticModel y .Report.
"""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "transform"))
from _common import PROCESSED, ROOT, base_parser, log, rel  # noqa: E402

NOMBRE = "YPF_Atlas"
SALIDA = ROOT / "powerbi"
MODELO = SALIDA / f"{NOMBRE}.SemanticModel"
REPORTE = SALIDA / f"{NOMBRE}.Report"
TEMA_BASE = Path(__file__).resolve().parent / "powerbi_recursos" / "CY24SU10.json"

# Versiones de esquema: las de un reporte guardado por Desktop, que la versión
# instalada abre sin migrar.
ESQUEMA = "https://developer.microsoft.com/json-schemas/fabric"
V_VISUAL = f"{ESQUEMA}/item/report/definition/visualContainer/2.0.0/schema.json"
V_PAGINA = f"{ESQUEMA}/item/report/definition/page/1.4.0/schema.json"
V_REPORTE = f"{ESQUEMA}/item/report/definition/report/1.3.0/schema.json"

# Paleta: la misma del tablero de Excel.
PAGINA = "#050b16"
TARJETA = "#0f213b"
BORDE = "#27466f"
TEXTO = "#eaf2ff"
TEXTO_SUAVE = "#8ea3c4"
CIAN = "#22d3ee"
AZUL = "#3b82f6"
INDIGO = "#818cf8"
AMBAR = "#fbbf24"
APAGADO = "#27405f"

MEDIDAS = "Medidas"


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def escribir(ruta: Path, contenido) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(contenido, (dict, list)):
        contenido = json.dumps(contenido, ensure_ascii=False, indent=2)
    ruta.write_text(contenido, encoding="utf-8")


def guid(semilla: str) -> str:
    """Identificadores estables: regenerar no cambia el diff."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ypf-atlas/{semilla}"))


def nombre_visual(semilla: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"ypf-atlas/visual/{semilla}").hex[:20]


def tmdl_nombre(nombre: str) -> str:
    return f"'{nombre}'" if any(c in nombre for c in " .=:'/()[]-&#%") else nombre


def sangrar(texto: str, tabs: int) -> str:
    return "\n".join("\t" * tabs + linea if linea.strip() else "" for linea in texto.strip("\n").splitlines())


# --------------------------------------------------------------------------- #
# Modelo
# --------------------------------------------------------------------------- #
def m_parquet(archivo: str, pasos: str) -> str:
    return f"""let
    Fuente = Parquet.Document(File.Contents(RutaDatos & "{archivo}")),
{pasos}"""


def m_con_orden(paso_previo: str, columna_periodo: str) -> str:
    return f"""    ConOrden = Table.NestedJoin({paso_previo}, {{"{columna_periodo}"}}, Trimestres, {{"Codigo"}}, "T", JoinKind.Inner),
    Expandido = Table.ExpandTableColumn(ConOrden, "T", {{"Orden"}})"""


TABLAS: list[dict] = [
    {
        "nombre": "Trimestres",
        "columnas": [("Codigo", "string"), ("Etiqueta", "string", "Orden"), ("Orden", "int64"),
                     ("Anio", "int64"), ("NTrim", "int64")],
        "m": m_parquet("statements_ypf.parquet", """    Trimestral = Table.SelectRows(Fuente, each [tipo] = "trimestre" and [periodo] >= "2019Q1"),
    Periodos = Table.Distinct(Table.SelectColumns(Trimestral, {"periodo", "anio", "trimestre"})),
    Ordenados = Table.Sort(Periodos, {{"periodo", Order.Ascending}}),
    ConIndice = Table.AddIndexColumn(Ordenados, "Orden", 1, 1, Int64.Type),
    ConEtiqueta = Table.AddColumn(ConIndice, "Etiqueta", each Text.From([trimestre]) & "T" & Text.End(Text.From([anio]), 2), type text),
    Renombrado = Table.RenameColumns(ConEtiqueta, {{"periodo", "Codigo"}, {"anio", "Anio"}, {"trimestre", "NTrim"}}),
    Tipos = Table.TransformColumnTypes(Renombrado, {{"Codigo", type text}, {"Anio", Int64.Type}, {"NTrim", Int64.Type}})
in
    Tipos"""),
    },
    {
        "nombre": "Eje",
        "columnas": [("Codigo", "string"), ("Etiqueta", "string", "Orden"), ("Orden", "int64"),
                     ("Anio", "int64"), ("NTrim", "int64")],
        "m": "let\n    Fuente = Trimestres\nin\n    Fuente",
    },
    {
        "nombre": "Estados",
        "oculta": True,
        "columnas": [("Estado", "string"), ("Clave", "string"), ("ValorMUSD", "double"), ("Orden", "int64")],
        "m": m_parquet("statements_ypf.parquet", f"""    Filas = Table.SelectRows(Fuente, each [tipo] = "trimestre"),
    Columnas = Table.SelectColumns(Filas, {{"estado", "clave", "periodo", "valor_musd"}}),
{m_con_orden("Columnas", "periodo")},
    Renombrado = Table.RenameColumns(Expandido, {{{{"estado", "Estado"}}, {{"clave", "Clave"}}, {{"valor_musd", "ValorMUSD"}}}}),
    Final = Table.TransformColumnTypes(Table.RemoveColumns(Renombrado, {{"periodo"}}), {{{{"ValorMUSD", type number}}, {{"Orden", Int64.Type}}}})
in
    Final"""),
    },
    {
        "nombre": "Release",
        "oculta": True,
        "columnas": [("Campo", "string"), ("Valor", "double"), ("Orden", "int64")],
        "m": m_parquet("financials_ypf.parquet", f"""    Largo = Table.UnpivotOtherColumns(Fuente, {{"trimestre"}}, "Campo", "Valor"),
{m_con_orden("Largo", "trimestre")},
    Final = Table.TransformColumnTypes(Table.RemoveColumns(Expandido, {{"trimestre"}}), {{{{"Valor", type number}}, {{"Campo", type text}}, {{"Orden", Int64.Type}}}})
in
    Final"""),
    },
    {
        "nombre": "Segmentos",
        "oculta": True,
        "columnas": [("Segmento", "string"), ("Concepto", "string"), ("ValorMUSD", "double"), ("Orden", "int64")],
        "m": m_parquet("segments_ypf_homologado.parquet", f"""    Filas = Table.SelectRows(Fuente, each [tipo] = "trimestre"),
    Columnas = Table.SelectColumns(Filas, {{"segmento", "concepto", "periodo", "valor_musd"}}),
{m_con_orden("Columnas", "periodo")},
    Renombrado = Table.RenameColumns(Expandido, {{{{"segmento", "Segmento"}}, {{"concepto", "Concepto"}}, {{"valor_musd", "ValorMUSD"}}}}),
    Final = Table.TransformColumnTypes(Table.RemoveColumns(Renombrado, {{"periodo"}}), {{{{"ValorMUSD", type number}}, {{"Orden", Int64.Type}}}})
in
    Final"""),
    },
]


def tabla_fija(nombre: str, columnas: list[tuple[str, str]], filas: list[tuple], oculta: bool = False,
               orden: dict | None = None) -> dict:
    """Una tabla chica escrita en el modelo: listas de selección, desfases."""
    tipos = {"string": "type text", "int64": "Int64.Type", "double": "type number"}
    literal = lambda v: f'"{v}"' if isinstance(v, str) else str(v)  # noqa: E731
    cuerpo = ", ".join("{" + ", ".join(literal(v) for v in fila) + "}" for fila in filas)
    encabezado = ", ".join(f'"{c}"' for c, _ in columnas)
    tipos_m = ", ".join(f'{{"{c}", {tipos[t]}}}' for c, t in columnas)
    return {
        "nombre": nombre,
        "oculta": oculta,
        "columnas": [(c, t, (orden or {}).get(c)) for c, t in columnas],
        "m": f"let\n    Fuente = #table({{{encabezado}}}, {{{cuerpo}}}),\n"
             f"    Tipos = Table.TransformColumnTypes(Fuente, {{{tipos_m}}})\nin\n    Tipos",
    }


METRICAS = ["Ingresos", "EBITDA ajustado", "Resultado operativo", "Capex", "Flujo operativo",
            "Flujo de caja libre", "Resultado neto"]
MARGENES = ["Bruto", "Operativo", "EBITDA", "Neto", "Flujo operativo"]
ACUMULADOS = ["Ingresos", "EBITDA ajustado", "Flujo operativo", "Capex"]

TABLAS += [
    tabla_fija("Segmento", [("Segmento", "string"), ("Orden", "int64")],
               [("Consolidado", 1), ("Upstream", 2), ("Downstream y gas", 3)], orden={"Segmento": "Orden"}),
    tabla_fija("Metrica", [("Metrica", "string"), ("Orden", "int64")],
               [(m, i + 1) for i, m in enumerate(METRICAS)], orden={"Metrica": "Orden"}),
    tabla_fija("Comparacion", [("Comparacion", "string"), ("Trimestres", "int64")],
               [("Año anterior", 4), ("Trimestre anterior", 1)], orden={"Comparacion": "Trimestres"}),
    tabla_fija("Desfase", [("N", "int64")], [(n,) for n in range(16)], oculta=True),
    tabla_fija("Margen", [("Margen", "string"), ("Orden", "int64")],
               [(m, i + 1) for i, m in enumerate(MARGENES)], orden={"Margen": "Orden"}),
    tabla_fija("Acumulado", [("Concepto", "string"), ("Orden", "int64")],
               [(m, i + 1) for i, m in enumerate(ACUMULADOS)], orden={"Concepto": "Orden"}),
]

TABLAS += [
    {
        # Una fila por concesión y trimestre, como la deja transform/tablero_mapa.py,
        # más una fila de total por trimestre.
        "nombre": "Mapa",
        "oculta": True,
        "columnas": [("Concesion", "string"), ("Boed", "double"), ("Orden", "int64")],
        "m": f"""let
    Fuente = Json.Document(File.Contents(RutaDatos & "tablero_mapa.json")),
    Periodos = Fuente[trimestres],
    PorConcesion = List.Combine(List.Transform(Fuente[concesiones], (c) =>
        List.Transform(List.Positions(c[boed]), (i) => [Concesion = c[nombre], periodo = Periodos{{i}}, Boed = c[boed]{{i}}]))),
    Total = List.Transform(List.Positions(Fuente[total_boed]), (i) =>
        [Concesion = "Total shale operado", periodo = Periodos{{i}}, Boed = Fuente[total_boed]{{i}}]),
    Tabla = Table.FromRecords(PorConcesion & Total),
{m_con_orden("Tabla", "periodo")},
    Final = Table.TransformColumnTypes(Table.RemoveColumns(Expandido, {{"periodo"}}), {{{{"Concesion", type text}}, {{"Boed", type number}}, {{"Orden", Int64.Type}}}})
in
    Final""",
    },
    {
        "nombre": "MapaConcesiones",
        "columnas": [("Concesion", "string"), ("X", "double"), ("Y", "double")],
        "m": """let
    Fuente = Json.Document(File.Contents(RutaDatos & "tablero_mapa.json")),
    Tabla = Table.FromRecords(List.Transform(Fuente[concesiones], (c) => [Concesion = c[nombre], X = c[x], Y = -c[y]])),
    Tipos = Table.TransformColumnTypes(Tabla, {{"Concesion", type text}, {"X", type number}, {"Y", type number}})
in
    Tipos""",
    },
    {
        "nombre": "Mercado",
        "oculta": True,
        "columnas": [("Fecha", "string"), ("Precio", "double"), ("Retorno", "double"), ("Anormal", "double"),
                     ("Acumulado", "double"), ("T", "double"), ("Embi", "double"), ("Orden", "int64")],
        "m": f"""let
    Fuente = Json.Document(File.Contents(RutaDatos & "market_reaction.json")),
    Tabla = Table.FromRecords(Fuente[eventos], {{"trimestre", "fecha_reporte", "precio_ypf", "retorno_dia", "retorno_anormal_dia", "car_0_3", "t_estadistico", "embi_dia"}}, MissingField.UseNull),
{m_con_orden("Tabla", "trimestre")},
    Renombrado = Table.RenameColumns(Table.RemoveColumns(Expandido, {{"trimestre"}}), {{{{"fecha_reporte", "Fecha"}}, {{"precio_ypf", "Precio"}}, {{"retorno_dia", "Retorno"}}, {{"retorno_anormal_dia", "Anormal"}}, {{"car_0_3", "Acumulado"}}, {{"t_estadistico", "T"}}, {{"embi_dia", "Embi"}}}}),
    Final = Table.TransformColumnTypes(Renombrado, {{{{"Fecha", type text}}, {{"Precio", type number}}, {{"Retorno", type number}}, {{"Anormal", type number}}, {{"Acumulado", type number}}, {{"T", type number}}, {{"Embi", type number}}, {{"Orden", Int64.Type}}}})
in
    Final""",
    },
]

CFO = "net cash flows from operating activities"
CAPEX = "acquisition of property plant and equipment and intangible assets | net cash flows used in investing activities"
DA = [
    "depreciation of property plant and equipment | net cash flows from operating activities",
    "amortization of intangible assets | net cash flows from operating activities",
    "depreciation of right of use assets | net cash flows from operating activities",
]

FORMATO_MUSD = '"US$ "#,##0"M";"−US$ "#,##0"M"'
FORMATO_PCT = '0.0%;−0.0%'
FORMATO_VAR = '"▲ "0.0%;"▼ "0.0%;"–"'


def estado(clave: str) -> str:
    return (f'VAR o = [_Orden]\nRETURN\n    CALCULATE(SUM(Estados[ValorMUSD]), Estados[Clave] = "{clave}", '
            f'Estados[Orden] = o)')


def segmento(concepto: str) -> str:
    return (f'VAR o = [_Orden]\nVAR s = [_Segmento]\nRETURN\n    CALCULATE(SUM(Segmentos[ValorMUSD]), '
            f'Segmentos[Concepto] = "{concepto}", Segmentos[Segmento] = s, Segmentos[Orden] = o)')


def release(campo: str) -> str:
    return (f'VAR o = [_Orden]\nRETURN\n    CALCULATE(SUM(Release[Valor]), Release[Campo] = "{campo}", '
            f'Release[Orden] = o)')


def en_ventana(expresion: str) -> str:
    """Solo los doce trimestres que terminan en el elegido."""
    return (f"VAR o = SELECTEDVALUE(Eje[Orden])\nVAR s = [_Orden elegido]\nRETURN\n"
            f"    IF(o <= s && o > s - 12, {expresion})")


# (nombre, expresión, formato, carpeta, oculta)
MEDIDAS_DAX: list[tuple[str, str, str | None, str, bool]] = [
    # --- contexto ---------------------------------------------------------
    ("_Orden elegido", "VAR o = SELECTEDVALUE(Trimestres[Orden])\nRETURN\n    IF(ISBLANK(o), MAX(Trimestres[Orden]), o)",
     "0", "Contexto", True),
    ("_Desfase", "SELECTEDVALUE(Desfase[N], 0)", "0", "Contexto", True),
    ("_Orden", "VAR base = IF(ISINSCOPE(Eje[Etiqueta]), SELECTEDVALUE(Eje[Orden]), [_Orden elegido])\n"
               "RETURN\n    base - [_Desfase]", "0", "Contexto", True),
    ("_Segmento", 'SELECTEDVALUE(Segmento[Segmento], "Consolidado")', None, "Contexto", True),
    ("_Consolidado", '[_Segmento] = "Consolidado"', None, "Contexto", True),
    ("_Trimestres comparación", "SELECTEDVALUE(Comparacion[Trimestres], 4)", "0", "Contexto", True),
    ("_Trimestre del año", "LOOKUPVALUE(Trimestres[NTrim], Trimestres[Orden], [_Orden elegido])", "0", "Contexto", True),
    ("Trimestre elegido", "LOOKUPVALUE(Trimestres[Etiqueta], Trimestres[Orden], [_Orden elegido])", None, "Textos", False),
    ("Trimestre de comparación",
     "LOOKUPVALUE(Trimestres[Etiqueta], Trimestres[Orden], [_Orden elegido] - [_Trimestres comparación])",
     None, "Textos", False),

    # --- de los estados (consolidado) ---------------------------------------
    ("_Ingresos estados", estado("revenues"), FORMATO_MUSD, "Base", True),
    ("_Resultado operativo estados", estado("operating profit"), FORMATO_MUSD, "Base", True),
    ("_Resultado bruto estados", estado("gross profit"), FORMATO_MUSD, "Base", True),
    ("_Resultado neto estados", estado("net profit"), FORMATO_MUSD, "Base", True),
    ("_Flujo operativo estados", estado(CFO), FORMATO_MUSD, "Base", True),
    ("_Capex estados", estado(CAPEX), FORMATO_MUSD, "Base", True),
    ("_DA estados", "VAR o = [_Orden]\nRETURN\n    CALCULATE(SUM(Estados[ValorMUSD]), Estados[Clave] IN {"
                    + ", ".join(f'"{c}"' for c in DA) + "}, Estados[Orden] = o)", FORMATO_MUSD, "Base", True),
    ("_Ingresos segmento", segmento("ingresos_totales"), FORMATO_MUSD, "Base", True),
    ("_Resultado operativo segmento", segmento("resultado_operativo"), FORMATO_MUSD, "Base", True),
    ("_Capex segmento", segmento("capex_ppe"), FORMATO_MUSD, "Base", True),
    ("_Depreciación segmento", segmento("depreciacion_ppe"), FORMATO_MUSD, "Base", True),
    ("_EBITDA ajustado release", release("adj_ebitda_musd"), FORMATO_MUSD, "Base", True),
    ("_Capex release", release("capex_musd"), FORMATO_MUSD, "Base", True),
    ("_FCF release", release("fcf_musd"), FORMATO_MUSD, "Base", True),
    ("_Apalancamiento release", release("net_leverage_x"), '0.0"x"', "Base", True),

    # --- métricas: consolidado o segmento -----------------------------------
    ("Ingresos", "IF([_Consolidado], [_Ingresos estados], [_Ingresos segmento])", FORMATO_MUSD, "Métricas", False),
    ("EBITDA ajustado",
     "IF([_Consolidado], [_EBITDA ajustado release], [_Resultado operativo segmento] + [_Depreciación segmento])",
     FORMATO_MUSD, "Métricas", False),
    # Siempre consolidados: son lecturas de los estados, que no se abren por segmento.
    ("EBITDA de los estados", "[_Resultado operativo estados] + [_DA estados]",
     FORMATO_MUSD, "Métricas", False),
    ("Resultado operativo", "IF([_Consolidado], [_Resultado operativo estados], [_Resultado operativo segmento])",
     FORMATO_MUSD, "Métricas", False),
    ("Capex", "IF([_Consolidado], -[_Capex estados], [_Capex segmento])", FORMATO_MUSD, "Métricas", False),
    ("Flujo operativo", "IF([_Consolidado], [_Flujo operativo estados])", FORMATO_MUSD, "Métricas", False),
    ("Flujo de caja libre", "IF([_Consolidado], [_Flujo operativo estados] + [_Capex estados])",
     FORMATO_MUSD, "Métricas", False),
    ("Resultado neto", "IF([_Consolidado], [_Resultado neto estados])", FORMATO_MUSD, "Métricas", False),
    ("Margen EBITDA", "DIVIDE([EBITDA ajustado], [Ingresos])", FORMATO_PCT, "Métricas", False),
    ("Capex pagado", "-[_Capex estados]", FORMATO_MUSD, "Lecturas del capex", False),
    ("Capex devengado", 'VAR o = [_Orden]\nRETURN\n    CALCULATE(SUM(Segmentos[ValorMUSD]), Segmentos[Concepto] = "capex_ppe", '
                        'Segmentos[Segmento] = "Total", Segmentos[Orden] = o)', FORMATO_MUSD, "Lecturas del capex", False),
    ("Capex publicado", "[_Capex release]", FORMATO_MUSD, "Lecturas del capex", False),
    ("Flujo libre publicado", "[_FCF release]", FORMATO_MUSD, "Lecturas del capex", False),
    ("Flujo libre calculado", "[_Flujo operativo estados] + [_Capex estados]", FORMATO_MUSD, "Lecturas del capex", False),
    ("Deuda neta / EBITDA", "[_Apalancamiento release]", '0.0"x"', "Métricas", False),

    ("Valor métrica", "SWITCH(SELECTEDVALUE(Metrica[Orden], 1), "
                      + ", ".join(f"{i + 1}, [{m}]" for i, m in enumerate(METRICAS)) + ")",
     FORMATO_MUSD, "Métricas", False),

    # --- comparación --------------------------------------------------------
    ("EBITDA ajustado comparación",
     "CALCULATE([EBITDA ajustado], TREATAS({[_Trimestres comparación]}, Desfase[N]))", FORMATO_MUSD, "Comparación", False),
    ("Variación EBITDA",
     "VAR a = [EBITDA ajustado]\nVAR b = [EBITDA ajustado comparación]\nRETURN\n"
     "    IF(NOT ISBLANK(b) && b <> 0, (a - b) / ABS(b))", FORMATO_VAR, "Comparación", False),

    # --- serie --------------------------------------------------------------
    ("Serie métrica", en_ventana("[Valor métrica]"), FORMATO_MUSD, "Serie", False),
    ("Serie EBITDA ajustado", en_ventana("[EBITDA ajustado]"), FORMATO_MUSD, "Serie", False),
    ("Serie flujo operativo", en_ventana("[Flujo operativo]"), FORMATO_MUSD, "Serie", False),
    ("Color serie", 'IF(SELECTEDVALUE(Eje[Orden]) > [_Orden elegido] - 3, "' + CIAN + '", "' + APAGADO + '")',
     None, "Serie", True),
    ("Métrica últimos doce meses",
     "SUMX(FILTER(ALL(Desfase), Desfase[N] < 4), CALCULATE([Valor métrica]))", FORMATO_MUSD, "Serie", False),

    # --- márgenes (consolidados) --------------------------------------------
    ("_Margen", "VAR ingresos = [_Ingresos estados]\nRETURN\n    SWITCH(SELECTEDVALUE(Margen[Orden]),\n"
                "        1, DIVIDE([_Resultado bruto estados], ingresos),\n"
                "        2, DIVIDE([_Resultado operativo estados], ingresos),\n"
                "        3, DIVIDE([_EBITDA ajustado release], ingresos),\n"
                "        4, DIVIDE([_Resultado neto estados], ingresos),\n"
                "        5, DIVIDE([_Flujo operativo estados], ingresos))", FORMATO_PCT, "Márgenes", True),
    ("Margen elegido", "[_Margen]", FORMATO_PCT, "Márgenes", False),
    ("Margen comparación", "CALCULATE([_Margen], TREATAS({[_Trimestres comparación]}, Desfase[N]))",
     FORMATO_PCT, "Márgenes", False),

    # --- lo que va del año --------------------------------------------------
    ("_Concepto acumulado", "SWITCH(SELECTEDVALUE(Acumulado[Orden]), 1, [Ingresos], 2, [EBITDA ajustado], "
                            "3, [Flujo operativo], 4, [Capex])", FORMATO_MUSD, "Acumulado", True),
    ("Acumulado del año",
     "VAR n = [_Trimestre del año]\nRETURN\n    SUMX(FILTER(ALL(Desfase), Desfase[N] < n), CALCULATE([_Concepto acumulado]))",
     FORMATO_MUSD, "Acumulado", False),
    ("Acumulado del año anterior",
     "VAR n = [_Trimestre del año]\nRETURN\n    SUMX(FILTER(ALL(Desfase), Desfase[N] >= 4 && Desfase[N] < 4 + n), "
     "CALCULATE([_Concepto acumulado]))", FORMATO_MUSD, "Acumulado", False),

    # --- textos -------------------------------------------------------------
    ("Título tablero", '"Trimestre " & [Trimestre elegido] & " · " & [_Segmento]', None, "Textos", False),
    ("Título EBITDA", 'IF([_Consolidado], "EBITDA ajustado · ", "EBITDA del segmento · ") & [Trimestre elegido]',
     None, "Textos", False),
    ("Título variación", '"EBITDA contra " & [Trimestre de comparación]', None, "Textos", False),
    ("Título serie", 'SELECTEDVALUE(Metrica[Metrica], "Ingresos") & " · doce trimestres hasta " & [Trimestre elegido]',
     None, "Textos", False),
    ("Título márgenes", '"Márgenes consolidados: " & [Trimestre elegido] & " contra " & [Trimestre de comparación]',
     None, "Textos", False),
    ("Título acumulado", 'VAR n = [_Trimestre del año]\nVAR tramo = SWITCH(n, 1, "1T", 2, "1S", 3, "9M", "FY")\n'
                         'VAR anio = LOOKUPVALUE(Trimestres[Anio], Trimestres[Orden], [_Orden elegido])\nRETURN\n'
                         '    "Lo que va del año: " & tramo & RIGHT(anio, 2) & " contra " & tramo & RIGHT(anio - 1, 2)',
     None, "Textos", False),
]


def mercado(columna: str) -> str:
    return f"VAR o = [_Orden]\nRETURN\n    CALCULATE(MAX(Mercado[{columna}]), Mercado[Orden] = o)"


FORMATO_RETORNO = '"+"0.0%;"−"0.0%;0.0%'
OPERATIVOS = [("Producción total", "produccion_kboed"), ("Petróleo shale", "shale_oil_kbbld"),
              ("Precio del crudo", "precio_crudo_usd_bbl"), ("Lifting cost", "lifting_cost_usd_boe")]

MEDIDAS_DAX += [
    ("Título operativo", '"Precio o volumen: doce trimestres hasta " & [Trimestre elegido] & " (consolidado, release)"',
     None, "Textos", False),
    ("Título mapa", '"Vaca Muerta: dónde produce YPF · shale operado, boe/d brutos · " & [Trimestre elegido] & " contra " & [Trimestre de comparación]',
     None, "Textos", False),
    ("Título mercado", 'VAR f = [_Fecha del reporte]\nRETURN\n    "Cómo reaccionó el mercado · " & IF(ISBLANK(f), '
                       '"sin estudio de evento para " & [Trimestre elegido], "balance de " & [Trimestre elegido] & '
                       '", presentado el " & RIGHT(f, 2) & "/" & MID(f, 6, 2) & "/" & LEFT(f, 4))',
     None, "Textos", False),
]
for nombre, campo in OPERATIVOS:
    MEDIDAS_DAX += [
        (nombre, release(campo), "#,##0.0", "Operativo", False),
        (f"Variación {nombre.lower()}",
         f"VAR a = [{nombre}]\nVAR b = CALCULATE([{nombre}], TREATAS({{[_Trimestres comparación]}}, Desfase[N]))\n"
         "RETURN\n    IF(NOT ISBLANK(a) && NOT ISBLANK(b) && b <> 0, (a - b) / ABS(b))", FORMATO_VAR, "Operativo", False),
    ]
MEDIDAS_DAX += [
    ("Serie producción total", en_ventana("[Producción total]"), "#,##0", "Operativo", False),
    ("Serie petróleo shale", en_ventana("[Petróleo shale]"), "#,##0", "Operativo", False),
    ("Serie precio del crudo", en_ventana("[Precio del crudo]"), "#,##0.0", "Operativo", False),

    # --- mapa -------------------------------------------------------------------
    ("Producción shale", 'VAR o = [_Orden]\nVAR c = SELECTEDVALUE(MapaConcesiones[Concesion], "Total shale operado")\n'
                         'RETURN\n    CALCULATE(SUM(Mapa[Boed]), Mapa[Orden] = o, Mapa[Concesion] = c)',
     "#,##0", "Mapa", False),
    ("Variación shale", "VAR a = [Producción shale]\nVAR b = CALCULATE([Producción shale], "
                        "TREATAS({[_Trimestres comparación]}, Desfase[N]))\nRETURN\n"
                        "    IF(NOT ISBLANK(b) && b > 0, (a - b) / b)", FORMATO_VAR, "Mapa", False),
    ("Mapa X", "SELECTEDVALUE(MapaConcesiones[X])", "0.0", "Mapa", True),
    ("Mapa Y", "SELECTEDVALUE(MapaConcesiones[Y])", "0.0", "Mapa", True),
    ("Color mapa", f'IF([Variación shale] < 0, "{AMBAR}", "{CIAN}")', None, "Mapa", True),

    # --- mercado ----------------------------------------------------------------
    ("_Fecha del reporte", "VAR o = [_Orden]\nRETURN\n    CALCULATE(MAX(Mercado[Fecha]), Mercado[Orden] = o)",
     None, "Mercado", True),
    ("Precio del ADR", mercado("Precio"), '"US$ "0.00', "Mercado", False),
    ("Retorno del día", mercado("Retorno"), FORMATO_RETORNO, "Mercado", False),
    ("Retorno anormal", mercado("Anormal"), FORMATO_RETORNO, "Mercado", False),
    ("Anormal acumulado 4 ruedas", mercado("Acumulado"), FORMATO_RETORNO, "Mercado", False),
    ("Estadístico t", mercado("T"), "0.00", "Mercado", False),
    ("Riesgo país ese día", mercado("Embi"), '#,##0" pb"', "Mercado", False),
    ("Serie retorno anormal", en_ventana("[Retorno anormal]"), FORMATO_RETORNO, "Mercado", False),
    ("Color reacción", f'VAR o = SELECTEDVALUE(Eje[Orden])\nRETURN\n    IF(o = [_Orden elegido], "{AMBAR}", '
                       f'IF([Retorno anormal] < 0, "#7c5a1e", "{APAGADO}"))', None, "Mercado", True),
]


def tabla_tmdl(tabla: dict) -> str:
    lineas = [f"table {tmdl_nombre(tabla['nombre'])}", f"\tlineageTag: {guid('tabla/' + tabla['nombre'])}", ""]
    for columna in tabla["columnas"]:
        nombre, tipo = columna[0], columna[1]
        orden = columna[2] if len(columna) > 2 else None
        lineas += [f"\tcolumn {tmdl_nombre(nombre)}", f"\t\tdataType: {tipo}"]
        if tabla.get("oculta") or nombre == "Orden" or (tabla["nombre"] in ("Trimestres", "Eje") and nombre != "Etiqueta"):
            lineas.append("\t\tisHidden")
        lineas += [f"\t\tlineageTag: {guid('columna/' + tabla['nombre'] + '/' + nombre)}", "\t\tsummarizeBy: none",
                   f"\t\tsourceColumn: {nombre}"]
        if orden:
            lineas.append(f"\t\tsortByColumn: {tmdl_nombre(orden)}")
        lineas += ["", "\t\tannotation SummarizationSetBy = User", ""]
    lineas += [f"\tpartition {tmdl_nombre(tabla['nombre'])} = m", "\t\tmode: import", "\t\tsource =",
               sangrar(tabla["m"], 4), ""]
    return "\n".join(lineas) + "\n"


def medidas_tmdl() -> str:
    lineas = [f"table {MEDIDAS}", f"\tlineageTag: {guid('tabla/' + MEDIDAS)}", ""]
    for nombre, expresion, formato, carpeta, oculta in MEDIDAS_DAX:
        lineas.append(f"\tmeasure {tmdl_nombre(nombre)} =")
        lineas.append(sangrar(expresion, 3))
        if formato:
            # Un formato con comillas va entre comillas, con las internas duplicadas.
            valor = '"' + formato.replace('"', '""') + '"' if '"' in formato else formato
            lineas.append(f"\t\tformatString: {valor}")
        if oculta:
            lineas.append("\t\tisHidden")
        lineas += [f"\t\tdisplayFolder: {carpeta}", f"\t\tlineageTag: {guid('medida/' + nombre)}", ""]
    lineas += ["\tcolumn _", "\t\tdataType: int64", "\t\tisHidden", f"\t\tlineageTag: {guid('columna/medidas')}",
               "\t\tsummarizeBy: none", "\t\tsourceColumn: _", "",
               f"\tpartition {MEDIDAS} = m", "\t\tmode: import", "\t\tsource =",
               sangrar('let\n    Fuente = #table(type table [_ = Int64.Type], {{1}})\nin\n    Fuente', 4), ""]
    return "\n".join(lineas) + "\n"


def escribir_modelo() -> None:
    definicion = MODELO / "definition"
    escribir(MODELO / "definition.pbism", {
        "$schema": f"{ESQUEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {"qnaEnabled": False},
    })
    escribir(MODELO / ".platform", {
        "$schema": f"{ESQUEMA}/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": NOMBRE},
        "config": {"version": "2.0", "logicalId": guid("modelo")},
    })
    escribir(definicion / "database.tmdl", "database\n\tcompatibilityLevel: 1601\n")
    tablas = [t["nombre"] for t in TABLAS] + [MEDIDAS]
    escribir(definicion / "model.tmdl", "\n".join([
        "model Model",
        "\tculture: es-ES",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tdiscourageImplicitMeasures",
        "\tsourceQueryCulture: en-US",
        "\tdataAccessOptions",
        "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull",
        "",
        "annotation __PBI_TimeIntelligenceEnabled = 0",
        "",
        f"annotation PBI_QueryOrder = {json.dumps(['RutaDatos', *tablas])}",
        "",
        *[f"ref table {tmdl_nombre(t)}" for t in tablas],
        "",
    ]))
    ruta = str(PROCESSED) + "\\"
    escribir(definicion / "expressions.tmdl", "\n".join([
        "/// Carpeta de data/processed/. Es lo único que hay que cambiar si el repo se mueve.",
        f'expression RutaDatos = "{ruta}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]',
        f"\tlineageTag: {guid('expresion/RutaDatos')}",
        "",
        "\tannotation PBI_ResultType = Text",
        "",
    ]))
    for tabla in TABLAS:
        escribir(definicion / "tables" / f"{tabla['nombre']}.tmdl", tabla_tmdl(tabla))
    escribir(definicion / "tables" / f"{MEDIDAS}.tmdl", medidas_tmdl())


# --------------------------------------------------------------------------- #
# Reporte
# --------------------------------------------------------------------------- #
def literal(valor) -> dict:
    if isinstance(valor, bool):
        texto = "true" if valor else "false"
    elif isinstance(valor, int):
        texto = f"{valor}L"
    elif isinstance(valor, float):
        texto = f"{valor}D"
    else:
        texto = "'" + str(valor).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": texto}}}


def color(hexa: str) -> dict:
    return {"solid": {"color": literal(hexa)}}


def color_medida(medida: str) -> dict:
    return {"solid": {"color": {"expr": medida_campo(medida)}}}


def medida_campo(medida: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": MEDIDAS}}, "Property": medida}}


def columna_campo(tabla: str, columna: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": tabla}}, "Property": columna}}


def proyeccion(campo: dict, nombre: str | None = None) -> dict:
    if "Measure" in campo:
        propiedad, entidad = campo["Measure"]["Property"], MEDIDAS
    else:
        propiedad, entidad = campo["Column"]["Property"], campo["Column"]["Expression"]["SourceRef"]["Entity"]
    salida = {"field": campo, "queryRef": f"{entidad}.{propiedad}", "nativeQueryRef": propiedad}
    if nombre:
        salida["displayName"] = nombre
    return salida


def props(**propiedades) -> dict:
    return {"properties": {k: (v if isinstance(v, dict) else literal(v)) for k, v in propiedades.items()}}


class Pagina:
    def __init__(self, nombre: str, titulo: str, ancho: int, alto: int):
        self.nombre, self.titulo, self.ancho, self.alto = nombre, titulo, ancho, alto
        self.visuales: list[dict] = []

    def agregar(self, semilla: str, tipo: str, x: float, y: float, w: float, h: float,
                roles: dict | None = None, objetos: dict | None = None, contenedor: dict | None = None,
                titulo: str | None = None, titulo_medida: str | None = None, orden: dict | None = None,
                fondo: bool = True) -> None:
        z = len(self.visuales) * 1000
        visual: dict = {"visualType": tipo}
        if roles:
            visual["query"] = {"queryState": {rol: {"projections": proys} for rol, proys in roles.items()}}
            if orden:
                visual["query"]["sortDefinition"] = orden
        if objetos:
            visual["objects"] = objetos
        cont = dict(contenedor or {})
        if titulo or titulo_medida:
            texto = {"expr": medida_campo(titulo_medida)} if titulo_medida else literal(titulo)
            cont["title"] = [props(show=True, text=texto, fontColor=color(TEXTO), fontSize=11.0)]
        else:
            cont.setdefault("title", [props(show=False)])
        if not fondo:
            cont["background"] = [props(show=False)]
            cont["border"] = [props(show=False)]
        visual["visualContainerObjects"] = cont
        visual["drillFilterOtherVisuals"] = True
        self.visuales.append({
            "$schema": V_VISUAL,
            "name": nombre_visual(f"{self.nombre}/{semilla}"),
            "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
            "visual": visual,
        })

    def escribir(self, carpeta: Path) -> None:
        base = carpeta / self.nombre
        escribir(base / "page.json", {
            "$schema": V_PAGINA, "name": self.nombre, "displayName": self.titulo,
            "displayOption": "FitToWidth", "height": self.alto, "width": self.ancho,
            "objects": {"background": [props(color=color(PAGINA), transparency=0.0)],
                        "outspace": [props(color=color(PAGINA))]},
        })
        for visual in self.visuales:
            escribir(base / "visuals" / visual["name"] / "visual.json", visual)


def tarjeta(pagina: Pagina, semilla: str, medida: str, x, y, w, h, titulo: str | None = None,
            titulo_medida: str | None = None, tamanio: float = 26.0, tinte: str = TEXTO) -> None:
    pagina.agregar(
        semilla, "card", x, y, w, h,
        roles={"Values": [proyeccion(medida_campo(medida))]},
        # Unidades de visualización en "ninguna": las medidas ya están en
        # millones y el formato lo dice; con "auto" Power BI escribe "milM".
        objetos={"labels": [props(color=color(tinte), fontSize=tamanio, labelDisplayUnits=1.0)],
                 "categoryLabels": [props(show=False)]},
        titulo=titulo, titulo_medida=titulo_medida,
    )


def marco(pagina: Pagina, semilla: str, medida_titulo: str, x, y, w, h) -> None:
    """Una tarjeta vacía que hace de fondo de un grupo de visuales, con título dinámico."""
    tarjeta(pagina, semilla, medida_titulo, x, y, w, h, titulo_medida=medida_titulo, tamanio=8.0, tinte=TARJETA)


def ejes(mostrar_valores: bool = True, **extra) -> dict:
    """Ejes sin título y sin unidades automáticas."""
    return {
        "categoryAxis": [props(show=True, showAxisTitle=False, labelColor=color(TEXTO_SUAVE), fontSize=8.0)],
        "valueAxis": [props(show=mostrar_valores, showAxisTitle=False, labelDisplayUnits=1.0,
                            labelColor=color(TEXTO_SUAVE), fontSize=8.0, gridlineShow=True,
                            gridlineColor=color("#1a2e4a"))],
        "labels": [props(show=True, color=color(TEXTO), fontSize=8.0, labelDisplayUnits=1.0)],
        "legend": [props(show=True, position="Top", labelColor=color(TEXTO_SUAVE))],
        **extra,
    }


def serie_colores(*pares: tuple[str, str]) -> list:
    """Un color fijo por medida del gráfico."""
    return [{"properties": {"fill": color(tinte)}, "selector": {"metadata": f"{MEDIDAS}.{medida}"}}
            for medida, tinte in pares]


def filtro(pagina: Pagina, semilla: str, tabla: str, columna: str, rotulo: str, x, y, w, h,
           descendente: bool = False, elegido: str | None = None) -> None:
    campo = columna_campo(tabla, columna)
    general = []
    if elegido is not None:
        # La selección inicial de la lista, en el formato en que Desktop la guarda.
        general = [{"properties": {"filter": {"filter": {
            "Version": 2,
            "From": [{"Name": "t", "Entity": tabla, "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": columna}}],
                "Values": [[{"Literal": {"Value": "'" + elegido + "'"}}]],
            }}}],
        }}}}]
    pagina.agregar(
        semilla, "slicer", x, y, w, h,
        roles={"Values": [proyeccion(campo)]},
        objetos={
            **({"general": general} if general else {}),
            "data": [props(mode="Dropdown")],
            "selection": [props(singleSelect=True)],
            "header": [props(show=True, text=rotulo, fontColor=color(TEXTO_SUAVE), textSize=9.0)],
            "items": [props(fontColor=color(TEXTO), background=color(TARJETA), textSize=10.0)],
        },
        orden={"sort": [{"field": campo, "direction": "Descending" if descendente else "Ascending"}]},
    )
    # La misma lista en todas las páginas: elegir el trimestre en una lo
    # cambia en las otras.
    pagina.visuales[-1]["visual"]["syncGroup"] = {"groupName": f"{tabla}.{columna}", "fieldChanges": True,
                                                  "filterChanges": True}


def escribir_reporte() -> None:
    definicion = REPORTE / "definition"
    escribir(REPORTE / "definition.pbir", {
        "$schema": f"{ESQUEMA}/item/report/definitionProperties/1.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{NOMBRE}.SemanticModel"}},
    })
    escribir(REPORTE / ".platform", {
        "$schema": f"{ESQUEMA}/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": NOMBRE},
        "config": {"version": "2.0", "logicalId": guid("reporte")},
    })

    recursos = REPORTE / "StaticResources"
    (recursos / "SharedResources" / "BaseThemes").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TEMA_BASE, recursos / "SharedResources" / "BaseThemes" / "CY24SU10.json")
    escribir(recursos / "RegisteredResources" / "YPF_Atlas_oscuro.json", tema())

    escribir(definicion / "version.json", {
        "$schema": f"{ESQUEMA}/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0",
    })
    escribir(definicion / "report.json", {
        "$schema": V_REPORTE,
        "themeCollection": {
            "baseTheme": {"name": "CY24SU10", "reportVersionAtImport": "5.61", "type": "SharedResources"},
            "customTheme": {"name": "YPF_Atlas_oscuro.json", "reportVersionAtImport": "5.61",
                            "type": "RegisteredResources"},
        },
        "layoutOptimization": "None",
        "objects": {"outspacePane": [props(expanded=False, visible=True)]},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": "YPF_Atlas_oscuro.json", "path": "YPF_Atlas_oscuro.json", "type": "CustomTheme"}]},
        ],
        "settings": {
            "useStylableVisualContainerHeader": True,
            "exportDataMode": "AllowSummarized",
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "useEnhancedTooltips": True,
        },
    })

    paginas = [pagina_tablero(), pagina_operativo()]
    escribir(definicion / "pages" / "pages.json", {
        "$schema": f"{ESQUEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p.nombre for p in paginas],
        "activePageName": paginas[0].nombre,
    })
    for pagina in paginas:
        pagina.escribir(definicion / "pages")


def tema() -> dict:
    """El tema oscuro: fondo de página, tarjetas redondeadas, textos claros."""
    tarjeta_estilo = {
        "background": [{"show": True, "color": {"solid": {"color": TARJETA}}, "transparency": 0}],
        "border": [{"show": True, "color": {"solid": {"color": BORDE}}, "radius": 14}],
        "dropShadow": [{"show": False}],
        "title": [{"show": True, "fontColor": {"solid": {"color": TEXTO}}, "fontSize": 11,
                   "fontFamily": "Segoe UI Semibold"}],
        "visualHeader": [{"show": False}],
        "padding": [{"top": 10, "bottom": 10, "left": 12, "right": 12}],
    }
    return {
        "name": "YPF Atlas oscuro",
        "dataColors": [CIAN, INDIGO, AZUL, AMBAR, "#94a3b8", "#1e3a8a", "#67e8f9", "#475569"],
        "background": PAGINA,
        "foreground": TEXTO,
        "tableAccent": CIAN,
        "good": CIAN,
        "bad": AMBAR,
        "neutral": TEXTO_SUAVE,
        "textClasses": {
            "callout": {"fontSize": 26, "fontFace": "Segoe UI Semibold", "color": TEXTO},
            "title": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": TEXTO},
            "header": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": TEXTO},
            "label": {"fontSize": 9, "fontFace": "Segoe UI", "color": TEXTO_SUAVE},
        },
        "visualStyles": {
            "*": {"*": {
                **tarjeta_estilo,
                "categoryAxis": [{"labelColor": {"solid": {"color": TEXTO_SUAVE}}, "gridlineShow": False}],
                "valueAxis": [{"labelColor": {"solid": {"color": TEXTO_SUAVE}},
                               "gridlineColor": {"solid": {"color": "#1a2e4a"}}}],
                "legend": [{"labelColor": {"solid": {"color": TEXTO_SUAVE}}}],
            }},
            "page": {"*": {"background": [{"color": {"solid": {"color": PAGINA}}, "transparency": 0}],
                           "outspace": [{"color": {"solid": {"color": PAGINA}}, "transparency": 0}]}},
            "slicer": {"*": {"items": [{"fontColor": {"solid": {"color": TEXTO}}}],
                             "header": [{"fontColor": {"solid": {"color": TEXTO_SUAVE}}}]}},
        },
    }


def cabecera(p: Pagina) -> None:
    """Título, subtítulo y las cuatro listas, iguales en todas las páginas."""
    M = 24
    p.agregar("titulo", "textbox", M, 8, 300, 60, objetos={"general": [{"properties": {"paragraphs": [
        {"textRuns": [{"value": "YPF · ATLAS", "textStyle": {"fontFamily": "Segoe UI Semibold", "fontSize": "20pt",
                                                               "color": TEXTO}}]}]}}]}, fondo=False)
    tarjeta(p, "subtitulo", "Título tablero", M, 62, 420, 34, tamanio=10.0, tinte=TEXTO_SUAVE)
    p.visuales[-1]["visual"]["visualContainerObjects"]["background"] = [props(show=False)]
    p.visuales[-1]["visual"]["visualContainerObjects"]["border"] = [props(show=False)]
    filtro(p, "f_trimestre", "Trimestres", "Etiqueta", "Trimestre", 640, 16, 200, 72, descendente=True,
           elegido=ultimo_trimestre())
    filtro(p, "f_segmento", "Segmento", "Segmento", "Segmento", 856, 16, 220, 72, elegido="Consolidado")
    filtro(p, "f_metrica", "Metrica", "Metrica", "Métrica de la serie", 1092, 16, 250, 72, elegido="Ingresos")
    filtro(p, "f_comparacion", "Comparacion", "Comparacion", "Comparar contra", 1358, 16, 218, 72,
           elegido="Año anterior")


def ultimo_trimestre() -> str:
    """El trimestre con el que abre el reporte: el último de los estados."""
    import pandas as pd

    datos = pd.read_parquet(PROCESSED / "statements_ypf.parquet", columns=["tipo", "periodo"])
    periodo = max(datos.loc[datos["tipo"] == "trimestre", "periodo"])
    return f"{periodo[-1]}T{periodo[2:4]}"


def pagina_tablero() -> Pagina:
    p = Pagina("tablero", "Tablero", 1600, 1000)
    M = 24
    cabecera(p)

    # Fila 1: tarjetas.
    y1, h1 = 104, 120
    ancho = (1600 - 2 * M - 5 * 16) / 6
    fichas = [
        ("ebitda", "EBITDA ajustado", None, "Título EBITDA", CIAN),
        ("ingresos", "Ingresos", "Ingresos del trimestre", None, TEXTO),
        ("margen", "Margen EBITDA", "Margen EBITDA", None, TEXTO),
        ("variacion", "Variación EBITDA", None, "Título variación", CIAN),
        ("contable", "EBITDA de los estados", "EBITDA de los estados (res. operativo + D&A)", None, TEXTO_SUAVE),
        ("apalancamiento", "Deuda neta / EBITDA", "Deuda neta / EBITDA (release)", None, TEXTO),
    ]
    for i, (semilla, medida, titulo, titulo_medida, tinte) in enumerate(fichas):
        tarjeta(p, semilla, medida, M + i * (ancho + 16), y1, ancho, h1, titulo=titulo,
                titulo_medida=titulo_medida, tinte=tinte, tamanio=24.0)

    # Fila 2: serie, doce meses, capex pagado y márgenes.
    y2, h2 = 240, 360
    eje = columna_campo("Eje", "Etiqueta")
    p.agregar(
        "serie", "clusteredColumnChart", M, y2, 960, h2,
        roles={"Category": [proyeccion(eje)], "Y": [proyeccion(medida_campo("Serie métrica"))]},
        objetos=ejes(
            legend=[props(show=False)],
            dataPoint=[{"properties": {"fill": color_medida("Color serie")},
                        "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
        ),
        titulo_medida="Título serie",
        orden={"sort": [{"field": eje, "direction": "Ascending"}]},
    )
    tarjeta(p, "udm", "Métrica últimos doce meses", M + 976, y2, 300, 110, titulo="Métrica, últimos doce meses",
            tamanio=22.0)
    tarjeta(p, "capex_pagado", "Capex pagado", M + 1292, y2, 1600 - 2 * M - 1292, 110, titulo="Capex pagado",
            tamanio=18.0)
    margen = columna_campo("Margen", "Margen")
    p.agregar(
        "margenes", "clusteredBarChart", M + 976, y2 + 126, 1600 - 2 * M - 976, h2 - 126,
        roles={"Category": [proyeccion(margen)],
               "Y": [proyeccion(medida_campo("Margen elegido"), "Elegido"),
                     proyeccion(medida_campo("Margen comparación"), "Comparación")]},
        objetos=ejes(False, dataPoint=serie_colores(("Margen elegido", CIAN), ("Margen comparación", INDIGO))),
        titulo_medida="Título márgenes",
        orden={"sort": [{"field": margen, "direction": "Ascending"}]},
    )

    # Fila 3: acumulado, EBITDA contra flujo, lecturas del capex.
    y3, h3 = 616, 360
    concepto = columna_campo("Acumulado", "Concepto")
    p.agregar(
        "acumulado", "clusteredBarChart", M, y3, 480, h3,
        roles={"Category": [proyeccion(concepto)],
               "Y": [proyeccion(medida_campo("Acumulado del año"), "Este año"),
                     proyeccion(medida_campo("Acumulado del año anterior"), "Año anterior")]},
        objetos=ejes(False, dataPoint=serie_colores(("Acumulado del año", CIAN),
                                                    ("Acumulado del año anterior", APAGADO))),
        titulo_medida="Título acumulado",
        orden={"sort": [{"field": concepto, "direction": "Ascending"}]},
    )
    p.agregar(
        "lineas", "lineChart", M + 496, y3, 700, h3,
        roles={"Category": [proyeccion(eje)],
               "Y": [proyeccion(medida_campo("Serie EBITDA ajustado"), "EBITDA ajustado"),
                     proyeccion(medida_campo("Serie flujo operativo"), "Flujo operativo")]},
        objetos=ejes(labels=[props(show=False)],
                     dataPoint=serie_colores(("Serie EBITDA ajustado", CIAN), ("Serie flujo operativo", INDIGO))),
        titulo="EBITDA ajustado y flujo operativo, doce trimestres",
        orden={"sort": [{"field": eje, "direction": "Ascending"}]},
    )
    x4 = M + 1212
    p.agregar(
        "lecturas", "multiRowCard", x4, y3, 1600 - M - x4, h3,
        roles={"Values": [proyeccion(medida_campo(m)) for m in
                          ("Capex pagado", "Capex devengado", "Capex publicado", "Flujo libre calculado",
                           "Flujo libre publicado")]},
        objetos={"dataLabels": [props(color=color(TEXTO), fontSize=16.0, labelDisplayUnits=1.0)],
                 "categoryLabels": [props(color=color(TEXTO_SUAVE), fontSize=9.0)]},
        titulo="Las lecturas del capex y del flujo libre (consolidado)",
    )
    return p


def imagen_mapa() -> tuple[str, int, int] | None:
    """El mapa del tablero de Excel como imagen: el mismo relieve y las mismas capas."""
    import base64
    import io

    from PIL import Image

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import tablero

    datos, web, relieve = tablero.cargar_mapa(PROCESSED)
    if not datos:
        return None
    x, y, w, h = tablero.recuadro_del_mapa(datos)
    s = tablero.ESCALA_IMAGEN
    lienzo = Image.new("RGBA", ((x + w) * s, (y + h) * s), (0, 0, 0, 0))
    tablero.dibujar_mapa(lienzo, datos, web, relieve)
    recorte = lienzo.crop((x * s, y * s, (x + w) * s, (y + h) * s)).convert("RGB")
    salida = io.BytesIO()
    recorte.save(salida, format="JPEG", quality=86)
    return "data:image/jpeg;base64," + base64.b64encode(salida.getvalue()).decode(), w, h


def pagina_operativo() -> Pagina:
    p = Pagina("operativo", "Operativo y mercado", 1600, 1000)
    M = 24
    cabecera(p)
    eje = columna_campo("Eje", "Etiqueta")

    # --- mapa ---------------------------------------------------------------
    y1, h1 = 104, 488
    marco(p, "mapa_marco", "Título mapa", M, y1, 740, h1)
    imagen = imagen_mapa()
    x2 = M + 756
    w2 = 1600 - M - x2
    if imagen:
        url, w, h = imagen
        mh = 420
        mw = round(w * mh / h)
        mx, my = M + 12, y1 + 56
        p.agregar("mapa_imagen", "image", mx, my, mw, mh,
                  objetos={"general": [props(imageUrl=url)], "imageScaling": [props(imageScalingType="Fill")]},
                  fondo=False)
        ventana = json.loads((PROCESSED / "tablero_mapa.json").read_text(encoding="utf-8"))["ventana"]
        concesion = columna_campo("MapaConcesiones", "Concesion")
        p.agregar(
            "mapa_burbujas", "scatterChart", mx, my, mw, mh,
            roles={"Category": [proyeccion(concesion)],
                   "X": [proyeccion(medida_campo("Mapa X"))],
                   "Y": [proyeccion(medida_campo("Mapa Y"))],
                   "Size": [proyeccion(medida_campo("Producción shale"))]},
            objetos={
                "categoryAxis": [props(show=False, start=float(ventana["x"]),
                                       end=float(ventana["x"] + ventana["ancho"]), gridlineShow=False,
                                       showAxisTitle=False)],
                "valueAxis": [props(show=False, start=float(-(ventana["y"] + ventana["alto"])),
                                    end=float(-ventana["y"]), gridlineShow=False, showAxisTitle=False)],
                "dataPoint": [{"properties": {"fill": color_medida("Color mapa")},
                               "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
                "categoryLabels": [props(show=False)],
                "legend": [props(show=False)],
                "plotArea": [props(transparency=100.0)],
            },
            contenedor={"padding": [props(top=0, bottom=0, left=0, right=0)]},
            fondo=False,
        )
        lx = mx + mw + 16
        p.agregar(
            "mapa_ranking", "tableEx", lx, my, M + 740 - 12 - lx, mh,
            roles={"Values": [proyeccion(concesion, "Concesión"),
                              proyeccion(medida_campo("Producción shale"), "boe/d"),
                              proyeccion(medida_campo("Variación shale"), "Var.")]},
            objetos={
                "grid": [props(gridVertical=False, gridHorizontal=True, gridHorizontalColor=color("#1a2e4a"),
                               rowPadding=4, textSize=9.0)],
                "columnHeaders": [props(fontColor=color(TEXTO_SUAVE), backColor=color(TARJETA), fontSize=8.0)],
                "values": [props(fontColorPrimary=color(TEXTO), backColorPrimary=color(TARJETA),
                                 fontColorSecondary=color(TEXTO), backColorSecondary=color(TARJETA))],
                "total": [props(totals=False)],
            },
            orden={"sort": [{"field": medida_campo("Producción shale"), "direction": "Descending"}]},
            fondo=False,
        )

    # --- precio o volumen ----------------------------------------------------
    fichas = [("Producción total", "kboe/d"), ("Petróleo shale", "kbbl/d"), ("Precio del crudo", "US$/bbl"),
              ("Lifting cost", "US$/boe")]
    ancho = (w2 - 3 * 12) / 4
    for i, (medida, unidad) in enumerate(fichas):
        tarjeta(p, f"op_{i}", medida, x2 + i * (ancho + 12), y1, ancho, 100, titulo=f"{medida} · {unidad}",
                tamanio=20.0)
        tarjeta(p, f"op_var_{i}", f"Variación {medida.lower()}", x2 + i * (ancho + 12), y1 + 104, ancho, 44,
                tamanio=11.0, tinte=CIAN)
        p.visuales[-1]["visual"]["visualContainerObjects"]["background"] = [props(show=False)]
        p.visuales[-1]["visual"]["visualContainerObjects"]["border"] = [props(show=False)]
    p.agregar(
        "precio_volumen", "lineClusteredColumnComboChart", x2, y1 + 156, w2, h1 - 156,
        roles={"Category": [proyeccion(eje)],
               "Y": [proyeccion(medida_campo("Serie producción total"), "Producción total, kboe/d"),
                     proyeccion(medida_campo("Serie petróleo shale"), "Petróleo shale, kbbl/d")],
               "Y2": [proyeccion(medida_campo("Serie precio del crudo"), "Precio del crudo, US$/bbl")]},
        objetos=ejes(labels=[props(show=False)],
                     dataPoint=serie_colores(("Serie producción total", APAGADO), ("Serie petróleo shale", CIAN),
                                             ("Serie precio del crudo", AMBAR))),
        titulo_medida="Título operativo",
        orden={"sort": [{"field": eje, "direction": "Ascending"}]},
    )

    # --- mercado ---------------------------------------------------------------
    y3, h3 = 608, 368
    marco(p, "mercado_marco", "Título mercado", M, y3, 740, h3)
    fichas = [("Precio del ADR", TEXTO), ("Retorno del día", TEXTO), ("Retorno anormal", CIAN),
              ("Anormal acumulado 4 ruedas", CIAN), ("Estadístico t", TEXTO_SUAVE),
              ("Riesgo país ese día", TEXTO_SUAVE)]
    ancho = (740 - 24 - 2 * 12) / 3
    for i, (medida, tinte) in enumerate(fichas):
        fx = M + 12 + (i % 3) * (ancho + 12)
        fy = y3 + 96 + (i // 3) * 132
        tarjeta(p, f"merc_{i}", medida, fx, fy, ancho, 120, titulo=medida, tamanio=20.0, tinte=tinte)
    p.agregar(
        "reaccion", "clusteredColumnChart", x2, y3, w2, h3,
        roles={"Category": [proyeccion(eje)], "Y": [proyeccion(medida_campo("Serie retorno anormal"))]},
        objetos=ejes(
            legend=[props(show=False)],
            dataPoint=[{"properties": {"fill": color_medida("Color reacción")},
                        "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
        ),
        titulo="Retorno anormal en cada balance: lo que la acción se movió más allá de Vista y el Brent",
        orden={"sort": [{"field": eje, "direction": "Ascending"}]},
    )
    return p


def main() -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.parse_args()
    for carpeta in (MODELO, REPORTE):
        if carpeta.exists():
            # Se conserva la caché local de Desktop (.pbi): pisarla obliga a
            # recargar todo al abrir.
            for hijo in carpeta.iterdir():
                if hijo.name != ".pbi":
                    shutil.rmtree(hijo) if hijo.is_dir() else hijo.unlink()
    escribir(SALIDA / f"{NOMBRE}.pbip", {
        "$schema": f"{ESQUEMA}/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{NOMBRE}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    escribir_modelo()
    escribir_reporte()
    log(f"{rel(SALIDA / (NOMBRE + '.pbip'))} · {len(TABLAS) + 1} tablas · {len(MEDIDAS_DAX)} medidas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
