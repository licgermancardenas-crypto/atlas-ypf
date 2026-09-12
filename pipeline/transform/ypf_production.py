"""Lo que produce YPF, abierto por dónde y por cuándo.

El módulo operativo mira el país: todos los operadores, la producción nacional,
el ranking. Esto mira una sola compañía y la abre en las cinco dimensiones en
las que un analista la piensa —cuenca, provincia, concesión, yacimiento y el
pueblo más cercano— y en las cuatro escalas de tiempo en las que se la mide.

Sobre el tiempo hay una aclaración que vale más que una nota al pie: la fuente
es mensual. No existe el dato diario, y lo que el sitio muestra como bbl/d es el
caudal promedio del período, que es volumen dividido días. Por eso acá se guarda
el volumen del mes y no el caudal: el volumen se puede sumar para armar un
trimestre o un año, y el caudal no —promediar caudales de meses de distinta
duración da un número que no es el de nadie—. El caudal lo calcula el frontend
al final, dividiendo por los días que tenga el período elegido.

La segunda aclaración es de qué producción se habla. La serie es bruta operada:
el operador declara todo lo que sale del área, incluida la parte de sus socios.
Es más que lo que YPF consolida en su balance, y esa diferencia es justamente el
puente entre este módulo y el de finanzas.

La dimensión "localidad" no viene en la fuente. Se arma acá, asignándole a cada
yacimiento el pueblo más cercano a su centroide, con la distancia guardada al
lado para que se vea cuándo la asignación es floja. Sirve para una pregunta que
la fuente no contesta sola y que en la cuenca se hace todo el tiempo: qué se
produce alrededor de Añelo.

Entrada: data/raw/production/sesco/{oil,gas}_yacimiento.csv (ingest/production_country.py)
         data/processed/geo/{fields,towns}.geojson       (transform/geo_layers.py)
Salida:  data/processed/ypf_produccion.json   (resumen y rankings, liviano)
         data/processed/ypf_dimensiones.json  (las series mensuales, se bajan aparte)
"""

from __future__ import annotations

import json
import math
import sys
import unicodedata
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
GEO = PROCESSED / "geo"
SALIDA = PROCESSED / "ypf_produccion.json"
SALIDA_DIMENSIONES = PROCESSED / "ypf_dimensiones.json"

EMPRESA = "YPF S.A."

# Cada dimensión y la columna de la que sale. Las cuatro primeras vienen en el
# mismo CSV; la quinta se arma con geometría, más abajo.
DIMENSIONES = {
    "cuenca": "cuenca",
    "provincia": "provincia",
    "concesion": "areapermisoconcesion",
    "yacimiento": "areayacimiento",
    "localidad": "localidad",
}

# Cuántos miembros llevan serie propia antes de caer en "Otros". Dieciséis entra
# en una leyenda y cubre, en las dimensiones largas, más del 90% de lo que la
# compañía produce. El ranking, que es liviano, va completo igual.
TOPE = 16

# Hasta acá se considera que un yacimiento "está cerca de" un pueblo. Más de
# cien kilómetros en la meseta es no estar cerca de nada.
DISTANCIA_MAXIMA_KM = 100.0

PARTICULAS = {"de", "del", "la", "las", "los", "y", "el", "en"}


def en_titulo(texto: str) -> str:
    palabras = str(texto).strip().lower().split()
    return " ".join(
        palabra if indice and palabra in PARTICULAS else palabra.capitalize()
        for indice, palabra in enumerate(palabras)
    )


def normalizar(texto: str) -> str:
    """Para cruzar nombres entre fuentes: sin acentos, sin dobles espacios."""
    plano = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return " ".join(plano.upper().split())


def clasificar_recurso(serie: pd.Series) -> np.ndarray:
    """El campo `concepto` nombra distinto al petróleo y al gas.

    "Shale Oil" contra "Shale Gas", "Tight_oil" contra "Tight_gas": lo único
    estable es la palabra.
    """
    texto = serie.fillna("").str.lower()
    return np.select(
        [texto.str.contains("shale"), texto.str.contains("tight")],
        ["shale", "tight"],
        default="convencional",
    )


