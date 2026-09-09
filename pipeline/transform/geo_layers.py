"""Capas geoespaciales listas para deck.gl: cuenca, concesiones, pozos y relieve.

Entradas: data/raw/geo/{basins,concessions,fields}/*.zip  (ingest/geo_layers.py)
          data/raw/geo/boundaries/*.geojson               (ingest/geo_layers.py)
          data/raw/geo/dem/neuquina_dem.tif               (ingest/dem_neuquina.py)
          data/processed/wells.parquet                    (transform/production_wells.py)
          data/processed/decline_curves.parquet, well_economics.parquet

Salidas:  data/processed/geo/*.geojson  (vectores, EPSG:4326)
          data/processed/geo/hillshade.png + terrain.png + raster.json
          data/processed/geo/_resumen.json

Tres decisiones que definen el resultado:

1. Todo se recorta a la cuenca Neuquina. Las capas nacionales traen 879
   yacimientos y 529 departamentos; el caso es sobre Vaca Muerta y cargar el
   resto es pagar peso por nada.
2. Las geometrías se simplifican con una tolerancia distinta por capa, en grados.
   Una provincia se ve igual con 200 m de tolerancia y pesa una décima parte; una
   concesión de 20 km de lado no tolera lo mismo. La tolerancia de cada capa está
   en SIMPLIFICACION y es el parámetro a tocar si el mapa carga lento.
3. El relieve sale en dos PNG: un hillshade en escala de grises para pintar de
   fondo, y un terrain-RGB (la codificación de Mapbox) para que deck.gl pueda
   extruir el terreno en 3D. Son la misma grilla y comparten el bounds del
   raster.json.
"""

from __future__ import annotations

import json
import os
import sys
import warnings
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from PIL import Image

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
)

RAW_GEO = RAW / "geo"
OUT = PROCESSED / "geo"

SRC_BASINS = RAW_GEO / "basins" / "exploracin-hidrocarburos-cuencas-sedimentarias.zip"
SRC_CONCESSIONS = RAW_GEO / "concessions" / "produccin-hidrocarburos-concesiones-de-explotacin.zip"
SRC_FIELDS = RAW_GEO / "fields" / "produccin-hidrocarburos-yacimientos.zip"
SRC_PROVINCIAS = RAW_GEO / "boundaries" / "provincias.geojson"
SRC_DEM = RAW_GEO / "dem" / "neuquina_dem.tif"
SRC_WELLS = PROCESSED / "wells.parquet"
SRC_DECLINE = PROCESSED / "decline_curves.parquet"
SRC_ECON = PROCESSED / "well_economics.parquet"

# Tolerancia de simplificación en grados (1 grado ~ 111 km en el ecuador).
SIMPLIFICACION = {
    "basin": 0.002,  # ~200 m: el contorno de la cuenca es referencia, no medición
    "concessions": 0.001,  # ~100 m: los bordes de área importan más
    "fields": 0.001,
    "provinces": 0.005,  # ~550 m: solo dan contexto de fondo
}

# Margen alrededor de la cuenca para no cortar lo que queda justo en el borde.
MARGEN_GRADOS = 0.25

# El azimut y la altura del sol del hillshade: 315/45 es la convención
# cartográfica (luz desde el noroeste), la que el ojo lee como relieve y no como
# hueco.
AZIMUT = 315.0
ALTURA_SOL = 45.0
NODATA = -32768

# Ancho máximo de cada PNG de relieve, en píxeles. El mosaico crudo son 1.800 x
# 2.100 celdas sobre 6 x 7 grados; a estos tamaños el mapa sigue viéndose igual y
# la carpeta pesa la mitad, que es lo que decide si el mapa entra en 3 segundos.
MAX_HILLSHADE_PX = 1400
MAX_TERRAIN_PX = 900


# --------------------------------------------------------------------------- #
# Vectores
# --------------------------------------------------------------------------- #
def leer_shapefile(zip_path: Path) -> gpd.GeoDataFrame:
    with zipfile.ZipFile(zip_path) as zf:
        shp = next(n for n in zf.namelist() if n.lower().endswith(".shp"))
    gdf = gpd.read_file(f"zip://{zip_path.as_posix()}!{shp}")
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf.to_crs("EPSG:4326")


def limpiar(gdf: gpd.GeoDataFrame, columnas: dict[str, str], tolerancia: float) -> gpd.GeoDataFrame:
    """Deja solo las columnas útiles, renombradas, y simplifica la geometría.

    La columna GEOJSON que traen los shapefiles de la Secretaría es la misma
    geometría repetida como texto: duplica el peso del archivo y no aporta nada.
    """
    disponibles = {viejo: nuevo for viejo, nuevo in columnas.items() if viejo in gdf.columns}
    salida = gdf[list(disponibles) + ["geometry"]].rename(columns=disponibles).copy()
    salida["geometry"] = salida.geometry.simplify(tolerancia, preserve_topology=True)
    salida = salida[~salida.geometry.is_empty & salida.geometry.notna()]
    return salida


