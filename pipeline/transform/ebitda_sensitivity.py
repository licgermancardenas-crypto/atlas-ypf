"""Sensibilidad del EBITDA de YPF a Brent, producción y tipo de cambio.

Entradas: data/processed/financials_ypf.parquet (transform/financials_ypf.py)
          data/raw/market/oil/{brent,wti}.json  (ingest/brent_wti.py)
          data/raw/macro/fx/ars_usd.json        (ingest/fx_ars_usd.py)
Salidas:  data/processed/ebitda_sensitivity.json  (coeficientes y grilla)
          data/processed/ebitda_quarterly.parquet (panel trimestral cruzado)

Qué contesta: cuánto del EBITDA trimestral explica el precio del crudo, cuánto
el volumen producido y cuánto queda sin explicar. Los coeficientes son la
entrada del simulador de escenarios de la Fase 5, así que se publican con su
error estándar y su intervalo: un slider que mueve un número sin decir cuán
firme es ese número miente por omisión.

Tres modelos, a propósito:

- El operativo (`adj_ebitda ~ brent + produccion + lifting cost + crudo
  procesado`) es el que tiene sentido económico y el que alimenta el simulador.
  El costo de extracción entra como regresor porque es la mitad de la historia
  del caso: entre 2024 y 2026 el lifting cost de YPF cayó de US$ 16 a US$ 8,4
  por boe, y sin esa variable el modelo le atribuye a Brent una mejora que en
  realidad es de eficiencia (el R² pasa de 0,27 a 0,84 al sumarla). El crudo
  procesado entra porque la otra mitad del EBITDA es downstream: sumarlo lleva
  el R² a 0,91 y recorta un tercio del residual del 2Q26, el trimestre en que el
  margen de refino saltó de 14,9 a 23,2 US$/bbl.
- El de mezcla (`adj_ebitda ~ brent + shale oil`) cuenta lo mismo desde el
  volumen: cuánto del EBITDA viene de que el barril es cada vez más de shale.
- El largo (`adj_ebitda ~ brent`) usa los 27 trimestres disponibles. Sirve de
  control: si el coeficiente de Brent cambia mucho entre modelos, la culpa es de
  la muestra corta y no del modelo.

YPF recién publica producción y costos trimestrales desde 2023, así que los dos
primeros corren sobre 15 y 11 observaciones: hay que leer los intervalos, no
solo el punto.

El tipo de cambio entra como variación real (depreciación nominal menos la
inflación implícita en el precio local de los combustibles), no como nivel: el
EBITDA se reporta en dólares y lo que mueve el margen es el atraso o el salto
cambiario, no el valor absoluto del peso.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

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

SRC_FIN = PROCESSED / "financials_ypf.parquet"
SRC_BRENT = RAW / "market" / "oil" / "brent.json"
SRC_WTI = RAW / "market" / "oil" / "wti.json"
SRC_FX = RAW / "macro" / "fx" / "ars_usd.json"

OUT_PANEL = PROCESSED / "ebitda_quarterly.parquet"
OUT_JSON = PROCESSED / "ebitda_sensitivity.json"

# Grilla del simulador: alrededor de los valores del último trimestre.
BRENT_GRID = [50, 60, 70, 80, 90, 100, 110, 120]
PRODUCCION_GRID = [480, 500, 520, 540, 560, 580]
LIFTING_GRID = [7.0, 8.5, 10.0, 12.0, 14.0, 16.0]

REGRESORES_OPERATIVO = [
    "brent_usd",
    "produccion_kboed",
    "lifting_cost_usd_boe",
    "crudo_procesado_kbbld",
]
# Los ingresos se modelan aparte porque el simulador necesita el margen, no solo
# el EBITDA. El lifting cost no entra: es un costo, no mueve la linea de arriba.
REGRESORES_INGRESOS = ["brent_usd", "produccion_kboed", "crudo_procesado_kbbld"]

# Variables que el simulador deja fijas en el ultimo dato cuando barre una grilla.
FIJAS_EN_GRILLA = ["lifting_cost_usd_boe", "crudo_procesado_kbbld"]


def serie_diaria(path: Path, nombre: str) -> pd.Series:
    """Cierres diarios de un JSON de Yahoo, indexados por fecha."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    resultado = payload["chart"]["result"][0]
    fechas = pd.to_datetime(resultado["timestamp"], unit="s", utc=True).tz_localize(None)
    cierres = resultado["indicators"]["quote"][0]["close"]
    serie = pd.Series(cierres, index=fechas, name=nombre, dtype="float64")
    return serie.dropna()


def a_trimestral(serie: pd.Series) -> pd.Series:
    """Promedio del trimestre: el EBITDA se devenga a lo largo del trimestre,
    no al cierre, así que el promedio es el precio que efectivamente enfrentó."""
    return serie.groupby(serie.index.to_period("Q")).mean()