def volumen(df: pd.DataFrame, fluido: str) -> pd.Series:
    """Volumen del mes: barriles si es petróleo, boe si es gas.

    La unidad se deduce del nombre de la columna y no del fluido. Si mañana la
    fuente cambia una de las dos, esto falla ruidosamente en vez de devolver un
    volumen mil veces menor sin avisar.
    """
    if "cantidad_mm3" in df.columns:
        return df.cantidad_mm3 * MM3_TO_BOE
    if "cantidad_m3" in df.columns:
        return df.cantidad_m3 * (M3_TO_BBL if fluido == "oil" else MM3_TO_BOE)
    raise RuntimeError(
        f"la serie de {fluido} no trae ni cantidad_m3 ni cantidad_mm3: {list(df.columns)}"
    )


def leer_fluido(fluido: str) -> pd.DataFrame:
    """Las filas de YPF del CSV de ese fluido, ya con volumen y recurso.

    Se lee por trozos porque cada archivo pesa cien megas y de esos, lo de YPF
    es una fracción chica: filtrar adentro del bucle evita tener las dos series
    enteras en memoria a la vez.
    """
    ruta = ORIGEN / f"{fluido}_yacimiento.csv"
    if not ruta.exists():
        raise SystemExit(f"falta {rel(ruta)}; correr ingest/production_country.py")

    columnas = [
        "indice_tiempo",
        "empresa",
        "areapermisoconcesion",
        "areayacimiento",
        "idareayacimiento",
        "cuenca",
        "provincia",
        "concepto",
    ]
    partes = []
    for trozo in pd.read_csv(
        ruta, encoding="utf-8-sig", chunksize=500_000, low_memory=False
    ):
        propio = trozo[trozo.empresa == EMPRESA]
        if propio.empty:
            continue
        propio = propio.copy()
        propio["volumen"] = volumen(propio, fluido)
        partes.append(propio[columnas + ["volumen"]])

    if not partes:
        raise SystemExit(f"no hay filas de {EMPRESA} en {rel(ruta)}")

    df = pd.concat(partes, ignore_index=True)
    df["fecha"] = pd.to_datetime(df.indice_tiempo, errors="coerce")
    df = df[df.fecha.notna() & (df.volumen > 0)].copy()
    df["recurso"] = clasificar_recurso(df.concepto)
    df["fluido"] = fluido
    return df.drop(columns=["concepto", "indice_tiempo", "empresa"])


def localidades_por_yacimiento(claves: list[tuple[str, str]]) -> dict[str, tuple[str, float]]:
    """A cada yacimiento, el pueblo más cercano a su centroide.

    El cruce con la capa de yacimientos se intenta primero por el código del
    área, que es el identificador de la Secretaría y no cambia, y recién si eso
    falla por el nombre normalizado —la capa del IGN y la serie escriben
    distinto los acentos—. Lo que no cruza, o lo que queda a más de cien
    kilómetros de cualquier pueblo, no se inventa: queda sin asignar.
    """
    ruta_campos, ruta_pueblos = GEO / "fields.geojson", GEO / "towns.geojson"
    if not ruta_campos.exists() or not ruta_pueblos.exists():
        log("  sin fields/towns.geojson: la dimensión localidad queda vacía")
        return {}

    from shapely.geometry import shape

    pueblos = []
    for feature in json.loads(ruta_pueblos.read_text(encoding="utf-8"))["features"]:
        geometria = shape(feature["geometry"])
        if geometria.is_empty:
            continue
        centro = geometria if geometria.geom_type == "Point" else geometria.centroid
        nombre = feature.get("properties", {}).get("nombre")
        if nombre:
            pueblos.append((en_titulo(nombre), centro.x, centro.y))
    if not pueblos:
        return {}

    por_codigo: dict[str, tuple[float, float]] = {}
    por_nombre: dict[str, tuple[float, float]] = {}
    for feature in json.loads(ruta_campos.read_text(encoding="utf-8"))["features"]:
        propiedades = feature.get("properties", {})
        geometria = shape(feature["geometry"])
        if geometria.is_empty:
            continue
        centro = geometria.centroid
        if propiedades.get("codigo"):
            por_codigo[normalizar(propiedades["codigo"])] = (centro.x, centro.y)
        if propiedades.get("yacimiento"):
            por_nombre[normalizar(propiedades["yacimiento"])] = (centro.x, centro.y)

    salida: dict[str, tuple[str, float]] = {}
    for nombre, codigo in claves:
        centro = por_codigo.get(normalizar(codigo)) or por_nombre.get(normalizar(nombre))
        if not centro:
            continue
        lon, lat = centro
        factor = math.cos(math.radians(lat))
        mejor, distancia = None, float("inf")
        for pueblo, plon, plat in pueblos:
            dx = (plon - lon) * factor * 111.32
            dy = (plat - lat) * 111.32
            candidata = math.hypot(dx, dy)
            if candidata < distancia:
                mejor, distancia = pueblo, candidata
        if mejor and distancia <= DISTANCIA_MAXIMA_KM:
            salida[nombre] = (mejor, round(distancia, 1))
    return salida


