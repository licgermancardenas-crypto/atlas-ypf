"""Arma la serie financiera trimestral de YPF a partir de los 6-K de EDGAR.

Por qué no sale del XBRL: EDGAR solo tiene tagueados los anuales del 20-F (y en
USD recién desde 2023). El dato trimestral —el que hace falta para explicar la
reacción del mercado al balance— vive en la tabla de highlights del earnings
release que YPF adjunta a cada 6-K. Este transform la parsea.

Entrada:  data/raw/financials/ypf/filings/*/  (los baja pipeline/ingest/financials_ypf.py)
Salidas:  data/processed/financials_ypf.parquet (panel trimestral ancho)
          data/processed/financials_ypf_long.parquet (kpi-período, con la fuente)
          data/processed/financials_ypf.json (series para el frontend)

El parseo es defensivo por necesidad: el layout de la tabla cambió tres veces
entre 2021 y 2026. Las columnas vienen partidas (el signo `(` de un negativo
queda en una celda y el `)` en la siguiente), los encabezados de período
aparecen duplicados en dos columnas contiguas y las filas de variación se
mezclan con las de valor. Por eso no se lee por posición fija: se ubica la fila
de encabezado por el patrón de período (2Q26, 1H25), se agrupan las columnas de
cada período y se toma el primer valor numérico de cada grupo.

Cada trimestre se toma del release donde es el trimestre titular; las columnas
de comparación de otros releases se usan solo para rellenar huecos, y en el
panel largo queda registrado de qué filing salió cada número.
"""

from __future__ import annotations

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

FILINGS = RAW / "financials" / "ypf" / "filings"

OUT_WIDE = PROCESSED / "financials_ypf.parquet"
OUT_LONG = PROCESSED / "financials_ypf_long.parquet"
OUT_JSON = PROCESSED / "financials_ypf.json"

RE_TRIMESTRE = re.compile(r"^([1-4])Q(\d{2})$")
RE_SEMESTRE = re.compile(r"^([12])H(\d{2})$")

# Los nombres de las filas cambian entre releases; se mapean a un nombre estable.
# El orden importa: el primer patrón que matchea gana.
KPI_MAP: list[tuple[str, str]] = [
    (r"^R&M Adj\.? EBITDA", ""),  # margen por barril de refino, no es el EBITDA
    (r"^Adjusted EBITDA$", "adj_ebitda_musd"),
    (r"^Revenues$", "revenues_musd"),
    (r"^Net Result$|^Net income$", "net_result_musd"),
    (r"^CAPEX$", "capex_musd"),
    (r"^FCF$", "fcf_musd"),
    (r"^Net Debt$", "net_debt_musd"),
    (r"^Net Leverage Ratio", "net_leverage_x"),
    (r"^Hydrocarbon Production", "produccion_kboed"),
    (r"^Crude Oil \(Kbbl/d\)", "petroleo_kbbld"),
    (r"^Natural Gas \(Mm3/d\)", "gas_mm3d"),
    (r"^NGL \(Kbbl/d\)", "ngl_kbbld"),
    (r"^Shale Oil Production", "shale_oil_kbbld"),
    (r"^Crude Oil Price", "precio_crudo_usd_bbl"),
    (r"^Natural Gas Price", "precio_gas_usd_mbtu"),
    (r"^Crude Oil Exports", "exportaciones_kbbld"),
    (r"^Total Lifting Cost", "lifting_cost_usd_boe"),
    (r"^Lifting cost shale", "lifting_shale_usd_boe"),
    (r"^Crude Processed", "crudo_procesado_kbbld"),
    (r"^Local Fuels Volume Sold", "combustibles_km3"),
    (r"^Local Fuels Net Price", "precio_combustibles_usd_m3"),
]

# KPI que el frontend grafica como serie principal.
KPI_FRONTEND = [
    "revenues_musd",
    "adj_ebitda_musd",
    "net_result_musd",
    "capex_musd",
    "fcf_musd",
    "net_debt_musd",
    "net_leverage_x",
    "produccion_kboed",
    "shale_oil_kbbld",
    "precio_crudo_usd_bbl",
    "lifting_cost_usd_boe",
]


