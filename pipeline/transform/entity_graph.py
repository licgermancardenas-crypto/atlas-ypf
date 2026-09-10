"""Grafo de entidades: concesiones, yacimientos, empresas y pozos.

Entrada: data/processed/production_wells.parquet   (transform/production_wells.py)
         data/raw/geo/concessions/*.zip            (ingest/geo_layers.py)
Salida:  data/processed/graph/entities.json        (grafo completo, con pozos)
         data/processed/graph/entities_agregado.json (sin pozos: lo que carga la web)

El resto del proyecto mira el negocio por una dimensión a la vez: la producción
por empresa, las reservas por cuenca, el NPV por yacimiento. Lo que ninguna de
esas vistas contesta es con quién comparte cada quien. Vaca Muerta se opera en
bloques con socios: la misma área tiene un operador y tres o cuatro empresas
más adentro con su porcentaje, y esas participaciones cruzadas son la razón por
la que la producción bruta operada y la neta consolidada no coinciden nunca.
El grafo es la forma de ver eso: quién opera qué, con quién, y cuánto sale de
cada nodo.

Dos decisiones que conviene tener a la vista antes de leer un número de acá:

1. **La titularidad sale del shapefile de concesiones, campo PARTICIPAC.** No
   hizo falta una fuente nueva: el padrón de Concesiones de Explotación de la
   Secretaría de Energía —el mismo que ya bajamos para dibujar los polígonos—
   trae la lista de socios con su porcentaje en las 297 áreas del país.

2. **Los nombres no se matchean de forma difusa, nunca.** De las 102
   concesiones con producción, 88 pegan exacto contra el padrón y 14 no. Las
   candidatas que ofrece un match aproximado son trampas: "BAJO DEL TORO"
   contra "BAJO DEL TORO NORTE" son áreas distintas, y "CERRO ARENA" contra
   "CERRO BANDERA" directamente no tienen nada que ver. Este proyecto ya tuvo
   un bug de este tipo —una fila de totales tomada por empresa, que le asignó
   las reservas del país entero a un solo operador— y la lección fue que un
   match plausible y equivocado es peor que un dato ausente. Las 14 quedan sin
   aristas de titularidad, se listan en el JSON y valen el 0,5% de la
   producción del mes.
"""

from __future__ import annotations

import glob
import re
import sys
import unicodedata
import warnings
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
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

SRC_PANEL = PROCESSED / "production_wells.parquet"
SRC_CONCESIONES = RAW / "geo" / "concessions"

OUT = PROCESSED / "graph"
SALIDA = OUT / "entities.json"
SALIDA_AGREGADO = OUT / "entities_agregado.json"
OUT_POZOS = OUT / "pozos"

# El estado con el que la Secretaría marca un pozo que efectivamente produjo en
# el mes. Todo lo demás —parado, en estudio, a abandonar— es inventario.
ESTADO_ACTIVO = "Extracción Efectiva"


# --------------------------------------------------------------------------- #
# Identidad de los nodos
# --------------------------------------------------------------------------- #
def slug(texto: str) -> str:
    """Identificador estable a partir de un nombre.

    Se usa el nombre y no el código del padrón porque las 14 concesiones sin
    match no tienen código, y un grafo donde el id depende de si el área pegó
    contra otro archivo es un grafo que se rompe solo.
    """
    limpio = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    limpio = re.sub(r"[^a-zA-Z0-9]+", "-", limpio).strip("-").lower()
    return limpio or "sin-dato"


def nid(tipo: str, nombre: str) -> str:
    return f"{tipo}:{slug(nombre)}"


# --------------------------------------------------------------------------- #
# Titularidad
# --------------------------------------------------------------------------- #
def canon_empresa(nombre: str) -> str:
    """Nombre comercial del operador, con la misma tabla que usan los pozos.

    Se importa de production_wells en vez de copiarse: si las dos listas
    divergen, el mismo operador entra al grafo como dos nodos distintos y el
    grafo miente sin dar ningún síntoma.
    """
    import importlib.util

    global _CANON
    if _CANON is None:
        ruta = Path(__file__).resolve().parent / "production_wells.py"
        especificacion = importlib.util.spec_from_file_location("production_wells", ruta)
        modulo = importlib.util.module_from_spec(especificacion)
        especificacion.loader.exec_module(modulo)
        _CANON = modulo.OPERADOR_CANON

    texto = str(nombre).strip()
    arriba = texto.upper()
    for patron, canonico in _CANON:
        if patron in arriba:
            return canonico
    return presentar(texto)


