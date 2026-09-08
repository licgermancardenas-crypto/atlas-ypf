"""Fitea curvas de declive de Arps por pozo sobre el panel pozo-mes.

Entrada:  data/processed/production_wells.parquet (transform/production_wells.py)
Salidas:  data/processed/decline_curves.parquet   (parámetros y EUR por pozo)
          data/processed/decline_type_curves.json (curvas tipo para el frontend)

Método (el estándar de la industria, con los recaudos que pide este dataset):

1. El caudal se calcula sobre días efectivos (`petroleo_bbl / dias_efectivos`),
   no sobre días calendario: un mes con el pozo parado por mantenimiento no es
   declive, y computarlo como tal ensucia el ajuste.
2. El ajuste arranca en el mes pico, no en el primer mes. Los pozos de Vaca
   Muerta tardan varios meses en llegar al plateau (flowback, puesta en marcha
   del sistema de evacuación); Arps describe el declive, no la rampa.
3. Se fitea en escala logarítmica. El caudal recorre dos órdenes de magnitud
   entre el pico y la cola, y en escala lineal el ajuste queda dominado por los
   primeros meses.
4. Arps hiperbólica q(t) = qi / (1 + b*Di*t)^(1/b), con b acotado a [0, 2]:
   b > 2 da reservas infinitas al integrar, que es el error clásico de
   sobreestimación de EUR en shale.
5. Para la EUR la hiperbólica no se integra sola: casi un cuarto de los pozos
   ajusta contra el techo b = 2, y con b alto la cola nunca termina de caer. Se
   usa Arps modificada — hiperbólica hasta que el declive nominal baja a
   D_MIN_ANUAL, exponencial de ahí en adelante — y se corta en el límite
   económico (Q_ECONOMICO_BD). Sin esos dos frenos la EUR se va al doble.

Las EUR son estimaciones sobre la curva ajustada a 30 años; no son reservas
certificadas y no reemplazan al reporte de reservas de la compañía.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    PROCESSED,
    base_parser,
    human,
    log,
    record,
    rel,
    save_json,
    save_parquet,
)

SRC_PANEL = PROCESSED / "production_wells.parquet"
OUT_FITS = PROCESSED / "decline_curves.parquet"
OUT_TYPE = PROCESSED / "decline_type_curves.json"

MIN_MESES_POST_PICO = 6  # menos que esto no define una curva, define ruido
B_MAX = 2.0
HORIZONTE_MESES = 360  # 30 años, el horizonte usual para EUR de shale
DIAS_MES = 30.4375

# Declive terminal: cuando el nominal de la hiperbólica cae a este valor, la
# curva pasa a exponencial. 8% anual efectivo es el supuesto habitual en shale.
D_MIN_ANUAL = 0.08
D_MIN_MENSUAL = -np.log(1.0 - D_MIN_ANUAL) / 12.0

# Límite económico: por debajo de este caudal el pozo no paga ni el opex y se
# abandona, así que la cola no cuenta como reserva.
Q_ECONOMICO_BD = 10.0


def arps(t: np.ndarray, qi: float, di: float, b: float) -> np.ndarray:
    """Caudal hiperbólico de Arps. b -> 0 colapsa al exponencial."""
    if b < 1e-6:
        return qi * np.exp(-di * t)
    return qi / np.power(1.0 + b * di * t, 1.0 / b)


def _fit_pozo(t: np.ndarray, q: np.ndarray) -> tuple[float, float, float, float] | None:
    """Devuelve (qi, Di mensual, b, R2) o None si el ajuste no converge."""
    q_pico = float(q[0])
    p0 = (q_pico, 0.10, 1.0)
    bounds = ([q_pico * 0.5, 1e-4, 0.0], [q_pico * 2.0, 1.0, B_MAX])

    def modelo_log(t_, qi, di, b):
        return np.log(np.maximum(arps(t_, qi, di, b), 1e-9))

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            popt, _ = curve_fit(modelo_log, t, np.log(q), p0=p0, bounds=bounds, maxfev=20000)
        except (RuntimeError, ValueError):
            return None

    pred = arps(t, *popt)
    ss_res = float(np.sum((q - pred) ** 2))
    ss_tot = float(np.sum((q - q.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
    return float(popt[0]), float(popt[1]), float(popt[2]), r2


def perfil_mensual(qi: float, di: float, b: float, meses: int = HORIZONTE_MESES) -> np.ndarray:
    """Perfil de caudal (bbl/d por mes) con Arps modificada y límite económico.

    Es la curva que después consume well_economics.py para armar el flujo de
    fondos, por eso devuelve el perfil entero y no solo su integral.
    """
    t = np.arange(0, meses, dtype=float)
    q = arps(t, qi, di, b)

    if b > 1e-6 and di > D_MIN_MENSUAL:
        # D(t) = di / (1 + b*di*t); se despeja el t donde D(t) = D_MIN_MENSUAL.
        t_switch = (di / D_MIN_MENSUAL - 1.0) / (b * di)
        if t_switch < meses:
            cola = t >= t_switch
            q_switch = float(arps(np.array([t_switch]), qi, di, b)[0])
            q[cola] = q_switch * np.exp(-D_MIN_MENSUAL * (t[cola] - t_switch))

    # Una vez que cae bajo el límite económico el pozo se abandona: no vuelve.
    bajo_limite = np.flatnonzero(q < Q_ECONOMICO_BD)
    if bajo_limite.size:
        q[bajo_limite[0] :] = 0.0
    return q


def _eur(qi: float, di: float, b: float, acum_previo: float) -> tuple[float, int]:
    """(EUR, meses de vida remanente): lo ya producido + la integral del perfil."""
    q = perfil_mensual(qi, di, b)
    return acum_previo + float(q.sum() * DIAS_MES), int(np.count_nonzero(q))


def fitear_pozos(panel: pd.DataFrame) -> pd.DataFrame:
    """Un ajuste por pozo de petróleo de Vaca Muerta con historia suficiente."""
    oil = panel[
        panel.es_vaca_muerta
        & (panel.tipo_pozo == "Petrolífero")
        & (panel.dias_efectivos > 0)
        & (panel.petroleo_bbl > 0)
        & panel.mes_prod.notna()
    ].copy()
    oil["caudal_bd"] = oil.petroleo_bbl / oil.dias_efectivos

    log(f"  {oil.pozo_id.nunique():,} pozos de petróleo de Vaca Muerta con producción")

    filas: list[dict] = []
    sin_convergencia = 0
    for pozo_id, g in oil.groupby("pozo_id", sort=False):
        g = g.sort_values("mes_prod")
        idx_pico = int(g.caudal_bd.values.argmax())
        post = g.iloc[idx_pico:]
        if len(post) < MIN_MESES_POST_PICO:
            continue

        t = (post.mes_prod.astype(float) - post.mes_prod.iloc[0]).to_numpy()
        q = post.caudal_bd.to_numpy(dtype=float)
        ajuste = _fit_pozo(t, q)
        if ajuste is None:
            sin_convergencia += 1
            continue
        qi, di, b, r2 = ajuste

        ultimo = g.iloc[-1]
        acum = float(g.petroleo_bbl.sum())
        # Declive efectivo del primer año: es la forma en que la industria
        # reporta el declive, y la que se puede comparar entre cuencas.
        d_ef_anual = 1.0 - float(arps(np.array([12.0]), qi, di, b)[0]) / qi
        eur, meses_remanentes = _eur(qi, di, b, acum)

        filas.append(
            {
                "pozo_id": int(pozo_id),
                "sigla": ultimo.sigla,
                "operador": ultimo.operador,
                "yacimiento": ultimo.yacimiento,
                "concesion": ultimo.concesion,
                "vintage": int(g.primera_prod.iloc[0].year),
                "lat": ultimo.lat,
                "lon": ultimo.lon,
                "meses_historia": int(len(g)),
                "meses_ajustados": int(len(post)),
                "mes_pico": int(post.mes_prod.iloc[0]),
                "pico_bd": float(q[0]),
                "qi_bd": qi,
                "di_mensual": di,
                "b": b,
                "declive_ef_anual": d_ef_anual,
                "r2": r2,
                "acum_bbl": acum,
                "eur_bbl": eur,
                "meses_remanentes": meses_remanentes,
            }
        )

    fits = pd.DataFrame(filas)
    if sin_convergencia:
        log(f"  ajustes que no convergieron, descartados: {sin_convergencia}")
    log(f"  ajustados: {len(fits):,} pozos (R2 mediano {fits.r2.median():.3f})")
    return fits


def curvas_tipo(panel: pd.DataFrame, por: str, top: int | None = None) -> list[dict]:
    """Curva tipo: caudal mediano por mes de producción dentro de cada grupo.

    La mediana y no el promedio: un puñado de pozos excepcionales corre el
    promedio hacia arriba y deja de describir al pozo típico, que es lo que
    interesa para comparar cohortes u operadores.
    """
    oil = panel[
        panel.es_vaca_muerta
        & (panel.tipo_pozo == "Petrolífero")
        & (panel.dias_efectivos > 0)
        & panel.mes_prod.between(1, 60)
    ].copy()
    oil["caudal_bd"] = oil.petroleo_bbl / oil.dias_efectivos

    if top is not None:
        ranking = oil.groupby(por).pozo_id.nunique().nlargest(top).index
        oil = oil[oil[por].isin(ranking)]

    g = (
        oil.groupby([por, "mes_prod"], observed=True)
        .agg(caudal_bd=("caudal_bd", "median"), pozos=("pozo_id", "nunique"))
        .reset_index()
    )
    # Con menos de 5 pozos la mediana deja de ser una curva tipo y pasa a ser
    # el pozo de alguien: se corta ahí.
    g = g[g.pozos >= 5]
    g["caudal_bd"] = g.caudal_bd.round(1)
    g[por] = g[por].astype(str)
    g["mes_prod"] = g.mes_prod.astype(int)
    return g.to_dict("records")


def construir_type_curves(panel: pd.DataFrame, fits: pd.DataFrame) -> dict:
    vintage = panel.assign(vintage=panel.primera_prod.dt.year)
    resumen_op = (
        fits.groupby("operador")
        .agg(
            pozos=("pozo_id", "size"),
            pico_bd_mediano=("pico_bd", "median"),
            b_mediano=("b", "median"),
            declive_ef_anual_mediano=("declive_ef_anual", "median"),
            eur_bbl_mediano=("eur_bbl", "median"),
        )
        .sort_values("pozos", ascending=False)
        .round(3)
        .reset_index()
    )
    resumen_vintage = (
        fits.groupby("vintage")
        .agg(
            pozos=("pozo_id", "size"),
            pico_bd_mediano=("pico_bd", "median"),
            b_mediano=("b", "median"),
            declive_ef_anual_mediano=("declive_ef_anual", "median"),
            eur_bbl_mediano=("eur_bbl", "median"),
        )
        .round(3)
        .reset_index()
    )

    return {
        "generado": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metodo": (
            "Arps hiperbolica ajustada desde el mes pico en escala logaritmica, sobre "
            "caudal por dia efectivo. EUR = acumulada + integral a 30 anios de la Arps "
            f"modificada (declive terminal {D_MIN_ANUAL:.0%} anual, limite economico "
            f"{Q_ECONOMICO_BD:.0f} bbl/d)."
        ),
        "unidades": {"caudal_bd": "bbl/d", "eur_bbl": "bbl", "declive_ef_anual": "fraccion"},
        "advertencia": "EUR estimada sobre la curva ajustada; no son reservas certificadas.",
        "pozos_ajustados": int(len(fits)),
        "por_operador": resumen_op.to_dict("records"),
        "por_vintage": resumen_vintage.to_dict("records"),
        "curva_tipo_por_vintage": curvas_tipo(vintage, "vintage"),
        "curva_tipo_por_operador": curvas_tipo(panel, "operador", top=6),
    }


def main() -> int:
    args = base_parser("Fitea curvas de Arps por pozo de Vaca Muerta").parse_args()

    if not SRC_PANEL.exists():
        log(f"falta {rel(SRC_PANEL)}; correr antes pipeline/transform/production_wells.py")
        return 1

    if OUT_FITS.exists() and not args.force:
        if OUT_FITS.stat().st_mtime > SRC_PANEL.stat().st_mtime:
            log(f"{rel(OUT_FITS)} esta al dia, se saltea (--force para rehacer)")
            return 0

    log(f"leyendo {rel(SRC_PANEL)}")
    panel = pd.read_parquet(SRC_PANEL)

    fits = fitear_pozos(panel)
    if fits.empty:
        log("ningun pozo con historia suficiente para ajustar")
        return 1

    payload = construir_type_curves(panel, fits)

    bytes_fits = save_parquet(fits, OUT_FITS)
    bytes_type = save_json(payload, OUT_TYPE)
    log(f"escrito {rel(OUT_FITS)} - {len(fits):,} pozos, {human(bytes_fits)}")
    log(f"escrito {rel(OUT_TYPE)} - {human(bytes_type)}")

    record(
        "decline_curves",
        source=rel(SRC_PANEL),
        outputs=[rel(OUT_FITS), rel(OUT_TYPE)],
        pozos_ajustados=int(len(fits)),
        r2_mediano=round(float(fits.r2.median()), 4),
        b_mediano=round(float(fits.b.median()), 3),
        eur_bbl_mediano=round(float(fits.eur_bbl.median()), 1),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