def serie_columnar(
    df: pd.DataFrame, columna: str, fechas: pd.DatetimeIndex, miembros: list[str]
) -> list[dict]:
    """Un miembro por fila, y adentro un array por fluido y recurso.

    Formato columnar y no lista de objetos: son cinco dimensiones por dieciséis
    miembros por doscientos meses, y repetir el nombre de cada campo en cada
    fila cuesta más en nombres de claves que en números.
    """
    tabla = (
        df.pivot_table(
            index=[columna, "fecha"],
            columns=["fluido", "recurso"],
            values="volumen",
            aggfunc="sum",
        )
        .fillna(0.0)
        .round(0)
    )

    salida = []
    for miembro in miembros:
        if miembro not in tabla.index.get_level_values(0):
            continue
        propio = tabla.xs(miembro, level=0).reindex(fechas).fillna(0.0)
        fila: dict = {"nombre": miembro}
        for fluido in ("oil", "gas"):
            for recurso in ("convencional", "shale", "tight"):
                clave = (fluido, recurso)
                valores = (
                    propio[clave].to_numpy() if clave in propio.columns else np.zeros(len(fechas))
                )
                if valores.any():
                    fila[f"{fluido}_{recurso}"] = [int(v) for v in valores]
        salida.append(fila)
    return salida


def ranking_de(df: pd.DataFrame, columna: str, fechas: pd.DatetimeIndex) -> list[dict]:
    """El ranking completo de la dimensión: últimos doce meses contra los doce previos.

    Doce meses y no el último mes: un área que paró la planta una semana no
    merece encabezar ninguna caída.
    """
    if len(fechas) < 24:
        ventana, previa = fechas, fechas[:0]
    else:
        ventana, previa = fechas[-12:], fechas[-24:-12]

    reciente = df[df.fecha.isin(ventana)]
    actual = reciente.groupby(columna).volumen.sum()
    anterior = df[df.fecha.isin(previa)].groupby(columna).volumen.sum()
    dias_actual = sum(fecha.days_in_month for fecha in ventana) or 1
    dias_previo = sum(fecha.days_in_month for fecha in previa) or 1
    total = actual.sum() or 1.0

    # La apertura del último año por fluido y por recurso. Va en el ranking y no
    # en las series porque es lo que necesita una tabla o una ficha para decir
    # qué clase de activo es cada uno, sin bajarse los doscientos meses.
    por_fluido = reciente.pivot_table(
        index=columna, columns="fluido", values="volumen", aggfunc="sum"
    ).fillna(0.0)
    por_recurso = reciente.pivot_table(
        index=columna, columns="recurso", values="volumen", aggfunc="sum"
    ).fillna(0.0)

    def caudal(tabla: pd.DataFrame, nombre: str, clave: str) -> float:
        if clave not in tabla.columns or nombre not in tabla.index:
            return 0.0
        return float(tabla.loc[nombre, clave]) / dias_actual

    # La union de las dos ventanas y no solo la actual. Un area que YPF entrego
    # produce en la ventana previa y no en la actual: si se la saltea, el total
    # previo del ranking queda corto y todo lo que se sume a partir de estas
    # filas —una provincia, una cuenca, la compania entera— muestra un
    # crecimiento que no existio. Con la union, esa area aparece con caudal cero
    # y -100%, que es exactamente lo que paso desde el punto de vista de YPF, y
    # los agregados cierran contra la serie total.
    universo = actual.reindex(actual.index.union(anterior.index), fill_value=0.0)

    filas = []
    for nombre, volumen_actual in universo.sort_values(ascending=False).items():
        volumen_previo = float(anterior.get(nombre, 0.0))
        caudal_actual = volumen_actual / dias_actual
        caudal_previo = volumen_previo / dias_previo
        shale = caudal(por_recurso, nombre, "shale")
        filas.append(
            {
                "nombre": nombre,
                "actual_bd": round(caudal_actual, 1),
                "previo_bd": round(caudal_previo, 1),
                "delta_bd": round(caudal_actual - caudal_previo, 1),
                "crecimiento": round(caudal_actual / caudal_previo - 1, 4) if caudal_previo else None,
                "participacion": round(volumen_actual / total, 4),
                "oil_bd": round(caudal(por_fluido, nombre, "oil"), 1),
                "gas_bd": round(caudal(por_fluido, nombre, "gas"), 1),
                "shale_bd": round(shale, 1),
                "convencional_bd": round(caudal(por_recurso, nombre, "convencional"), 1),
                "tight_bd": round(caudal(por_recurso, nombre, "tight"), 1),
                "shale_share": round(shale / caudal_actual, 4) if caudal_actual else None,
            }
        )
    return filas