_CANON: list[tuple[str, str]] | None = None

# Sufijos societarios: en un nombre propio van en mayuscula, no capitalizados.
SUFIJOS = {
    "SA", "SAU", "SRL", "SE", "SL", "SAPEM", "SAIC", "SAAIC", "LLC", "LTD",
    "AS", "EP", "SAS", "SCA", "OGE", "E&P",
}


def _capitalizar(palabra: str) -> str:
    """capitalize() pero sobre la primera letra, no sobre el primer caracter.

    Hace falta por los nombres entre parentesis: capitalize() sobre
    "(SUCURSAL" mira el parentesis, no encuentra letra que subir y baja todo
    el resto.
    """
    bajo = palabra.lower()
    for indice, caracter in enumerate(bajo):
        if caracter.isalpha():
            return bajo[:indice] + caracter.upper() + bajo[indice + 1 :]
    return bajo


def presentar(nombre: str) -> str:
    """Casing legible para los nombres que el canon no toca.

    El padron publica casi todo en mayuscula sostenida y alguno en minuscula
    ("petronas e&p argentina s.a"), lo que en una lista de chips se lee como si
    fueran fuentes distintas. Se capitaliza palabra por palabra, dejando los
    sufijos societarios en mayuscula.

    Las palabras que ya mezclan mayusculas y minusculas se dejan como estan:
    "PBBPolisur" lo escribio asi la empresa, y title() lo arruinaria.
    """
    palabras = []
    for palabra in nombre.split():
        desnudo = palabra.replace(".", "").replace(",", "").upper()
        if desnudo in SUFIJOS:
            palabras.append(palabra.upper())
        elif palabra.isupper() or palabra.islower():
            palabras.append(_capitalizar(palabra))
        else:
            palabras.append(palabra)
    return " ".join(palabras)

# "<br> YPF S.A.: 53 %<br> TECPETROL S.A.: 23 %" -> [("YPF S.A.", 53.0), ...]
SOCIO = re.compile(r"([^<>:]+?)\s*:\s*([\d.,]+)\s*%")


def parsear_participacion(texto: str) -> list[tuple[str, float]]:
    """Saca los pares empresa/porcentaje del campo PARTICIPAC del padrón."""
    if not isinstance(texto, str) or not texto.strip():
        return []
    socios: list[tuple[str, float]] = []
    for nombre, porcentaje in SOCIO.findall(texto.replace("<br>", " ")):
        nombre = nombre.strip(" .-")
        if not nombre:
            continue
        try:
            pct = float(porcentaje.replace(",", "."))
        except ValueError:
            continue
        socios.append((canon_empresa(nombre), round(pct, 2)))

    # Un mismo grupo puede figurar dos veces con razones sociales distintas y
    # quedar unificado por el canon: se suman los porcentajes en vez de dejar
    # dos aristas al mismo nodo.
    unidos: dict[str, float] = {}
    for nombre, pct in socios:
        unidos[nombre] = round(unidos.get(nombre, 0.0) + pct, 2)
    return sorted(unidos.items(), key=lambda par: -par[1])


def leer_titularidad() -> dict[str, list[tuple[str, float]]]:
    """Socios y porcentajes por concesión, indexados por nombre en mayúsculas."""
    zips = sorted(glob.glob(str(SRC_CONCESIONES / "*.zip")))
    if not zips:
        log(f"falta {rel(SRC_CONCESIONES)}: correr antes pipeline/ingest/geo_layers.py")
        return {}

    import geopandas as gpd

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        padron = gpd.read_file("zip://" + zips[0])

    if "PARTICIPAC" not in padron.columns or "NOMBRE_DE_" not in padron.columns:
        log("el padron de concesiones no trae NOMBRE_DE_/PARTICIPAC; sin titularidad")
        return {}

    titulares: dict[str, list[tuple[str, float]]] = {}
    for _, fila in padron.iterrows():
        nombre = str(fila.NOMBRE_DE_ or "").strip().upper()
        if not nombre:
            continue
        socios = parsear_participacion(fila.PARTICIPAC)
        if socios:
            titulares[nombre] = socios

    log(f"  titularidad: {len(titulares)} concesiones del padron con socios y porcentaje")
    return titulares


