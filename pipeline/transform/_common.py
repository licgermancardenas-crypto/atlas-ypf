"""Utilidades compartidas por los transforms.

Convención del proyecto (ver CLAUDE.md):
- los transforms leen de data/raw/, nunca de la red;
- todo lo que consume el frontend sale a data/processed/ (JSON liviano) y,
  cuando el volumen lo justifica, a Parquet para el resto del pipeline;
- cada corrida deja constancia en data/processed/_manifest.json, igual que la
  ingesta, para saber con qué crudo se generó cada salida.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
MANIFEST = PROCESSED / "_manifest.json"

# 1 m3 = 6.2898 bbl. Para el gas la Secretaría reporta Mm3 (miles de m3) y
# 1 boe ≈ 159 m3 de gas, así que el mismo factor lleva Mm3 -> boe.
M3_TO_BBL = 6.2898
MM3_TO_BOE = 6.2898

# Bounding box de la Argentina continental + plataforma, para detectar filas con
# las coordenadas invertidas (la fuente las trae dadas vuelta en algunos pozos).
LON_RANGE = (-74.0, -53.0)
LAT_RANGE = (-56.0, -21.0)


def base_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--force",
        action="store_true",
        help="regenera las salidas aunque ya existan y el crudo no haya cambiado",
    )
    return parser


def record(key: str, **fields) -> None:
    """Registra (o pisa) una entrada del manifest de processed."""
    manifest = {}
    if MANIFEST.exists():
        try:
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log("manifest de processed ilegible, se reconstruye desde cero")
    entry = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    entry.update(fields)
    manifest[key] = entry
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(MANIFEST)


def save_parquet(df, dest: Path, **kwargs) -> int:
    """Guarda un DataFrame comprimido y devuelve el tamaño en bytes."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dest, index=False, compression="zstd", **kwargs)
    return dest.stat().st_size


def _sin_nan(obj):
    """NaN e infinitos a null.

    JSON no los admite y JSON.parse del browser tampoco: dejarlos pasar como
    `NaN` literal rompe el fetch del frontend en runtime, que es el peor lugar
    para enterarse. Un null es explícito y el chart lo saltea.
    """
    if isinstance(obj, dict):
        return {k: _sin_nan(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sin_nan(v) for v in obj]
    if isinstance(obj, float) and (obj != obj or obj in (float("inf"), float("-inf"))):
        return None
    return obj


def save_json(payload, dest: Path, indent: int | None = None) -> int:
    """Guarda un JSON para el frontend (compacto por default) y devuelve bytes."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    separators = None if indent else (",", ":")
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_text(
        json.dumps(_sin_nan(payload), ensure_ascii=False, indent=indent,
                   separators=separators, allow_nan=False),
        encoding="utf-8",
    )
    tmp.replace(dest)
    return dest.stat().st_size


def serie_yahoo(path: Path, nombre: str, campo: str = "close"):
    """Serie diaria de un JSON crudo de Yahoo, indexada por fecha (sin huso).

    La usan todos los transforms que cruzan mercado, así que vive acá y no
    duplicada en cada uno.
    """
    import pandas as pd  # local: _common lo usan scripts que no siempre traen pandas

    payload = json.loads(path.read_text(encoding="utf-8"))
    resultado = payload["chart"]["result"][0]
    fechas = pd.to_datetime(resultado["timestamp"], unit="s", utc=True).tz_localize(None).normalize()
    valores = resultado["indicators"]["quote"][0][campo]
    serie = pd.Series(valores, index=fechas, name=nombre, dtype="float64")
    return serie[~serie.index.duplicated(keep="last")].dropna()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def human(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}GB"


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)
