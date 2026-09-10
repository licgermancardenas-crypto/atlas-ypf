"""Los comparables —Vista y Pampa— en las mismas líneas que YPF.

Sale del XBRL de sus 20-F, que a diferencia del de YPF sí está tagueado en la
taxonomía IFRS: no hay que parsear HTML, alcanza con leer los hechos y quedarse
con los del ejercicio completo en dólares.

De la portada del 20-F salen dos datos que el XBRL no trae y sin los cuales la
capitalización bursátil sale mal: cuántas acciones hay en circulación y cuántas
representa cada ADS. En Pampa, cada ADS son 25 acciones; en Vista, una. Sin ese
factor, el múltiplo de Pampa daría veinticinco veces lo que vale.

Entrada:  data/raw/financials/peers/<TICKER>/  (los baja ingest/peers_sec.py)
Salidas:  data/processed/peers.parquet         (largo: emisor-concepto-ejercicio)
          data/processed/peers.json            (fichas de cada emisor)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

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
    save_parquet,
)

ENTRADA = RAW / "financials" / "peers"
OUT_LONG = PROCESSED / "peers.parquet"
OUT_JSON = PROCESSED / "peers.json"

# El nombre del hecho XBRL y el de la línea equivalente en el libro de YPF. El
# orden es el de un estado de resultados que sigue hasta el balance.
# Cada línea con los hechos que la pueden traer, en orden de preferencia. No
# todos los emisores taguean lo mismo: Pampa no publica "DepreciationAnd
# AmortisationExpense" y hay que ir a buscar el ajuste del flujo de efectivo,
# que es el mismo número visto desde el otro estado.
CONCEPTOS = {
    "ingresos": ["Revenue", "RevenueFromContractsWithCustomers"],
    "costo_de_ventas": ["CostOfSales"],
    "resultado_bruto": ["GrossProfit"],
    "resultado_operativo": ["ProfitLossFromOperatingActivities"],
    "depreciacion_y_amortizacion": [
        "DepreciationAndAmortisationExpense",
        "AdjustmentsForDepreciationAndAmortisationExpense",
    ],
    "costos_financieros": ["FinanceCosts"],
    "impuesto_a_las_ganancias": ["IncomeTaxExpenseContinuingOperations"],
    "resultado_neto": ["ProfitLoss"],
    "activos": ["Assets"],
    "patrimonio": ["Equity"],
    "caja": ["CashAndCashEquivalents"],
    "deuda_financiera": ["Borrowings"],
    "bienes_de_uso": ["PropertyPlantAndEquipment"],
    "flujo_operativo": ["CashFlowsFromUsedInOperatingActivities"],
    "capex": ["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"],
}

# Cuando ni la línea ni su alternativa existen, se suma lo que sí está: la
# depreciación de bienes de uso, la de derechos de uso y la amortización de
# intangibles son las tres partes de la misma línea.
SUMAS = {
    "depreciacion_y_amortizacion": [
        "DepreciationPropertyPlantAndEquipment",
        "DepreciationRightofuseAssets",
        "AmortisationIntangibleAssetsOtherThanGoodwill",
    ],
    "deuda_financiera": [
        "CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings",
        "NoncurrentBorrowings",
    ],
}

RE_ADS = re.compile(r"each representing ([a-z0-9]+) (?:series [a-z] )?shares?", re.IGNORECASE)
RE_ACCIONES = re.compile(r"([\d,]{7,})\s+outstanding (?:series [a-z] )?shares", re.IGNORECASE)
NUMEROS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10, "twenty": 20, "twenty-five": 25}


def texto_plano(ruta: Path) -> str:
    crudo = ruta.read_text(encoding="utf-8", errors="ignore")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", crudo)).replace("&#160;", " ")


def ficha_de_portada(ruta: Path) -> dict:
    """Acciones en circulación y acciones por ADS, de la portada del 20-F."""
    texto = texto_plano(ruta)
    ficha: dict = {}

    ads = RE_ADS.search(texto)
    if ads:
        valor = ads.group(1).lower()
        ficha["acciones_por_ads"] = int(valor) if valor.isdigit() else NUMEROS.get(valor)

    acciones = RE_ACCIONES.search(texto)
    if acciones:
        ficha["acciones"] = int(acciones.group(1).replace(",", ""))
    return ficha


def hechos_anuales(companyfacts: dict) -> pd.DataFrame:
    """Los hechos del ejercicio completo, en dólares, uno por concepto y año.

    El XBRL trae el mismo concepto muchas veces: el ejercicio, el trimestre, la
    versión de cada presentación. Se toma el período de doce meses —o el saldo
    al 31 de diciembre, para los stocks— y, cuando hay más de una versión del
    mismo año, la de la presentación más reciente.
    """
    ifrs = companyfacts.get("facts", {}).get("ifrs-full", {})

    def anuales(tag: str) -> list[dict]:
        hecho = ifrs.get(tag)
        if not hecho:
            return []
        salida = []
        for valor in hecho.get("units", {}).get("USD", []):
            fin = valor.get("end", "")
            if not fin.endswith("-12-31"):
                continue
            inicio = valor.get("start")
            if inicio:
                dias = (pd.Timestamp(fin) - pd.Timestamp(inicio)).days
                if dias < 300 or dias > 400:
                    continue  # trimestres y semestres afuera
            salida.append(
                {
                    "anio": int(fin[:4]),
                    "valor_usd": float(valor["val"]),
                    "presentado": valor.get("filed", ""),
                    "form": valor.get("form", ""),
                    "tag": tag,
                }
            )
        return salida

    def por_anio(tags: list[str]) -> pd.DataFrame:
        registros = [r for tag in tags for r in anuales(tag)]
        if not registros:
            return pd.DataFrame()
        tabla = pd.DataFrame(registros)
        # Entre dos versiones del mismo año gana la presentación más reciente;
        # entre dos tags, el que aparece primero en la lista de preferencia.
        tabla["prioridad"] = tabla["tag"].map({t: i for i, t in enumerate(tags)})
        return (
            tabla.sort_values(["prioridad", "presentado"], ascending=[False, True])
            .drop_duplicates("anio", keep="last")
            .drop(columns=["prioridad"])
        )

    filas = []
    for concepto, tags in CONCEPTOS.items():
        tabla = por_anio(tags)
        if tabla.empty and concepto in SUMAS:
            partes = [por_anio([tag]) for tag in SUMAS[concepto]]
            partes = [p for p in partes if not p.empty]
            if partes:
                juntas = pd.concat(partes)
                tabla = (
                    juntas.groupby("anio")
                    .agg(valor_usd=("valor_usd", "sum"), presentado=("presentado", "max"),
                         form=("form", "last"), tag=("tag", lambda v: "+".join(sorted(set(v)))))
                    .reset_index()
                )
        if tabla.empty:
            continue
        tabla = tabla.assign(concepto=concepto)
        filas.append(tabla)

    if not filas:
        return pd.DataFrame(columns=["concepto", "anio", "valor_usd"])
    return pd.concat(filas, ignore_index=True)


def recolectar() -> tuple[pd.DataFrame, list[dict]]:
    registros: list[pd.DataFrame] = []
    fichas: list[dict] = []

    for carpeta in sorted(p for p in ENTRADA.iterdir() if p.is_dir()):
        ruta_hechos = carpeta / "companyfacts.json"
        if not ruta_hechos.exists():
            continue
        companyfacts = json.loads(ruta_hechos.read_text(encoding="utf-8"))
        tabla = hechos_anuales(companyfacts)
        tabla["ticker"] = carpeta.name
        registros.append(tabla)

        meta_path = carpeta / "_meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        ficha = {
            "ticker": carpeta.name,
            "nombre": meta.get("nombre", carpeta.name),
            "cik": meta.get("cik"),
            "ultimo_20f": meta.get("periodo"),
            "presentado": meta.get("presentado"),
        }
        portada = carpeta / "20-F.htm"
        if portada.exists():
            ficha.update(ficha_de_portada(portada))

        # El dei del XBRL trae las acciones de la portada; si el regex falló,
        # sirve de red.
        dei = companyfacts.get("facts", {}).get("dei", {}).get("EntityCommonStockSharesOutstanding", {})
        valores = [v for unidad in dei.get("units", {}).values() for v in unidad]
        if valores and not ficha.get("acciones"):
            ficha["acciones"] = int(sorted(valores, key=lambda v: v.get("end", ""))[-1]["val"])

        anios = sorted(tabla["anio"].unique()) if len(tabla) else []
        ficha["ejercicios"] = [int(a) for a in anios]
        fichas.append(ficha)
        log(
            f"{carpeta.name}: {len(tabla)} hechos, ejercicios {anios[0] if anios else '?'}"
            f"–{anios[-1] if anios else '?'}, {ficha.get('acciones', '?')} acciones, "
            f"{ficha.get('acciones_por_ads', '?')} por ADS"
        )

    if not registros:
        raise SystemExit("no se encontró ningún comparable; correr ingest/peers_sec.py")
    return pd.concat(registros, ignore_index=True), fichas


def main() -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.parse_args()

    tabla, fichas = recolectar()
    tabla = tabla[["ticker", "concepto", "anio", "valor_usd", "form", "presentado", "tag"]].sort_values(
        ["ticker", "concepto", "anio"]
    )

    bytes_parquet = save_parquet(tabla.reset_index(drop=True), OUT_LONG)
    payload = {
        "generado": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "moneda": "USD",
        "fuente": "SEC EDGAR, XBRL de los 20-F (taxonomía IFRS)",
        "emisores": fichas,
        "conceptos": sorted(tabla["concepto"].unique()),
        "nota": (
            "Solo ejercicio completo: el XBRL de un emisor privado extranjero no "
            "trae el trimestre. Las acciones y el ratio de ADS salen de la portada "
            "del último 20-F."
        ),
    }
    bytes_json = save_json(payload, OUT_JSON, indent=2)

    log(f"{len(tabla)} hechos de {tabla['ticker'].nunique()} emisores")
    record(
        "transform/peers",
        rows=int(len(tabla)),
        bytes=int(bytes_parquet + bytes_json),
        outputs=[rel(OUT_LONG), rel(OUT_JSON)],
        source=rel(ENTRADA),
        note="comparables anuales en dólares desde el XBRL de los 20-F",
    )
    log(f"{rel(OUT_LONG)} ({human(bytes_parquet)}) · {rel(OUT_JSON)} ({human(bytes_json)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