def metadatos(df: pd.DataFrame, ventana) -> dict[str, dict]:
    """Dónde queda cada activo y de qué está hecho.

    La ventana que se le pasa cubre las dos que compara el ranking —los últimos
    doce meses y los doce previos— y no solo la última: un área entregada a otro
    operador sigue teniendo una fila en el ranking, y sin ficha quedaría sin
    provincia ni cuenca, que en el árbol territorial es caer en "Sin declarar".

    Son las mismas columnas de la fuente, pivoteadas para que la ficha de una
    concesión pueda decir "Neuquén · Neuquina · 3 yacimientos" sin bajarse las
    series. Cuando un miembro aparece en más de una provincia o cuenca —pasa con
    algunas concesiones que cruzan el límite— se guarda la de mayor volumen y se
    anota que hay más de una, en vez de elegir en silencio.
    """
    reciente = df[df.fecha.isin(ventana)]
    if reciente.empty:
        reciente = df

    def dominante(grupo: pd.DataFrame, columna: str) -> tuple[str | None, int]:
        if columna not in grupo.columns:
            return None, 0
        suma = grupo.groupby(columna).volumen.sum().sort_values(ascending=False)
        suma = suma[suma > 0]
        if suma.empty:
            return None, 0
        return str(suma.index[0]), int(len(suma))

    salida: dict[str, dict] = {}
    for id_dimension, columna in DIMENSIONES.items():
        if id_dimension in ("cuenca", "provincia"):
            continue
        fichas: dict[str, dict] = {}
        for nombre, grupo in reciente.groupby(columna):
            provincia, provincias = dominante(grupo, "provincia")
            cuenca, cuencas = dominante(grupo, "cuenca")
            ficha: dict = {"provincia": provincia, "cuenca": cuenca}
            if provincias > 1:
                ficha["provincias"] = provincias
            if cuencas > 1:
                ficha["cuencas"] = cuencas
            if id_dimension != "yacimiento":
                ficha["yacimientos"] = int(grupo.areayacimiento.nunique())
            if id_dimension != "concesion":
                concesion, concesiones = dominante(grupo, "areapermisoconcesion")
                ficha["concesion"] = concesion
                if concesiones > 1:
                    ficha["concesiones"] = concesiones
            if id_dimension != "localidad":
                localidad, _ = dominante(grupo, "localidad")
                ficha["localidad"] = localidad
            fichas[str(nombre)] = {k: v for k, v in ficha.items() if v is not None}
        salida[id_dimension] = fichas
    return salida


COHORTES = [
    (2014, "2010-2014"),
    (2018, "2015-2018"),
    (2021, "2019-2021"),
    (9999, "2022 en adelante"),
]

ORDEN_COHORTES = ["Ya producía en 2009", *[etiqueta for _, etiqueta in COHORTES]]