# --------------------------------------------------------------------------- #
# Construcción del grafo
# --------------------------------------------------------------------------- #
def construir(panel: pd.DataFrame, titulares: dict[str, list[tuple[str, float]]]) -> dict:
    mes = panel.fecha.max()
    ultimo = panel[panel.fecha == mes].copy()
    dias = int(mes.days_in_month)

    # Un pozo sin operadora asignada no puede colgar de ninguna empresa: sin esa
    # arista el nodo queda suelto y ensucia el grafo sin aportar nada.
    sin_operador = ultimo.operador.isna() | (ultimo.operador.astype("string").str.strip() == "")
    excluidos = int(sin_operador.sum())
    ultimo = ultimo[~sin_operador]
    log(f"  pozos excluidos por no tener empresa operadora: {excluidos}")

    ultimo["bbl_d"] = (ultimo.petroleo_bbl / dias).round(1)
    # El panel guarda el gas ya convertido a boe; para publicarlo en m3/d hay que
    # deshacer esa conversión (el crudo viene en Mm3, o sea miles de m3).
    ultimo["gas_m3_d"] = (ultimo.gas_boe / MM3_TO_BOE * 1000 / dias).round(1)
    # Cuatro pozos del ultimo mes vienen sin estado. Comparar contra NA da NA, y
    # un NA en un `if` explota; ausencia de estado se lee como no activo.
    ultimo["activo"] = ultimo.estado.eq(ESTADO_ACTIVO).fillna(False).astype(bool)

    ultimo["concesion"] = ultimo.concesion.str.strip()
    ultimo["yacimiento"] = ultimo.yacimiento.str.strip()
    ultimo["empresa"] = ultimo.operador.map(lambda nombre: canon_empresa(str(nombre)))

    nodos: list[dict] = []
    aristas: list[dict] = []

    # --- empresas ---------------------------------------------------------- #
    #
    # Se indexan por id de nodo y no por nombre. La razon es concreta: el padron
    # escribe la misma empresa de varias formas -"COMPAÑIA" y "COMPAÑÍA", con y
    # sin acento- y dos nombres distintos que caen en el mismo slug son un id
    # repetido, o sea dos nodos para una sola empresa. El validador de
    # integridad lo caza, pero es mejor no generarlo.
    #
    # El label que sobrevive es el del panel de produccion, que entra primero y
    # ya viene canonizado por production_wells; las variantes del padron solo
    # aportan metricas, nunca pisan el nombre.
    empresas: dict[str, dict] = {}

    def registrar_empresa(nombre: str) -> str:
        id_empresa = nid("empresa", nombre)
        if id_empresa not in empresas:
            empresas[id_empresa] = {
                "label": nombre,
                "pozos_operados": 0,
                "produccion_atribuida_bbl_d": 0.0,
                "yacimientos_presentes": 0,
                "concesiones_operadas": 0,
            }
        return id_empresa

    for nombre, grupo in ultimo.groupby("empresa", observed=True):
        ficha = empresas[registrar_empresa(str(nombre))]
        ficha["pozos_operados"] += int(len(grupo))
        ficha["produccion_atribuida_bbl_d"] = round(
            ficha["produccion_atribuida_bbl_d"] + float(grupo.bbl_d.sum()), 1
        )
        ficha["yacimientos_presentes"] += int(grupo.yacimiento.nunique())
        ficha["concesiones_operadas"] += int(grupo.concesion.nunique())

    # --- concesiones ------------------------------------------------------- #
    sin_titularidad: list[str] = []
    for nombre, grupo in ultimo.groupby("concesion", observed=True):
        socios = titulares.get(nombre.upper(), [])
        if not socios:
            sin_titularidad.append(nombre)

        nodos.append(
            {
                "id": nid("concesion", nombre),
                "type": "concesion",
                "label": nombre,
                "props": {
                    "cuenca": str(grupo.cuenca.mode().iloc[0]) if not grupo.cuenca.isna().all() else None,
                    "provincia": str(grupo.provincia.mode().iloc[0])
                    if not grupo.provincia.isna().all()
                    else None,
                    "empresas": [empresa for empresa, _ in socios],
                    "operadores": sorted(grupo.empresa.dropna().unique().tolist()),
                    "yacimientos": sorted(grupo.yacimiento.dropna().unique().tolist()),
                    "produccion_total_bbl_d": round(float(grupo.bbl_d.sum()), 1),
                    "produccion_gas_m3d": round(float(grupo.gas_m3_d.sum()), 1),
                    "cantidad_pozos": int(len(grupo)),
                    "pozos_activos": int(grupo.activo.sum()),
                    "titularidad_conocida": bool(socios),
                },
            }
        )
        for empresa, pct in socios:
            aristas.append(
                {
                    "source": nid("concesion", nombre),
                    "target": registrar_empresa(empresa),
                    "type": "titularidad",
                    "props": {"participacion_pct": pct},
                }
            )

    # --- yacimientos ------------------------------------------------------- #
    #
    # El id sale del nombre del yacimiento solo, sin la concesion adelante. Es
    # lo que permite que el mapa seleccione un yacimiento: fields.geojson trae
    # el nombre y no la concesion, asi que un id compuesto seria un id que el
    # mapa no puede construir.
    #
    # Es seguro mientras los nombres no se repitan entre concesiones -hoy son
    # 141 nombres para 141 pares-, y si algun dia se repiten se desambigua con
    # la concesion en vez de generar un id duplicado en silencio.
    nombres_repetidos = {
        nombre
        for nombre, cuantas in ultimo.groupby("yacimiento", observed=True).concesion.nunique().items()
        if cuantas > 1
    }
    if nombres_repetidos:
        log(
            f"  {len(nombres_repetidos)} yacimientos con el mismo nombre en varias concesiones: "
            "se les agrega la concesion al id"
        )

    for (concesion, yacimiento), grupo in ultimo.groupby(["concesion", "yacimiento"], observed=True):
        id_yac = nid(
            "yacimiento",
            f"{concesion} {yacimiento}" if yacimiento in nombres_repetidos else yacimiento,
        )
        nodos.append(
            {
                "id": id_yac,
                "type": "yacimiento",
                "label": yacimiento,
                "props": {
                    "concesion": concesion,
                    "cuenca": str(grupo.cuenca.mode().iloc[0]) if not grupo.cuenca.isna().all() else None,
                    "empresas_operando": sorted(grupo.empresa.dropna().unique().tolist()),
                    "cantidad_empresas": int(grupo.empresa.nunique()),
                    "cantidad_pozos": int(len(grupo)),
                    "pozos_activos": int(grupo.activo.sum()),
                    "produccion_bbl_d": round(float(grupo.bbl_d.sum()), 1),
                    "produccion_gas_m3d": round(float(grupo.gas_m3_d.sum()), 1),
                    "vaca_muerta": bool(grupo.es_vaca_muerta.any()),
                },
            }
        )
        aristas.append(
            {
                "source": nid("concesion", concesion),
                "target": id_yac,
                "type": "contiene",
            }
        )

        for pozo in grupo.itertuples():
            id_pozo = f"pozo:{int(pozo.pozo_id)}"
            nodos.append(
                {
                    "id": id_pozo,
                    "type": "pozo",
                    "label": str(pozo.sigla),
                    "props": {
                        "empresa": str(pozo.empresa),
                        "yacimiento": yacimiento,
                        "concesion": concesion,
                        "formacion": str(pozo.formacion) if pd.notna(pozo.formacion) else None,
                        "produccion_bbl_d": float(pozo.bbl_d),
                        "produccion_gas_m3d": float(pozo.gas_m3_d),
                        "estado": "activo" if pozo.activo else "inactivo",
                        "estado_detalle": str(pozo.estado) if pd.notna(pozo.estado) else None,
                        "vaca_muerta": bool(pozo.es_vaca_muerta is True),
                    },
                }
            )
            aristas.append({"source": id_yac, "target": id_pozo, "type": "tiene_pozo"})
            aristas.append(
                {
                    "source": id_pozo,
                    "target": nid("empresa", str(pozo.empresa)),
                    "type": "operado_por",
                }
            )

    # --- empresas, ya con todo lo que las toca ----------------------------- #
    participadas = {}
    for arista in aristas:
        if arista["type"] == "titularidad":
            participadas[arista["target"]] = participadas.get(arista["target"], 0) + 1

    for id_empresa, metricas in sorted(empresas.items()):
        nodos.append(
            {
                "id": id_empresa,
                "type": "empresa",
                "label": metricas["label"],
                "props": {
                    "concesiones_participadas": participadas.get(id_empresa, 0),
                    "concesiones_operadas": metricas["concesiones_operadas"],
                    "yacimientos_presentes": metricas["yacimientos_presentes"],
                    "produccion_atribuida_bbl_d": metricas["produccion_atribuida_bbl_d"],
                    "pozos_operados": metricas["pozos_operados"],
                },
            }
        )

    if sin_titularidad:
        log(
            f"  {len(sin_titularidad)} concesiones sin match en el padron: "
            f"{', '.join(sorted(sin_titularidad)[:6])}"
            + (" ..." if len(sin_titularidad) > 6 else "")
        )

    return {
        "generado": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mes_referencia": mes.strftime("%Y-%m"),
        "fuentes": [
            "Secretaria de Energia, produccion por pozo (capitulo IV)",
            "Secretaria de Energia, Concesiones de Explotacion (campo PARTICIPAC)",
        ],
        "unidades": {"produccion_bbl_d": "bbl/d", "produccion_gas_m3d": "m3/d"},
        "advertencias": {
            "pozos_sin_operadora_excluidos": excluidos,
            "concesiones_sin_titularidad": sorted(sin_titularidad),
            "criterio_match": (
                "El cruce contra el padron de concesiones es por nombre exacto. No se usa "
                "match aproximado: las candidatas cercanas son areas distintas."
            ),
            "produccion": (
                f"Bruta operada del mes {mes.strftime('%Y-%m')}, no neta consolidada. "
                "La participacion de los socios esta incluida en el total del operador."
            ),
        },
        "nodes": nodos,
        "edges": aristas,
    }


