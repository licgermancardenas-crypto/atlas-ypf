"""Reservas por operador, cuenca y concesión, y vida de reservas.

Entrada: data/raw/reserves/*.zip            (ingest/reserves.py)
         data/raw/production/sesco/*_empresa.csv (para el cociente reservas/producción)
Salida:  data/processed/reserves.json

La métrica que justifica todo esto es la vida de reservas: cuántos años dura el
inventario comprobado al ritmo de producción actual. Con la producción sola se
sabe cuánto sale hoy; con las reservas, cuánto queda. Una compañía que crece
producción mientras se le cae la vida de reservas no está creciendo, se está
consumiendo el stock, y esa diferencia no aparece en ningún titular de balance.

Sobre el parseo: cada año es un Excel con cuatro filas de encabezados
combinados —tipo, grupo, categoría y fluido— sobre veintitantas columnas. No se
leen por posición fija sino reconstruyendo la jerarquía con relleno hacia la
derecha, porque entre 2017 y 2024 las hojas cambian de nombre y las columnas se
corren.

Se usa la hoja "fin de concesión" y no la de fin de vida útil: es lo que la
compañía tiene derecho a producir bajo el contrato vigente, que es el criterio
conservador y el que se puede comparar contra un balance.
"""

from __future__ import annotations

import io
import sys
import unicodedata
import warnings
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    M3_TO_BBL,
    PROCESSED,
    RAW,
    base_parser,
    human,
    log,
    record,
    rel,
    save_json,
)

ORIGEN = RAW / "reserves"
SESCO = RAW / "production" / "sesco"
SALIDA = PROCESSED / "reserves.json"

# El petróleo viene en Mm3 (miles de m3) y el gas en MMm3 (millones). Los dos
# terminan en miles de barriles equivalentes con el mismo factor: mil metros
# cúbicos de petróleo son 6,29 miles de barriles, y un millón de metros cúbicos
# de gas son 6,29 miles de boe.
A_MBOE = M3_TO_BBL

CANON = [
    ("YPF", "YPF"),
    ("VISTA", "Vista Energy"),
    ("PAMPA", "Pampa Energía"),
    ("PETROLERA ACONCAGUA", "Pampa Energía"),
    ("TECPETROL", "Tecpetrol"),
    ("PAN AMERICAN", "Pan American Energy"),
    ("SHELL", "Shell"),
    ("TOTAL AUSTRAL", "TotalEnergies"),
    ("TOTALENERGIES", "TotalEnergies"),
    ("CHEVRON", "Chevron"),
    ("PLUSPETROL", "Pluspetrol"),
    ("CAPEX", "Capex"),
    ("WINTERSHALL", "Wintershall"),
]


def sin_acentos(texto: object) -> str:
    limpio = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in limpio if unicodedata.category(c) != "Mn").upper().strip()


def canon_operador(serie: pd.Series) -> pd.Series:
    upper = serie.fillna("").astype(str).str.upper()
    salida = serie.fillna("Sin dato").astype("object")
    for patron, nombre in CANON:
        salida = salida.mask(upper.str.contains(patron, regex=False), nombre)
    return salida.astype("string")


def elegir_hoja(libro: pd.ExcelFile) -> str:
    """La hoja de fin de concesión, que entre años se llama de tres formas."""
    for hoja in libro.sheet_names:
        if "CONCESION" in sin_acentos(hoja):
            return hoja
    return libro.sheet_names[0]


def fila_encabezado(crudo: pd.DataFrame) -> int | None:
    for i in range(min(len(crudo), 14)):
        if any(sin_acentos(v) == "OPERADOR" for v in crudo.iloc[i]):
            return i
    return None