def canon_kpi(label: str) -> str:
    label = re.sub(r"\s+", " ", str(label)).strip()
    label = re.sub(r"\s*\(\d\)$", "", label)  # llamadas al pie: "(1)", "(2)"
    for patron, nombre in KPI_MAP:
        if re.search(patron, label, re.IGNORECASE):
            return nombre
    return ""


def periodo_de(etiqueta: str) -> pd.Period | None:
    """'2Q26' -> Period 2026Q2. Los semestres y las columnas de variacion se ignoran."""
    etiqueta = str(etiqueta).strip()
    m = RE_TRIMESTRE.match(etiqueta)
    if not m:
        return None
    trimestre, anio = int(m.group(1)), 2000 + int(m.group(2))
    return pd.Period(year=anio, quarter=trimestre, freq="Q")


def a_numero(celdas: list[str]) -> float:
    """Primer numero de un grupo de celdas, respetando el parentesis del negativo.

    Los negativos vienen partidos: '(365' en una celda y ')' en la siguiente, y
    a veces el '%' queda solo. Se arma el token concatenando el grupo.
    """
    texto = "".join(c for c in celdas if c and c.lower() != "nan").strip()
    if not texto:
        return np.nan
    texto = texto.replace(",", "").replace("%", "").replace("$", "").strip()
    if texto in {"-", "--", "N/A", "N.M", "N.M.", "n/a"}:
        return np.nan
    negativo = texto.startswith("(")
    texto = texto.strip("()").strip()

    # Los releases de 2021-2022 usan el punto como separador de miles
    # ("6.160" son 6.160 millones, no 6,16). Se distingue por la forma: grupos
    # de exactamente tres digitos despues del punto. La compania no reporta
    # ningun KPI con tres decimales, asi que no hay ambiguedad real.
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", texto):
        texto = texto.replace(".", "")
    try:
        valor = float(texto)
    except ValueError:
        return np.nan
    return -valor if negativo else valor


def _fila_encabezado(tabla: pd.DataFrame) -> int | None:
    """Indice de la primera fila con al menos dos etiquetas de periodo."""
    for i in range(min(len(tabla), 6)):
        celdas = [str(c).strip() for c in tabla.iloc[i]]
        periodos = sum(bool(RE_TRIMESTRE.match(c) or RE_SEMESTRE.match(c)) for c in celdas)
        if periodos >= 2:
            return i
    return None


def _grupos_de_columnas(encabezado: pd.Series) -> dict[pd.Period, list[int]]:
    """Columnas que corresponden a cada trimestre.

    El encabezado repite la etiqueta en dos columnas contiguas y deja NaN en las
    de relleno; cada grupo va desde la columna que trae la etiqueta hasta la
    siguiente etiqueta distinta.
    """
    etiquetas = [str(c).strip() for c in encabezado]
    grupos: dict[pd.Period, list[int]] = {}
    actual: pd.Period | None = None

    for i, etiqueta in enumerate(etiquetas):
        es_periodo = bool(RE_TRIMESTRE.match(etiqueta) or RE_SEMESTRE.match(etiqueta))
        if etiqueta and etiqueta.lower() != "nan" and not es_periodo:
            actual = None  # columna de variacion (Y/Y, Q/Q) o texto: corta el grupo
            continue
        if es_periodo:
            periodo = periodo_de(etiqueta)
            actual = periodo
            if periodo is not None and periodo not in grupos:
                grupos[periodo] = []
        if actual is not None:
            grupos[actual].append(i)

    return grupos


