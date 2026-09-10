"""Chequeos de invariantes sobre lo que el pipeline dejó en data/processed/.

Por qué existe. Este proyecto ya tuvo dos errores de datos que llegaron hasta el
final: el gas leído en la unidad equivocada, y la fila de totales del Excel de
reservas colándose como si fuera un operador —lo que le sumó las reservas de
toda la Argentina a TotalEnergies—. Los dos se encontraron mirando, de casualidad,
porque un número quedó raro. El tercero se publica.

Un chequeo de invariantes no verifica que el dato sea correcto: verifica que no
sea imposible. Que las partes sumen al total, que ningún operador produzca más
que el país, que un porcentaje esté entre cero y uno, que una coordenada caiga
en la Argentina. Es un cinturón barato contra la clase de error que no se ve
leyendo el código, sino comparando dos números que tenían que coincidir.

Corre como última etapa de run_all.py, así que una violación deja el job de
Actions en rojo y frena el commit automático de datos.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"

# Tolerancia relativa al comparar dos caminos que deberían dar lo mismo. No es
# cero porque los redondeos a un decimal de cada serie se acumulan.
TOLERANCIA = 0.02


class Problema(Exception):
    """Una invariante violada. El mensaje tiene que decir qué se esperaba."""


def leer(nombre: str) -> dict | None:
    ruta = PROCESSED / nombre
    if not ruta.exists():
        return None
    return json.loads(ruta.read_text(encoding="utf-8"))


def cerca(a: float, b: float, tolerancia: float = TOLERANCIA) -> bool:
    if a == 0 and b == 0:
        return True
    escala = max(abs(a), abs(b))
    return abs(a - b) / escala <= tolerancia


# --------------------------------------------------------------------------- #
# Chequeos
# --------------------------------------------------------------------------- #
def chequear_pais(problemas: list[str]) -> None:
    """Convencional mas shale mas tight tiene que dar el total de cada mes."""
    datos = leer("country_production.json")
    if not datos:
        return

    for mes in datos["pais"]:
        partes = [mes.get(f"oil_{c}") for c in ("convencional", "shale", "tight")]
        total = mes.get("oil_total")
        if total is None or any(p is None for p in partes):
            continue
        if not cerca(sum(partes), total, 0.001):
            problemas.append(
                f"pais {mes['fecha']}: convencional+shale+tight = {sum(partes):,.0f} "
                f"pero oil_total = {total:,.0f}"
            )
            break  # con uno alcanza para saber que la serie está mal armada

    ultimo = datos["pais"][-1]
    if ultimo.get("oil_total") and not 200_000 < ultimo["oil_total"] < 3_000_000:
        problemas.append(
            f"pais {ultimo['fecha']}: {ultimo['oil_total']:,.0f} bbl/d esta fuera de todo "
            "rango historico de la Argentina (200 mil a 3 millones)"
        )


def chequear_rankings(problemas: list[str]) -> None:
    """Ningún miembro puede producir una fracción absurda del país.

    Es el chequeo que habría cazado la fila de totales del Excel: cuando un
    total se cuela como si fuera una empresa, esa empresa pasa a valer casi
    tanto como el país entero.
    """
    datos = leer("country_production.json")
    if not datos:
        return

    for dimension, filas in (datos.get("rankings") or {}).items():
        if not filas:
            continue
        total = sum(fila["actual_bd"] for fila in filas if fila["actual_bd"] > 0)
        if total <= 0:
            continue
        mayor = max(filas, key=lambda fila: fila["actual_bd"])
        # Una cuenca sí puede ser el 80% del país (la Neuquina lo es); una
        # empresa o un yacimiento, no.
        techo = 0.9 if dimension in ("cuenca", "provincia") else 0.55
        if mayor["actual_bd"] / total > techo:
            problemas.append(
                f"rankings/{dimension}: '{mayor['nombre']}' concentra "
                f"{mayor['actual_bd'] / total:.0%} del total; sospecha de fila de totales "
                "leida como si fuera un miembro"
            )


def chequear_reservas(problemas: list[str]) -> None:
    """El desglose por cuenca y el desglose por fluido tienen que dar lo mismo."""
    datos = leer("reserves.json")
    if not datos:
        return

    filas = datos["ranking_ultimo"]
    if not filas:
        problemas.append("reservas: el ranking del ultimo anio vino vacio")
        return

    total = sum(fila["comprobadas_mboe"] for fila in filas)
    mayor = max(filas, key=lambda fila: fila["comprobadas_mboe"])
    if total and mayor["comprobadas_mboe"] / total > 0.55:
        problemas.append(
            f"reservas: '{mayor['operador']}' tiene {mayor['comprobadas_mboe'] / total:.0%} "
            "de las reservas del ranking; sospecha de fila de totales"
        )

    for fila in filas:
        vida = fila.get("vida_reservas")
        if vida is not None and not 0 < vida < 100:
            problemas.append(
                f"reservas: vida de reservas de {fila['operador']} = {vida} anios, fuera de rango"
            )
        share = fila.get("share_no_convencional")
        if share is not None and not 0 <= share <= 1:
            problemas.append(
                f"reservas: share no convencional de {fila['operador']} = {share}, fuera de [0,1]"
            )


def chequear_cruce_shale(problemas: list[str]) -> None:
    """El shale del país tiene que dar igual por dos caminos distintos.

    Uno sale de sumar los pozos del capítulo IV uno por uno; el otro, de la
    serie agregada de SESCO. Son dos publicaciones distintas de la misma
    Secretaría: si dejan de coincidir, alguna conversión se rompió.
    """
    pais = leer("country_production.json")
    pozos = leer("production_summary.json")
    if not pais or not pozos:
        return

    ultimo_pais = next(
        (mes for mes in reversed(pais["pais"]) if mes.get("oil_shale")), None
    )
    if not ultimo_pais:
        return

    mes = ultimo_pais["fecha"]
    desde_pozos = next(
        (punto for punto in pozos.get("vaca_muerta_total", []) if punto["fecha"] == mes), None
    )
    if not desde_pozos:
        return

    # El panel pozo-mes solo tiene Vaca Muerta; la serie del país incluye el
    # shale de otras formaciones, así que el agregado nunca puede ser menor.
    if desde_pozos["petroleo_bd"] > ultimo_pais["oil_shale"] * (1 + TOLERANCIA):
        problemas.append(
            f"cruce {mes}: Vaca Muerta desde los pozos da {desde_pozos['petroleo_bd']:,.0f} bbl/d "
            f"pero el shale de todo el pais da {ultimo_pais['oil_shale']:,.0f}; "
            "la parte no puede ser mayor que el todo"
        )


def chequear_financieros(problemas: list[str]) -> None:
    """Ningun trimestre puede traer margenes ni deuda fuera de rango posible."""
    datos = leer("financials_ypf.json")
    if not datos:
        return

    for fila in datos["serie"]:
        margen = fila.get("margen_ebitda")
        if margen is not None and not -1 <= margen <= 1:
            problemas.append(
                f"financieros {fila['trimestre']}: margen EBITDA = {margen}, fuera de [-1,1]"
            )
        ingresos = fila.get("revenues_musd")
        if ingresos is not None and not 500 < ingresos < 20_000:
            problemas.append(
                f"financieros {fila['trimestre']}: ingresos = {ingresos} MUSD, fuera de rango"
            )


def chequear_modelo(problemas: list[str]) -> None:
    """Los coeficientes del simulador tienen que conservar signo y ajuste."""
    datos = leer("scenario_coefficients.json")
    if not datos:
        return

    for clave in ("r2_ebitda", "r2_ingresos"):
        valor = datos.get(clave)
        if valor is not None and not 0 <= valor <= 1:
            problemas.append(f"simulador: {clave} = {valor}, fuera de [0,1]")

    base = datos.get("caso_base", {})
    if base.get("brent_usd") and not 10 < base["brent_usd"] < 250:
        problemas.append(f"simulador: Brent base = {base['brent_usd']}, fuera de rango")


def chequear_geo(problemas: list[str]) -> None:
    """Todas las coordenadas de pozo tienen que caer dentro de la Argentina."""
    ruta = PROCESSED / "geo" / "wells.geojson"
    if not ruta.exists():
        return

    coleccion = json.loads(ruta.read_text(encoding="utf-8"))
    fuera = 0
    for feature in coleccion["features"]:
        lon, lat = feature["geometry"]["coordinates"][:2]
        if not (-74 <= lon <= -53 and -56 <= lat <= -21):
            fuera += 1
    if fuera:
        problemas.append(f"geo: {fuera} pozos con coordenadas fuera de la Argentina")


def chequear_grafo(problemas: list[str]) -> None:
    """Ninguna arista del grafo puede apuntar a un nodo que no existe.

    El transform ya valida esto antes de escribir, pero el chequeo se repite
    aca por una razon: el archivo publicado puede quedar desfasado respecto del
    codigo que lo genero -una corrida a medias, un merge, un commit parcial- y
    lo que rompe el frontend es el archivo, no el transform.
    """
    ruta = PROCESSED / "graph" / "entities.json"
    if not ruta.exists():
        return

    grafo = json.loads(ruta.read_text(encoding="utf-8"))
    ids = {nodo["id"] for nodo in grafo["nodes"]}

    if len(ids) != len(grafo["nodes"]):
        problemas.append(
            f"grafo: {len(grafo['nodes']) - len(ids)} ids de nodo repetidos"
        )

    huerfanas = sum(
        1
        for arista in grafo["edges"]
        if arista["source"] not in ids or arista["target"] not in ids
    )
    if huerfanas:
        problemas.append(f"grafo: {huerfanas} aristas apuntan a nodos inexistentes")

    for tipo in ("concesion", "yacimiento", "empresa", "pozo"):
        if not any(nodo["type"] == tipo for nodo in grafo["nodes"]):
            problemas.append(f"grafo: no hay ningun nodo de tipo {tipo}")

    # Las participaciones de una concesion suman 100% o el padron esta mal
    # leido. Se tolera medio punto por los redondeos de la fuente.
    por_concesion: dict[str, float] = {}
    for arista in grafo["edges"]:
        if arista["type"] == "titularidad":
            pct = (arista.get("props") or {}).get("participacion_pct", 0)
            por_concesion[arista["source"]] = por_concesion.get(arista["source"], 0) + pct
    torcidas = {c: round(t, 2) for c, t in por_concesion.items() if abs(t - 100) > 0.5}
    if torcidas:
        ejemplo = sorted(torcidas.items())[:3]
        problemas.append(
            f"grafo: {len(torcidas)} concesiones con participaciones que no suman 100% "
            f"(p. ej. {ejemplo})"
        )


def chequear_estados(problemas: list[str]) -> None:
    """Los tres estados tienen que cerrar entre ellos y contra el release.

    Estos estados no salen de un XBRL: salen de parsear las tablas HTML de los
    6-K, y el trimestre de flujo de efectivo es una resta entre dos
    presentaciones distintas. Si el parseo se corre una fila o una columna, el
    activo deja de dar pasivo mas patrimonio y los cuatro trimestres dejan de
    sumar el ejercicio. Es el chequeo mas barato que hay contra eso.
    """
    ruta = PROCESSED / "statements_ypf.parquet"
    if not ruta.exists():
        return

    import pandas as pd

    datos = pd.read_parquet(ruta)

    def serie(estado: str, clave: str, tipo: str = "trimestre"):
        sub = datos[(datos["estado"] == estado) & (datos["clave"] == clave) & (datos["tipo"] == tipo)]
        return sub.groupby("periodo")["valor_musd"].first()

    activo = serie("balance", "total assets")
    pasivo = serie("balance", "total liabilities")
    patrimonio = serie("balance", "total shareholders equity")
    descuadre = (activo - (pasivo + patrimonio)).abs().max()
    if descuadre and descuadre > 0.5:
        problemas.append(f"estados: el balance no cierra, hasta {descuadre:.0f} MUSD de diferencia")

    caja_flujo = serie("flujo", "cash and cash equivalents at the end of the period")
    caja_balance = serie("balance", "cash and cash equivalents | total current assets")
    comun = caja_flujo.index.intersection(caja_balance.index)
    if len(comun):
        diferencia = (caja_flujo[comun] - caja_balance[comun]).abs().max()
        if diferencia > 0.5:
            problemas.append(
                f"estados: la caja del flujo no es la del balance, hasta {diferencia:.0f} MUSD"
            )

    # Los cuatro trimestres tienen que dar el ejercicio: es lo que valida que el
    # 4T derivado y las restas de acumulados estén bien armados.
    for estado, clave, nombre in [
        ("resultados", "revenues", "ingresos"),
        ("resultados", "net profit", "resultado neto"),
        ("flujo", "net cash flows from operating activities", "flujo operativo"),
    ]:
        trimestral = serie(estado, clave)
        anual = serie(estado, clave, "anual")
        for anio, total in anual.items():
            piezas = [v for periodo, v in trimestral.items() if periodo.startswith(str(anio))]
            if len(piezas) != 4:
                continue
            if abs(sum(piezas) - total) > 0.5:
                problemas.append(
                    f"estados: los trimestres de {anio} no suman el ejercicio en {nombre} "
                    f"({sum(piezas):.0f} contra {total:.0f} MUSD)"
                )

    # Y contra lo que la compañía publica en su earnings release, que es una
    # fuente distinta dentro del mismo filing.
    financieros = leer("financials_ypf.json")
    if not financieros:
        return
    ingresos = serie("resultados", "revenues")
    for punto in financieros.get("serie", []):
        periodo, valor = punto.get("trimestre"), punto.get("revenues_musd")
        if periodo in ingresos.index and valor and not cerca(float(valor), float(ingresos[periodo]), 0.01):
            problemas.append(
                f"estados: los ingresos de {periodo} no coinciden con el release "
                f"({ingresos[periodo]:.0f} contra {valor:.0f} MUSD)"
            )


CHEQUEOS = (
    ("produccion del pais", chequear_pais),
    ("rankings", chequear_rankings),
    ("reservas", chequear_reservas),
    ("cruce shale pozos vs pais", chequear_cruce_shale),
    ("financieros", chequear_financieros),
    ("simulador", chequear_modelo),
    ("geo", chequear_geo),
    ("grafo de entidades", chequear_grafo),
    ("estados contables", chequear_estados),
)


def main() -> int:
    problemas: list[str] = []
    for nombre, chequeo in CHEQUEOS:
        antes = len(problemas)
        try:
            chequeo(problemas)
        except Exception as exc:  # noqa: BLE001 - un chequeo roto es un problema en sí
            problemas.append(f"{nombre}: el chequeo fallo con {exc.__class__.__name__}: {exc}")
        estado = "OK" if len(problemas) == antes else "FALLA"
        print(f"[checks] {nombre:28s} {estado}")

    if problemas:
        print(f"\n[checks] {len(problemas)} invariante(s) violada(s):")
        for problema in problemas:
            print(f"  - {problema}")
        return 1

    print(f"\n[checks] {len(CHEQUEOS)}/{len(CHEQUEOS)} chequeos OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