def construir_panel() -> pd.DataFrame:
    fin = pd.read_parquet(SRC_FIN)
    fin["trimestre"] = pd.PeriodIndex(fin.trimestre, freq="Q")
    fin = fin.set_index("trimestre").sort_index()

    mercado = pd.DataFrame(
        {
            "brent_usd": a_trimestral(serie_diaria(SRC_BRENT, "brent")),
            "wti_usd": a_trimestral(serie_diaria(SRC_WTI, "wti")),
            "fx_ars_usd": a_trimestral(serie_diaria(SRC_FX, "fx")),
        }
    )

    panel = fin.join(mercado, how="left")
    panel["fx_var"] = panel.fx_ars_usd.pct_change()

    # Depreciación real: cuánto se movió el dólar por encima de lo que se movió
    # el precio local de los combustibles. Es el proxy de atraso cambiario que
    # se puede armar sin series de inflación, con el propio dato de la compañía.
    panel["combustibles_var"] = panel.precio_combustibles_usd_m3.pct_change()
    panel["fx_var_real"] = panel.fx_var - panel.combustibles_var

    dias = panel.index.to_timestamp(how="end").day_of_year - panel.index.to_timestamp().day_of_year
    panel["dias_trimestre"] = dias + 1
    panel["boe_trimestre_mm"] = panel.produccion_kboed * panel.dias_trimestre / 1000.0
    panel["ebitda_por_boe"] = panel.adj_ebitda_musd / panel.boe_trimestre_mm

    # Descuento del crudo local contra Brent: es el canal por el que el precio
    # internacional llega (o no llega) al balance.
    panel["diferencial_usd_bbl"] = panel.brent_usd - panel.precio_crudo_usd_bbl

    log(f"  panel cruzado: {len(panel)} trimestres, Brent desde {panel.brent_usd.first_valid_index()}")
    return panel


def ajustar(panel: pd.DataFrame, regresores: list[str], y: str = "adj_ebitda_musd"):
    datos = panel[[y] + regresores].dropna()
    modelo = sm.OLS(datos[y], sm.add_constant(datos[regresores])).fit()
    return modelo, datos


def resumen_modelo(modelo, nombre: str, datos: pd.DataFrame) -> dict:
    intervalos = modelo.conf_int(alpha=0.05)
    coeficientes = []
    for var in modelo.params.index:
        coeficientes.append(
            {
                "variable": var,
                "coeficiente": round(float(modelo.params[var]), 4),
                "error_estandar": round(float(modelo.bse[var]), 4),
                "p_valor": round(float(modelo.pvalues[var]), 4),
                "ic_95": [round(float(intervalos.loc[var, 0]), 4), round(float(intervalos.loc[var, 1]), 4)],
            }
        )
    return {
        "nombre": nombre,
        "observaciones": int(modelo.nobs),
        "periodo": [str(datos.index.min()), str(datos.index.max())],
        "r2": round(float(modelo.rsquared), 4),
        "r2_ajustado": round(float(modelo.rsquared_adj), 4),
        "error_estandar_residual_musd": round(float(np.sqrt(modelo.mse_resid)), 1),
        "coeficientes": coeficientes,
    }


def _predecir(modelo, escenario: dict) -> tuple[float, float, float]:
    x = pd.DataFrame([{"const": 1.0, **escenario}])[modelo.params.index]
    pred = modelo.get_prediction(x).summary_frame(alpha=0.05).iloc[0]
    return float(pred["mean"]), float(pred["obs_ci_lower"]), float(pred["obs_ci_upper"])


def grilla_escenarios(modelo, ultimo: pd.Series) -> list[dict]:
    """EBITDA proyectado en la grilla Brent x producción, con su banda.

    El lifting cost queda fijo en el del último trimestre: mover las tres
    variables a la vez da 288 celdas y ninguna intuición. La sensibilidad al
    costo va aparte, en su propia grilla.
    """
    salida = []
    for produccion in PRODUCCION_GRID:
        for brent in BRENT_GRID:
            media, bajo, alto = _predecir(
                modelo,
                {
                    "brent_usd": brent,
                    "produccion_kboed": produccion,
                    **{v: float(ultimo[v]) for v in FIJAS_EN_GRILLA},
                },
            )
            salida.append(
                {
                    "brent": brent,
                    "produccion_kboed": produccion,
                    "ebitda_musd": round(media, 0),
                    "ic_95": [round(bajo, 0), round(alto, 0)],
                    "delta_vs_ultimo": round(media - float(ultimo.adj_ebitda_musd), 0),
                }
            )
    return salida