def parsear_tabla(tabla: pd.DataFrame) -> list[dict]:
    """Extrae (kpi, periodo, valor) de una tabla de highlights."""
    fila_hdr = _fila_encabezado(tabla)
    if fila_hdr is None:
        return []
    grupos = _grupos_de_columnas(tabla.iloc[fila_hdr])
    if not grupos:
        return []

    columnas_valor = {i for cols in grupos.values() for i in cols}

    salida: list[dict] = []
    for _, fila in tabla.iloc[fila_hdr + 1 :].iterrows():
        celdas = [str(c) for c in fila]
        # El nombre del KPI no siempre esta en la primera columna: desde 2024 la
        # tabla abre con el segmento ("Financial", "Upstream") y el KPI va en la
        # siguiente. Se prueban todas las celdas de texto y gana la primera que
        # mapea a un KPI conocido.
        kpi = ""
        for i, celda in enumerate(celdas):
            if i in columnas_valor or not celda or celda.lower() == "nan":
                continue
            kpi = canon_kpi(celda)
            if kpi:
                break
        if not kpi:
            continue
        for periodo, columnas in grupos.items():
            valor = a_numero([celdas[i] for i in columnas if i < len(celdas)])
            if not np.isnan(valor):
                salida.append({"periodo": periodo, "kpi": kpi, "valor": valor})
    return salida


# Cada release trae, ademas de los highlights, una tabla por segmento (Upstream,
# Downstream, Gas & Power, Corporate) que repite filas como "Revenues" o
# "Adjusted EBITDA" con el numero del segmento. Estos cuatro KPI, en cambio,
# solo existen a nivel compania: su presencia identifica a la tabla consolidada
# sin ambiguedad y es lo que decide cual gana cuando dos tablas informan el
# mismo KPI. Por la misma razon no se extraen "EBITDA" ni "Operating income" a
# secas: desde 2024 el highlights dejo de traerlos y quedarian tomados del
# segmento. La metrica titular, la que mira el mercado, es el Adjusted EBITDA.
KPI_SOLO_CONSOLIDADOS = {"net_result_musd", "net_debt_musd", "fcf_musd", "net_leverage_x"}
KPI_CONSOLIDADOS = KPI_SOLO_CONSOLIDADOS | {"revenues_musd", "adj_ebitda_musd", "capex_musd"}


def _prioridad_tabla(observaciones: list[dict]) -> tuple[int, int, int]:
    kpis = {o["kpi"] for o in observaciones}
    return len(kpis & KPI_SOLO_CONSOLIDADOS), len(kpis & KPI_CONSOLIDADOS), len(kpis)


def leer_filing(carpeta: Path) -> tuple[list[dict], str]:
    """Devuelve las observaciones de un 6-K y la fecha de presentacion."""
    meta = json.loads((carpeta / "_meta.json").read_text(encoding="utf-8"))
    documentos = [p for p in carpeta.glob("*.htm")]
    observaciones: list[dict] = []

    for doc in documentos:
        contenido = doc.read_text(encoding="utf-8", errors="replace")
        if "EBITDA" not in contenido:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                tablas = pd.read_html(doc)
            except (ValueError, OSError):
                continue
        # Un mismo release trae la tabla de highlights y, mas abajo, los estados
        # contables completos, que repiten algunas filas con otra apertura. La
        # tabla que mapea mas KPI es la de highlights: se le da prioridad y las
        # demas solo rellenan lo que falte.
        parseadas = [parsear_tabla(t.dropna(axis=1, how="all")) for t in tablas]
        parseadas = [obs for obs in parseadas if obs]
        parseadas.sort(key=_prioridad_tabla, reverse=True)
        for orden, obs in enumerate(parseadas):
            observaciones.extend({**o, "orden_tabla": orden} for o in obs)

    return observaciones, meta.get("filing_date", "")


def recolectar() -> pd.DataFrame:
    """Recorre los 6-K y arma el panel largo (kpi, periodo, valor, fuente)."""
    carpetas = sorted(p for p in FILINGS.iterdir() if (p / "_meta.json").exists())
    log(f"revisando {len(carpetas):,} filings en {rel(FILINGS)}")

    filas: list[dict] = []
    con_datos = 0
    for carpeta in carpetas:
        observaciones, filing_date = leer_filing(carpeta)
        if not observaciones:
            continue
        con_datos += 1
        titular = max(o["periodo"] for o in observaciones)
        for obs in observaciones:
            filas.append(
                {
                    **obs,
                    "accession": carpeta.name,
                    "filing_date": filing_date,
                    # El trimestre titular del release es el dato original; las
                    # columnas comparativas de otro release solo rellenan huecos.
                    "es_titular": obs["periodo"] == titular,
                }
            )

    largo = pd.DataFrame(filas)
    if largo.empty:
        return largo

    log(f"  {con_datos} releases con tabla de highlights, {len(largo):,} observaciones")

    # Una observacion por (kpi, periodo): gana el release titular y, entre
    # varios, el mas reciente (una reexpresion posterior corrige a la anterior).
    largo = largo.sort_values(
        ["kpi", "periodo", "es_titular", "filing_date", "orden_tabla"],
        ascending=[True, True, False, False, True],
    )
    largo["duplicado"] = largo.duplicated(["kpi", "periodo"])
    return largo


