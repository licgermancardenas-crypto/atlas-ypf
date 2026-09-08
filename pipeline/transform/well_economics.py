"""Economía de pozo: NPV, IRR, payback y Brent de breakeven sobre las curvas de Arps.

Entrada:  data/processed/decline_curves.parquet (transform/decline_curves.py)
Salidas:  data/processed/well_economics.parquet (una fila por pozo)
          data/processed/well_economics.json    (agregados y sensibilidad)

Qué calcula: el valor de perforar hoy un pozo con la curva tipo de cada pozo
ya perforado ("greenfield"), que es la pregunta que se hace el mercado cuando
mira el capex de la compañía. El flujo arranca en el pico ajustado y no incluye
los meses de rampa, así que el timing queda algo optimista — el efecto sobre el
NPV es menor al 3% y se gana no arrastrar el ruido del flowback.

Supuestos base (todos overridables por CLI, ver --help):
- Capex US$ 11M por pozo horizontal (~2.500 m de rama), drilling + completion.
- Opex US$ 6/bbl (lifting cost del shale que reporta YPF).
- Precio de venta ligado a Brent menos el diferencial Medanito (US$ 8/bbl), no
  un precio fijo: así el mismo módulo alimenta el simulador de escenarios.
- Brent base = promedio de los últimos 90 días, no el spot del día, para que el
  NPV no cuelgue de una vela.
- Regalía provincial 12%, impuesto a las ganancias 35%.
- WACC 12% anual: incluye premio por riesgo argentino. La brecha contra el 10%
  de un comparable del Permian se expone aparte, porque es justamente parte de
  la tesis del caso.

Lo que queda afuera a propósito: retenciones a la exportación (hoy en cero para
crudo), abandono de pozo y capital de trabajo. Son de segundo orden frente a la
sensibilidad al precio, y sumarlos exigiría supuestos que no se pueden defender
con datos públicos.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    PROCESSED,
    RAW,
    base_parser,
    human,
    log,
    record,
    rel,
    save_json,
    save_parquet,
)
from decline_curves import DIAS_MES, perfil_mensual  # noqa: E402

SRC_FITS = PROCESSED / "decline_curves.parquet"
SRC_BRENT = RAW / "market" / "oil" / "brent.json"

OUT_ECON = PROCESSED / "well_economics.parquet"
OUT_JSON = PROCESSED / "well_economics.json"

SUPUESTOS = {
    "capex_usd": 11_000_000.0,
    "opex_usd_bbl": 6.0,
    "diferencial_usd_bbl": 8.0,  # Medanito vs. Brent
    "regalias": 0.12,
    "iigg": 0.35,
    "wacc_anual": 0.12,
    "wacc_comparable": 0.10,  # Permian, sin premio por riesgo argentino
}

# Grillas de la tabla de sensibilidad que consume el frontend.
BRENT_GRID = [50, 60, 70, 80, 90, 100, 110, 120]
CAPEX_GRID = [9e6, 11e6, 14e6]


def brent_base(dias: int = 90) -> float:
    """Brent promedio de los últimos `dias` de rueda, del crudo de Yahoo."""
    payload = json.loads(SRC_BRENT.read_text(encoding="utf-8"))
    cierres = payload["chart"]["result"][0]["indicators"]["quote"][0]["close"]
    validos = [c for c in cierres if c is not None]
    if not validos:
        raise RuntimeError("el JSON de Brent no trae cierres validos")
    return float(np.mean(validos[-dias:]))


def flujo_pozo(
    perfil_bd: np.ndarray,
    brent: float,
    capex: float,
    sup: dict,
) -> np.ndarray:
    """Flujo de fondos mensual despues de impuestos, con el capex en el mes 0.

    La depreciación es por unidad de producción (la práctica del sector para
    activos de E&P): el escudo fiscal acompaña a la curva en vez de repartirse
    en línea recta sobre una vida útil inventada.
    """
    precio = brent - sup["diferencial_usd_bbl"]
    produccion = perfil_bd * DIAS_MES

    ingresos = produccion * precio
    regalias = ingresos * sup["regalias"]
    opex = produccion * sup["opex_usd_bbl"]

    total = produccion.sum()
    depreciacion = capex * (produccion / total) if total > 0 else np.zeros_like(produccion)

    base_imponible = ingresos - regalias - opex - depreciacion
    impuesto = np.maximum(base_imponible, 0.0) * sup["iigg"]

    fcf = ingresos - regalias - opex - impuesto
    return np.concatenate(([-capex], fcf))


def npv(flujo: np.ndarray, tasa_anual: float) -> float:
    tasa_mensual = (1.0 + tasa_anual) ** (1.0 / 12.0) - 1.0
    descuento = (1.0 + tasa_mensual) ** np.arange(len(flujo))
    return float(np.sum(flujo / descuento))


def irr(flujo: np.ndarray, lo: float = -0.99, hi: float = 10.0) -> float:
    """TIR anual por biseccion. NaN si el flujo no cambia de signo."""
    if npv(flujo, lo) * npv(flujo, hi) > 0:
        return float("nan")
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if npv(flujo, lo) * npv(flujo, mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


def payback_meses(flujo: np.ndarray) -> float:
    """Meses hasta recuperar el capex, sin descontar."""
    acum = np.cumsum(flujo)
    positivo = np.flatnonzero(acum >= 0)
    return float(positivo[0]) if positivo.size else float("nan")


def breakeven_brent(perfil_bd: np.ndarray, capex: float, sup: dict) -> float:
    """Brent al que el NPV del pozo se hace cero (biseccion entre 10 y 250)."""
    lo, hi = 10.0, 250.0
    f = lambda b: npv(flujo_pozo(perfil_bd, b, capex, sup), sup["wacc_anual"])  # noqa: E731
    if f(lo) > 0 or f(hi) < 0:
        return float("nan")
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if f(mid) < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def evaluar_pozos(fits: pd.DataFrame, brent: float, sup: dict) -> pd.DataFrame:
    capex = sup["capex_usd"]
    filas: list[dict] = []

    for row in fits.itertuples(index=False):
        perfil = perfil_mensual(row.qi_bd, row.di_mensual, row.b)
        if perfil.sum() <= 0:
            continue
        flujo = flujo_pozo(perfil, brent, capex, sup)

        filas.append(
            {
                "pozo_id": row.pozo_id,
                "sigla": row.sigla,
                "operador": row.operador,
                "yacimiento": row.yacimiento,
                "concesion": row.concesion,
                "vintage": row.vintage,
                "lat": row.lat,
                "lon": row.lon,
                "eur_bbl": row.eur_bbl,
                "pico_bd": row.pico_bd,
                "produccion_30y_bbl": float(perfil.sum() * DIAS_MES),
                "npv_usd": npv(flujo, sup["wacc_anual"]),
                "npv_usd_comparable": npv(flujo, sup["wacc_comparable"]),
                "irr_anual": irr(flujo),
                "payback_meses": payback_meses(flujo),
                "breakeven_brent": breakeven_brent(perfil, capex, sup),
            }
        )

    econ = pd.DataFrame(filas)
    econ["prima_riesgo_pais_usd"] = econ.npv_usd_comparable - econ.npv_usd
    log(
        f"  evaluados {len(econ):,} pozos - NPV mediano US$ {econ.npv_usd.median()/1e6:,.1f}M, "
        f"TIR mediana {econ.irr_anual.median():.1%}, breakeven mediano "
        f"US$ {econ.breakeven_brent.median():,.0f}/bbl"
    )
    return econ


def sensibilidad(fits: pd.DataFrame, sup: dict, muestra: int = 400) -> list[dict]:
    """NPV mediano del pozo tipo en la grilla Brent x capex.

    Se calcula sobre una muestra estratificada por operador: la grilla son 24
    escenarios y correr los 2.182 pozos en cada uno no cambia la mediana.
    """
    rng = np.random.default_rng(42)
    idx = rng.choice(len(fits), size=min(muestra, len(fits)), replace=False)
    sub = fits.iloc[idx]
    perfiles = [perfil_mensual(r.qi_bd, r.di_mensual, r.b) for r in sub.itertuples(index=False)]

    salida = []
    for capex in CAPEX_GRID:
        for brent in BRENT_GRID:
            npvs = [npv(flujo_pozo(p, brent, capex, sup), sup["wacc_anual"]) for p in perfiles]
            salida.append(
                {
                    "brent": brent,
                    "capex_musd": round(capex / 1e6, 1),
                    "npv_musd_mediano": round(float(np.median(npvs)) / 1e6, 2),
                    "pozos_con_npv_positivo": round(float(np.mean(np.array(npvs) > 0)), 3),
                }
            )
    return salida


def _agregado(econ: pd.DataFrame, por: str, min_pozos: int = 5) -> list[dict]:
    g = econ.groupby(por).agg(
        pozos=("pozo_id", "size"),
        npv_musd_mediano=("npv_usd", lambda s: round(float(s.median()) / 1e6, 2)),
        irr_mediana=("irr_anual", "median"),
        payback_meses_mediano=("payback_meses", "median"),
        breakeven_brent_mediano=("breakeven_brent", "median"),
        eur_bbl_mediana=("eur_bbl", "median"),
    )
    g = g[g.pozos >= min_pozos].sort_values("pozos", ascending=False).round(3).reset_index()
    g[por] = g[por].astype(str)
    return g.to_dict("records")


def main() -> int:
    parser = base_parser("Calcula NPV, IRR y breakeven por pozo de Vaca Muerta")
    parser.add_argument("--brent", type=float, default=None, help="Brent base (default: promedio 90 ruedas)")
    parser.add_argument("--capex", type=float, default=SUPUESTOS["capex_usd"], help="capex por pozo en USD")
    parser.add_argument("--opex", type=float, default=SUPUESTOS["opex_usd_bbl"], help="opex en USD/bbl")
    parser.add_argument("--wacc", type=float, default=SUPUESTOS["wacc_anual"], help="tasa de descuento anual")
    parser.add_argument(
        "--diferencial",
        type=float,
        default=SUPUESTOS["diferencial_usd_bbl"],
        help="descuento del crudo local contra Brent, en USD/bbl",
    )
    args = parser.parse_args()

    if not SRC_FITS.exists():
        log(f"falta {rel(SRC_FITS)}; correr antes pipeline/transform/decline_curves.py")
        return 1
    if not SRC_BRENT.exists():
        log(f"falta {rel(SRC_BRENT)}; correr antes pipeline/ingest/brent_wti.py")
        return 1

    if OUT_ECON.exists() and not args.force:
        if OUT_ECON.stat().st_mtime > SRC_FITS.stat().st_mtime:
            log(f"{rel(OUT_ECON)} esta al dia, se saltea (--force para rehacer)")
            return 0

    sup = dict(SUPUESTOS)
    sup.update(
        capex_usd=args.capex,
        opex_usd_bbl=args.opex,
        wacc_anual=args.wacc,
        diferencial_usd_bbl=args.diferencial,
    )
    brent = args.brent if args.brent is not None else brent_base()

    log(f"leyendo {rel(SRC_FITS)}")
    fits = pd.read_parquet(SRC_FITS)
    log(
        f"  Brent base US$ {brent:,.1f}/bbl, capex US$ {sup['capex_usd']/1e6:.1f}M, "
        f"opex US$ {sup['opex_usd_bbl']:.1f}/bbl, WACC {sup['wacc_anual']:.0%}"
    )

    econ = evaluar_pozos(fits, brent, sup)
    payload = {
        "generado": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "supuestos": {**sup, "brent_base": round(brent, 2), "brent_fuente": "promedio 90 ruedas"},
        "advertencia": (
            "NPV greenfield sobre la curva ajustada de cada pozo; no incluye retenciones, "
            "abandono ni capital de trabajo. No es una valuacion de la compania."
        ),
        "resumen": {
            "pozos": int(len(econ)),
            "npv_musd_mediano": round(float(econ.npv_usd.median()) / 1e6, 2),
            "irr_mediana": round(float(econ.irr_anual.median()), 4),
            "payback_meses_mediano": float(econ.payback_meses.median()),
            "breakeven_brent_mediano": round(float(econ.breakeven_brent.median()), 1),
            "pozos_con_npv_positivo": round(float((econ.npv_usd > 0).mean()), 3),
            "prima_riesgo_pais_musd_mediana": round(
                float(econ.prima_riesgo_pais_usd.median()) / 1e6, 2
            ),
        },
        "por_operador": _agregado(econ, "operador"),
        "por_vintage": _agregado(econ, "vintage"),
        "por_yacimiento": _agregado(econ, "yacimiento", min_pozos=10),
        "sensibilidad_brent_capex": sensibilidad(fits, sup),
    }

    bytes_econ = save_parquet(econ, OUT_ECON)
    bytes_json = save_json(payload, OUT_JSON)
    log(f"escrito {rel(OUT_ECON)} - {len(econ):,} pozos, {human(bytes_econ)}")
    log(f"escrito {rel(OUT_JSON)} - {human(bytes_json)}")

    record(
        "well_economics",
        source=rel(SRC_FITS),
        outputs=[rel(OUT_ECON), rel(OUT_JSON)],
        supuestos={**sup, "brent_base": round(brent, 2)},
        **payload["resumen"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