def cohorte_por_yacimiento(df: pd.DataFrame, fechas: pd.DatetimeIndex) -> pd.Series:
    """A que epoca pertenece cada yacimiento, por su primer mes con produccion.

    La tesis del caso es que el shale compensa el declino del convencional. Eso
    se afirma con un porcentaje; esta apertura lo muestra: cuanto del caudal de
    hoy sale de algo que ya producia hace quince anios y cuanto de algo que
    arranco anteayer.

    Se calcula aca y no en el frontend por una razon de fondo: el archivo de
    series solo publica los dieciseis miembros mas grandes y agrupa la cola en
    "Otros", asi que una cohorte armada en el navegador tomaria diecisiete
    series en vez de ciento once, y "Otros" entero caeria en la cohorte mas
    vieja. El pipeline si tiene los ciento once.
    """
    con_volumen = df[df.volumen > 0]
    primero = con_volumen.groupby("areayacimiento").fecha.min()
    inicio = fechas[0]

    def etiqueta(fecha) -> str:
        # Lo que ya producia en el primer mes del archivo esta censurado por la
        # izquierda: no sabemos cuando arranco, y se lo nombra por lo que se
        # sabe en vez de ponerle una fecha que la fuente no dice.
        if fecha <= inicio:
            return ORDEN_COHORTES[0]
        anio = int(fecha.year)
        for hasta, nombre in COHORTES:
            if anio <= hasta:
                return nombre
        return COHORTES[-1][1]

    return primero.map(etiqueta)


def traspasos(df: pd.DataFrame, fechas: pd.DatetimeIndex) -> list[dict]:
    """Las areas que dejaron de figurar como operadas por YPF.

    Una serie que cae a cero y se queda en cero no siempre es un derrumbe: casi
    siempre es un cambio de operador. La diferencia importa porque la pantalla
    la leeria como una caida del 100% y diria algo falso.

    Para saber cual de las dos cosas es se cruza contra el archivo del pais, que
    tiene la misma fuente sin filtrar por operador: si el area sigue produciendo
    ahi despues del ultimo mes de YPF, entonces no dejo de producir, dejo de ser
    de YPF. Si el archivo del pais no esta o no la tiene, se dice lo unico que
    se sabe —que YPF no declara produccion desde tal mes— y no se afirma la
    causa.
    """
    if len(fechas) < 4:
        return []

    pais = {}
    archivo = PROCESSED / "country_dimensions.json"
    if archivo.exists():
        try:
            crudo = json.loads(archivo.read_text(encoding="utf-8"))
            for miembro in crudo.get("dimensiones", {}).get("yacimiento", {}).get("miembros", []):
                # Solo los dos totales: el archivo del pais publica ademas la
                # apertura por recurso, y sumar todas las listas contaria cada
                # barril dos veces.
                series = [
                    v for k, v in miembro.items() if k in ("oil_total", "gas_total") and isinstance(v, list)
                ]
                if series:
                    pais[normalizar(miembro["nombre"])] = [sum(x) for x in zip(*series)]
        except (ValueError, OSError):
            pais = {}

    ultimos = list(fechas[-3:])
    salida: list[dict] = []
    for id_dimension in ("yacimiento", "concesion"):
        columna = DIMENSIONES[id_dimension]
        por_mes = (
            df.pivot_table(index=columna, columns="fecha", values="volumen", aggfunc="sum")
            .reindex(columns=fechas)
            .fillna(0.0)
        )
        for nombre, fila in por_mes.iterrows():
            if fila[ultimos].sum() > 0:
                continue
            previos = fila[fila.index < ultimos[0]]
            if previos.empty or previos.tail(3).sum() <= 0:
                continue

            activos = fila[fila > 0]
            ultimo_mes = activos.index[-1]
            dias_previos = sum(f.days_in_month for f in activos.index[-3:]) or 1
            registro = {
                "dimension": id_dimension,
                "nombre": nombre,
                "ultimo_mes": ultimo_mes.strftime("%Y-%m"),
                "bd_previo": round(float(activos.tail(3).sum()) / dias_previos, 1),
            }

            serie_pais = pais.get(normalizar(str(nombre)))
            if serie_pais and len(serie_pais) >= len(fechas):
                cola = serie_pais[len(fechas) - 3 : len(fechas)]
                dias_cola = sum(f.days_in_month for f in ultimos) or 1
                if sum(cola) > 0:
                    registro["sigue_en_el_pais"] = True
                    # El archivo del pais publica caudal diario, no volumen: se
                    # promedia y no se divide por dias.
                    registro["bd_pais"] = round(float(sum(cola)) / 3, 1)
            salida.append(registro)

    salida.sort(key=lambda fila: -fila["bd_previo"])
    return salida