# --------------------------------------------------------------------------- #
# Integridad referencial
# --------------------------------------------------------------------------- #
def validar(grafo: dict) -> list[str]:
    """Ninguna arista puede apuntar a un nodo que no existe, y ningún id repetirse.

    Se corre antes de escribir y no después: un grafo con aristas huérfanas
    rompe el frontend en el momento de dibujar, lejos de acá, con un error que
    no dice nada de su causa.
    """
    problemas: list[str] = []

    vistos: set[str] = set()
    duplicados: set[str] = set()
    for nodo in grafo["nodes"]:
        if nodo["id"] in vistos:
            duplicados.add(nodo["id"])
        vistos.add(nodo["id"])
    if duplicados:
        problemas.append(
            f"{len(duplicados)} ids de nodo repetidos (p. ej. {sorted(duplicados)[:3]})"
        )

    huerfanas = [
        arista
        for arista in grafo["edges"]
        if arista["source"] not in vistos or arista["target"] not in vistos
    ]
    if huerfanas:
        ejemplo = huerfanas[0]
        problemas.append(
            f"{len(huerfanas)} aristas apuntan a nodos inexistentes "
            f"(p. ej. {ejemplo['source']} -> {ejemplo['target']})"
        )

    for tipo in ("concesion", "yacimiento", "empresa", "pozo"):
        if not any(nodo["type"] == tipo for nodo in grafo["nodes"]):
            problemas.append(f"no hay ningun nodo de tipo {tipo}")

    return problemas


