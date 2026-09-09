"""Datasets 9, 10 y contexto — Capas vectoriales del mapa.

Fuentes:
- datos.energia.gob.ar (Secretaría de Energía): shapefiles de concesiones de
  explotación, cuencas sedimentarias y yacimientos, en ZIP.
- IGN, por WFS (wms.ign.gob.ar/geoserver): provincias y departamentos en GeoJSON.
  El IGN no publica los shapefiles por URL directa —la descarga es por
  formulario— pero sí expone las mismas capas por WFS, que además permite pedir
  GeoJSON en EPSG:4326 y evitarse la conversión.
- IGN, también por WFS y acotado al recuadro de la cuenca: rutas nacionales y
  provinciales, localidades, ríos permanentes y ferrocarril. Es el contexto que
  convierte una nube de puntos en un mapa que se puede leer.
- datos.energia.gob.ar, infraestructura: refinerías, oleoductos y ductos de la
  Res. 319/93, gasoductos de transporte de ENARGAS, instalaciones empadronadas
  y terminales de despacho. Es la capa de logística: por dónde sale el crudo de
  la cuenca, dónde se trata y dónde se despacha.

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

# Infraestructura de hidrocarburos, también del CKAN de la Secretaría. Es la
# capa de logística del caso: por dónde sale el crudo de la cuenca, dónde se
# refina y dónde se despacha. Los ductos genéricos del IGN no sirven para esto
# —no distinguen un oleoducto de un caño de agua— y estas capas sí traen
# operador, fluido y traza.
INFRAESTRUCTURA = {
    "refinerias": {
        "nombre": "Refinerías de hidrocarburos",
        "package": "a9eed347-78ab-45c0-a489-b227fe42ee1b",
        "resource": "4399cb2d-c221-4b9a-9799-8fc008cefd77",
        "archivo": "refinacin-hidrocarburos-refineras.zip",
    },
    "ductos": {
        "nombre": "Ductos de hidrocarburos y agua (Res. 319/93)",
        "package": "84681f81-dbbb-49eb-be30-e61778736ad9",
        "resource": "17fcc6b7-9d9c-4005-a93a-1b2d3a7b1ce5",
        "archivo": "instalaciones-hidrocarburos-ductos-res-319-93.zip",
    },
    "gasoductos": {
        "nombre": "Gasoductos de transporte (ENARGAS)",
        "package": "8758101a-1e0d-413f-8cc5-83e21ece6391",
        "resource": "5af07e15-f356-40b9-a369-63dbf38a938a",
        "archivo": "gasoductos-de-transporte-enargas-.zip",
    },
    "instalaciones": {
        "nombre": "Instalaciones de hidrocarburos empadronadas (Res. 318)",
        "package": "164e7197-3222-4d21-81df-9db30ccd3940",
        "resource": "601bccb9-5e24-4ea1-9d90-e4d72da11d1f",
        "archivo": "instalaciones-hidrocarburos-instalaciones-res-318.zip",
    },
    "terminales": {
        "nombre": "Terminales de despacho de combustibles líquidos",
        "package": "99ba34a0-08f2-48e3-8d37-4d92542f740e",
        "resource": "d9e6759e-bcae-4321-9317-10ed7b6ceccb",
        "archivo": (
            "comercializacin-de-hidrocarburos-terminales-de-despacho-de-"
            "combustibles-lquidos-segn-res-110204-.zip"
        ),
    },
}

WFS = "https://wms.ign.gob.ar/geoserver/ows"
CAPAS_IGN = {
    "provincias": "ign:provincia",
    "departamentos": "ign:departamento",
}

# Extensión de la cuenca Neuquina redondeada al grado, la misma que usa
# ingest/dem_neuquina.py. Estas capas se piden acotadas a ese recuadro: la red
# vial de toda la Argentina son cientos de megas para dibujar seis grados
# cuadrados de mapa.
BBOX_NEUQUINA = "-72,-41,-66,-34"

# Capas de contexto del mapa. Sin rutas ni pueblos, la cuenca es una mancha de
# puntos flotando en el vacío: son las que dejan ubicar dónde está cada pozo.
CAPAS_CONTEXTO = {
    "rutas_nacionales": "ign:vial_nacional",
    "rutas_provinciales": "ign:vial_provincial",
    "localidades": "ign:localidad_bahra",
    "ductos": "ign:lineas_de_estructura_asociada_ducto_subterraneo",
    "rios": "ign:lineas_de_aguas_continentales_perenne",
    "ferrocarril": "ign:lineas_de_transporte_ferroviario_AN010",
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


def bajar_wfs(slug: str, capa: str, args, bbox: str | None = None, subdir: str = "boundaries") -> bool:
    """Una capa del IGN por WFS, ya en GeoJSON y EPSG:4326.

    Con `bbox` se pide solo el recuadro de la cuenca. Se usa la versión 1.0.0
    del protocolo justamente para eso: desde la 1.1 el orden de los ejes de
    EPSG:4326 pasa a ser lat/lon y el mismo recuadro devuelve el otro lado del
    planeta sin avisar.
    """
    key = f"geo/{subdir}/{slug}"
    if is_fresh(key, args.force, args.max_age_days):
        log(f"{slug}: fresco en el manifest, se saltea (--force para rebajar)")
        return False

    session = http_session({"Accept": "application/json"})
    params = {
        "service": "WFS",
        "version": "1.0.0" if bbox else "2.0.0",
        "request": "GetFeature",
        "typeName" if bbox else "typeNames": capa,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
    }
    if bbox:
        params["bbox"] = bbox
    response = session.get(WFS, params=params, timeout=600)
    response.raise_for_status()
    payload = response.json()

    features = payload.get("features")
    if not features:
        raise RuntimeError(f"el WFS del IGN devolvio {capa} sin features")

    destino = DEST / subdir / f"{slug}.geojson"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    size = destino.stat().st_size

    record(
        key,
        dataset_id=10,
        source="IGN (WFS wms.ign.gob.ar/geoserver)",
        capa=capa,
        bbox=bbox,
        url=f"{WFS}?service=WFS&request=GetFeature&typeName={capa}",
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

    for slug, spec in INFRAESTRUCTURA.items():
        spec = {**spec, "subdir": f"energy/{slug}"}
        try:
            if bajar_shapefile(slug, spec, args):
                bajados += 1
        except Exception as exc:  # noqa: BLE001
            log(f"{slug}: FALLO {exc}")
            fallidos.append(slug)

    for slug, capa in CAPAS_CONTEXTO.items():
        try:
            if bajar_wfs(slug, capa, args, bbox=BBOX_NEUQUINA, subdir="context"):
                bajados += 1
        except Exception as exc:  # noqa: BLE001
            log(f"{slug}: FALLO {exc}")
            fallidos.append(slug)

    total = len(SHAPEFILES) + len(INFRAESTRUCTURA) + len(CAPAS_IGN) + len(CAPAS_CONTEXTO)
    log(f"listo: {bajados}/{total} capas bajadas")
    if fallidos:
        log(f"ATENCION: fallaron {', '.join(fallidos)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
