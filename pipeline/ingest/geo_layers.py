"""Datasets 9 y 10 — Capas vectoriales: concesiones, cuencas, yacimientos y límites.

Fuentes:
- datos.energia.gob.ar (Secretaría de Energía): shapefiles de concesiones de
  explotación, cuencas sedimentarias y yacimientos, en ZIP.
- IGN, por WFS (wms.ign.gob.ar/geoserver): provincias y departamentos en GeoJSON.
  El IGN no publica los shapefiles por URL directa —la descarga es por
  formulario— pero sí expone las mismas capas por WFS, que además permite pedir
  GeoJSON en EPSG:4326 y evitarse la conversión.

Todo crudo a data/raw/geo/. El recorte a la cuenca Neuquina, la simplificación
de geometrías y el armado de las capas para deck.gl son trabajo de
pipeline/transform/geo_layers.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    RAW,
    base_parser,
    download,
    http_session,
    human,
    is_fresh,
    log,
    record,
    rel,
    sha256,
)

DEST = RAW / "geo"

# Shapefiles de la Secretaría de Energía (CKAN de datos.energia.gob.ar).
SHAPEFILES = {
    "concessions": {
        "nombre": "Concesiones de explotación de hidrocarburos",
        "package": "81cfad0a-4162-4f85-ad71-837f5a5fae57",
        "resource": "48a306a3-d5da-4f28-8ab5-7f80767ffdec",
        "archivo": "produccin-hidrocarburos-concesiones-de-explotacin.zip",
        "subdir": "concessions",
    },
    "basins": {
        "nombre": "Cuencas sedimentarias",
        "package": "0d4a18ee-9371-439a-8a94-4f53a9822664",
        "resource": "c477f5a7-75cf-4123-ba7b-e298eb52abbd",
        "archivo": "exploracin-hidrocarburos-cuencas-sedimentarias.zip",
        "subdir": "basins",
    },
    "fields": {
        "nombre": "Yacimientos",
        "package": "7378520e-4d10-48a9-92e9-7e20e69a8277",
        "resource": "82f83e7e-5e07-4cf7-8015-0e01d2cfa51f",
        "archivo": "produccin-hidrocarburos-yacimientos.zip",
        "subdir": "fields",
    },
}

WFS = "https://wms.ign.gob.ar/geoserver/ows"
CAPAS_IGN = {
    "provincias": "ign:provincia",
    "departamentos": "ign:departamento",
}


def url_ckan(spec: dict) -> str:
    return (
        f"http://datos.energia.gob.ar/dataset/{spec['package']}"
        f"/resource/{spec['resource']}/download/{spec['archivo']}"
    )


def bajar_shapefile(slug: str, spec: dict, args) -> bool:
    key = f"geo/{spec['subdir']}"
    if is_fresh(key, args.force, args.max_age_days):
        log(f"{slug}: fresco en el manifest, se saltea (--force para rebajar)")
        return False

    destino = DEST / spec["subdir"] / spec["archivo"]
    download(url_ckan(spec), destino, session=http_session())
    size = destino.stat().st_size

    record(
        key,
        dataset_id=9,
        source="datos.energia.gob.ar",
        nombre=spec["nombre"],
        package=spec["package"],
        resource_id=spec["resource"],
        url=url_ckan(spec),
        path=rel(destino),
        bytes=size,
        sha256=sha256(destino),
    )
    log(f"{slug}: {human(size)} -> {rel(destino)}")
    return True


def bajar_wfs(slug: str, capa: str, args) -> bool:
    """Una capa del IGN por WFS, ya en GeoJSON y EPSG:4326."""
    key = f"geo/boundaries/{slug}"
    if is_fresh(key, args.force, args.max_age_days):
        log(f"{slug}: fresco en el manifest, se saltea (--force para rebajar)")
        return False

    session = http_session({"Accept": "application/json"})
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": capa,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
    }
    response = session.get(WFS, params=params, timeout=600)
    response.raise_for_status()
    payload = response.json()

    features = payload.get("features")
    if not features:
        raise RuntimeError(f"el WFS del IGN devolvio {capa} sin features")

    destino = DEST / "boundaries" / f"{slug}.geojson"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    size = destino.stat().st_size

    record(
        key,
        dataset_id=10,
        source="IGN (WFS wms.ign.gob.ar/geoserver)",
        capa=capa,
        url=f"{WFS}?service=WFS&request=GetFeature&typeNames={capa}",
        path=rel(destino),
        rows=len(features),
        crs="EPSG:4326",
        bytes=size,
    )
    log(f"{slug}: {len(features):,} features, {human(size)} -> {rel(destino)}")
    return True


def main() -> int:
    args = base_parser("Baja las capas vectoriales de concesiones, cuencas y limites").parse_args()

    bajados, fallidos = 0, []

    for slug, spec in SHAPEFILES.items():
        try:
            if bajar_shapefile(slug, spec, args):
                bajados += 1
        except Exception as exc:  # noqa: BLE001 - una capa rota no corta el resto
            log(f"{slug}: FALLO {exc}")
            fallidos.append(slug)

    for slug, capa in CAPAS_IGN.items():
        try:
            if bajar_wfs(slug, capa, args):
                bajados += 1
        except Exception as exc:  # noqa: BLE001
            log(f"{slug}: FALLO {exc}")
            fallidos.append(slug)

    total = len(SHAPEFILES) + len(CAPAS_IGN)
    log(f"listo: {bajados}/{total} capas bajadas")
    if fallidos:
        log(f"ATENCION: fallaron {', '.join(fallidos)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
