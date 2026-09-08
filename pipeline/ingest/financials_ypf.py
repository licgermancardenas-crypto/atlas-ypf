"""Dataset 1 — Financieros de YPF S.A. (trimestral y anual), vía SEC EDGAR.

YPF cotiza en NYSE como emisor privado extranjero: el anual va en 20-F y los
resultados trimestrales llegan como exhibits de los 6-K. Este script baja:

  submissions.json    índice completo de presentaciones ante la SEC;
  companyfacts.json   XBRL estructurado (IFRS) — solo tiene el detalle anual del
                      20-F, por eso NO alcanza y hay que bajar igual los 6-K;
  filings/<acc>/      por cada 6-K y 20-F desde --since, el índice de la
                      presentación y sus documentos (el cuerpo y los exhibits).

El parseo de los estados contables no vive acá: este script deja el crudo tal
cual, y la limpieza va en pipeline/transform/.

Nota: la SEC pide un User-Agent identificable y limita a ~10 req/s. Se respeta
con una pausa fija entre pedidos; no bajar esa pausa.
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
)

CIK = "0000904851"  # YPF SOCIEDAD ANONIMA
CIK_SHORT = CIK.lstrip("0")
DEST = RAW / "financials" / "ypf"

SUBMISSIONS_URL = f"https://data.sec.gov/submissions/CIK{CIK}.json"
COMPANYFACTS_URL = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json"
ARCHIVES = f"https://www.sec.gov/Archives/edgar/data/{CIK_SHORT}"

FORMS = ("6-K", "20-F")
SEC_PAUSE = 0.15  # segundos entre pedidos: la SEC corta arriba de ~10 req/s
SKIP_SUFFIXES = (".gif", ".jpg", ".jpeg", ".png", ".zip")


def sec_session():
    return http_session({"Accept": "application/json, text/html;q=0.9"})


def get_json(session, url: str, dest: Path | None = None) -> dict:
    time.sleep(SEC_PAUSE)
    response = session.get(url, timeout=120)
    response.raise_for_status()
    payload = response.json()
    if dest is not None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return payload


def iter_filings(submissions: dict, session) -> list[dict]:
    """Aplana submissions.json (bloque recent + archivos paginados) a dicts."""
    blocks = [submissions["filings"]["recent"]]
    for extra in submissions["filings"].get("files", []):
        blocks.append(get_json(session, f"https://data.sec.gov/submissions/{extra['name']}"))

    filings = []
    for block in blocks:
        for i in range(len(block["accessionNumber"])):
            filings.append(
                {
                    "accession": block["accessionNumber"][i],
                    "form": block["form"][i],
                    "filing_date": block["filingDate"][i],
                    "report_date": block["reportDate"][i],
                    "primary_document": block["primaryDocument"][i],
                    "description": block["primaryDocDescription"][i],
                }
            )
    return filings


def wanted_documents(index: dict, accession_nodash: str, max_bytes: int) -> list[dict]:
    """Documentos de la presentación que valen la pena: cuerpo y exhibits.

    Se descartan imágenes, los índices HTML que genera EDGAR y el .txt de la
    presentación completa, que repite todo lo demás concatenado.
    """
    out = []
    for item in index["directory"]["item"]:
        name = item["name"]
        lower = name.lower()
        if lower.endswith(SKIP_SUFFIXES):
            continue
        if "-index" in lower:
            continue
        if lower.endswith(".txt") and lower.replace("-", "").startswith(accession_nodash):
            continue  # la presentación completa concatenada
        size = int(item.get("size") or 0)
        if max_bytes and size > max_bytes:
            log(f"    salteo {name} ({human(size)} supera el tope)")
            continue
        out.append({"name": name, "size": size})
    return out


def fetch_filing(session, filing: dict, max_bytes: int) -> dict:
    accession_nodash = filing["accession"].replace("-", "")
    folder = DEST / "filings" / filing["accession"]
    index = get_json(
        session,
        f"{ARCHIVES}/{accession_nodash}/index.json",
        dest=folder / "_index.json",
    )

    bajados = []
    for doc in wanted_documents(index, accession_nodash, max_bytes):
        target = folder / doc["name"]
        if target.exists() and doc["size"] and target.stat().st_size == doc["size"]:
            bajados.append(doc["name"])
            continue
        time.sleep(SEC_PAUSE)
        download(f"{ARCHIVES}/{accession_nodash}/{doc['name']}", target, session=session)
        bajados.append(doc["name"])

    meta = dict(filing)
    meta["documents"] = bajados
    (folder / "_meta.json").write_text(
        json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    return meta


def main() -> int:
    parser = base_parser("Baja los financieros de YPF desde SEC EDGAR")
    parser.add_argument(
        "--since",
        default="2021-01-01",
        help="fecha mínima de presentación, YYYY-MM-DD (default: 2021-01-01)",
    )
    parser.add_argument(
        "--max-doc-mb",
        type=float,
        default=30.0,
        help="tope por documento en MB, para no bajar exhibits gigantes (default: 30)",
    )
    parser.add_argument("--limit", type=int, default=0, help="cortar tras N presentaciones (debug)")
    args = parser.parse_args()

    key = "financials/ypf"
    if is_fresh(key, args.force, args.max_age_days):
        log("financials/ypf: fresco en el manifest, se saltea (--force para rebajar)")
        return 0

    session = sec_session()
    max_bytes = int(args.max_doc_mb * 1024 * 1024)

    log("bajando submissions.json y companyfacts.json (XBRL)")
    submissions = get_json(session, SUBMISSIONS_URL, dest=DEST / "submissions.json")
    get_json(session, COMPANYFACTS_URL, dest=DEST / "companyfacts.json")

    filings = [
        f
        for f in iter_filings(submissions, session)
        if f["form"] in FORMS and f["filing_date"] >= args.since
    ]
    filings.sort(key=lambda f: f["filing_date"], reverse=True)
    if args.limit:
        filings = filings[: args.limit]

    log(f"{len(filings)} presentaciones 6-K/20-F desde {args.since}")

    procesadas, docs_total, fallidas = [], 0, []
    for i, filing in enumerate(filings, 1):
        etiqueta = f"{filing['form']} {filing['filing_date']} {filing['accession']}"
        try:
            meta = fetch_filing(session, filing, max_bytes)
        except Exception as exc:  # noqa: BLE001 - una presentación rota no corta el resto
            log(f"  [{i}/{len(filings)}] {etiqueta}: FALLO {exc}")
            fallidas.append({"accession": filing["accession"], "error": str(exc)})
            continue
        procesadas.append(meta)
        docs_total += len(meta["documents"])
        if i % 25 == 0 or i == len(filings):
            log(f"  [{i}/{len(filings)}] {etiqueta} — {docs_total} documentos acumulados")

    (DEST / "filings_index.json").write_text(
        json.dumps(procesadas, indent=1, ensure_ascii=False), encoding="utf-8"
    )

    total_bytes = sum(p.stat().st_size for p in DEST.rglob("*") if p.is_file())
    record(
        key,
        dataset_id=1,
        source="SEC EDGAR",
        cik=CIK,
        forms=list(FORMS),
        since=args.since,
        url=SUBMISSIONS_URL,
        path=rel(DEST),
        rows=len(procesadas),  # filas = presentaciones bajadas
        documents=docs_total,
        failed=fallidas,
        bytes=total_bytes,
    )
    log(f"listo: {len(procesadas)} presentaciones, {docs_total} documentos, {human(total_bytes)}")
    if fallidas:
        log(f"ATENCION: {len(fallidas)} presentaciones fallaron (ver _manifest.json)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