def mapa_columnas(crudo: pd.DataFrame, fila: int) -> dict[int, tuple[str, str, str]]:
    """Reconstruye (tipo, categoría, fluido) de cada columna numérica.

    Los encabezados están combinados: el nombre aparece solo en la primera
    celda del bloque y el resto viene vacío. Rellenar hacia la derecha es lo que
    devuelve la jerarquía completa.
    """
    def rellenar(indice: int) -> list[str]:
        valores, ultimo = [], ""
        for celda in crudo.iloc[indice]:
            texto = sin_acentos(celda)
            if texto and texto != "NAN":
                ultimo = texto
            valores.append(ultimo)
        return valores

    tipos = rellenar(fila - 4)
    grupos = rellenar(fila - 3)
    categorias = rellenar(fila - 2)
    fluidos = [sin_acentos(v) for v in crudo.iloc[fila - 1]]

    salida: dict[int, tuple[str, str, str]] = {}
    for columna, fluido in enumerate(fluidos):
        if fluido not in ("PET", "GAS"):
            continue
        tipo = tipos[columna]
        # El bloque "convencional + no convencional" es la suma de los otros
        # dos: se descarta y se recalcula, así el total nunca puede contradecir
        # a sus partes.
        if "+" in tipo:
            continue
        categoria = "CONTINGENTES" if "CONTINGENTE" in grupos[columna] else categorias[columna]
        salida[columna] = (
            "no convencional" if "NO CONVENCIONAL" in tipo else "convencional",
            categoria.lower(),
            "petroleo" if fluido == "PET" else "gas",
        )
    return salida


def leer_anio(anio: int, ruta: Path) -> pd.DataFrame | None:
    with zipfile.ZipFile(ruta) as zf:
        excels = [n for n in zf.namelist() if n.lower().endswith((".xlsx", ".xls"))]
        if not excels:
            log(f"  {anio}: el zip no trae Excel")
            return None
        contenido = io.BytesIO(zf.read(excels[0]))

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        libro = pd.ExcelFile(contenido)
        crudo = libro.parse(elegir_hoja(libro), header=None)

    fila = fila_encabezado(crudo)
    if fila is None or fila < 4:
        log(f"  {anio}: no se encontro la fila de encabezado, se saltea")
        return None

    columnas = mapa_columnas(crudo, fila)
    if not columnas:
        log(f"  {anio}: no se reconocieron columnas de petroleo/gas, se saltea")
        return None

    datos = crudo.iloc[fila + 1 :].copy()
    etiquetas = {0: "operador", 1: "cuenca", 2: "provincia", 3: "concesion", 4: "yacimiento"}
    filas = []
    for columna, (tipo, categoria, fluido) in columnas.items():
        parcial = datos[[*etiquetas, columna]].copy()
        parcial.columns = [*etiquetas.values(), "valor"]
        parcial["tipo"], parcial["categoria"], parcial["fluido"] = tipo, categoria, fluido
        filas.append(parcial)

    tabla = pd.concat(filas, ignore_index=True)
    tabla["valor"] = pd.to_numeric(tabla.valor, errors="coerce")
    tabla = tabla[tabla.valor.notna() & tabla.operador.notna()]

    # La última fila de la planilla es el total general y dice "TOTAL" en la
    # columna de operador. Sumarla como si fuera una empresa le agregaba las
    # reservas de todo el país a un operador —y como el patrón de nombres
    # comerciales tomaba "TOTAL", se las agregaba justo a TotalEnergies—. Se
    # reconocen por no tener cuenca: ninguna fila de detalle viene sin ella.
    etiqueta = tabla.operador.map(sin_acentos)
    tabla = tabla[~etiqueta.str.fullmatch(r"TOTAL(ES)?|TOTAL GENERAL") & tabla.cuenca.notna()]
    tabla["anio"] = anio
    tabla["operador"] = canon_operador(tabla.operador)
    # Mm3 de petróleo y MMm3 de gas terminan los dos en miles de boe.
    tabla["mboe"] = tabla.valor * A_MBOE
    return tabla


def produccion_anual() -> pd.DataFrame:
    """Producción anual por operador, en miles de boe, para el cociente R/P.

    Se lee del CSV crudo de SESCO y no del JSON de producción: ese JSON guarda
    solo los doce operadores más grandes y agrupa al resto en "Otros", así que
    los que quedan afuera se quedarían sin vida de reservas sin ninguna razón.
    """
    filas = []
    for fluido, columna in (("oil", "cantidad_m3"), ("gas", "cantidad_mm3")):
        ruta = SESCO / f"{fluido}_empresa.csv"
        if not ruta.exists():
            log(f"  falta {rel(ruta)}: la vida de reservas va a quedar incompleta")
            continue
        datos = pd.read_csv(ruta, encoding="utf-8-sig", low_memory=False)
        if columna not in datos.columns:
            columna = "cantidad_m3"
        # Mm3 de petróleo y MMm3 de gas terminan los dos en miles de boe.
        datos["mboe"] = pd.to_numeric(datos[columna], errors="coerce") / 1000 * A_MBOE
        datos["operador"] = canon_operador(datos.empresa)
        filas.append(datos.groupby(["anio", "operador"], observed=True).mboe.sum().reset_index())

    if not filas:
        return pd.DataFrame()
    juntas = pd.concat(filas, ignore_index=True)
    return (
        juntas.groupby(["anio", "operador"], observed=True)
        .mboe.sum()
        .reset_index()
        .rename(columns={"mboe": "produccion_mboe"})
    )