def construir_panel(largo: pd.DataFrame) -> pd.DataFrame:
    unico = largo[~largo.duplicado]
    panel = unico.pivot(index="periodo", columns="kpi", values="valor").sort_index()
    panel.index = panel.index.astype(str)

    # Margen de EBITDA: la metrica con la que el mercado juzga el trimestre.
    if {"adj_ebitda_musd", "revenues_musd"} <= set(panel.columns):
        panel["margen_ebitda"] = (panel.adj_ebitda_musd / panel.revenues_musd).round(4)

    log(f"  panel: {len(panel):,} trimestres ({panel.index[0]} a {panel.index[-1]}), "
        f"{panel.shape[1]} KPI")
    return panel.reset_index().rename(columns={"periodo": "trimestre"})


def construir_json(panel: pd.DataFrame, largo: pd.DataFrame) -> dict:
    columnas = ["trimestre"] + [k for k in KPI_FRONTEND if k in panel.columns]
    serie = panel[columnas].replace({np.nan: None}).to_dict("records")

    cobertura = (
        largo[~largo.duplicado]
        .groupby("kpi")
        .agg(trimestres=("periodo", "nunique"), desde=("periodo", "min"), hasta=("periodo", "max"))
        .reset_index()
    )
    cobertura["desde"] = cobertura.desde.astype(str)
    cobertura["hasta"] = cobertura.hasta.astype(str)

    return {
        "generado": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fuente": "SEC EDGAR, tabla de highlights de los earnings releases 6-K de YPF",
        "unidades": "US$ millones salvo donde el nombre del KPI indique otra cosa",
        "trimestres": len(panel),
        "serie": serie,
        "cobertura_por_kpi": cobertura.to_dict("records"),
    }


def main() -> int:
    args = base_parser("Arma la serie financiera trimestral de YPF desde los 6-K").parse_args()

    if not FILINGS.exists():
        log(f"falta {rel(FILINGS)}; correr antes pipeline/ingest/financials_ypf.py")
        return 1

    if OUT_WIDE.exists() and not args.force:
        mas_nuevo = max(p.stat().st_mtime for p in FILINGS.glob("*/_meta.json"))
        if OUT_WIDE.stat().st_mtime > mas_nuevo:
            log(f"{rel(OUT_WIDE)} esta al dia, se saltea (--force para rehacer)")
            return 0

    largo = recolectar()
    if largo.empty:
        log("ningun 6-K con tabla de highlights parseable")
        return 1

    panel = construir_panel(largo)
    payload = construir_json(panel, largo)

    largo_out = largo.assign(periodo=largo.periodo.astype(str))
    salidas = [
        (OUT_WIDE, len(panel), save_parquet(panel, OUT_WIDE)),
        (OUT_LONG, len(largo_out), save_parquet(largo_out, OUT_LONG)),
        (OUT_JSON, len(payload["serie"]), save_json(payload, OUT_JSON)),
    ]
    for destino, filas, size in salidas:
        log(f"escrito {rel(destino)} - {filas:,} filas, {human(size)}")

    record(
        "financials_ypf",
        source=rel(FILINGS),
        outputs=[rel(d) for d, _, _ in salidas],
        trimestres=len(panel),
        desde=panel.trimestre.iloc[0],
        hasta=panel.trimestre.iloc[-1],
        kpis=int(panel.shape[1] - 1),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
