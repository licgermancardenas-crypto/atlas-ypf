"""Utilidades compartidas por los scripts de ingesta.

Convención del proyecto (ver CLAUDE.md y la skill fetch-datasets):
- un script por fuente, nunca mezclados;
- cada script baja el crudo tal cual lo devuelve la fuente a data/raw/;
- cada descarga se loguea en data/raw/_manifest.json con fecha y nº de filas;
- si el dataset tiene menos de MAX_AGE_DAYS según el manifest, no se vuelve a
  bajar salvo que se pase --force.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
MANIFEST = RAW / "_manifest.json"

MAX_AGE_DAYS = 7
CHUNK = 1 << 20  # 1 MiB: la RAM de esta máquina es escasa, nunca cargar entero

# La SEC exige un User-Agent identificable; el resto de las fuentes lo toleran.
USER_AGENT = os.environ.get(
    "ATLAS_YPF_UA", "ATLAS-YPF research (nestorrojascastaneda@gmail.com)"
)


# --------------------------------------------------------------------------- #
# Manifest
# --------------------------------------------------------------------------- #
def load_manifest() -> dict:
    if not MANIFEST.exists():
        return {}
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log("manifest ilegible, se reconstruye desde cero")
        return {}


def save_manifest(manifest: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(MANIFEST)


def age_days(key: str) -> float | None:
    """Antigüedad en días de la última descarga registrada, o None si no hay."""
    entry = load_manifest().get(key)
    if not entry or not entry.get("downloaded_at"):
        return None
    try:
        ts = datetime.fromisoformat(entry["downloaded_at"])
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).total_seconds() / 86400


def is_fresh(key: str, force: bool = False, max_age_days: int = MAX_AGE_DAYS) -> bool:
    """True si conviene saltear la descarga (dataset reciente y sin --force)."""
    if force:
        return False
    age = age_days(key)
    if age is None:
        return False
    entry = load_manifest().get(key, {})
    path = entry.get("path")
    if path and not (ROOT / path).exists():
        return False  # el manifest miente: el archivo no está
    return age < max_age_days


def record(key: str, **fields) -> None:
    """Registra (o pisa) una entrada del manifest y lo persiste enseguida."""
    manifest = load_manifest()
    entry = {"downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    entry.update(fields)
    manifest[key] = entry
    save_manifest(manifest)


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def http_session(extra_headers: dict | None = None) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"})
    if extra_headers:
        session.headers.update(extra_headers)
    return session


def download(
    url: str,
    dest: Path,
    session: requests.Session | None = None,
    timeout: int = 180,
    retries: int = 3,
) -> Path:
    """Baja url a dest por streaming (nunca entero en memoria).

    Escribe a un .part y recién al final renombra, para que una descarga cortada
    no deje un archivo truncado haciéndose pasar por bueno.
    """
    session = session or http_session()
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with session.get(url, stream=True, timeout=timeout) as response:
                response.raise_for_status()
                written = 0
                with open(part, "wb") as fh:
                    for chunk in response.iter_content(CHUNK):
                        if chunk:
                            fh.write(chunk)
                            written += len(chunk)
            part.replace(dest)
            return dest
        except Exception as exc:  # noqa: BLE001 - se reintenta y si no, se propaga
            last_error = exc
            part.unlink(missing_ok=True)
            if attempt < retries:
                wait = 2 ** attempt
                log(f"  fallo ({exc.__class__.__name__}), reintento {attempt}/{retries - 1} en {wait}s")
                time.sleep(wait)

    raise RuntimeError(f"no se pudo bajar {url}: {last_error}")


# --------------------------------------------------------------------------- #
# Yahoo Finance (misma fuente para stock_prices.py y brent_wti.py)
# --------------------------------------------------------------------------- #
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# Yahoo devuelve 429 a los clientes que no parecen un navegador.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)


def yahoo_session() -> requests.Session:
    return http_session({"User-Agent": BROWSER_UA, "Accept": "application/json"})


def yahoo_chart(session: requests.Session, symbol: str, interval: str = "1d") -> dict:
    """Serie histórica completa de un ticker. Devuelve el JSON crudo de Yahoo."""
    params = {
        "period1": 0,
        "period2": int(time.time()),
        "interval": interval,
        "events": "div,splits",
        "includeAdjustedClose": "true",
    }
    response = session.get(YAHOO_CHART.format(symbol=symbol), params=params, timeout=120)
    response.raise_for_status()
    payload = response.json()

    error = payload.get("chart", {}).get("error")
    if error:
        raise RuntimeError(f"Yahoo devolvio error para {symbol}: {error}")
    if not payload.get("chart", {}).get("result"):
        raise RuntimeError(f"Yahoo no devolvio serie para {symbol}")
    return payload


def save_json(payload: dict, dest: Path) -> int:
    """Guarda un JSON crudo compacto y devuelve su tamaño en bytes."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return dest.stat().st_size


# --------------------------------------------------------------------------- #
# Inspección de archivos ya bajados
# --------------------------------------------------------------------------- #
def count_csv_rows(path: Path, has_header: bool = True) -> int:
    """Cuenta filas de un CSV por streaming, sin abrirlo con pandas."""
    lines = 0
    tail = b""
    with open(path, "rb") as fh:
        while chunk := fh.read(CHUNK):
            lines += chunk.count(b"\n")
            tail = chunk[-1:]
    if tail and tail != b"\n":  # última línea sin salto final
        lines += 1
    return max(lines - 1, 0) if has_header else lines


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    """Ruta relativa a la raíz del repo, con / como separador."""
    return path.resolve().relative_to(ROOT).as_posix()


def human(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}GB"


# --------------------------------------------------------------------------- #
# CLI / logging
# --------------------------------------------------------------------------- #
def base_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--force",
        action="store_true",
        help=f"rebaja aunque el manifest diga que tiene menos de {MAX_AGE_DAYS} días",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=MAX_AGE_DAYS,
        help=f"umbral de frescura en días (default: {MAX_AGE_DAYS})",
    )
    return parser


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)
