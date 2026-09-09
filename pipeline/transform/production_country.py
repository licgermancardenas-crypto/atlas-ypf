"""Producción nacional por cuenca, provincia, empresa y yacimiento.

Entrada: data/raw/production/sesco/*.csv  (ingest/production_country.py)
Salida:  data/processed/country_production.json

Qué habilita: hasta acá el proyecto solo miraba el no convencional, así que
podía decir cuánto creció el shale pero no qué parte del total era. Estas series
suman el convencional y traen el campo `concepto`, que separa convencional,
shale y tight en la misma fila. Con eso se puede contestar lo que un analista
pregunta después del titular: cuando el shale de YPF crece 47%, ¿la compañía
crece o está tapando la caída de sus áreas viejas?

El JSON sale en formato columnar —una lista de fechas y un array por serie— y no
como lista de objetos. Son cuatro dimensiones por trece miembros por doscientos
meses: repetir el nombre de cada campo en cada fila cuesta más de un megabyte en
nombres de claves.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
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
)

ORIGEN = RAW / "production" / "sesco"
SALIDA = PROCESSED / "country_production.json"

# Cada dimensión sale de un archivo y de una columna. Las de yacimiento y
# concesión salen del mismo CSV: el de yacimiento trae también el área de
# concesión, la empresa, la cuenca y la provincia, así que la quinta dimensión
# no cuesta una descarga más.
DIMENSIONES = {
    "cuenca": ("cuenca", "cuenca"),
    "provincia": ("provincia", "provincia"),
    "empresa": ("empresa", "empresa"),
    "concesion": ("yacimiento", "areapermisoconcesion"),
    "yacimiento": ("yacimiento", "areayacimiento"),
}

# Cuántos miembros entran por dimensión antes de agrupar en "Otros". Doce es lo
# que entra en una leyenda sin que el gráfico se vuelva un plato de fideos.
TOPE = 12

# Los nombres comerciales de los tres comparables del caso, para que no queden
# escondidos detrás de la razón social en el ranking.
CANON = [
    ("YPF", "YPF"),
    ("VISTA", "Vista Energy"),
    ("PAMPA", "Pampa Energía"),
    ("PETROLERA ACONCAGUA", "Pampa Energía"),
    ("TECPETROL", "Tecpetrol"),
    ("PAN AMERICAN", "Pan American Energy"),
    ("SHELL", "Shell"),
    ("TOTAL", "TotalEnergies"),
    ("CHEVRON", "Chevron"),
    ("PLUSPETROL", "Pluspetrol"),
    ("CAPEX", "Capex"),
    ("WINTERSHALL", "Wintershall"),
]


def canon_empresa(serie: pd.Series) -> pd.Series:
    upper = serie.fillna("").str.upper()
    salida = serie.fillna("Sin dato").astype("object")
    for patron, nombre in CANON:
        salida = salida.mask(upper.str.contains(patron, regex=False), nombre)
    return salida.astype("string")


def clasificar_concepto(serie: pd.Series) -> pd.Series:
    """El campo `concepto` viene con nombres distintos entre petróleo y gas
    ("Shale Oil" contra "Shale Gas", "Tight_oil" contra "Tight_gas")."""
    texto = serie.fillna("").str.lower()
    return np.select(
        [texto.str.contains("shale"), texto.str.contains("tight")],
        ["shale", "tight"],
        default="convencional",
    )


def leer(slug: str) -> pd.DataFrame | None:
    ruta = ORIGEN / f"{slug}.csv"
    if not ruta.exists():
        log(f"  falta {rel(ruta)}, se saltea")
        return None
    df = pd.read_csv(ruta, encoding="utf-8-sig", low_memory=False)
    df["fecha"] = pd.to_datetime(df.indice_tiempo, errors="coerce")
    df = df[df.fecha.notna()].copy()
    df["concepto"] = clasificar_concepto(df.concepto)
    df["dias"] = df.fecha.dt.days_in_month
    return df


def a_caudal(df: pd.DataFrame, fluido: str) -> pd.Series:
    """Volumen del mes -> bbl/d si es petróleo, boe/d si es gas.

    La unidad se deduce del nombre de la columna y no del fluido: la serie de
    petróleo trae `cantidad_m3` y la de gas `cantidad_mm3`, en miles de m3. Leer
    el nombre es más seguro que asumir la convención, y si mañana la fuente
    cambia una de las dos, esto falla ruidosamente en vez de devolver un caudal
    mil veces menor sin avisar.
    """
    if "cantidad_mm3" in df.columns:
        return df.cantidad_mm3 * MM3_TO_BOE / df.dias
    if "cantidad_m3" in df.columns:
        return df.cantidad_m3 * (M3_TO_BBL if fluido == "oil" else MM3_TO_BOE) / df.dias
    raise RuntimeError(
        f"la serie de {fluido} no trae ni cantidad_m3 ni cantidad_mm3: {list(df.columns)}"
    )


def serie_pais(fluido: str) -> pd.DataFrame | None:
    df = leer(f"{fluido}_pais")
    if df is None:
        return None
    df["caudal"] = a_caudal(df, fluido)
    tabla = (
        df.pivot_table(index="fecha", columns="concepto", values="caudal", aggfunc="sum")
        .fillna(0)
        .round(1)
    )
    tabla.columns = [f"{fluido}_{columna}" for columna in tabla.columns]
    tabla[f"{fluido}_total"] = tabla.sum(axis=1).round(1)
    return tabla


def serie_dimension(fluido: str, dimension: str) -> pd.DataFrame | None:
    archivo, columna = DIMENSIONES[dimension]
    df = leer(f"{fluido}_{archivo}")
    if df is None:
        return None
    if columna not in df.columns:
        log(f"  {fluido}_{dimension}: no trae la columna {columna}")
        return None

    df["miembro"] = canon_empresa(df[columna]) if dimension == "empresa" else df[columna].astype("string")
    df["caudal"] = a_caudal(df, fluido)
    return df.groupby(["fecha", "miembro", "concepto"], observed=True).caudal.sum().reset_index()


def armar_dimension(dimension: str) -> dict | None:
    partes = {fluido: serie_dimension(fluido, dimension) for fluido in ("oil", "gas")}
    if partes["oil"] is None:
        return None

    # El ranking se hace sobre el último año disponible y no sobre la historia
    # entera: interesa quién produce hoy, no quién produjo en 2009.
    oil = partes["oil"]
    ultimo_anio = oil.fecha.max().year
    ranking = (
        oil[oil.fecha.dt.year == ultimo_anio]
        .groupby("miembro", observed=True)
        .caudal.sum()
        .nlargest(TOPE)
        .index.tolist()
    )

    fechas = sorted(oil.fecha.unique())
    indice = pd.DatetimeIndex(fechas)
    miembros: list[dict] = []

    for nombre in [*ranking, "Otros"]:
        registro: dict = {"nombre": nombre}
        for fluido, datos in partes.items():
            if datos is None:
                continue
            seleccion = (
                datos[datos.miembro.isin(ranking)]
                if nombre == "Otros"
                else datos[datos.miembro == nombre]
            )
            if nombre == "Otros":
                seleccion = datos[~datos.miembro.isin(ranking)]

            pivot = (
                seleccion.pivot_table(
                    index="fecha", columns="concepto", values="caudal", aggfunc="sum"
                )
                .reindex(indice)
                .fillna(0)
            )
            for concepto in ("convencional", "shale", "tight"):
                if concepto not in pivot.columns:
                    pivot[concepto] = 0.0
            registro[f"{fluido}_total"] = pivot.sum(axis=1).round(1).tolist()
            for concepto in ("convencional", "shale", "tight"):
                registro[f"{fluido}_{concepto}"] = pivot[concepto].round(1).tolist()
        miembros.append(registro)

    return {
        "fechas": [fecha.strftime("%Y-%m") for fecha in indice],
        "miembros": miembros,
    }


def main() -> int:
    args = base_parser("Arma la serie de produccion nacional por dimension").parse_args()

    if not ORIGEN.exists():
        log(f"falta {rel(ORIGEN)}; correr antes pipeline/ingest/production_country.py")
        return 1

    if SALIDA.exists() and not args.force:
        crudos = list(ORIGEN.glob("*.csv"))
        if crudos and SALIDA.stat().st_mtime > max(p.stat().st_mtime for p in crudos):
            log(f"{rel(SALIDA)} esta al dia, se saltea (--force para rehacer)")
            return 0

    log("armando el total pais")
    # Sin fillna: la serie de gas termina antes que la de petróleo, y rellenar
    # con cero los meses que le faltan inventaría una caída del gas a cero en vez
    # de decir "todavía no hay dato".
    pais = pd.concat([s for s in (serie_pais("oil"), serie_pais("gas")) if s is not None], axis=1)
    pais["boed_total"] = (pais.get("oil_total", 0).fillna(0) + pais.get("gas_total", 0).fillna(0)).round(1)

    # Chequeo de unidades sobre el último mes que sí tiene gas: si viniera en m3
    # y no en miles, la producción del país daría cien millones de boe/d.
    gas = pais.get("gas_total", pd.Series(dtype=float)).dropna()
    if len(gas):
        log(f"  gas de {gas.index[-1]:%Y-%m}: {float(gas.iloc[-1]):,.0f} boe/d")
        if float(gas.iloc[-1]) > 5_000_000:
            log("  ATENCION: el gas parece venir en m3 y no en miles; revisar a_caudal()")
    dimensiones = {}
    for dimension in DIMENSIONES:
        log(f"armando {dimension}")
        armada = armar_dimension(dimension)
        if armada:
            dimensiones[dimension] = armada
            log(f"  {len(armada['miembros'])} miembros, {len(armada['fechas'])} meses")

    pais_json = pais.reset_index()
    pais_json["fecha"] = pais_json.fecha.dt.strftime("%Y-%m")

    payload = {
        "generado": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fuente": "Secretaria de Energia, series SESCO + capitulo IV",
        "unidades": {"oil": "bbl/d", "gas": "boe/d", "boed_total": "boe/d"},
        "nota": (
            "Produccion bruta operada: incluye la participacion de los socios, asi que es "
            "mayor que la que cada compania consolida en su balance."
        ),
        "cobertura": {
            "desde": str(pais_json.fecha.iloc[0]),
            "hasta": str(pais_json.fecha.iloc[-1]),
        },
        "pais": pais_json.replace({np.nan: None}).to_dict("records"),
        "dimensiones": dimensiones,
    }

    bytes_salida = save_json(payload, SALIDA)
    log(f"escrito {rel(SALIDA)} - {human(bytes_salida)}")

    record(
        "production_country",
        source=rel(ORIGEN),
        outputs=[rel(SALIDA)],
        meses=len(pais_json),
        dimensiones=list(dimensiones),
        desde=payload["cobertura"]["desde"],
        hasta=payload["cobertura"]["hasta"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
