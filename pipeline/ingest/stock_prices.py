"""Dataset 4 — Precio de la acción de YPF (ADR en NYSE y local en BYMA).

Fuente: API de charts de Yahoo Finance. Se guarda el JSON crudo tal cual, un
archivo por ticker, en data/raw/market/stock/.

  YPF       ADR en NYSE, en USD — es el precio que reacciona al balance
  YPFD.BA   la acción local en BYMA, en ARS

Con --with-comparables suma VIST (Vista Energy) y PAM (Pampa Energía), los dos
comparables del análisis. La serie arranca en el primer dato disponible del
ticker: el recorte por fechas es trabajo de pipeline/transform/.
"""

from __future__ import annotations

import sys
import time
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

DEST = RAW / "market" / "stock"
TICKERS = ["YPF", "YPFD.BA"]
COMPARABLES = ["VIST", "PAM"]


def fetch(session, symbol: str, args) -> bool:
    key = f"market/stock/{symbol}"
    if is_fresh(key, args.force, args.max_age_days):
        log(f"{symbol}: fresco en el manifest, se saltea (--force para rebajar)")
        return False

    payload = yahoo_chart(session, symbol, args.interval)
    result = payload["chart"]["result"][0]
    timestamps = result.get("timestamp") or []
    meta = result.get("meta", {})

    dest = DEST / f"{symbol.replace('.', '_')}.json"
    size = save_json(payload, dest)

    record(
        key,
        dataset_id=4,
        source="Yahoo Finance",
        symbol=symbol,
        exchange=meta.get("fullExchangeName"),
        currency=meta.get("currency"),
        interval=args.interval,
        url=f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
        path=rel(dest),
        rows=len(timestamps),
        bytes=size,
    )
    log(
        f"{symbol}: {len(timestamps):,} ruedas ({meta.get('currency')}, "
        f"{meta.get('fullExchangeName')}), {human(size)} -> {rel(dest)}"
    )
    return True


def main() -> int:
    parser = base_parser("Baja el precio de la accion de YPF desde Yahoo Finance")
    parser.add_argument("--interval", default="1d", help="granularidad Yahoo (default: 1d)")
    parser.add_argument(
        "--with-comparables",
        action="store_true",
        help="suma VIST y PAM, los comparables del analisis",
    )
    args = parser.parse_args()

    symbols = TICKERS + (COMPARABLES if args.with_comparables else [])
    session = yahoo_session()

    bajados, fallidos = 0, []
    for symbol in symbols:
        try:
            if fetch(session, symbol, args):
                bajados += 1
        except Exception as exc:  # noqa: BLE001 - un ticker roto no corta el resto
            log(f"{symbol}: FALLO {exc}")
            fallidos.append(symbol)
        time.sleep(1)  # Yahoo agradece el respiro

    log(f"listo: {bajados}/{len(symbols)} tickers bajados")
    if fallidos:
        log(f"ATENCION: fallaron {', '.join(fallidos)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