def grilla_costos(modelo, ultimo: pd.Series) -> list[dict]:
    """Sensibilidad al lifting cost, con Brent y producción en el último dato."""
    salida = []
    for lifting in LIFTING_GRID:
        media, bajo, alto = _predecir(
            modelo,
            {
                "brent_usd": float(ultimo.brent_usd),
                "produccion_kboed": float(ultimo.produccion_kboed),
                "lifting_cost_usd_boe": lifting,
                "crudo_procesado_kbbld": float(ultimo.crudo_procesado_kbbld),
            },
        )
        salida.append(
            {
                "lifting_cost_usd_boe": lifting,
                "ebitda_musd": round(media, 0),
                "ic_95": [round(bajo, 0), round(alto, 0)],
                "delta_vs_ultimo": round(media - float(ultimo.adj_ebitda_musd), 0),
            }
        )
    return salida


def descomponer_ultimo(modelo, panel: pd.DataFrame) -> dict:
    """Atribución del salto de EBITDA del último trimestre contra el anterior.

    El puente price/volume/resto es la lectura estándar de un balance: separa
    lo que el management controla (volumen, costos) de lo que le pasó por
    encima (el precio internacional).
    """
    validos = panel.dropna(subset=["adj_ebitda_musd"] + REGRESORES_OPERATIVO)
    actual, previo = validos.iloc[-1], validos.iloc[-2]

    efecto_precio = float(modelo.params["brent_usd"]) * (actual.brent_usd - previo.brent_usd)
    efecto_volumen = float(modelo.params["produccion_kboed"]) * (
        actual.produccion_kboed - previo.produccion_kboed
    )
    efecto_costo = float(modelo.params["lifting_cost_usd_boe"]) * (
        actual.lifting_cost_usd_boe - previo.lifting_cost_usd_boe
    )
    efecto_downstream = float(modelo.params["crudo_procesado_kbbld"]) * (
        actual.crudo_procesado_kbbld - previo.crudo_procesado_kbbld
    )
    delta_real = float(actual.adj_ebitda_musd - previo.adj_ebitda_musd)

    # De donde sale, en realidad, el residual del puente.
    #
    # El residual no es una partida que falte: es la diferencia entre dos
    # errores del modelo. Si el trimestre anterior el modelo se paso de
    # optimista y este se quedo corto, el puente arrastra las dos cosas juntas
    # y parece un one-off que no existe. Publicar los dos residuos por separado
    # es lo que evita salir a buscar una venta de activos para explicar lo que
    # explica un modelo con quince observaciones.
    residuos = pd.Series(modelo.resid, index=modelo.model.data.row_labels)
    residual_previo = float(residuos.get(validos.index[-2], float("nan")))
    residual_actual = float(residuos.get(validos.index[-1], float("nan")))

    return {
        "desde": str(validos.index[-2]),
        "hasta": str(validos.index[-1]),
        "ebitda_previo_musd": float(previo.adj_ebitda_musd),
        "ebitda_actual_musd": float(actual.adj_ebitda_musd),
        "delta_musd": round(delta_real, 1),
        "efecto_precio_musd": round(efecto_precio, 1),
        "efecto_volumen_musd": round(efecto_volumen, 1),
        "efecto_costo_musd": round(efecto_costo, 1),
        "efecto_downstream_musd": round(efecto_downstream, 1),
        "residual_musd": round(
            delta_real - efecto_precio - efecto_volumen - efecto_costo - efecto_downstream, 1
        ),
        "residual_previo_musd": round(residual_previo, 1),
        "residual_actual_musd": round(residual_actual, 1),
        "error_estandar_residual_musd": round(float(np.sqrt(modelo.mse_resid)), 1),
        "brent_previo": round(float(previo.brent_usd), 1),
        "brent_actual": round(float(actual.brent_usd), 1),
        "produccion_previa_kboed": float(previo.produccion_kboed),
        "produccion_actual_kboed": float(actual.produccion_kboed),
        "lifting_previo_usd_boe": float(previo.lifting_cost_usd_boe),
        "lifting_actual_usd_boe": float(actual.lifting_cost_usd_boe),
        "procesado_previo_kbbld": float(previo.crudo_procesado_kbbld),
        "procesado_actual_kbbld": float(actual.crudo_procesado_kbbld),
    }


def serie_frontend(panel: pd.DataFrame, modelo, datos: pd.DataFrame) -> list[dict]:
    ajustado = pd.Series(modelo.fittedvalues, index=datos.index, name="ebitda_ajustado_musd")
    salida = panel.join(ajustado)[
        [
            "adj_ebitda_musd",
            "ebitda_ajustado_musd",
            "revenues_musd",
            "brent_usd",
            "wti_usd",
            "precio_crudo_usd_bbl",
            "diferencial_usd_bbl",
            "produccion_kboed",
            "shale_oil_kbbld",
            "ebitda_por_boe",
            "lifting_cost_usd_boe",
            "fx_ars_usd",
            "margen_ebitda",
        ]
    ].round(3)
    salida.insert(0, "trimestre", salida.index.astype(str))
    return salida.replace({np.nan: None}).to_dict("records")


