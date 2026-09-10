"""Dataset 14 — Financieros de los comparables: Vista Energy y Pampa Energía.

Fuente: SEC EDGAR. Los dos cotizan en NYSE como emisores privados extranjeros,
presentan 20-F y —a diferencia de YPF— tienen el XBRL de esos 20-F tagueado en
la taxonomía IFRS, así que el anual sale estructurado y no hay que parsear HTML.

Para qué entra al análisis: una valuación por múltiplos contra la mediana del
propio papel es media valuación. Falta contra quién, y el brief define a esos
dos como los únicos comparables con disclosure equiparable. Vista es shale puro
—sirve para aislar cuánto del múltiplo de YPF es Vaca Muerta— y Pampa mezcla
upstream con generación eléctrica, que es el otro extremo.

Qué baja, por compañía:
  companyfacts.json   todos los hechos XBRL del emisor (anual, en dólares);
  20-F.htm            la portada del último 20-F, de donde salen las acciones
                      en circulación y cuántas representa cada ADS. Ese ratio
                      no está en el XBRL y sin él la capitalización bursátil
                      sale mal por un factor de 25.

Advertencia: el XBRL trae el ejercicio completo, no el trimestre. La serie
trimestral de estos dos no existe en formato estructurado, así que la
comparación es anual.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    RAW,
    base_parser,
    download,
    human,
    http_session,
    is_fresh,
    log,
    record,
    rel,
    save_json,
)

DEST = RAW / "financials" / "peers"
KEY = "financials/peers"
SEC_PAUSE = 0.15

COMPARABLES = {
    "VIST": {"cik": "0001762506", "nombre": "Vista Energy, S.A.B. de C.V."},
    "PAM": {"cik": "0001469395", "nombre": "Pampa Energía S.A."},
}


def get_json(session, url: str, dest: Path | None = None) -> dict:
    time.sleep(SEC_PAUSE)
    response = session.get(url, timeout=120)
    response.raise_for_status()
    payload = response.json()
    if dest is not None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return payload


def ultimo_20f(session, cik: str) -> dict | None:
    """La presentación 20-F más reciente del emisor."""
    submissions = get_json(session, f"https://data.sec.gov/submissions/CIK{cik}.json")
    recientes = submissions["filings"]["recent"]
    for i in range(len(recientes["form"])):
        if recientes["form"][i] == "20-F":
            return {
                "accession": recientes["accessionNumber"][i],
                "documento": recientes["primaryDocument"][i],
                "presentado": recientes["filingDate"][i],
                "periodo": recientes["reportDate"][i],
            }
    return None


def main() -> int:
    parser = base_parser("Baja los financieros de Vista y Pampa desde SEC EDGAR")
    args = parser.parse_args()

    if is_fresh(KEY, args.force, args.max_age_days):
        log("peers: fresco en el manifest, se saltea (--force para rebajar)")
        return 0

    session = http_session({"Accept": "application/json, text/html;q=0.9"})
    total_bytes = 0
    resumen = []

    for ticker, ficha in COMPARABLES.items():
        carpeta = DEST / ticker
        cik = ficha["cik"]

        hechos = get_json(
            session,
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
            dest=carpeta / "companyfacts.json",
        )
        conceptos = len(hechos.get("facts", {}).get("ifrs-full", {}))

        filing = ultimo_20f(session, cik)
        documento = None
        if filing:
            sin_guiones = filing["accession"].replace("-", "")
            url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/"
                f"{sin_guiones}/{filing['documento']}"
            )
            documento = carpeta / "20-F.htm"
            time.sleep(SEC_PAUSE)
            download(url, documento, session=session)
            (carpeta / "_meta.json").write_text(
                json.dumps({"ticker": ticker, **ficha, **filing, "url": url}, indent=1),
                encoding="utf-8",
            )

        bytes_ticker = sum(f.stat().st_size for f in carpeta.iterdir() if f.is_file())
        total_bytes += bytes_ticker
        resumen.append(f"{ticker}: {conceptos} conceptos IFRS, 20-F de {filing['periodo'] if filing else '?'}")
        log(f"{ticker}: {conceptos} conceptos, {human(bytes_ticker)} -> {rel(carpeta)}")

    record(
        KEY,
        dataset_id=14,
        source="SEC EDGAR (XBRL companyfacts y 20-F)",
        emisores=list(COMPARABLES),
        url="https://data.sec.gov/api/xbrl/companyfacts/",
        path=rel(DEST),
        bytes=total_bytes,
        note="; ".join(resumen),
    )
    log(f"peers: {len(COMPARABLES)} emisores, {human(total_bytes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
