"""El perfil de vencimientos de la deuda: cuánto vence cada año y a qué tasa.

Por qué importa en este caso: una petrolera argentina no cotiza solo por lo que
gana, sino por cuándo tiene que devolver la plata y a qué costo. Un EBITDA
récord con un muro de vencimientos cerca vale menos que el mismo EBITDA con la
deuda estirada, y eso explica parte del múltiplo al que cotiza la acción.

transform/debt_ypf.py ya deja los instrumentos uno por uno. Acá se agrupan por
año de vencimiento y se calcula el costo promedio ponderado por monto, que es
como se lee un perfil de deuda.

La tasa es el cupón del instrumento, no el rendimiento de mercado: dice lo que
la compañía paga, no lo que el mercado le exigiría hoy por refinanciar.

Entrada: data/processed/debt_ypf.parquet
Salida:  data/processed/deuda_perfil.parquet + .json
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, base_parser, human, log, record, rel, save_json, save_parquet  # noqa: E402

ENTRADA = PROCESSED / "debt_ypf.parquet"
SALIDA = PROCESSED / "deuda_perfil.parquet"
SALIDA_JSON = PROCESSED / "deuda_perfil.json"

RE_TASA = re.compile(r"([\d.]+)\s*%")


def tasa_de(texto: str) -> float | None:
    encontrado = RE_TASA.search(str(texto or ""))
    return float(encontrado.group(1)) if encontrado else None


def main() -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.parse_args()
    if not ENTRADA.exists():
        raise SystemExit("falta debt_ypf.parquet; correr transform/debt_ypf.py")

    deuda = pd.read_parquet(ENTRADA).copy()
    deuda["tasa_pct"] = deuda["tasa"].map(tasa_de)
    deuda["anio"] = pd.to_numeric(deuda["vencimiento"], errors="coerce")
    deuda = deuda.dropna(subset=["anio"])
    deuda["anio"] = deuda["anio"].astype(int)

    def ponderada(grupo: pd.DataFrame) -> float:
        con_tasa = grupo.dropna(subset=["tasa_pct"])
        if con_tasa.empty or con_tasa["total_musd"].sum() == 0:
            return float("nan")
        return float((con_tasa["tasa_pct"] * con_tasa["total_musd"]).sum() / con_tasa["total_musd"].sum())

    filas = []
    for anio, grupo in deuda.groupby("anio"):
        filas.append({
            "anio": int(anio),
            "monto_musd": float(grupo["total_musd"].sum()),
            "corriente_musd": float(grupo["corriente_musd"].sum()),
            "no_corriente_musd": float(grupo["no_corriente_musd"].sum()),
            "tasa_promedio_pct": ponderada(grupo),
            "instrumentos": int(len(grupo)),
            "clases": ", ".join(sorted(str(c) for c in grupo["clase"] if str(c) not in ("-", "None"))),
        })
    perfil = pd.DataFrame(filas).sort_values("anio").reset_index(drop=True)

    total = float(deuda["total_musd"].sum())
    hoy = pd.Timestamp.now().year
    # Vida promedio: años hasta el vencimiento, ponderados por monto.
    vida = float(((deuda["anio"] - hoy).clip(lower=0) * deuda["total_musd"]).sum() / total) if total else float("nan")
    payload = {
        "generado": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "unidades": {"monto_musd": "millones de dólares", "tasa_promedio_pct": "cupón, en % anual"},
        "total_musd": total,
        "tasa_promedio_pct": ponderada(deuda),
        "vida_promedio_anios": vida,
        "instrumentos": int(len(deuda)),
        "primer_vencimiento": int(perfil["anio"].min()),
        "ultimo_vencimiento": int(perfil["anio"].max()),
        "escalera": perfil.to_dict("records"),
        "nota": ("El año es el del vencimiento del capital. Los instrumentos que amortizan en cuotas figuran "
                 "enteros contra su último vencimiento: la escalera es un techo por año, no un calendario de pagos."),
    }
    bytes_parquet = save_parquet(perfil, SALIDA)
    bytes_json = save_json(payload, SALIDA_JSON, indent=2)
    record(
        "transform/deuda-perfil",
        rows=int(len(perfil)),
        bytes=int(bytes_parquet + bytes_json),
        outputs=[rel(SALIDA), rel(SALIDA_JSON)],
        note=f"{perfil['anio'].min()}–{perfil['anio'].max()}; US$ {total:,.0f}M en {len(deuda)} instrumentos",
    )
    log(f"{rel(SALIDA)} ({human(bytes_parquet)}) · US$ {total:,.0f}M · cupón promedio "
        f"{payload['tasa_promedio_pct']:.2f}% · vida {vida:.1f} años")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