def main() -> int:
    args = base_parser("Modela la sensibilidad del EBITDA a Brent, produccion y FX").parse_args()

    faltantes = [p for p in (SRC_FIN, SRC_BRENT, SRC_WTI, SRC_FX) if not p.exists()]
    if faltantes:
        log(f"faltan insumos: {', '.join(rel(p) for p in faltantes)}")
        return 1

    if OUT_JSON.exists() and not args.force:
        if OUT_JSON.stat().st_mtime > SRC_FIN.stat().st_mtime:
            log(f"{rel(OUT_JSON)} esta al dia, se saltea (--force para rehacer)")
            return 0

    panel = construir_panel()

    operativo, datos_op = ajustar(panel, REGRESORES_OPERATIVO)
    ingresos, datos_ingresos = ajustar(panel, REGRESORES_INGRESOS, y="revenues_musd")
    # Especificacion alternativa: agrega el atraso cambiario. Se estima para
    # poder decir con numeros que no es significativo (p 0,12 sobre 11
    # trimestres), en vez de dejarlo afuera sin explicacion.
    fx, datos_fx = ajustar(panel, REGRESORES_OPERATIVO + ["fx_var_real"])
    mezcla, datos_mezcla = ajustar(panel, ["brent_usd", "shale_oil_kbbld"])
    largo, datos_largo = ajustar(panel, ["brent_usd"])
    for nombre, modelo in (("operativo", operativo), ("mezcla   ", mezcla), ("largo    ", largo)):
        coef_brent = float(modelo.params["brent_usd"])
        log(
            f"  modelo {nombre}: R2 {modelo.rsquared:.3f} sobre {int(modelo.nobs)} trimestres; "
            f"Brent {coef_brent:+.1f} MUSD por US$/bbl"
        )

    ultimo = panel.dropna(subset=["adj_ebitda_musd"] + REGRESORES_OPERATIVO).iloc[-1]

    payload = {
        "generado": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "advertencia": (
            "Coeficientes estimados sobre pocos trimestres: usar el intervalo, no el punto. "
            "No son una proyeccion de la compania."
        ),
        "modelo_operativo": resumen_modelo(
            operativo,
            "adj_ebitda ~ brent + produccion + lifting_cost + crudo_procesado",
            datos_op,
        ),
        "modelo_ingresos": resumen_modelo(
            ingresos, "revenues ~ brent + produccion + crudo_procesado", datos_ingresos
        ),
        "modelo_fx": resumen_modelo(
            fx, "adj_ebitda ~ brent + produccion + lifting_cost + crudo_procesado + fx_var_real", datos_fx
        ),
        "modelo_mezcla": resumen_modelo(mezcla, "adj_ebitda ~ brent + shale_oil", datos_mezcla),
        "modelo_largo": resumen_modelo(largo, "adj_ebitda ~ brent", datos_largo),
        "ultimo_trimestre": {
            "trimestre": str(ultimo.name),
            "adj_ebitda_musd": float(ultimo.adj_ebitda_musd),
            "brent_usd": round(float(ultimo.brent_usd), 2),
            "produccion_kboed": float(ultimo.produccion_kboed),
            "lifting_cost_usd_boe": float(ultimo.lifting_cost_usd_boe),
            "crudo_procesado_kbbld": float(ultimo.crudo_procesado_kbbld),
            "revenues_musd": float(ultimo.revenues_musd),
        },
        "descomposicion_ultimo_trimestre": descomponer_ultimo(operativo, panel),
        "grilla_escenarios": grilla_escenarios(operativo, ultimo),
        "grilla_costos": grilla_costos(operativo, ultimo),
        "serie": serie_frontend(panel, operativo, datos_op),
    }

    panel_out = panel.reset_index()
    panel_out["trimestre"] = panel_out.trimestre.astype(str)

    salidas = [
        (OUT_PANEL, len(panel_out), save_parquet(panel_out, OUT_PANEL)),
        (OUT_JSON, len(payload["serie"]), save_json(payload, OUT_JSON)),
    ]
    for destino, filas, size in salidas:
        log(f"escrito {rel(destino)} - {filas:,} filas, {human(size)}")

    record(
        "ebitda_sensitivity",
        sources=[rel(SRC_FIN), rel(SRC_BRENT), rel(SRC_FX)],
        outputs=[rel(d) for d, _, _ in salidas],
        r2_operativo=payload["modelo_operativo"]["r2"],
        r2_ingresos=payload["modelo_ingresos"]["r2"],
        r2_mezcla=payload["modelo_mezcla"]["r2"],
        r2_largo=payload["modelo_largo"]["r2"],
        observaciones_operativo=payload["modelo_operativo"]["observaciones"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