def main() -> int:
    args = base_parser("Arma la serie de reservas y la vida de reservas").parse_args()

    if not ORIGEN.exists():
        log(f"falta {rel(ORIGEN)}; correr antes pipeline/ingest/reserves.py")
        return 1

    archivos = sorted(ORIGEN.glob("*.zip"))
    if SALIDA.exists() and not args.force:
        if archivos and SALIDA.stat().st_mtime > max(p.stat().st_mtime for p in archivos):
            log(f"{rel(SALIDA)} esta al dia, se saltea (--force para rehacer)")
            return 0

    partes = []
    for ruta in archivos:
        anio = int(ruta.stem)
        log(f"leyendo {anio}")
        tabla = leer_anio(anio, ruta)
        if tabla is not None:
            partes.append(tabla)
            log(f"  {len(tabla):,} filas")

    if not partes:
        log("ningun año se pudo parsear")
        return 1

    detalle = pd.concat(partes, ignore_index=True)

    comprobadas = detalle[detalle.categoria == "comprobadas"]
    por_operador = (
        comprobadas.groupby(["anio", "operador"], observed=True)
        .agg(
            comprobadas_mboe=("mboe", "sum"),
            petroleo_mboe=("mboe", lambda s: float(s[detalle.loc[s.index, "fluido"] == "petroleo"].sum())),
            no_convencional_mboe=(
                "mboe",
                lambda s: float(s[detalle.loc[s.index, "tipo"] == "no convencional"].sum()),
            ),
        )
        .reset_index()
    )

    produccion = produccion_anual()
    if not produccion.empty:
        por_operador = por_operador.merge(produccion, on=["anio", "operador"], how="left")
        # Vida de reservas: años que dura el inventario comprobado al ritmo
        # de producción de ese mismo año.
        por_operador["vida_reservas"] = (
            por_operador.comprobadas_mboe / por_operador.produccion_mboe.replace(0, np.nan)
        ).round(1)
    else:
        por_operador["produccion_mboe"] = np.nan
        por_operador["vida_reservas"] = np.nan

    por_operador["share_no_convencional"] = (
        por_operador.no_convencional_mboe / por_operador.comprobadas_mboe.replace(0, np.nan)
    ).round(4)
    for columna in ("comprobadas_mboe", "petroleo_mboe", "no_convencional_mboe", "produccion_mboe"):
        por_operador[columna] = por_operador[columna].round(1)

    pais = (
        comprobadas.groupby(["anio", "tipo", "fluido"], observed=True)
        .mboe.sum()
        .round(1)
        .reset_index()
    )
    por_cuenca = (
        comprobadas.groupby(["anio", "cuenca"], observed=True).mboe.sum().round(1).reset_index()
    )

    ultimo = int(por_operador.anio.max())
    ranking = (
        por_operador[por_operador.anio == ultimo]
        .sort_values("comprobadas_mboe", ascending=False)
        .head(15)
    )

    payload = {
        "generado": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fuente": "Secretaria de Energia, informe anual de reservas (hoja fin de concesion)",
        "unidades": {"reservas": "miles de boe", "vida_reservas": "anios"},
        "advertencia": (
            "Reservas comprobadas hasta el fin de la concesion vigente, declaradas por el "
            "operador. No son las reservas certificadas que reporta la compania en su 20-F, "
            "que usan otro criterio y otra fecha de corte."
        ),
        "anios": sorted(int(a) for a in por_operador.anio.unique()),
        "ultimo_anio": ultimo,
        "por_operador": por_operador.replace({np.nan: None}).to_dict("records"),
        "ranking_ultimo": ranking.replace({np.nan: None}).to_dict("records"),
        "pais": pais.to_dict("records"),
        "por_cuenca": por_cuenca.to_dict("records"),
    }

    bytes_salida = save_json(payload, SALIDA)
    log(f"escrito {rel(SALIDA)} - {human(bytes_salida)}")

    record(
        "reserves",
        source=rel(ORIGEN),
        outputs=[rel(SALIDA)],
        anios=payload["anios"],
        operadores=int(por_operador.operador.nunique()),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
