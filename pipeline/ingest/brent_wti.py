"""Dataset 5 — Precio del crudo: Brent y WTI.

Fuente: futuros continuos de Yahoo Finance (BZ=F Brent, CL=F WTI). Se guarda el
JSON crudo, un archivo por contrato, en data/raw/market/oil/.

Brent es la referencia que importa para el análisis: el precio de exportación de
YPF y el escenario del simulador se mueven contra Brent. WTI se baja como
control y para comparar contra la referencia de Permian.
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

DEST = RAW / "market" / "oil"

# ticker Yahoo -> nombre de archivo (los símbolos traen "=", ilegal en Windows)
CONTRATOS = {
    "BZ=F": "brent",
    "CL=F": "wti",
}


def fetch(session, symbol: str, slug: str, args) -> bool:
    key = f"market/oil/{slug}"
    if is_fresh(key, args.force, args.max_age_days):
        log(f"{slug}: fresco en el manifest, se saltea (--force para rebajar)")
        return False

    payload = yahoo_chart(session, symbol, args.interval)
    result = payload["chart"]["result"][0]
    timestamps = result.get("timestamp") or []
    meta = result.get("meta", {})

    dest = DEST / f"{slug}.json"
    size = save_json(payload, dest)

    record(
        key,
        dataset_id=5,
        source="Yahoo Finance",
        symbol=symbol,
        currency=meta.get("currency"),
        interval=args.interval,
        url=f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
        path=rel(dest),
        rows=len(timestamps),
        bytes=size,
    )
    log(f"{slug} ({symbol}): {len(timestamps):,} ruedas, {human(size)} -> {rel(dest)}")
    return True


def main() -> int:
    parser = base_parser("Baja Brent y WTI desde Yahoo Finance")
    parser.add_argument("--interval", default="1d", help="granularidad Yahoo (default: 1d)")
    args = parser.parse_args()

    session = yahoo_session()
    bajados, fallidos = 0, []
    for symbol, slug in CONTRATOS.items():
        try:
            if fetch(session, symbol, slug, args):
                bajados += 1
        except Exception as exc:  # noqa: BLE001 - un contrato roto no corta el resto
            log(f"{slug}: FALLO {exc}")
            fallidos.append(slug)
        time.sleep(1)

    log(f"listo: {bajados}/{len(CONTRATOS)} contratos bajados")
    if fallidos:
        log(f"ATENCION: fallaron {', '.join(fallidos)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
