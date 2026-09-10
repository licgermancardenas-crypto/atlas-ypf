"""Orquestador del pipeline: corre la ingesta y (más adelante) los transforms.

Es lo que va a ejecutar el GitHub Action de refresh semanal (Fase 7). Cada etapa
corre como subproceso: si un script de ingesta falla, se registra y el proceso
termina con exit code distinto de cero, para que el job quede en rojo en vez de
fallar en silencio.

Uso:
    python pipeline/run_all.py                    # ingesta + transforms
    python pipeline/run_all.py --force            # ignora la frescura del manifest
    python pipeline/run_all.py --only market      # solo los scripts que matcheen
    python pipeline/run_all.py --skip-ingest      # solo transforms, sin tocar la red
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INGEST = ROOT / "pipeline" / "ingest"
TRANSFORM = ROOT / "pipeline" / "transform"
EXPORT = ROOT / "pipeline" / "export"

# Orden deliberado: primero lo liviano, para fallar rápido si no hay red.
# El tercer elemento son los argumentos propios de esa etapa, si los tiene.
INGEST_SCRIPTS = [
    # Los comparables (VIST, PAM) no son opcionales acá: el event study de
    # transform/market_reaction.py estima el retorno anormal contra Vista.
    ("market/stock", INGEST / "stock_prices.py", ["--with-comparables"]),
    ("market/oil", INGEST / "brent_wti.py", []),
    ("macro/fx", INGEST / "fx_ars_usd.py", []),
    ("macro/country-risk", INGEST / "country_risk.py", []),
    ("production", INGEST / "production_wells.py", []),
    ("production/sesco", INGEST / "production_country.py", []),
    ("reservas", INGEST / "reserves.py", []),
    ("financials/ypf", INGEST / "financials_ypf.py", []),
    # Los comparables: su XBRL sale estructurado, asi que es una descarga chica
    # y un transform sin parseo de HTML.
    ("financials/peers", INGEST / "peers_sec.py", []),
    ("geo/vectores", INGEST / "geo_layers.py", []),
    ("geo/dem", INGEST / "dem_neuquina.py", []),
]

# Los transforms corren despues de la ingesta y dependen de ella: production
# normaliza el panel pozo-mes que consumen los transforms financieros.
TRANSFORM_SCRIPTS: list[tuple[str, Path, list[str]]] = [
    ("transform/financials", TRANSFORM / "financials_ypf.py", []),
    # Los estados contables completos salen de los mismos filings que los
    # highlights, pero de las tablas del Item 1 y no de la de resumen.
    ("transform/estados", TRANSFORM / "statements_ypf.py", []),
    # Los segmentos salen de la misma nota del mismo filing, pero de otra
    # tabla: es lo que abre el consolidado en los tres negocios que lo forman.
    ("transform/segmentos", TRANSFORM / "segments_ypf.py", []),
    ("transform/peers", TRANSFORM / "peers.py", []),
    ("transform/production", TRANSFORM / "production_wells.py", []),
    ("transform/pais", TRANSFORM / "production_country.py", []),
    ("transform/reservas", TRANSFORM / "reserves.py", []),
    ("transform/decline", TRANSFORM / "decline_curves.py", []),
    ("transform/economics", TRANSFORM / "well_economics.py", []),
    ("transform/sensitivity", TRANSFORM / "ebitda_sensitivity.py", []),
    ("transform/market", TRANSFORM / "market_reaction.py", []),
    ("transform/scenario", TRANSFORM / "scenario_engine.py", []),
    ("transform/geo", TRANSFORM / "geo_layers.py", []),
    # Despues de geo: la titularidad sale del padron de concesiones que baja
    # ingest/geo_layers.py, y las metricas del panel de produccion.
    ("transform/grafo", TRANSFORM / "entity_graph.py", []),
    ("transform/catalogo", TRANSFORM / "catalogo.py", []),
    # El Excel se arma despues del catalogo: es una salida de presentacion,
    # no una entrada de ningun otro paso.
    ("export/excel", EXPORT / "excel_estados.py", []),
    # Ultima etapa: si algo quedo imposible, el job termina en rojo y el commit
    # automatico de datos no llega a ejecutarse.
    ("checks", ROOT / "pipeline" / "checks.py", []),
]


def run(nombre: str, script: Path, propios: list[str], extra: list[str]) -> int:
    if not script.exists():
        print(f"[run_all] {nombre}: falta {script.name}, se saltea")
        return 0
    print(f"\n[run_all] === {nombre} ({script.name}) ===", flush=True)
    result = subprocess.run([sys.executable, str(script), *propios, *extra], cwd=ROOT)
    if result.returncode != 0:
        print(f"[run_all] {nombre}: FALLO (exit {result.returncode})")
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Corre el pipeline completo")
    parser.add_argument("--force", action="store_true", help="se lo pasa a cada script de ingesta")
    parser.add_argument("--only", default="", help="corre solo las etapas cuyo nombre contenga esto")
    parser.add_argument(
        "--skip",
        default="",
        help="saltea las etapas cuyo nombre contenga alguno de estos textos (separados por coma)",
    )
    parser.add_argument("--skip-ingest", action="store_true", help="saltea la ingesta")
    args = parser.parse_args()

    extra = ["--force"] if args.force else []
    etapas = ([] if args.skip_ingest else INGEST_SCRIPTS) + TRANSFORM_SCRIPTS
    if args.only:
        etapas = [e for e in etapas if args.only in e[0]]
    # --skip existe para el refresh semanal: las capas geoespaciales pesan cientos
    # de megas y no cambian de una semana a la otra, así que el job las saltea.
    for patron in filter(None, (p.strip() for p in args.skip.split(","))):
        etapas = [e for e in etapas if patron not in e[0]]

    fallidas = [
        nombre for nombre, script, propios in etapas if run(nombre, script, propios, extra) != 0
    ]

    print(f"\n[run_all] {len(etapas) - len(fallidas)}/{len(etapas)} etapas OK")
    if fallidas:
        print(f"[run_all] fallaron: {', '.join(fallidas)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
