"""Dataset 6 — Tipo de cambio ARS/USD.

Fuente: Yahoo Finance (ARS=X, mayorista implícito en la cotización que publica
el proveedor). Se guarda el JSON crudo en data/raw/macro/fx/.

Para qué entra al análisis: el EBITDA de YPF se reporta en dólares, pero los
costos y buena parte de los precios regulados se fijan en pesos. El atraso o el
salto del tipo de cambio se traduce en margen, y es una de las variables del
simulador de escenarios. Además, la brecha contra el crudo Brent explica parte
del diferencial del crudo local.

Limitación conocida: es el oficial, no el financiero (CCL/MEP). Para la lectura
de mercado del caso conviene tener presente esa diferencia; si el análisis
termina necesitando el CCL, la fuente es otra (BCRA o Ámbito) y va en su propio
script, no acá.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    RAW,
    base_parser,
    human,
    is_fresh,
    log,
    record,
    rel,
    save_json,
    yahoo_chart,
    yahoo_session,
)

DEST = RAW / "macro" / "fx"
SYMBOL = "ARS=X"
KEY = "macro/fx/ars_usd"


def main() -> int:
    parser = base_parser("Baja el tipo de cambio ARS/USD desde Yahoo Finance")
    parser.add_argument("--interval", default="1d", help="granularidad Yahoo (default: 1d)")
    args = parser.parse_args()

    if is_fresh(KEY, args.force, args.max_age_days):
        log("ars_usd: fresco en el manifest, se saltea (--force para rebajar)")
        return 0

    session = yahoo_session()
    payload = yahoo_chart(session, SYMBOL, args.interval)
    result = payload["chart"]["result"][0]
    timestamps = result.get("timestamp") or []
    meta = result.get("meta", {})

    dest = DEST / "ars_usd.json"
    size = save_json(payload, dest)

    record(
        KEY,
        dataset_id=6,
        source="Yahoo Finance",
        symbol=SYMBOL,
        currency=meta.get("currency"),
        interval=args.interval,
        url=f"https://query1.finance.yahoo.com/v8/finance/chart/{SYMBOL}",
        path=rel(dest),
        rows=len(timestamps),
        bytes=size,
    )
    log(f"ars_usd ({SYMBOL}): {len(timestamps):,} ruedas, {human(size)} -> {rel(dest)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
