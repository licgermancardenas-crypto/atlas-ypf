"""Convierte las capas geográficas en trazos SVG para el sitio.

Por qué existe: el módulo del mapa ya dibuja la cuenca con deck.gl, pero eso
pesa un megabyte largo y solo sirve adentro de esa página. Para ilustrar —el
encabezado de un módulo, una tarjeta, una sección de infraestructura— hace falta
lo mismo pero liviano: la cuenca, los ductos y las rutas convertidos a unos
pocos trazos SVG que se sirven con la página.

La diferencia con dibujar un mapa a mano es que estos trazos son los de verdad.
El oleoducto que cruza la ilustración es el oleoducto, simplificado hasta donde
el ojo no nota la diferencia a ese tamaño, y sale del mismo archivo que alimenta
el mapa interactivo.

Entrada:  data/processed/geo/*.geojson  (los arma transform/geo_layers.py)
Salida:   data/processed/mapa_web.json  (trazos ya proyectados al lienzo)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

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

# El lienzo. Apenas más ancho que alto: la cuenca es alta y estirar el marco a
# formato panorámico deja un tercio del dibujo en blanco. Lo que sobra a la
# derecha lo ocupan los gasoductos troncales, que se van para el Atlántico.
ANCHO = 330
ALTO = 280
MARGEN = 10

# Cuánto se puede simplificar cada capa sin que se note. En grados: 0,01° son
# aproximadamente un kilómetro, y a este tamaño un kilómetro es medio píxel.
TOLERANCIAS = {
    "basin": 0.02,
    "concessions": 0.02,
    "pipelines": 0.012,
    "gas_pipelines": 0.012,
    "roads": 0.012,
    "rivers": 0.025,
    "provinces": 0.03,
}

# Largo mínimo, en grados, para que un trazo entre al dibujo. Las redes vienen
# como una maraña de tramos —cada empalme corta la línea— y a esta escala un
# tramo de dos kilómetros es un punto. Se unen los que se tocan y se descarta lo
# que quede corto: queda el trazado troncal, que es lo que la ilustración tiene
# que mostrar.
MINIMOS = {
    "pipelines": 0.02,
    "gas_pipelines": 0.02,
    "roads": 0.05,
    "rivers": 0.12,
}


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
        import math

        oeste, sur, este, norte = bbox
        self.oeste, self.sur, self.este, self.norte = oeste, sur, este, norte
        self.factor_x = math.cos(math.radians((sur + norte) / 2))

        ancho_geo = (este - oeste) * self.factor_x
        alto_geo = norte - sur
        escala = min((ANCHO - 2 * MARGEN) / ancho_geo, (ALTO - 2 * MARGEN) / alto_geo)
        self.escala = escala
        self.desplazamiento_x = (ANCHO - ancho_geo * escala) / 2
        self.desplazamiento_y = (ALTO - alto_geo * escala) / 2

    def punto(self, lon: float, lat: float) -> tuple[float, float]:
        x = (lon - self.oeste) * self.factor_x * self.escala + self.desplazamiento_x
        y = (self.norte - lat) * self.escala + self.desplazamiento_y
        return round(x, 1), round(y, 1)


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


def capa_de_lineas(nombre: str, proyectar, caja=None, filtro=None) -> list[str]:
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
    minimo = MINIMOS.get(nombre, 0.0)
    partes = [parte for parte in partes if parte.length >= minimo]

    trazos: list[str] = []
    for parte in partes:
        trazos.extend(a_trazos(parte.__geo_interface__, proyectar, TOLERANCIAS.get(nombre, 0.01), caja))
    return [t for t in trazos if t.count("L") >= 2]


def capa_disuelta(nombre: str, proyectar, caja=None, pegado: float = 0.0) -> list[str]:
    """Las concesiones, fundidas en una sola silueta.

    Dibujadas una por una son ciento ochenta rectángulos y quince kilobytes de
    ruido; el mapa interactivo ya las muestra así, con su nombre y su operador.
    Acá interesa otra cosa: la mancha, dónde está efectivamente concesionada la
    cuenca. Se las une con un pegado chico para que los lotes linderos cierren
    en una figura en vez de quedar como piezas sueltas.
    """
    figuras = []
    for feature in leer(nombre):
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


def capa_de_poligonos(nombre: str, proyectar, caja=None, filtro=None) -> list[str]:
    trazos: list[str] = []
    for feature in leer(nombre):
        if filtro and not filtro(feature.get("properties", {})):
            continue
        trazos.extend(a_trazos(feature["geometry"], proyectar, TOLERANCIAS.get(nombre, 0.01), caja))
    return [t for t in trazos if t.count("L") >= 2]


def puntos_de(nombre: str, proyectar, caja=None, campo: str | None = None, limite: int = 0) -> list[dict]:
    salida = []
    for feature in leer(nombre):
        geometria = shape(feature["geometry"])
        if geometria.is_empty:
            continue
        centro = geometria if geometria.geom_type == "Point" else geometria.centroid
        if caja is not None and not caja.contains(centro):
            continue
        x, y = proyectar(centro.x, centro.y)
        punto = {"x": x, "y": y}
        if campo:
            etiqueta = feature.get("properties", {}).get(campo)
            if etiqueta:
                punto["nombre"] = str(etiqueta).title()
        salida.append(punto)
    if limite:
        salida = salida[:limite]
    return salida


def main() -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.parse_args()

    cuenca = leer("basin")
    if not cuenca:
        raise SystemExit("falta data/processed/geo/basin.geojson; correr transform/geo_layers.py")

    # El encuadre sale de la cuenca más un respiro, con dos correcciones. Una,
    # se estira hacia el este, que es por donde salen los ductos y donde están
    # las refinerías: sin eso el dibujo termina en el borde de la cuenca y no se
    # entiende adónde va el crudo. Dos, se ajusta a la proporción del lienzo,
    # porque la cuenca es más alta que ancha y encuadrarla tal cual dejaría la
    # mitad del ancho en blanco.
    import math

    figura_cuenca = unary_union([shape(f["geometry"]) for f in cuenca])
    oeste, sur, este, norte = figura_cuenca.bounds
    oeste -= 0.2
    este += (este - oeste) * 0.1
    sur -= 0.2
    norte += 0.2

    factor_x = math.cos(math.radians((sur + norte) / 2))
    proporcion = (ANCHO - 2 * MARGEN) / (ALTO - 2 * MARGEN)
    ancho_geo = (este - oeste) * factor_x
    alto_geo = norte - sur
    if ancho_geo / alto_geo < proporcion:
        falta = (alto_geo * proporcion - ancho_geo) / factor_x
        # algo más hacia el este, que es adonde salen los gasoductos troncales
        oeste -= falta * 0.4
        este += falta * 0.6
    else:
        falta = ancho_geo / proporcion - alto_geo
        sur -= falta / 2
        norte += falta / 2

    proyeccion = Proyeccion((oeste, sur, este, norte))
    proyectar = proyeccion.punto
    # Todo se recorta al marco: las provincias siguen hasta el Atlántico y los
    # puntos de terminales llegan hasta el norte del país, y lo que se sale del
    # lienzo no dibuja nada, solo pesa.
    caja = box(oeste, sur, este, norte)

    capas = {
        "cuenca": [t for f in cuenca for t in a_trazos(f["geometry"], proyectar, TOLERANCIAS["basin"], caja)],
        "provincias": capa_de_poligonos("provinces", proyectar, caja),
        "concesiones": capa_disuelta("concessions", proyectar, caja, pegado=0.012),
        "ductos": capa_de_lineas("pipelines", proyectar, caja, lambda p: p.get("tipo") != "GASODUCTO"),
        "gasoductos": capa_de_lineas("gas_pipelines", proyectar, caja),
        "rutas": capa_de_lineas("roads", proyectar, caja, lambda p: p.get("jerarquia") == "nacional"),
        "rios": capa_de_lineas("rivers", proyectar, caja),
    }

    puntos = {
        "refinerias": puntos_de("refineries", proyectar, caja, "nombre"),
        "terminales": puntos_de("terminals", proyectar, caja, "localidad"),
        "localidades": puntos_de("towns", proyectar, caja, "nombre"),
        "pozos": puntos_de("well_clusters", proyectar, caja),
    }

    payload = {
        "generado": __import__("pandas").Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lienzo": {"ancho": ANCHO, "alto": ALTO},
        "encuadre": [round(v, 3) for v in (proyeccion.oeste, proyeccion.sur, proyeccion.este, proyeccion.norte)],
        "capas": capas,
        "puntos": puntos,
        "nota": (
            "Trazos reales, simplificados con Douglas-Peucker hasta la tolerancia "
            "en la que el ojo no distingue la diferencia a este tamaño. Salen de "
            "las mismas capas que alimentan el mapa interactivo."
        ),
    }
    tamanio = save_json(payload, SALIDA)

    resumen = ", ".join(f"{nombre} {len(trazos)}" for nombre, trazos in capas.items() if trazos)
    log(f"{resumen} · puntos: " + ", ".join(f"{n} {len(p)}" for n, p in puntos.items() if p))
    record(
        "transform/mapa-web",
        rows=sum(len(t) for t in capas.values()),
        bytes=int(tamanio),
        outputs=[rel(SALIDA)],
        source=rel(GEO),
        note="trazos SVG de cuenca, ductos y rutas para las ilustraciones del sitio",
    )
    log(f"{rel(SALIDA)} ({human(tamanio)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