def escribir_shards(grafo: dict) -> tuple[int, int]:
    """Un archivo de pozos por concesion, para expandir de a un nodo.

    El grafo completo pesa 2,5 MB y el 95% son pozos. Bajarlo entero para que
    alguien abra una concesion repite el error que ya se corrigio en el mapa:
    pagar todo el detalle por adelantado para mostrar una parte. Partido por
    concesion, expandir un nodo cuesta entre 5 y 200 KB.

    El corte es por concesion y no por yacimiento porque una concesion contiene
    a sus yacimientos: expandir cualquiera de los dos se resuelve con el mismo
    archivo, y son 102 en vez de 141.
    """
    pozos = [nodo for nodo in grafo["nodes"] if nodo["type"] == "pozo"]
    ids_pozo = {nodo["id"] for nodo in pozos}
    aristas = [
        arista
        for arista in grafo["edges"]
        if arista["source"] in ids_pozo or arista["target"] in ids_pozo
    ]

    por_concesion: dict[str, dict] = {}
    for nodo in pozos:
        clave = slug(nodo["props"]["concesion"])
        por_concesion.setdefault(clave, {"nodes": [], "edges": []})["nodes"].append(nodo)

    indice = {nodo["id"]: slug(nodo["props"]["concesion"]) for nodo in pozos}
    for arista in aristas:
        extremo = arista["source"] if arista["source"] in ids_pozo else arista["target"]
        por_concesion[indice[extremo]]["edges"].append(arista)

    if OUT_POZOS.exists():
        for viejo in OUT_POZOS.glob("*.json"):
            viejo.unlink()
    OUT_POZOS.mkdir(parents=True, exist_ok=True)

    total = 0
    for clave, partes in por_concesion.items():
        total += save_json(
            {"concesion": clave, "mes_referencia": grafo["mes_referencia"], **partes},
            OUT_POZOS / f"{clave}.json",
        )
    return len(por_concesion), total


