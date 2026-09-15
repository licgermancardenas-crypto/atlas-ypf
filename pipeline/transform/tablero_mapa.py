"""Dónde produce YPF en Vaca Muerta, trimestre a trimestre, para el tablero del Excel.

Por qué existe: el tablero del libro de estados tiene un mapa que cambia con el
trimestre elegido. Excel no calcula centroides ni promedios diarios, y la regla
del proyecto es que las salidas de presentación no calculan: leen. Este paso
deja todo resuelto —la posición de cada concesión en el lienzo del mapa y su
producción promedio de cada trimestre— y el tablero solo lo indexa.

Qué se cuenta: la producción no convencional operada por YPF del panel pozo-mes
(capítulo IV de la Secretaría de Energía), agrupada por concesión. Es bruta
operada: incluye la parte de los socios. No es la producción que la compañía
publica en su release, que es neta y suma lo convencional; es dónde está la
actividad que explica el crecimiento.

Dónde va cada burbuja: el promedio de la ubicación de los pozos de la
concesión, pesado por lo que produjo cada uno en toda su historia. Cae donde
está la producción y no en el centro geométrico de un polígono que puede ser
mayormente exploratorio. Se proyecta con la misma proyección y el mismo marco
que el mapa del sitio (transform/map_svg.py), así que coincide con su relieve.

Entrada:  data/processed/production_wells.parquet  (transform/production_wells.py)
          data/processed/mapa_web.json              (transform/map_svg.py)
Salida:   data/processed/tablero_mapa.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, base_parser, human, log, record, rel, save_json  # noqa: E402
from map_svg import Proyeccion, en_titulo  # noqa: E402

POZOS = PROCESSED / "production_wells.parquet"
MAPA = PROCESSED / "mapa_web.json"
SALIDA = PROCESSED / "tablero_mapa.json"

OPERADOR = "YPF"
DESDE = "2019Q1"
# Las concesiones que se dibujan. El resto se suma en el total pero no lleva
# burbuja: a la escala de una tarjeta, una concesión de doscientos barriles es
# un punto que tapa el relieve sin decir nada.
TOPE = 14
# La ventana del mapa, en unidades del lienzo: el respiro alrededor de las
# burbujas y la proporción ancho/alto del recuadro donde se dibuja.
RESPIRO = 16
PROPORCION = 0.86


def nombre_de(concesion: str) -> str:
    """En título, con los bloques en romanos: "LA ANGOSTURA SUR II" → "La Angostura Sur II"."""
    palabras = en_titulo(concesion.strip()).split(" ")
    return " ".join(p.upper() if p.upper() in {"I", "II", "III", "IV"} else p for p in palabras)


def main() -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.parse_args()

    if not POZOS.exists() or not MAPA.exists():
        raise SystemExit("faltan production_wells.parquet o mapa_web.json; correr esos transforms antes")

    mapa = json.loads(MAPA.read_text(encoding="utf-8"))
    proyeccion = Proyeccion(tuple(mapa["encuadre"]))

    pozos = pd.read_parquet(POZOS, columns=["operador", "concesion", "fecha", "boe", "lon", "lat"])
    pozos = pozos[pozos["operador"] == OPERADOR].dropna(subset=["concesion", "fecha"])
    pozos["concesion"] = pozos["concesion"].map(nombre_de)
    pozos["trimestre"] = pozos["fecha"].dt.to_period("Q")

    # Solo trimestres completos: un trimestre con un mes cargado daría un
    # promedio diario de un tercio.
    meses = pozos.groupby("trimestre")["fecha"].nunique()
    completos = meses[meses == 3].index
    pozos = pozos[pozos["trimestre"].isin(completos) & (pozos["trimestre"] >= pd.Period(DESDE, "Q"))]
    trimestres = sorted(pozos["trimestre"].unique())
    dias = pd.Series({t: (t.end_time.normalize() - t.start_time.normalize()).days + 1 for t in trimestres})

    volumen = pozos.groupby(["concesion", "trimestre"])["boe"].sum().unstack("trimestre").reindex(columns=trimestres)
    diario = volumen.div(dias, axis=1).fillna(0.0)
    total = pozos.groupby("trimestre")["boe"].sum().reindex(trimestres).div(dias)

    # Se eligen por lo que produjeron en el último año: una concesión grande
    # hace cinco años y apagada hoy no merece una burbuja fija.
    ultimo_anio = diario.iloc[:, -4:].mean(axis=1).sort_values(ascending=False)
    elegidas = ultimo_anio.head(TOPE).index

    ubicados = pozos.dropna(subset=["lon", "lat"])
    ubicados = ubicados[ubicados["concesion"].isin(elegidas) & (ubicados["boe"] > 0)]
    peso = ubicados.groupby("concesion")["boe"].sum()
    lon = (ubicados["lon"] * ubicados["boe"]).groupby(ubicados["concesion"]).sum() / peso
    lat = (ubicados["lat"] * ubicados["boe"]).groupby(ubicados["concesion"]).sum() / peso

    concesiones = []
    for nombre in elegidas:
        if nombre not in lon.index:
            continue
        x, y = proyeccion.punto(float(lon[nombre]), float(lat[nombre]))
        concesiones.append({
            "nombre": nombre,
            "x": x,
            "y": y,
            "boed": [round(float(v), 0) for v in diario.loc[nombre]],
        })

    # La ventana: las concesiones de YPF ocupan un rincón de la cuenca, y con
    # el mapa entero las catorce burbujas serían una sola mancha. Se encuadra
    # el núcleo con un respiro y en la proporción de la tarjeta.
    xs, ys = [c["x"] for c in concesiones], [c["y"] for c in concesiones]
    x0, x1 = min(xs) - RESPIRO, max(xs) + RESPIRO
    y0, y1 = min(ys) - RESPIRO, max(ys) + RESPIRO
    ancho, alto = x1 - x0, y1 - y0
    if ancho / alto < PROPORCION:
        falta = alto * PROPORCION - ancho
        x0, x1 = x0 - falta / 2, x1 + falta / 2
    else:
        falta = ancho / PROPORCION - alto
        y0, y1 = y0 - falta / 2, y1 + falta / 2

    payload = {
        "generado": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fuente": "Secretaría de Energía, capítulo IV (producción no convencional por pozo)",
        "unidades": {"boed": "boe/d promedio del trimestre, producción bruta operada"},
        "lienzo": mapa["lienzo"],
        "relieve": mapa["relieve"],
        "ventana": {"x": round(x0, 1), "y": round(y0, 1), "ancho": round(x1 - x0, 1), "alto": round(y1 - y0, 1)},
        "trimestres": [str(t) for t in trimestres],
        "total_boed": [round(float(v), 0) for v in total],
        "concesiones": concesiones,
        "nota": (
            "Producción no convencional operada por YPF, bruta (incluye la parte de los socios). "
            "No es la producción neta del release. La ubicación es el promedio de los pozos de la "
            "concesión pesado por su producción acumulada."
        ),
    }
    tamanio = save_json(payload, SALIDA)
    record(
        "transform/tablero-mapa",
        rows=len(concesiones),
        bytes=int(tamanio),
        outputs=[rel(SALIDA)],
        note=f"{trimestres[0]}–{trimestres[-1]}, {len(concesiones)} concesiones",
    )
    log(f"{rel(SALIDA)} ({human(tamanio)}) · {len(concesiones)} concesiones · {trimestres[0]}–{trimestres[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
