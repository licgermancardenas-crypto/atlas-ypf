"""Dataset 11 — Modelo digital de elevaciones de la cuenca Neuquina.

Fuente: Copernicus DEM GLO-30 (ESA), en COG públicos sobre S3, sin credenciales.

Por qué no el MDE-Ar del IGN, que es lo que pedía el brief: el IGN distribuye el
MDE-Ar por hojas, detrás de un formulario de descarga, y su GeoServer no expone
WCS (se verificó: la respuesta de GetCapabilities no trae coberturas). No hay
manera de bajarlo de forma reproducible desde un pipeline. Copernicus GLO-30 es
de la misma clase de resolución (30 m), cubre todo el país, es abierto y está en
COG, que es lo que permite el truco de acá abajo. Queda anotado como sustitución
deliberada, no como equivalencia.

El truco: no se bajan los tiles enteros. Un grado cuadrado a 30 m son 3.600 x
3.600 celdas y la cuenca son 42 tiles: unos 2 GB para terminar dibujando un
hillshade de 2.000 píxeles de ancho. Como los COG traen overviews, se pide cada
tile ya remuestreado (300 celdas por grado, ~370 m) y por HTTP viaja solo esa
pirámide. El mosaico final pesa pocos megabytes y le sobra resolución al mapa.

Si en algún momento el análisis necesita el detalle a 30 m —por ejemplo para
perfiles de terreno sobre un pad— hay que bajar los tiles completos y este
script necesita otro modo, no un ajuste de parámetro.

Salida: data/raw/geo/dem/neuquina_dem.tif (int16, EPSG:4326)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.errors import RasterioIOError
from rasterio.transform import from_origin

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    RAW,
    base_parser,
    human,
    is_fresh,
    log,
    record,
    rel,
)

DEST = RAW / "geo" / "dem"
KEY = "geo/dem/neuquina"

# Extensión de la cuenca Neuquina según la capa de cuencas sedimentarias de la
# Secretaría de Energía (-71,83 / -40,36 / -66,58 / -34,26), redondeada al grado.
BBOX = {"oeste": -72, "este": -66, "sur": -41, "norte": -34}

CELDAS_POR_GRADO = 300  # ~370 m en el ecuador; de sobra para un hillshade web
NODATA = -32768

URL_TILE = (
    "https://copernicus-dem-30m.s3.amazonaws.com/"
    "Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM/"
    "Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM.tif"
)


def url_tile(lat_sur: int, lon_oeste: int) -> str:
    """URL del tile de 1 grado cuyo vértice suroeste es (lat_sur, lon_oeste)."""
    return URL_TILE.format(
        ns="S" if lat_sur < 0 else "N",
        lat=abs(lat_sur),
        ew="W" if lon_oeste < 0 else "E",
        lon=abs(lon_oeste),
    )


def construir_mosaico() -> tuple[np.ndarray, rasterio.Affine, int, int]:
    ancho = (BBOX["este"] - BBOX["oeste"]) * CELDAS_POR_GRADO
    alto = (BBOX["norte"] - BBOX["sur"]) * CELDAS_POR_GRADO
    mosaico = np.full((alto, ancho), NODATA, dtype=np.int16)
    transform = from_origin(
        BBOX["oeste"], BBOX["norte"], 1 / CELDAS_POR_GRADO, 1 / CELDAS_POR_GRADO
    )

    encontrados, faltantes = 0, 0
    for lat in range(BBOX["sur"], BBOX["norte"]):
        for lon in range(BBOX["oeste"], BBOX["este"]):
            url = url_tile(lat, lon)
            try:
                with rasterio.open(url) as src:
                    datos = src.read(
                        1,
                        out_shape=(CELDAS_POR_GRADO, CELDAS_POR_GRADO),
                        resampling=Resampling.average,
                    )
            except RasterioIOError:
                # Sobre el océano y en algunos bordes el tile no existe: es
                # esperable y no es un error del pipeline.
                faltantes += 1
                continue

            fila = (BBOX["norte"] - (lat + 1)) * CELDAS_POR_GRADO
            columna = (lon - BBOX["oeste"]) * CELDAS_POR_GRADO
            valores = np.nan_to_num(datos, nan=NODATA, posinf=NODATA, neginf=NODATA)
            mosaico[fila : fila + CELDAS_POR_GRADO, columna : columna + CELDAS_POR_GRADO] = (
                np.rint(valores).astype(np.int16)
            )
            encontrados += 1
            if encontrados % 10 == 0:
                log(f"  {encontrados} tiles leidos...")

    log(f"  {encontrados} tiles en el mosaico, {faltantes} sin datos (oceano o borde)")
    return mosaico, transform, encontrados, faltantes


def main() -> int:
    parser = base_parser("Arma el MDE de la cuenca Neuquina desde Copernicus GLO-30")
    args = parser.parse_args()

    # El relieve no cambia entre corridas semanales: la frescura se mide en años,
    # no en los 7 días que usan las series de mercado.
    if is_fresh(KEY, args.force, max(args.max_age_days, 365)):
        log("dem: fresco en el manifest, se saltea (--force para rebajar)")
        return 0

    log(f"leyendo tiles de Copernicus GLO-30 para {BBOX}")
    mosaico, transform, encontrados, faltantes = construir_mosaico()
    if encontrados == 0:
        log("no se pudo leer ningun tile: revisar conectividad o el naming de Copernicus")
        return 1

    destino = DEST / "neuquina_dem.tif"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        destino,
        "w",
        driver="GTiff",
        height=mosaico.shape[0],
        width=mosaico.shape[1],
        count=1,
        dtype="int16",
        crs="EPSG:4326",
        transform=transform,
        nodata=NODATA,
        compress="lzw",
        tiled=True,
    ) as dst:
        dst.write(mosaico, 1)

    size = destino.stat().st_size
    validos = mosaico[mosaico != NODATA]

    record(
        KEY,
        dataset_id=11,
        source="Copernicus DEM GLO-30 (ESA), COG publicos en S3",
        sustituye="MDE-Ar del IGN: no tiene descarga programatica (sin WCS, hojas por formulario)",
        bbox=BBOX,
        resolucion_grados=round(1 / CELDAS_POR_GRADO, 6),
        tiles=encontrados,
        tiles_sin_datos=faltantes,
        path=rel(destino),
        shape=list(mosaico.shape),
        elevacion_min=int(validos.min()),
        elevacion_max=int(validos.max()),
        bytes=size,
    )
    log(
        f"dem: {mosaico.shape[1]}x{mosaico.shape[0]} celdas, "
        f"{int(validos.min())}-{int(validos.max())} m, {human(size)} -> {rel(destino)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