def agregado(grafo: dict) -> dict:
    """El mismo grafo sin los pozos: es lo que carga la web por defecto.

    Los pozos son el 97% de los nodos y el 95% del peso. Mandarlos siempre para
    que el usuario mire cuatro concesiones es el mismo error que ya se corrigió
    en el mapa.
    """
    nodos = [nodo for nodo in grafo["nodes"] if nodo["type"] != "pozo"]
    ids = {nodo["id"] for nodo in nodos}
    aristas = [
        arista
        for arista in grafo["edges"]
        if arista["source"] in ids and arista["target"] in ids
    ]
    return {**grafo, "nodes": nodos, "edges": aristas, "incluye_pozos": False}


def main() -> int:
    args = base_parser("Arma el grafo de concesiones, yacimientos, empresas y pozos").parse_args()

    if not SRC_PANEL.exists():
        log(f"falta {rel(SRC_PANEL)}: correr antes transform/production_wells.py")
        return 1

    if SALIDA.exists() and not args.force:
        if SALIDA.stat().st_mtime > SRC_PANEL.stat().st_mtime:
            log(f"{rel(SALIDA)} esta al dia, se saltea (--force para rehacer)")
            return 0

    panel = pd.read_parquet(
        SRC_PANEL,
        columns=[
            "pozo_id", "fecha", "sigla", "operador", "concesion", "yacimiento",
            "cuenca", "provincia", "formacion", "estado", "es_vaca_muerta",
            "petroleo_bbl", "gas_boe",
        ],
    )
    titulares = leer_titularidad()
    if not titulares:
        log("sin dataset de titularidad: el grafo queda sin aristas de participacion")

    grafo = construir(panel, titulares)

    problemas = validar(grafo)
    if problemas:
        for problema in problemas:
            log(f"  INTEGRIDAD: {problema}")
        log("el grafo no se escribe: primero hay que arreglar la integridad referencial")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    bytes_completo = save_json(grafo, SALIDA)
    bytes_agregado = save_json(agregado(grafo), SALIDA_AGREGADO)
    shards, bytes_shards = escribir_shards(grafo)

    conteo = pd.Series([nodo["type"] for nodo in grafo["nodes"]]).value_counts()
    tipos = pd.Series([arista["type"] for arista in grafo["edges"]]).value_counts()
    log(
        f"escrito {rel(SALIDA)} - {len(grafo['nodes']):,} nodos, "
        f"{len(grafo['edges']):,} aristas, {human(bytes_completo)}"
    )
    log("  nodos:   " + ", ".join(f"{k} {v:,}" for k, v in conteo.items()))
    log("  aristas: " + ", ".join(f"{k} {v:,}" for k, v in tipos.items()))
    log(f"escrito {rel(SALIDA_AGREGADO)} - sin pozos, {human(bytes_agregado)}")
    log(
        f"escritos {shards} archivos en {rel(OUT_POZOS)} - pozos por concesion, "
        f"{human(bytes_shards)} en total"
    )

    record(
        "entity_graph",
        sources=[rel(SRC_PANEL), rel(SRC_CONCESIONES)],
        outputs=[rel(SALIDA), rel(SALIDA_AGREGADO), rel(OUT_POZOS)],
        shards_de_pozos=shards,
        mes_referencia=grafo["mes_referencia"],
        nodos=len(grafo["nodes"]),
        aristas=len(grafo["edges"]),
        nodos_por_tipo={str(k): int(v) for k, v in conteo.items()},
        aristas_por_tipo={str(k): int(v) for k, v in tipos.items()},
        pozos_excluidos=grafo["advertencias"]["pozos_sin_operadora_excluidos"],
        concesiones_sin_titularidad=len(grafo["advertencias"]["concesiones_sin_titularidad"]),
        bytes=bytes_completo + bytes_agregado + bytes_shards,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
