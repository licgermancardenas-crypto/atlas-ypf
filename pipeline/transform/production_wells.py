"""Normaliza la producción no convencional cruda en el panel pozo-mes del proyecto.

Entrada (data/raw/production/, la baja pipeline/ingest/production_wells.py):
- no_convencional.csv  : una fila por pozo-mes con producción, operador y ubicación
- padron_pozos.csv     : fecha de primera producción declarada por pozo
- pozos_cap_iv.csv     : ficha del pozo (fechas de perforación/terminación)

Salidas (data/processed/):
- production_wells.parquet : panel pozo-mes limpio, en unidades de mercado (bbl/boe)
- wells.parquet            : una fila por pozo (operador, área, geo, acumulados)
- production_summary.json  : series mensuales agregadas para el frontend

Decisiones que conviene tener presentes:
- La fuente reporta petróleo en m3/mes y gas en Mm3/mes; acá se pasa todo a bbl
  y boe, que es la unidad en la que YPF reporta y la que hace comparable el dato
  operativo con el financiero.
- Algunos pozos traen las coordenadas invertidas (la latitud en el campo de
  longitud); se detecta por bounding box y se corrige, en vez de tirar la fila.
- El operador de un pozo cambia con el tiempo (cesiones de área): el panel
  conserva el operador de cada mes y la dimensión guarda el último.
- `mes_prod` cuenta meses desde la primera producción efectiva del pozo: es el
  eje sobre el que después se fitean las curvas de Arps (decline_curves.py).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    LAT_RANGE,
    LON_RANGE,
    M3_TO_BBL,
    MM3_TO_BOE,
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

SRC_NC = RAW / "production" / "no_convencional.csv"
SRC_PADRON = RAW / "production" / "padron_pozos.csv"
SRC_CAP_IV = RAW / "production" / "pozos_cap_iv.csv"

OUT_PANEL = PROCESSED / "production_wells.parquet"
OUT_WELLS = PROCESSED / "wells.parquet"
OUT_SUMMARY = PROCESSED / "production_summary.json"

# Solo las columnas que se usan: el CSV crudo pesa 145 MB y trae 40.
NC_TEXT_COLS = [
    "empresa",
    "sigla",
    "cuenca",
    "provincia",
    "formacion",
    "areapermisoconcesion",
    "areayacimiento",
    "sub_tipo_recurso",
    "clasificacion",
    "tipopozo",
    "tipoestado",
    "tipoextraccion",
]
NC_NUM_COLS = [
    "idpozo",
    "anio",
    "mes",
    "coordenadax",
    "coordenaday",
    "prod_pet",
    "prod_gas",
    "prod_agua",
    "tef",
]

RENAME = {
    "idpozo": "pozo_id",
    "empresa": "operador",
    "areapermisoconcesion": "concesion",
    "areayacimiento": "yacimiento",
    "sub_tipo_recurso": "recurso",
    "tipopozo": "tipo_pozo",
    "tipoestado": "estado",
    "tipoextraccion": "extraccion",
    "prod_agua": "agua_m3",
    "tef": "dias_efectivos",
}

# Los nombres vienen con razón social completa y variantes; el análisis solo
# necesita distinguir a los tres comparables del brief del resto del panel.
OPERADOR_CANON = [
    ("YPF", "YPF"),
    ("YSUR", "YPF"),  # subsidiaria de YPF, opera varias áreas del bloque
    ("VISTA", "Vista Energy"),
    ("PAMPA", "Pampa Energia"),
    ("PETROLERA ACONCAGUA", "Pampa Energia"),
    ("SHELL", "Shell"),
    ("PAN AMERICAN", "Pan American Energy"),
    ("PLUSPETROL", "Pluspetrol"),
    ("TECPETROL", "Tecpetrol"),
    ("TOTAL", "TotalEnergies"),
    ("CHEVRON", "Chevron"),
    ("EXXON", "ExxonMobil"),
    ("WINTERSHALL", "Wintershall"),
    ("CAPEX", "Capex"),
    ("PHOENIX", "Phoenix Global Resources"),
]


def canon_operador(nombre: pd.Series) -> pd.Series:
    """Agrupa razones sociales bajo el nombre comercial del operador."""
    upper = nombre.fillna("").str.upper()
    out = nombre.fillna("Sin dato").astype("object")
    for patron, canonico in OPERADOR_CANON:
        out = out.mask(upper.str.contains(patron, regex=False), canonico)
    return out.astype("string")


def fix_coords(df: pd.DataFrame) -> pd.DataFrame:
    """Corrige los pozos con lat/lon invertidas y anula lo que caiga fuera del país."""
    lon = df["coordenadax"].copy()
    lat = df["coordenaday"].copy()

    lon_ok = lon.between(*LON_RANGE) & lat.between(*LAT_RANGE)
    invertidas = ~lon_ok & lat.between(*LON_RANGE) & lon.between(*LAT_RANGE)
    if invertidas.any():
        log(f"  coordenadas invertidas corregidas: {int(invertidas.sum()):,} filas")
        lon_inv = df.loc[invertidas, "coordenaday"]
        lat_inv = df.loc[invertidas, "coordenadax"]
        lon.loc[invertidas] = lon_inv
        lat.loc[invertidas] = lat_inv

    fuera = ~(lon.between(*LON_RANGE) & lat.between(*LAT_RANGE))
    if fuera.any():
        log(f"  coordenadas fuera de la Argentina, se anulan: {int(fuera.sum()):,} filas")
        lon.loc[fuera] = np.nan
        lat.loc[fuera] = np.nan

    df["lon"] = lon.astype("float32")
    df["lat"] = lat.astype("float32")
    return df.drop(columns=["coordenadax", "coordenaday"])


def cargar_panel() -> pd.DataFrame:
    log(f"leyendo {rel(SRC_NC)} ({human(SRC_NC.stat().st_size)})")
    df = pd.read_csv(
        SRC_NC,
        usecols=NC_TEXT_COLS + NC_NUM_COLS,
        dtype={col: "string" for col in NC_TEXT_COLS},
        encoding="utf-8-sig",
        low_memory=False,
    )
    log(f"  {len(df):,} filas crudas, {df.idpozo.nunique():,} pozos")

    df = df.rename(columns=RENAME)
    df["fecha"] = pd.to_datetime(dict(year=df.anio, month=df.mes, day=1))
    df["anio"] = df.anio.astype("int16")
    df["mes"] = df.mes.astype("int8")
    df["pozo_id"] = df.pozo_id.astype("int32")

    # Unidades de mercado: la fuente da petróleo en m3 y gas en Mm3 (miles de m3).
    df["petroleo_bbl"] = df.pop("prod_pet") * M3_TO_BBL
    df["gas_boe"] = df.pop("prod_gas") * MM3_TO_BOE
    df["boe"] = df.petroleo_bbl + df.gas_boe

    # Producción negativa: son ajustes contables de la fuente, no producción.
    negativos = (df[["petroleo_bbl", "gas_boe"]] < 0).any(axis=1)
    if negativos.any():
        log(f"  filas con producción negativa (ajustes de la fuente), a 0: {int(negativos.sum())}")
        cols = ["petroleo_bbl", "gas_boe", "boe"]
        df.loc[negativos, cols] = df.loc[negativos, cols].clip(lower=0)

    df["operador"] = canon_operador(df["operador"])
    df["es_vaca_muerta"] = df.formacion.fillna("").str.lower().str.strip().eq("vaca muerta")
    df = fix_coords(df)

    # mes_prod: meses corridos desde la primera producción efectiva del pozo. Se
    # cuenta sobre el calendario y no sobre las filas, para que un mes sin
    # reporte no corra la curva de declive un escalón hacia atrás.
    primera = df.loc[df.boe > 0].groupby("pozo_id").fecha.min().rename("primera_prod")
    df = df.merge(primera, on="pozo_id", how="left")
    delta = (df.fecha.dt.year - df.primera_prod.dt.year) * 12 + (
        df.fecha.dt.month - df.primera_prod.dt.month
    )
    df["mes_prod"] = (delta + 1).where(delta >= 0).astype("Int16")

    df = df.sort_values(["pozo_id", "fecha"], ignore_index=True)
    log(f"  panel: {len(df):,} filas pozo-mes, {int(df.es_vaca_muerta.sum()):,} de Vaca Muerta")
    return df


def cargar_padron() -> pd.DataFrame:
    """Primera producción declarada en el padrón (dato independiente del panel)."""
    pad = pd.read_csv(SRC_PADRON, encoding="utf-8-sig").rename(columns={"idpozo": "pozo_id"})
    pad["primera_prod_padron"] = pd.to_datetime(
        dict(year=pad.anio, month=pad.mes, day=1), errors="coerce"
    )
    return pad[["pozo_id", "primera_prod_padron"]]


def cargar_fichas() -> pd.DataFrame:
    """Ficha del capítulo IV: profundidad y fechas de perforación/terminación."""
    fichas = pd.read_csv(
        SRC_CAP_IV,
        usecols=[
            "idpozo",
            "cota",
            "profundidad",
            "adjiv_fecha_inicio_perf",
            "adjiv_fecha_fin_term",
        ],
        encoding="utf-8-sig",
        low_memory=False,
    ).rename(
        columns={
            "idpozo": "pozo_id",
            "adjiv_fecha_inicio_perf": "inicio_perforacion",
            "adjiv_fecha_fin_term": "fin_terminacion",
        }
    )
    for col in ("inicio_perforacion", "fin_terminacion"):
        fichas[col] = pd.to_datetime(fichas[col], errors="coerce")
    for col in ("cota", "profundidad"):
        fichas[col] = pd.to_numeric(fichas[col], errors="coerce").astype("float32")
    return fichas.drop_duplicates("pozo_id")


def construir_wells(panel: pd.DataFrame) -> pd.DataFrame:
    """Dimensión de pozos: atributos estables, acumulados y operador vigente."""
    ultimo = panel.groupby("pozo_id").tail(1).set_index("pozo_id")
    agg = panel.groupby("pozo_id").agg(
        primera_prod=("primera_prod", "min"),
        ultima_prod=("fecha", "max"),
        meses_reportados=("fecha", "size"),
        petroleo_acum_bbl=("petroleo_bbl", "sum"),
        gas_acum_boe=("gas_boe", "sum"),
        boe_acum=("boe", "sum"),
        pico_mensual_boe=("boe", "max"),
    )

    estables = [
        "sigla",
        "cuenca",
        "provincia",
        "formacion",
        "concesion",
        "yacimiento",
        "recurso",
        "clasificacion",
        "tipo_pozo",
        "es_vaca_muerta",
        "lat",
        "lon",
        "operador",
        "estado",
        "extraccion",
    ]
    wells = agg.join(ultimo[estables]).rename(
        columns={"operador": "operador_actual", "estado": "estado_ultimo"}
    )

    # Producción de los primeros 12 meses: la métrica que hace comparables pozos
    # de distinta antigüedad (y el input del ranking de productividad).
    boe_12m = panel[panel.mes_prod.between(1, 12)].groupby("pozo_id").boe.sum().rename("boe_12m")
    meses_activos = panel[panel.boe > 0].groupby("pozo_id").size().rename("meses_produccion")

    wells = (
        wells.join(boe_12m)
        .join(meses_activos)
        .reset_index()
        .merge(cargar_padron(), on="pozo_id", how="left")
        .merge(cargar_fichas(), on="pozo_id", how="left")
    )
    wells["meses_produccion"] = wells.meses_produccion.fillna(0).astype("int16")

    log(f"  wells: {len(wells):,} pozos ({int(wells.es_vaca_muerta.sum()):,} de Vaca Muerta)")
    return wells


def _serie_mensual(df: pd.DataFrame, por: str | None = None, top: int = 8) -> list[dict]:
    """Serie mensual en bbl/d y boe/d, opcionalmente abierta por una dimensión."""
    dias = df.fecha.dt.days_in_month
    tmp = df.assign(
        petroleo_bd=df.petroleo_bbl / dias,
        gas_boed=df.gas_boe / dias,
        boed=df.boe / dias,
    )
    if por:
        ranking = tmp.groupby(por).boe.sum().nlargest(top).index
        tmp = tmp[tmp[por].isin(ranking)]

    claves = ["fecha"] + ([por] if por else [])
    g = (
        tmp.groupby(claves, observed=True)
        .agg(
            petroleo_bd=("petroleo_bd", "sum"),
            gas_boed=("gas_boed", "sum"),
            boed=("boed", "sum"),
            pozos=("pozo_id", "nunique"),
        )
        .reset_index()
    )

    g["fecha"] = g.fecha.dt.strftime("%Y-%m")
    for col in ("petroleo_bd", "gas_boed", "boed"):
        g[col] = g[col].round(1)
    return g.to_dict("records")


def construir_summary(panel: pd.DataFrame, wells: pd.DataFrame) -> dict:
    """Agregados livianos para el frontend (el browser nunca lee el parquet)."""
    activo = panel[panel.boe > 0]
    vm = activo[activo.es_vaca_muerta]

    return {
        "generado": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fuente": "Secretaria de Energia (datos.energia.gob.ar), capitulo IV",
        "unidades": {"petroleo_bd": "bbl/d", "gas_boed": "boe/d", "boed": "boe/d"},
        "cobertura": {
            "desde": panel.fecha.min().strftime("%Y-%m"),
            "hasta": panel.fecha.max().strftime("%Y-%m"),
            "pozos": int(wells.pozo_id.nunique()),
            "pozos_vaca_muerta": int(wells.es_vaca_muerta.sum()),
            "operadores": int(panel.operador.nunique()),
        },
        "vaca_muerta_total": _serie_mensual(vm),
        "vaca_muerta_por_operador": _serie_mensual(vm, "operador", top=8),
        "ypf_vaca_muerta": _serie_mensual(vm[vm.operador == "YPF"]),
        "no_convencional_por_formacion": _serie_mensual(activo, "formacion", top=6),
    }


def main() -> int:
    args = base_parser("Normaliza la produccion no convencional a panel pozo-mes").parse_args()

    faltantes = [p for p in (SRC_NC, SRC_PADRON, SRC_CAP_IV) if not p.exists()]
    if faltantes:
        log(f"faltan crudos: {', '.join(rel(p) for p in faltantes)}")
        log("correr antes: python pipeline/ingest/production_wells.py")
        return 1

    if OUT_PANEL.exists() and not args.force:
        if OUT_PANEL.stat().st_mtime > SRC_NC.stat().st_mtime:
            log(f"{rel(OUT_PANEL)} es mas nuevo que el crudo, se saltea (--force para rehacer)")
            return 0

    panel = cargar_panel()
    wells = construir_wells(panel)
    summary = construir_summary(panel, wells)

    salidas = [
        (OUT_PANEL, len(panel), save_parquet(panel, OUT_PANEL)),
        (OUT_WELLS, len(wells), save_parquet(wells, OUT_WELLS)),
        (OUT_SUMMARY, len(summary["vaca_muerta_total"]), save_json(summary, OUT_SUMMARY)),
    ]
    for destino, filas, size in salidas:
        log(f"escrito {rel(destino)} - {filas:,} filas, {human(size)}")

    record(
        "production_wells",
        source=rel(SRC_NC),
        outputs=[rel(destino) for destino, _, _ in salidas],
        rows_panel=len(panel),
        wells=len(wells),
        wells_vaca_muerta=int(wells.es_vaca_muerta.sum()),
        periodo=[panel.fecha.min().strftime("%Y-%m"), panel.fecha.max().strftime("%Y-%m")],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
