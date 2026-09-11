"""Convierte las capas geográficas en un mapa liviano para el sitio.

Por qué existe: el módulo del mapa ya dibuja la cuenca con deck.gl, pero eso
pesa un megabyte largo y solo sirve adentro de esa página. Para ilustrar —el
encabezado de un módulo, una tarjeta, una sección de infraestructura— hace falta
lo mismo pero liviano: la cuenca, los ductos y las rutas convertidos a unos
pocos trazos SVG que se sirven con la página.

La diferencia con dibujar un mapa a mano es que estos trazos son los de verdad.
El oleoducto que cruza la ilustración es el oleoducto, simplificado hasta donde
el ojo no nota la diferencia a ese tamaño, y sale del mismo archivo que alimenta
el mapa interactivo.

El relieve también es real. Sale de decodificar el terrain-RGB que ya genera
transform/geo_layers.py a partir del DEM de Copernicus, y se sombrea con el sol
en el noroeste, que es la convención cartográfica desde hace un siglo y medio:
el ojo lee mal un relieve iluminado desde abajo. Sin sombreado el dibujo era
correcto y plano; con sombreado se ve que la cuenca es una depresión entre la
cordillera y la meseta, que es media explicación de por qué el crudo está donde
está.

Entrada:  data/processed/geo/*.geojson  (los arma transform/geo_layers.py)
          data/processed/geo/terrain.png + raster.json (idem)
Salida:   data/processed/mapa_web.json  (trazos ya proyectados al lienzo)
          data/processed/mapa_relieve.png (el sombreado, recortado al marco)
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from shapely.geometry import box, shape
from shapely.ops import linemerge, unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    PROCESSED,
    base_parser,
    human,
    log,
    record,
    rel,
    save_json,
)

GEO = PROCESSED / "geo"
SALIDA = PROCESSED / "mapa_web.json"
RELIEVE = PROCESSED / "mapa_relieve.png"

# El lienzo. Vertical, porque la cuenca lo es: son seiscientos kilómetros de
# norte a sur contra cuatrocientos de este a oeste, y estirarla a formato
# panorámico deja media ilustración en blanco.
ANCHO = 300
ALTO = 400
MARGEN = 6

# El marco se limita a lo que cubre el DEM. Alcanza: la cuenca entra entera y
# sobra cordillera al oeste, que es justo el contexto que hace entender el
# dibujo. Los troncales que siguen hacia el Atlántico se cortan en el borde, y
# que se corten dice lo que hay que decir: siguen.
RECORTE_DEM = (-72.0, -41.0, -66.0, -34.0)

# Cuánto se puede simplificar cada capa sin que se note. En grados: 0,01° son
# aproximadamente un kilómetro, y a este tamaño un kilómetro es medio píxel.
TOLERANCIAS = {
    "basin": 0.01,
    "concessions": 0.008,
    "fields": 0.006,
    "pipelines": 0.008,
    "gas_pipelines": 0.008,
    "roads": 0.008,
    "rail": 0.01,
    "rivers": 0.008,
    "provinces": 0.02,
}

# Largo mínimo, en grados, para que un trazo entre al dibujo. Las redes vienen
# como una maraña de tramos —cada empalme corta la línea— y a esta escala un
# tramo de dos kilómetros es un punto. Se unen los que se tocan y se descarta lo
# que quede corto: queda el trazado troncal, que es lo que la ilustración tiene
# que mostrar.
MINIMOS = {
    "pipelines": 0.02,
    "gas_pipelines": 0.02,
    "roads": 0.04,
    "rail": 0.05,
    "rivers": 0.06,
    "arroyos": 0.12,
}

# Las localidades que se rotulan. La capa del IGN no trae población, así que la
# selección es editorial y se declara como tal: la capital, el corredor del Alto
# Valle para ubicar al lector, y los pueblos de la actividad, que son los que
# este caso nombra todo el tiempo.
LOCALIDADES_CLAVE = {
    "Neuquén": "capital",
    "Añelo": "actividad",
    # Cutral Có y Plaza Huincul son una sola mancha urbana y sus nombres no
    # entran los dos. Gana Plaza Huincul: ahí está la refinería.
    "Plaza Huincul": "actividad",
    "Cutral Có": "referencia",
    "Rincón de los Sauces": "actividad",
    "Catriel": "actividad",
    "Zapala": "referencia",
    "Chos Malal": "referencia",
    "General Roca": "referencia",
}


PARTICULAS = {"de", "del", "la", "las", "los", "y", "el"}


def en_titulo(texto: str) -> str:
    """Título castellano: las partículas van en minúscula.

    str.title() devuelve "Rincón De Los Sauces", que no es como se escribe.
    """
    palabras = str(texto).strip().lower().split()
    return " ".join(
        palabra if indice and palabra in PARTICULAS else palabra.capitalize()
        for indice, palabra in enumerate(palabras)
    )


def leer(nombre: str) -> list[dict]:
    ruta = GEO / f"{nombre}.geojson"
    if not ruta.exists():
        return []
    return json.loads(ruta.read_text(encoding="utf-8")).get("features", [])


class Proyeccion:
    """Equirectangular simple, encuadrada a la cuenca.

    A esta latitud y en un recorte de seis grados, la distorsión contra una
    proyección seria es menor que el grosor del trazo. Lo único que se corrige
    es el achatamiento por la latitud, que sin corregir dejaría la cuenca
    visiblemente ancha.
    """

    def __init__(self, bbox: tuple[float, float, float, float]):
        oeste, sur, este, norte = bbox
        self.oeste, self.sur, self.este, self.norte = oeste, sur, este, norte
        self.factor_x = math.cos(math.radians((sur + norte) / 2))

        ancho_geo = (este - oeste) * self.factor_x
        alto_geo = norte - sur
        self.escala = min((ANCHO - 2 * MARGEN) / ancho_geo, (ALTO - 2 * MARGEN) / alto_geo)
        self.desplazamiento_x = (ANCHO - ancho_geo * self.escala) / 2
        self.desplazamiento_y = (ALTO - alto_geo * self.escala) / 2

    def punto(self, lon: float, lat: float) -> tuple[float, float]:
        x = (lon - self.oeste) * self.factor_x * self.escala + self.desplazamiento_x
        y = (self.norte - lat) * self.escala + self.desplazamiento_y
        return round(x, 1), round(y, 1)

    @property
    def caja_dibujada(self) -> tuple[float, float, float, float]:
        """El rectángulo del lienzo que ocupa el marco, para apoyar el relieve."""
        x0, y0 = self.punto(self.oeste, self.norte)
        x1, y1 = self.punto(self.este, self.sur)
        return x0, y0, x1, y1

    @property
    def km_por_unidad(self) -> float:
        """Para la barra de escala: un grado de latitud son 111,32 km."""
        return 111.32 / self.escala


def trazo(coordenadas, proyectar, cerrado: bool) -> str:
    partes = []
    for indice, (lon, lat) in enumerate(coordenadas):
        x, y = proyectar(lon, lat)
        partes.append(f"{'M' if indice == 0 else 'L'}{x} {y}")
    if cerrado:
        partes.append("Z")
    return "".join(partes)


def a_trazos(geometria, proyectar, tolerancia: float, caja=None) -> list[str]:
    """Un GeoJSON a una lista de paths, simplificando antes de proyectar."""
    figura = shape(geometria)
    if tolerancia:
        figura = figura.simplify(tolerancia, preserve_topology=True)
    if caja is not None:
        figura = figura.intersection(caja)
    if figura.is_empty:
        return []

    trazos: list[str] = []
    tipo = figura.geom_type
    partes = figura.geoms if tipo.startswith("Multi") or tipo == "GeometryCollection" else [figura]
    for parte in partes:
        if parte.geom_type == "Polygon":
            trazos.append(trazo(parte.exterior.coords, proyectar, cerrado=True))
        elif parte.geom_type == "LineString":
            trazos.append(trazo(parte.coords, proyectar, cerrado=False))
        elif parte.geom_type == "Point":
            x, y = proyectar(parte.x, parte.y)
            trazos.append(f"M{x} {y}")
    return trazos


def capa_de_lineas(
    nombre: str, proyectar, caja=None, filtro=None, clave: str | None = None
) -> list[str]:
    """Recorta al marco, une lo que se toca, tira lo corto y recién ahí dibuja."""
    geometrias = []
    for feature in leer(nombre):
        if filtro and not filtro(feature.get("properties", {})):
            continue
        figura = shape(feature["geometry"])
        if caja is not None:
            figura = figura.intersection(caja)
        if not figura.is_empty:
            geometrias.append(figura)
    if not geometrias:
        return []

    unidas = linemerge(unary_union(geometrias))
    partes = list(unidas.geoms) if unidas.geom_type.startswith("Multi") else [unidas]
    minimo = MINIMOS.get(clave or nombre, 0.0)
    partes = [parte for parte in partes if parte.length >= minimo]

    trazos: list[str] = []
    for parte in partes:
        trazos.extend(
            a_trazos(parte.__geo_interface__, proyectar, TOLERANCIAS.get(nombre, 0.01), caja)
        )
    return [t for t in trazos if t.count("L") >= 2]


def capa_de_poligonos(nombre: str, proyectar, caja=None, filtro=None) -> list[str]:
    trazos: list[str] = []
    for feature in leer(nombre):
        if filtro and not filtro(feature.get("properties", {})):
            continue
        trazos.extend(a_trazos(feature["geometry"], proyectar, TOLERANCIAS.get(nombre, 0.01), caja))
    return [t for t in trazos if t.count("L") >= 2]


def capa_disuelta(nombre: str, proyectar, caja=None, pegado: float = 0.0, filtro=None) -> list[str]:
    """Las concesiones, fundidas en una sola silueta.

    Dibujadas una por una son ciento ochenta rectángulos y quince kilobytes de
    ruido; el mapa interactivo ya las muestra así, con su nombre y su operador.
    Acá interesa otra cosa: la mancha, dónde está efectivamente concesionada la
    cuenca. Se las une con un pegado chico para que los lotes linderos cierren
    en una figura en vez de quedar como piezas sueltas.
    """
    figuras = []
    for feature in leer(nombre):
        if filtro and not filtro(feature.get("properties", {})):
            continue
        figura = shape(feature["geometry"])
        if caja is not None:
            figura = figura.intersection(caja)
        if not figura.is_empty:
            figuras.append(figura.buffer(pegado) if pegado else figura)
    if not figuras:
        return []
    unida = unary_union(figuras)
    if pegado:
        unida = unida.buffer(-pegado)
    return a_trazos(unida.__geo_interface__, proyectar, TOLERANCIAS.get(nombre, 0.01))


def puntos_de(
    nombre: str,
    proyectar,
    caja=None,
    campo: str | None = None,
    limite: int = 0,
) -> list[dict]:
    salida = []
    for feature in leer(nombre):
        geometria = shape(feature["geometry"])
        if geometria.is_empty:
            continue
        centro = geometria if geometria.geom_type == "Point" else geometria.centroid
        if caja is not None and not caja.contains(centro):
            continue
        x, y = proyectar(centro.x, centro.y)
        punto: dict = {"x": x, "y": y}
        if campo:
            etiqueta = feature.get("properties", {}).get(campo)
            if etiqueta:
                punto["nombre"] = en_titulo(etiqueta)
        salida.append(punto)
    if limite:
        salida = salida[:limite]
    return salida


def colocar_rotulos(localidades: list[dict]) -> None:
    """Decide de qué lado va cada nombre para que no se pisen.

    En el Alto Valle hay cinco pueblos en cincuenta kilómetros y a esta escala
    sus nombres se superponen. Se prueban cuatro posiciones por rótulo —derecha,
    izquierda, arriba, abajo— y se toma la primera que no choque con ninguno de
    los ya colocados; si las cuatro chocan, el pueblo se queda con su punto y
    sin nombre, que es mejor que dos palabras encimadas.

    El orden importa: primero la capital, después los pueblos de la actividad y
    al final las referencias. Así, cuando algo tiene que caerse, se cae lo menos
    importante.
    """
    prioridad = {"capital": 0, "actividad": 1, "referencia": 2}
    candidatos = sorted(
        (p for p in localidades if p.get("rango")),
        key=lambda p: (prioridad.get(p["rango"], 9), p.get("nombre", "")),
    )

    ocupadas: list[tuple[float, float, float, float]] = []
    for punto in candidatos:
        nombre = punto.get("nombre", "")
        cuerpo = 6.2 if punto["rango"] == "capital" else 5.2
        ancho = len(nombre) * cuerpo * 0.52
        alto = cuerpo

        posiciones = (
            (2.6, 1.8, "start"),
            (-2.6, 1.8, "end"),
            (2.6, -2.6, "start"),
            (-2.6, -2.6, "end"),
            (0, -3.4, "middle"),
            (0, 6.6, "middle"),
            (2.6, 5.6, "start"),
            (-2.6, 5.6, "end"),
        )
        for dx, dy, ancla in posiciones:
            x = punto["x"] + dx
            y = punto["y"] + dy
            izquierda = x if ancla == "start" else x - ancho if ancla == "end" else x - ancho / 2
            # El aire horizontal es mucho más ancho que el vertical a propósito:
            # dos nombres uno al lado del otro se leen como una sola frase larga
            # —"Zapala Plaza Huincul Cutral Có"—, y uno encima del otro no.
            caja = (izquierda - 6, y - alto - 0.5, izquierda + ancho + 6, y + alto * 0.25 + 0.5)
            choca = any(
                caja[0] < otra[2] and otra[0] < caja[2] and caja[1] < otra[3] and otra[1] < caja[3]
                for otra in ocupadas
            )
            if not choca:
                punto["tx"] = round(dx, 1)
                punto["ty"] = round(dy, 1)
                punto["anc"] = ancla
                ocupadas.append(caja)
                break
        else:
            punto.pop("rango", None)


def pozos_con_peso(proyectar, caja) -> list[dict]:
    """Los racimos de pozos, con el tamaño que les corresponde.

    Cada punto es un yacimiento y no un pozo: dibujar los cinco mil pozos a esta
    escala es pintar una mancha. El peso va de 0 a 1 por producción acumulada y
    en raíz, para que lo proporcional sea el área del círculo y no el radio; con
    escala lineal, Loma Campana tapa media cuenca.
    """
    crudos = []
    for feature in leer("well_clusters"):
        geometria = shape(feature["geometry"])
        if geometria.is_empty or (caja is not None and not caja.contains(geometria)):
            continue
        propiedades = feature.get("properties", {})
        try:
            acumulada = float(propiedades.get("boe_acum_mboe"))
        except (TypeError, ValueError):
            acumulada = 0.0
        x, y = proyectar(geometria.x, geometria.y)
        crudos.append(
            {
                "x": x,
                "y": y,
                "acumulada": max(acumulada, 0.0),
                "vm": 1 if str(propiedades.get("vaca_muerta", "0")) not in ("0", "None", "") else 0,
            }
        )

    if not crudos:
        return []
    techo = max(punto["acumulada"] for punto in crudos) or 1.0
    return [
        {
            "x": punto["x"],
            "y": punto["y"],
            "p": round(math.sqrt(punto["acumulada"] / techo), 3),
            "vm": punto["vm"],
        }
        for punto in crudos
    ]


# --------------------------------------------------------------------------- #
# El relieve
# --------------------------------------------------------------------------- #
def elevacion_del_terrain(raster: dict) -> np.ndarray:
    """Deshace la codificación terrain-RGB de Mapbox y devuelve metros.

    Se lee el PNG procesado y no el GeoTIFF crudo a propósito: data/raw no se
    versiona, así que el pipeline que corre en CI tiene el PNG y no el DEM.
    """
    with Image.open(GEO / raster["terrain"]["archivo"]) as imagen:
        rgb = np.asarray(imagen.convert("RGB"), dtype=np.float32)
    return -10000.0 + (rgb[:, :, 0] * 65536.0 + rgb[:, :, 1] * 256.0 + rgb[:, :, 2]) * 0.1


def recortar(elevacion: np.ndarray, bounds, marco, ancho_px: int, alto_px: int) -> np.ndarray:
    """Recorta el DEM al marco y lo remuestrea al tamaño del sombreado."""
    oeste_dem, sur_dem, este_dem, norte_dem = bounds
    oeste, sur, este, norte = marco
    alto_fuente, ancho_fuente = elevacion.shape

    columnas = np.linspace(oeste, este, ancho_px)
    filas = np.linspace(norte, sur, alto_px)
    ix = (columnas - oeste_dem) / (este_dem - oeste_dem) * (ancho_fuente - 1)
    iy = (norte_dem - filas) / (norte_dem - sur_dem) * (alto_fuente - 1)

    # Bilineal a mano: son dos interpolaciones y ahorra arrastrar scipy.
    x0 = np.clip(np.floor(ix).astype(int), 0, ancho_fuente - 1)
    x1 = np.clip(x0 + 1, 0, ancho_fuente - 1)
    y0 = np.clip(np.floor(iy).astype(int), 0, alto_fuente - 1)
    y1 = np.clip(y0 + 1, 0, alto_fuente - 1)
    fx = (ix - x0)[None, :]
    fy = (iy - y0)[:, None]

    arriba = elevacion[np.ix_(y0, x0)] * (1 - fx) + elevacion[np.ix_(y0, x1)] * fx
    abajo = elevacion[np.ix_(y1, x0)] * (1 - fx) + elevacion[np.ix_(y1, x1)] * fx
    return arriba * (1 - fy) + abajo * fy


def sombrear(elevacion: np.ndarray, metros_por_px: float, exageracion: float = 3.0) -> np.ndarray:
    """Hillshade clásico: sol en el noroeste a 45° sobre el horizonte."""
    dy, dx = np.gradient(elevacion * exageracion, metros_por_px)
    pendiente = np.arctan(np.hypot(dx, dy))
    orientacion = np.arctan2(-dx, dy)

    azimut = math.radians(360.0 - 315.0 + 90.0)
    cenit = math.radians(90.0 - 45.0)
    sombra = np.cos(cenit) * np.cos(pendiente) + np.sin(cenit) * np.sin(pendiente) * np.cos(
        azimut - orientacion
    )
    return np.clip(sombra, 0.0, 1.0)


def escribir_relieve(marco) -> tuple[int, int, int] | None:
    """El sombreado del marco, como PNG en gris con canal alfa.

    Gris y no color: el fondo lo pone el CSS del sitio, y una imagen en escala
    de grises con alfa se apoya sobre cualquier tema sin pelearse con la paleta.
    Además pesa un tercio de lo que pesaría en color.
    """
    ruta_raster = GEO / "raster.json"
    if not ruta_raster.exists() or not (GEO / "terrain.png").exists():
        log("sin terrain.png: el mapa sale sin relieve")
        return None

    raster = json.loads(ruta_raster.read_text(encoding="utf-8"))
    elevacion = elevacion_del_terrain(raster)

    oeste, sur, este, norte = marco
    factor_x = math.cos(math.radians((sur + norte) / 2))
    # Dos veces el lienzo: a este tamaño el relieve es textura, pero en una
    # pantalla densa no tiene que verse el píxel.
    alto_px = ALTO * 2
    ancho_px = max(1, round(alto_px * ((este - oeste) * factor_x) / (norte - sur)))

    recorte = recortar(elevacion, raster["bounds"], marco, ancho_px, alto_px)
    metros_por_px = (norte - sur) * 111_320.0 / alto_px
    sombra = sombrear(recorte, metros_por_px)

    # Se centra en la mediana del propio recorte: así la llanura queda casi
    # transparente y solo aparecen las laderas, que es lo que dibuja el terreno.
    diferencia = sombra - float(np.median(sombra))
    gris = np.where(diferencia < 0, 0, 255).astype(np.uint8)
    alfa = np.clip(np.abs(diferencia) * np.where(diferencia < 0, 2.3, 1.5), 0, 1)
    # El alfa se escalona en dieciséis niveles antes de guardar. A ojo no cambia
    # nada —son sombras suaves— y al PNG le importa mucho: un degradado continuo
    # no se comprime, dieciséis grises sí.
    alfa = np.round(alfa * 15) / 15

    Image.fromarray(np.dstack([gris, (alfa * 255).astype(np.uint8)]), mode="LA").save(
        RELIEVE, optimize=True
    )
    return RELIEVE.stat().st_size, ancho_px, alto_px


def main() -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.parse_args()

    cuenca = leer("basin")
    if not cuenca:
        raise SystemExit("falta data/processed/geo/basin.geojson; correr transform/geo_layers.py")

    # El encuadre sale de la cuenca más un respiro, recortado a lo que cubre el
    # DEM y ajustado después a la proporción del lienzo.
    figura_cuenca = unary_union([shape(f["geometry"]) for f in cuenca])
    oeste, sur, este, norte = figura_cuenca.bounds
    oeste, sur, este, norte = oeste - 0.25, sur - 0.25, este + 0.25, norte + 0.25
    oeste, sur = max(oeste, RECORTE_DEM[0]), max(sur, RECORTE_DEM[1])
    este, norte = min(este, RECORTE_DEM[2]), min(norte, RECORTE_DEM[3])

    factor_x = math.cos(math.radians((sur + norte) / 2))
    proporcion = (ANCHO - 2 * MARGEN) / (ALTO - 2 * MARGEN)
    ancho_geo = (este - oeste) * factor_x
    alto_geo = norte - sur
    if ancho_geo / alto_geo < proporcion:
        falta = (alto_geo * proporcion - ancho_geo) / factor_x
        oeste = max(oeste - falta / 2, RECORTE_DEM[0])
        este = min(este + falta / 2, RECORTE_DEM[2])
    else:
        falta = ancho_geo / proporcion - alto_geo
        sur = max(sur - falta / 2, RECORTE_DEM[1])
        norte = min(norte + falta / 2, RECORTE_DEM[3])

    marco = (oeste, sur, este, norte)
    proyeccion = Proyeccion(marco)
    proyectar = proyeccion.punto
    # Todo se recorta al marco: las provincias siguen hasta el Atlántico y las
    # terminales llegan al norte del país, y lo que se sale del lienzo no dibuja
    # nada, solo pesa.
    caja = box(*marco)

    def es_rio(propiedades: dict) -> bool:
        return str(propiedades.get("tipo", "")).lower().startswith("río")

    def es_de_vaca_muerta(propiedades: dict) -> bool:
        return str(propiedades.get("vaca_muerta", "0")) not in ("0", "None", "")

    def tiene_a_ypf(propiedades: dict) -> bool:
        """Operada por YPF o con YPF en el título. El padrón trae las dos cosas."""
        texto = f"{propiedades.get('operador', '')} {propiedades.get('participacion', '')}"
        return "YPF" in texto.upper()

    capas = {
        "cuenca": [
            t for f in cuenca for t in a_trazos(f["geometry"], proyectar, TOLERANCIAS["basin"], caja)
        ],
        "provincias": capa_de_poligonos("provinces", proyectar, caja),
        "concesiones": capa_disuelta("concessions", proyectar, caja, pegado=0.012),
        # Las áreas donde está YPF, para el módulo que mira solo a la compañía.
        "areas_ypf": capa_disuelta("concessions", proyectar, caja, pegado=0.012, filtro=tiene_a_ypf),
        # Los yacimientos son el detalle fino adentro de la mancha: dónde está
        # de verdad la roca que se perfora. Los de Vaca Muerta van en su propia
        # capa porque son los que cuenta este caso.
        "yacimientos": capa_de_poligonos(
            "fields", proyectar, caja, lambda p: not es_de_vaca_muerta(p)
        ),
        "vaca_muerta": capa_de_poligonos("fields", proyectar, caja, es_de_vaca_muerta),
        "rios": capa_de_lineas("rivers", proyectar, caja, es_rio, clave="rivers"),
        "arroyos": capa_de_lineas("rivers", proyectar, caja, lambda p: not es_rio(p), clave="arroyos"),
        "rutas": capa_de_lineas("roads", proyectar, caja, lambda p: p.get("jerarquia") == "nacional"),
        "rutas_provinciales": capa_de_lineas(
            "roads", proyectar, caja, lambda p: p.get("jerarquia") != "nacional"
        ),
        "ferrocarril": capa_de_lineas("rail", proyectar, caja),
        "gasoductos": capa_de_lineas("gas_pipelines", proyectar, caja),
        "ductos": capa_de_lineas("pipelines", proyectar, caja, lambda p: p.get("tipo") != "GASODUCTO"),
    }

    localidades = puntos_de("towns", proyectar, caja, "nombre")
    for punto in localidades:
        rango = LOCALIDADES_CLAVE.get(punto.get("nombre", ""))
        if rango:
            punto["rango"] = rango
    colocar_rotulos(localidades)

    puntos = {
        "instalaciones": puntos_de("facilities", proyectar, caja),
        "localidades": localidades,
        "pozos": pozos_con_peso(proyectar, caja),
        "terminales": puntos_de("terminals", proyectar, caja, "localidad"),
        "refinerias": puntos_de("refineries", proyectar, caja, "nombre"),
    }

    relieve = escribir_relieve(marco)
    x0, y0, x1, y1 = proyeccion.caja_dibujada

    payload = {
        "generado": __import__("pandas").Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lienzo": {"ancho": ANCHO, "alto": ALTO},
        "encuadre": [round(v, 3) for v in marco],
        "escala_km": round(proyeccion.km_por_unidad, 3),
        "relieve": (
            {
                "archivo": "mapa_relieve.png",
                "x": round(x0, 1),
                "y": round(y0, 1),
                "ancho": round(x1 - x0, 1),
                "alto": round(y1 - y0, 1),
                "fuente": "Copernicus DEM GLO-30 (ESA)",
            }
            if relieve
            else None
        ),
        "capas": capas,
        "puntos": puntos,
        "nota": (
            "Trazos reales, simplificados con Douglas-Peucker hasta la tolerancia "
            "en la que el ojo no distingue la diferencia a este tamaño. Salen de "
            "las mismas capas que alimentan el mapa interactivo; el sombreado, "
            "del mismo DEM."
        ),
    }
    tamanio = save_json(payload, SALIDA)

    resumen = ", ".join(f"{nombre} {len(trazos)}" for nombre, trazos in capas.items() if trazos)
    log(f"{resumen} · puntos: " + ", ".join(f"{n} {len(p)}" for n, p in puntos.items() if p))
    if relieve:
        bytes_relieve, ancho_px, alto_px = relieve
        log(f"{rel(RELIEVE)} ({human(bytes_relieve)}, {ancho_px}x{alto_px})")
    record(
        "transform/mapa-web",
        rows=sum(len(t) for t in capas.values()),
        bytes=int(tamanio) + (relieve[0] if relieve else 0),
        outputs=[rel(SALIDA)] + ([rel(RELIEVE)] if relieve else []),
        source=rel(GEO),
        note="mapa liviano: cuenca, yacimientos, ductos, rutas y relieve sombreado",
    )
    log(f"{rel(SALIDA)} ({human(tamanio)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
