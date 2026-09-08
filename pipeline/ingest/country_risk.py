"""Dataset 8 — Riesgo país (EMBI+ Argentina).

Fuente: API pública de ArgentinaDatos, que republica la serie diaria del EMBI+
Argentina de JP Morgan (el índice en sí es propietario y no tiene endpoint
oficial gratuito). Se guarda el JSON crudo en data/raw/macro/country-risk/.

Para qué entra al análisis: el EMBI es el precio al que el mercado descuenta
cualquier flujo argentino. Es la variable que permite separar cuánto del
castigo a la acción es de YPF y cuánto es del país — el mismo EBITDA vale menos
si la tasa a la que se descuenta sube 200 puntos básicos.

Advertencia sobre la fuente: es un republicador, no el emisor. Si la serie deja
de actualizarse o cambia de forma, hay que revisar acá antes que en el
transform.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    RAW,
    base_parser,
    http_session,
    human,
    is_fresh,
    log,
    record,
    rel,
    save_json,
)

DEST = RAW / "macro" / "country-risk"
URL = "https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais"
KEY = "macro/country-risk/embi"


def main() -> int:
    args = base_parser("Baja la serie diaria del EMBI+ Argentina").parse_args()

    if is_fresh(KEY, args.force, args.max_age_days):
        log("embi: fresco en el manifest, se saltea (--force para rebajar)")
        return 0

    session = http_session({"Accept": "application/json"})
    response = session.get(URL, timeout=120)
    response.raise_for_status()
    serie = response.json()

    if not isinstance(serie, list) or not serie:
        raise RuntimeError(f"la API de riesgo pais no devolvio una serie: {str(serie)[:200]}")
    if not {"fecha", "valor"} <= set(serie[0]):
        raise RuntimeError(f"la serie cambio de forma: {json.dumps(serie[0])}")

    dest = DEST / "embi.json"
    size = save_json({"serie": serie}, dest)

    record(
        KEY,
        dataset_id=8,
        source="ArgentinaDatos (republica EMBI+ Argentina de JP Morgan)",
        indicador="EMBI+ Argentina",
        unidad="puntos basicos",
        url=URL,
        path=rel(dest),
        rows=len(serie),
        desde=serie[0]["fecha"],
        hasta=serie[-1]["fecha"],
        bytes=size,
    )
    log(
        f"embi: {len(serie):,} ruedas ({serie[0]['fecha']} a {serie[-1]['fecha']}), "
        f"ultimo {serie[-1]['valor']} pb, {human(size)} -> {rel(dest)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