def escribir_geojson(gdf: gpd.GeoDataFrame, nombre: str, decimales: int = 5) -> int:
    """GeoJSON compacto: cinco decimales son ~1 m, y de ahí en más es ruido."""
    destino = OUT / f"{nombre}.geojson"
    destino.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(gdf.to_json(drop_id=True, to_wgs84=True))

    def redondear(coords):
        if isinstance(coords[0], (int, float)):
            return [round(float(c), decimales) for c in coords[:2]]
        return [redondear(c) for c in coords]

    for feature in payload["features"]:
        feature["geometry"]["coordinates"] = redondear(feature["geometry"]["coordinates"])

    destino.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    size = destino.stat().st_size
    log(f"escrito {rel(destino)} - {len(gdf):,} features, {human(size)}")
    return size


def capas_vectoriales() -> tuple[dict[str, int], gpd.GeoSeries]:
    cuencas = leer_shapefile(SRC_BASINS)
    neuquina = cuencas[cuencas.CUENCA.str.contains("NEUQ", case=False, na=False)]
    if neuquina.empty:
        raise RuntimeError("la capa de cuencas no trae la Neuquina")
    # El buffer va en grados a propósito: es un margen de encuadre para no cortar
    # lo que queda pegado al borde de la cuenca, no una distancia métrica, así que
    # reproyectar para hacerlo exacto sería precisión falsa.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*geographic CRS.*")
        recorte = neuquina.geometry.buffer(MARGEN_GRADOS).union_all()

    tamanos: dict[str, int] = {}

    basin = limpiar(neuquina, {"CUENCA": "cuenca", "TIPO": "tipo"}, SIMPLIFICACION["basin"])
    tamanos["basin"] = escribir_geojson(basin, "basin")

    concesiones = leer_shapefile(SRC_CONCESSIONS)
    concesiones = concesiones[concesiones.intersects(recorte)]
    concesiones = limpiar(
        concesiones,
        {
            "NOMBRE_DE_": "nombre",
            "CODIGO_DE_": "codigo",
            "EMPRESA_OP": "operador",
            "PARTICIPAC": "participacion",
        },
        SIMPLIFICACION["concessions"],
    )
    if "participacion" in concesiones:
        # La fuente arma esa columna para un popup HTML y la manda con <br>
        # adentro; el tooltip del mapa la quiere como texto plano.
        concesiones["participacion"] = (
            concesiones.participacion.fillna("")
            .str.replace(r"<[^>]+>", " ", regex=True)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
    tamanos["concessions"] = escribir_geojson(concesiones, "concessions")

    yacimientos = leer_shapefile(SRC_FIELDS)
    yacimientos = yacimientos[yacimientos.intersects(recorte)]
    yacimientos = limpiar(
        yacimientos,
        {"AREAYACIMI": "yacimiento", "IDYA": "codigo", "EMPRESA_OP": "operador"},
        SIMPLIFICACION["fields"],
    )
    tamanos["fields"] = escribir_geojson(yacimientos, "fields")

    # Las provincias del IGN vienen con el detalle completo del límite: una sola
    # feature supera el tope por objeto que GDAL trae por defecto para GeoJSON.
    os.environ.setdefault("OGR_GEOJSON_MAX_OBJ_SIZE", "0")
    provincias = gpd.read_file(SRC_PROVINCIAS).to_crs("EPSG:4326")
    provincias = provincias[provincias.intersects(recorte)]
    columna_nombre = next(
        (c for c in ("nam", "nombre", "NAM", "NOMBRE") if c in provincias.columns), None
    )
    provincias = limpiar(
        provincias, {columna_nombre: "provincia"} if columna_nombre else {}, SIMPLIFICACION["provinces"]
    )
    tamanos["provinces"] = escribir_geojson(provincias, "provinces", decimales=4)

    return tamanos, recorte


# --------------------------------------------------------------------------- #
# Pozos
# --------------------------------------------------------------------------- #
def capa_pozos() -> tuple[int, int]:
    """Pozos con producción acumulada y, si están, EUR y NPV del pozo.

    Es la capa que colorea el mapa por volumen, así que carga solo lo que se
    dibuja: un pozo sin coordenadas o sin producción no aporta un punto.
    """
    wells = pd.read_parquet(SRC_WELLS)
    pozos = wells[wells.lat.notna() & wells.lon.notna() & (wells.boe_acum > 0)].copy()

    if SRC_DECLINE.exists():
        decline = pd.read_parquet(SRC_DECLINE)[["pozo_id", "eur_bbl", "declive_ef_anual"]]
        pozos = pozos.merge(decline, on="pozo_id", how="left")
    if SRC_ECON.exists():
        econ = pd.read_parquet(SRC_ECON)[["pozo_id", "npv_usd", "breakeven_brent"]]
        pozos = pozos.merge(econ, on="pozo_id", how="left")

    campos = {
        "sigla": lambda s: s.astype("string"),
        "operador_actual": lambda s: s.astype("string"),
        "yacimiento": lambda s: s.astype("string"),
        "formacion": lambda s: s.astype("string"),
        "es_vaca_muerta": lambda s: s.astype(bool),
        "boe_acum": lambda s: (s / 1000).round(1),  # Mboe: el mapa no necesita el barril
        "petroleo_acum_bbl": lambda s: (s / 1000).round(1),
        "eur_bbl": lambda s: (s / 1000).round(1),
        "npv_usd": lambda s: (s / 1e6).round(2),  # US$ millones
        "breakeven_brent": lambda s: s.round(1),
        "meses_produccion": lambda s: s.astype("int16"),
    }
    salida = pd.DataFrame({nombre: fn(pozos[nombre]) for nombre, fn in campos.items() if nombre in pozos})
    salida = salida.rename(
        columns={
            "operador_actual": "operador",
            "boe_acum": "boe_acum_mboe",
            "petroleo_acum_bbl": "petroleo_acum_mbbl",
            "eur_bbl": "eur_mbbl",
            "npv_usd": "npv_musd",
        }
    )
    salida["anio_inicio"] = pozos.primera_prod.dt.year.astype("Int16")

    geo = gpd.GeoDataFrame(
        salida,
        geometry=gpd.points_from_xy(pozos.lon.round(5), pozos.lat.round(5)),
        crs="EPSG:4326",
    )
    size = escribir_geojson(geo, "wells")
    return len(geo), size


# --------------------------------------------------------------------------- #
# Relieve
# --------------------------------------------------------------------------- #
def hillshade(elevacion: np.ndarray, resolucion_m: float) -> np.ndarray:
    """Sombreado analítico estándar (Horn) a partir del gradiente del terreno."""
    dy, dx = np.gradient(elevacion.astype("float32"), resolucion_m)
    pendiente = np.arctan(np.hypot(dx, dy))
    aspecto = np.arctan2(-dx, dy)

    azimut = np.radians(360.0 - AZIMUT + 90.0)
    altura = np.radians(ALTURA_SOL)
    sombra = np.sin(altura) * np.cos(pendiente) + np.cos(altura) * np.sin(pendiente) * np.cos(
        azimut - aspecto
    )
    return np.clip(sombra, 0, 1)


def _encajar(tamano: tuple[int, int], ancho_max: int) -> tuple[int, int]:
    """Escala (ancho, alto) para que el ancho no pase de ancho_max, sin deformar."""
    ancho, alto = tamano
    escala = ancho_max / ancho
    return ancho_max, max(int(round(alto * escala)), 1)


def terrain_rgb(elevacion: np.ndarray) -> np.ndarray:
    """Codificación terrain-RGB de Mapbox: altura = -10000 + (R*65536+G*256+B)*0.1."""
    valores = np.clip((elevacion.astype("float64") + 10000.0) / 0.1, 0, 256**3 - 1).astype("uint32")
    return np.dstack(
        [
            (valores >> 16 & 0xFF).astype("uint8"),
            (valores >> 8 & 0xFF).astype("uint8"),
            (valores & 0xFF).astype("uint8"),
        ]
    )


def capas_raster() -> dict:
    with rasterio.open(SRC_DEM) as src:
        elevacion = src.read(1).astype("float32")
        bounds = src.bounds
        resolucion_grados = src.res[0]

    sin_datos = elevacion == NODATA
    if sin_datos.any():
        # El hillshade necesita una superficie continua: los huecos van al nivel
        # del mar, que es lo que son (océano o borde del mosaico).
        elevacion[sin_datos] = 0.0

    # Un grado de latitud son ~111 km; alcanza para que la pendiente tenga escala
    # física y el sombreado no dependa del tamaño del píxel.
    resolucion_m = resolucion_grados * 111_320.0

    sombra = (hillshade(elevacion, resolucion_m) * 255).astype("uint8")
    OUT.mkdir(parents=True, exist_ok=True)
    imagen_sombra = Image.fromarray(sombra, mode="L")
    if imagen_sombra.width > MAX_HILLSHADE_PX:
        # Se remuestrea el sombreado ya calculado, no la elevación: la pendiente
        # se computa a resolución completa y recién después se reduce, que es lo
        # que conserva el detalle fino del relieve.
        imagen_sombra = imagen_sombra.resize(_encajar(imagen_sombra.size, MAX_HILLSHADE_PX), Image.LANCZOS)
    imagen_sombra.save(OUT / "hillshade.png", optimize=True)

    # El terrain-RGB no comprime como el hillshade: cada píxel es un número de 24
    # bits sin patrón, así que el PNG queda enorme a resolución completa. Para
    # extruir el terreno en el mapa alcanza con la mitad de detalle, y se
    # remuestrea la elevación antes de codificarla (después de codificar, cada
    # canal es un dígito y promediarlos daría alturas inventadas).
    terreno = elevacion
    if terreno.shape[1] > MAX_TERRAIN_PX:
        destino_px = _encajar((terreno.shape[1], terreno.shape[0]), MAX_TERRAIN_PX)
        terreno = np.asarray(
            Image.fromarray(terreno, mode="F").resize(destino_px, Image.BILINEAR), dtype="float32"
        )
    Image.fromarray(terrain_rgb(terreno), mode="RGB").save(OUT / "terrain.png", optimize=True)

    validos = elevacion[~sin_datos]
    raster = {
        "bounds": [
            round(bounds.left, 4),
            round(bounds.bottom, 4),
            round(bounds.right, 4),
            round(bounds.top, 4),
        ],
        "ancho": int(elevacion.shape[1]),
        "alto": int(elevacion.shape[0]),
        "resolucion_grados": round(resolucion_grados, 6),
        "elevacion_min_m": int(validos.min()),
        "elevacion_max_m": int(validos.max()),
        "hillshade": {
            "archivo": "hillshade.png",
            "ancho": imagen_sombra.width,
            "alto": imagen_sombra.height,
            "azimut": AZIMUT,
            "altura_sol": ALTURA_SOL,
        },
        "terrain": {
            "archivo": "terrain.png",
            "ancho": int(terreno.shape[1]),
            "alto": int(terreno.shape[0]),
            "codificacion": "mapbox terrain-rgb",
            "formula": "altura_m = -10000 + (R * 65536 + G * 256 + B) * 0.1",
        },
        "fuente": "Copernicus DEM GLO-30 (ESA)",
    }
    save_json(raster, OUT / "raster.json", indent=2)

    for archivo in ("hillshade.png", "terrain.png", "raster.json"):
        log(f"escrito {rel(OUT / archivo)} - {human((OUT / archivo).stat().st_size)}")
    return raster


def main() -> int:
    args = base_parser("Arma las capas geoespaciales para deck.gl").parse_args()

    fuentes = (SRC_BASINS, SRC_CONCESSIONS, SRC_FIELDS, SRC_PROVINCIAS, SRC_WELLS)
    faltantes = [p for p in fuentes if not p.exists()]
    if faltantes:
        log(f"faltan insumos: {', '.join(rel(p) for p in faltantes)}")
        log("correr antes: pipeline/ingest/geo_layers.py y transform/production_wells.py")
        return 1

    salida_control = OUT / "wells.geojson"
    if salida_control.exists() and not args.force:
        if salida_control.stat().st_mtime > max(p.stat().st_mtime for p in fuentes):
            log(f"{rel(salida_control)} esta al dia, se saltea (--force para rehacer)")
            return 0

    tamanos, _ = capas_vectoriales()
    pozos, tamanos["wells"] = capa_pozos()

    raster = None
    if SRC_DEM.exists():
        raster = capas_raster()
    else:
        log(f"sin {rel(SRC_DEM)}: se saltea el relieve (correr ingest/dem_neuquina.py)")

    resumen = {
        "generado": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "crs": "EPSG:4326",
        "recorte": "cuenca Neuquina + 0,25 grados de margen",
        "simplificacion_grados": SIMPLIFICACION,
        "capas": {nombre: {"bytes": size} for nombre, size in tamanos.items()},
        "pozos": pozos,
        "raster": raster,
    }
    save_json(resumen, OUT / "_resumen.json", indent=2)

    total = sum(tamanos.values()) + sum(
        (OUT / a).stat().st_size for a in ("hillshade.png", "terrain.png") if (OUT / a).exists()
    )
    log(f"total de la carpeta geo para el frontend: {human(total)}")

    record(
        "geo_layers",
        sources=[rel(p) for p in fuentes],
        outputs=[rel(p) for p in sorted(OUT.glob("*")) if p.is_file()],
        pozos=pozos,
        bytes_totales=total,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
