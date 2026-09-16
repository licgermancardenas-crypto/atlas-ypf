"""La producción de YPF por cuenca, provincia, concesión, yacimiento y localidad.

Por qué existe: el consolidado dice cuánto produce la compañía; el territorio
dice de dónde sale y qué se está apagando. Un trimestre récord con la producción
concentrándose en tres concesiones de Vaca Muerta y el convencional cayendo es
una historia distinta a un crecimiento parejo, y esa diferencia es la que se
mira cuando se valúa una petrolera.

transform/ypf_production.py deja las cinco dimensiones como series mensuales.
Acá se pasan a trimestres —promedio diario del trimestre, que es como la
compañía informa su producción— y se agrega el corte por tipo de recurso, que
es lo que separa el shale del convencional.

Entrada: data/processed/ypf_dimensiones.json
Salida:  data/processed/tablero_territorio.parquet + .json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, base_parser, human, log, record, rel, save_json, save_parquet  # noqa: E402

ENTRADA = PROCESSED / "ypf_dimensiones.json"
SALIDA = PROCESSED / "tablero_territorio.parquet"
SALIDA_JSON = PROCESSED / "tablero_territorio.json"

DESDE = "2019Q1"
DIMENSIONES = {"cuenca": "Cuenca", "provincia": "Provincia", "concesion": "Concesión",
               "yacimiento": "Yacimiento", "localidad": "Localidad"}
# Las series vienen en volumen del mes: petróleo en barriles y gas ya en boe.
FLUIDOS = ["oil_convencional", "oil_shale", "oil_tight", "gas_convencional", "gas_shale", "gas_tight"]


def main() -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.parse_args()
    if not ENTRADA.exists():
        raise SystemExit("falta ypf_dimensiones.json; correr transform/ypf_production.py")

    datos = json.loads(ENTRADA.read_text(encoding="utf-8"))
    meses = pd.PeriodIndex(datos["fechas"], freq="M")
    dias = pd.Series(datos["dias"], index=meses, dtype=float)
    trimestres = meses.asfreq("Q")
    # Solo trimestres con sus tres meses: uno suelto daría un promedio diario falso.
    completos = {t for t, cuenta in pd.Series(trimestres).value_counts().items() if cuenta == 3}

    filas = []
    for clave, etiqueta in DIMENSIONES.items():
        for miembro in datos["dimensiones"].get(clave, {}).get("miembros", []):
            # Un miembro puede no tener un fluido: esa serie no viene en el JSON.
            series = {f: pd.Series(miembro.get(f) or [0.0] * len(meses), index=meses, dtype=float) for f in FLUIDOS}
            marco = pd.DataFrame(series)
            marco["dias"] = dias
            marco["trimestre"] = trimestres
            marco = marco[marco["trimestre"].isin(completos) & (marco["trimestre"] >= pd.Period(DESDE, "Q"))]
            for trimestre, grupo in marco.groupby("trimestre", observed=True):
                dias_trimestre = float(grupo["dias"].sum())
                if not dias_trimestre:
                    continue
                volumen = {f: float(grupo[f].sum()) for f in FLUIDOS}
                oil = sum(v for f, v in volumen.items() if f.startswith("oil"))
                gas = sum(v for f, v in volumen.items() if f.startswith("gas"))
                filas.append({
                    "dimension": etiqueta,
                    "miembro": miembro["nombre"],
                    "periodo": str(trimestre),
                    "boed": (oil + gas) / dias_trimestre,
                    "oil_bd": oil / dias_trimestre,
                    "gas_boed": gas / dias_trimestre,
                    "shale_boed": (volumen["oil_shale"] + volumen["gas_shale"]) / dias_trimestre,
                    "convencional_boed": (volumen["oil_convencional"] + volumen["gas_convencional"]) / dias_trimestre,
                    "tight_boed": (volumen["oil_tight"] + volumen["gas_tight"]) / dias_trimestre,
                })

    tabla = pd.DataFrame(filas)
    if tabla.empty:
        raise SystemExit("no se armó ninguna serie por territorio")
    tabla["participacion"] = tabla["boed"] / tabla.groupby(["dimension", "periodo"])["boed"].transform("sum")
    tabla = tabla.sort_values(["dimension", "miembro", "periodo"]).reset_index(drop=True)

    ultimo = tabla["periodo"].max()
    bytes_parquet = save_parquet(tabla, SALIDA)
    payload = {
        "generado": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fuente": "Secretaría de Energía, series SESCO por yacimiento (vía transform/ypf_production.py)",
        "unidades": {"boed": "boe/d, promedio del trimestre; producción bruta operada"},
        "dimensiones": list(DIMENSIONES.values()),
        "trimestres": sorted(tabla["periodo"].unique()),
        "ultimo": ultimo,
        "miembros_por_dimension": {d: int(g["miembro"].nunique()) for d, g in tabla.groupby("dimension")},
        "nota": ("Bruta operada: incluye la parte de los socios en las áreas que YPF opera. No es la producción "
                 "neta del release, que es la que se cruza con los estados."),
    }
    bytes_json = save_json(payload, SALIDA_JSON, indent=2)
    record(
        "transform/tablero-territorio",
        rows=int(len(tabla)),
        bytes=int(bytes_parquet + bytes_json),
        outputs=[rel(SALIDA), rel(SALIDA_JSON)],
        note=f"5 dimensiones, {tabla['periodo'].min()}–{ultimo}",
    )
    log(f"{rel(SALIDA)} ({human(bytes_parquet)}) · {len(tabla)} filas · "
        f"{tabla['miembro'].nunique()} miembros · hasta {ultimo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
