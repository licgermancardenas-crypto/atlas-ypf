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

# Orden deliberado: primero lo liviano, para fallar rápido si no hay red.
INGEST_SCRIPTS = [
    ("market/stock", INGEST / "stock_prices.py"),
    ("market/oil", INGEST / "brent_wti.py"),
    ("production", INGEST / "production_wells.py"),
    ("financials/ypf", INGEST / "financials_ypf.py"),
]

# Los transforms corren despues de la ingesta y dependen de ella: production
# normaliza el panel pozo-mes que consumen los transforms financieros.
TRANSFORM_SCRIPTS: list[tuple[str, Path]] = [
    ("transform/financials", TRANSFORM / "financials_ypf.py"),
    ("transform/production", TRANSFORM / "production_wells.py"),
    ("transform/decline", TRANSFORM / "decline_curves.py"),
    ("transform/economics", TRANSFORM / "well_economics.py"),
]


def run(nombre: str, script: Path, extra: list[str]) -> int:
    if not script.exists():
        print(f"[run_all] {nombre}: falta {script.name}, se saltea")
        return 0
    print(f"\n[run_all] === {nombre} ({script.name}) ===", flush=True)
    result = subprocess.run([sys.executable, str(script), *extra], cwd=ROOT)
    if result.returncode != 0:
        print(f"[run_all] {nombre}: FALLO (exit {result.returncode})")
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Corre el pipeline completo")
    parser.add_argument("--force", action="store_true", help="se lo pasa a cada script de ingesta")
    parser.add_argument("--only", default="", help="corre solo las etapas cuyo nombre contenga esto")
    parser.add_argument("--skip-ingest", action="store_true", help="saltea la ingesta")
    args = parser.parse_args()

    extra = ["--force"] if args.force else []
    etapas = ([] if args.skip_ingest else INGEST_SCRIPTS) + TRANSFORM_SCRIPTS
    if args.only:
        etapas = [e for e in etapas if args.only in e[0]]

    fallidas = [nombre for nombre, script in etapas if run(nombre, script, extra) != 0]

    print(f"\n[run_all] {len(etapas) - len(fallidas)}/{len(etapas)} etapas OK")
    if fallidas:
        print(f"[run_all] fallaron: {', '.join(fallidas)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