def main() -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.parse_args()

    df = pd.concat([leer_fluido("oil"), leer_fluido("gas")], ignore_index=True)
    log(f"{len(df):,} filas de {EMPRESA} entre los dos fluidos")

    # Los nombres de la fuente vienen en mayúscula sostenida. Se presentan en
    # título acá y no en el frontend: así el CSV que se descarga y la pantalla
    # dicen lo mismo.
    for columna in ("cuenca", "provincia", "areapermisoconcesion", "areayacimiento"):
        df[columna] = df[columna].fillna("Sin dato").map(en_titulo)

    claves = (
        df[["areayacimiento", "idareayacimiento"]]
        .drop_duplicates()
        .fillna("")
        .itertuples(index=False, name=None)
    )
    cercanas = localidades_por_yacimiento(sorted(claves))
    # La capa de yacimientos del proyecto cubre la cuenca neuquina, así que los
    # campos del Golfo San Jorge, Cuyana y Austral no tienen centroide y no
    # pueden tener pueblo. Se los dice, en vez de amontonarlos en un "sin dato"
    # que haría pensar en un error de cruce.
    df["localidad"] = [
        cercanas[nombre][0]
        if nombre in cercanas
        else ("Sin asignar" if cuenca == "Neuquina" else "Fuera de la cuenca neuquina")
        for nombre, cuenca in zip(df.areayacimiento, df.cuenca)
    ]
    log(
        f"localidad asignada a {len(cercanas)} de "
        f"{df.areayacimiento.nunique()} yacimientos por cercanía"
    )

    fechas = pd.DatetimeIndex(sorted(df.fecha.unique()))
    etiquetas = [fecha.strftime("%Y-%m") for fecha in fechas]
    dias = [int(fecha.days_in_month) for fecha in fechas]

    # El total de la compañía, que es la serie que abre la página.
    total = (
        df.pivot_table(index="fecha", columns=["fluido", "recurso"], values="volumen", aggfunc="sum")
        .reindex(fechas)
        .fillna(0.0)
    )
    totales = {
        f"{fluido}_{recurso}": [int(round(v)) for v in total[(fluido, recurso)]]
        for fluido in ("oil", "gas")
        for recurso in ("convencional", "shale", "tight")
        if (fluido, recurso) in total.columns
    }

    dimensiones: dict[str, dict] = {}
    rankings: dict[str, list[dict]] = {}
    for id_dimension, columna in DIMENSIONES.items():
        ranking = ranking_de(df, columna, fechas)
        rankings[id_dimension] = ranking
        # Los que llevan serie propia salen del volumen histórico y no del
        # ranking: un área que YPF entregó hace cinco años no aparece en los
        # últimos doce meses, pero sí tiene que estar en el gráfico de su época.
        elegidos = list(
            df.groupby(columna).volumen.sum().sort_values(ascending=False).head(TOPE).index
        )
        miembros = serie_columnar(df, columna, fechas, elegidos)

        resto = df[~df[columna].isin(elegidos)]
        if not resto.empty:
            otros = serie_columnar(resto.assign(**{columna: "Otros"}), columna, fechas, ["Otros"])
            miembros.extend(otros)
        dimensiones[id_dimension] = {"miembros": miembros}
        log(f"  {id_dimension}: {len(ranking)} miembros, {len(miembros)} con serie")

    # La sexta dimension no es un corte del padron sino del tiempo: cada
    # yacimiento entra en la cohorte del anio en que empezo a producir. Viaja
    # con las demas para que el frontend la dibuje con el mismo codigo, sin un
    # caso especial que se pueda desincronizar del grafico principal.
    df["cohorte"] = df.areayacimiento.map(cohorte_por_yacimiento(df, fechas))
    dimensiones["cohorte"] = {
        "miembros": serie_columnar(df, "cohorte", fechas, ORDEN_COHORTES)
    }
    cuenta = df.groupby("cohorte").areayacimiento.nunique().to_dict()
    log(
        "  cohorte: "
        + ", ".join(f"{cuenta.get(nombre, 0)} en {nombre}" for nombre in ORDEN_COHORTES)
    )

    movidas = traspasos(df, fechas)
    if movidas:
        log(
            "  traspasos detectados: "
            + ", ".join(
                f"{fila['nombre']} (ultimo {fila['ultimo_mes']}"
                + (", sigue en el pais)" if fila.get("sigue_en_el_pais") else ")")
                for fila in movidas
            )
        )

    ultimos_doce = fechas[-12:]
    ventana = df[df.fecha.isin(ultimos_doce)]
    dias_doce = sum(fecha.days_in_month for fecha in ultimos_doce) or 1
    por_recurso = ventana.groupby(["fluido", "recurso"]).volumen.sum()

    resumen = {
        "petroleo_bd": round(por_recurso.get("oil", pd.Series(dtype=float)).sum() / dias_doce, 1),
        "gas_boed": round(por_recurso.get("gas", pd.Series(dtype=float)).sum() / dias_doce, 1),
        "shale_bd": round(
            sum(v for (fluido, recurso), v in por_recurso.items() if recurso == "shale")
            / dias_doce,
            1,
        ),
        "convencional_bd": round(
            sum(v for (fluido, recurso), v in por_recurso.items() if recurso == "convencional")
            / dias_doce,
            1,
        ),
        "tight_bd": round(
            sum(v for (fluido, recurso), v in por_recurso.items() if recurso == "tight")
            / dias_doce,
            1,
        ),
        "concesiones": int(ventana.areapermisoconcesion.nunique()),
        "yacimientos": int(ventana.areayacimiento.nunique()),
        "cuencas": int(ventana.cuenca.nunique()),
        "provincias": int(ventana.provincia.nunique()),
    }

    payload = {
        "generado": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "empresa": EMPRESA,
        "fuente": "Secretaría de Energía, series SESCO por yacimiento",
        "unidades": {
            "volumen_oil": "bbl",
            "volumen_gas": "boe",
            "caudal": "bbl/d y boe/d, promedio del período",
        },
        "nota": (
            "Producción bruta operada: incluye la participación de los socios en las "
            "áreas que YPF opera, así que es mayor que la que la compañía consolida en "
            "su balance. La fuente es mensual; no hay dato diario. Lo que el sitio "
            "muestra en bbl/d es el caudal promedio del período, que es el volumen "
            "dividido por los días que tiene ese período."
        ),
        "nota_localidad": (
            f"La localidad es la más cercana al centroide del yacimiento, hasta "
            f"{DISTANCIA_MAXIMA_KM:.0f} km. No es una jurisdicción: es una referencia "
            "geográfica para ubicar la producción."
        ),
        "cobertura": {"desde": etiquetas[0], "hasta": etiquetas[-1], "meses": len(etiquetas)},
        "fechas": etiquetas,
        "dias": dias,
        "total": totales,
        "resumen": resumen,
        "rankings": rankings,
        "meta": metadatos(df, fechas[-24:]),
        "traspasos": movidas,
        "cohortes": ORDEN_COHORTES,
        "localidades": {nombre: {"pueblo": p, "km": k} for nombre, (p, k) in cercanas.items()},
        "dimensiones_en": "data/processed/ypf_dimensiones.json",
    }
    tamanio = save_json(payload, SALIDA)

    tamanio_dimensiones = save_json(
        {
            "generado": payload["generado"],
            "fechas": etiquetas,
            "dias": dias,
            "dimensiones": dimensiones,
        },
        SALIDA_DIMENSIONES,
    )

    log(
        f"{resumen['petroleo_bd']:,.0f} bbl/d de petróleo y {resumen['gas_boed']:,.0f} boe/d de gas "
        f"en {resumen['concesiones']} concesiones y {resumen['yacimientos']} yacimientos (UDM)"
    )
    record(
        "transform/ypf-produccion",
        rows=len(df),
        bytes=int(tamanio) + int(tamanio_dimensiones),
        outputs=[rel(SALIDA), rel(SALIDA_DIMENSIONES)],
        source=rel(ORIGEN),
        note="producción de YPF por cuenca, provincia, concesión, yacimiento y localidad",
    )
    log(f"{rel(SALIDA)} ({human(tamanio)}) + {rel(SALIDA_DIMENSIONES)} ({human(tamanio_dimensiones)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
