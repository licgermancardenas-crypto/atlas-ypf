"""Reacción de la acción de YPF a cada balance, y cuánto de eso es riesgo país.

Entradas: data/processed/financials_ypf_long.parquet (fechas de cada release)
          data/processed/financials_ypf.parquet      (KPI del trimestre)
          data/raw/market/stock/{YPF,VIST,PAM}.json  (ingest/stock_prices.py)
          data/raw/market/oil/brent.json             (ingest/brent_wti.py)
          data/raw/macro/country-risk/embi.json      (ingest/country_risk.py)
Salidas:  data/processed/market_reaction.json  (event study + serie diaria)
          data/processed/market_events.parquet (una fila por balance)

El event study, en criollo: aislar cuánto se movió la acción por el balance y
no por el petróleo, el sector o el humor del país ese día. Para eso se estima,
antes de cada evento, un modelo de mercado

    r_YPF = α + β1·r_VIST + β2·r_Brent + ε

sobre 120 ruedas que terminan 11 días antes del reporte (la ventana se corta
antes para que el propio rumor previo al balance no contamine la referencia).
El retorno anormal del día del balance es lo que el modelo no explica, y el CAR
lo acumula en la ventana pedida.

Vista como comparable y no un índice: es la empresa que comparte cuenca,
regulación y país, así que absorbe casi todo lo que no es específico de YPF.
Para los eventos anteriores a que Vista tuviera historia suficiente, el modelo
cae automáticamente a Brent solo, y queda anotado en la salida.

Convención de fecha, que no es un detalle: el `filing_date` de EDGAR no sirve
como día del evento. Un release aceptado a las 18:20 del 10 de agosto queda
fechado el 11, y usar esa fecha corre el evento un día y mide la rueda
equivocada. Se usa la hora de aceptación real (el `last-modified` del índice del
filing, en hora del Este): si es posterior al cierre —y en YPF siempre lo es—,
el evento es la rueda siguiente. Con esa regla el 2Q26 cae en la rueda del 11 de
agosto de 2026, la que efectivamente marcó el mercado con -3,6%.
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
    serie_yahoo,
)

FILINGS = RAW / "financials" / "ypf" / "filings"

SRC_LONG = PROCESSED / "financials_ypf_long.parquet"
SRC_FIN = PROCESSED / "financials_ypf.parquet"
SRC_YPF = RAW / "market" / "stock" / "YPF.json"
SRC_VIST = RAW / "market" / "stock" / "VIST.json"
SRC_PAM = RAW / "market" / "stock" / "PAM.json"
SRC_BRENT = RAW / "market" / "oil" / "brent.json"
SRC_EMBI = RAW / "macro" / "country-risk" / "embi.json"

OUT_JSON = PROCESSED / "market_reaction.json"
OUT_EVENTS = PROCESSED / "market_events.parquet"

VENTANA_ESTIMACION = 120  # ruedas del modelo de mercado
HUECO_PREVIO = 10  # ruedas entre el fin de la estimacion y el evento
MIN_ESTIMACION = 60  # menos que esto no alcanza para estimar betas
CIERRE_NYSE = 16  # hora del Este a partir de la cual el release ya no opera ese dia
VENTANAS_CAR = {"car_0_1": (0, 1), "car_m1_p1": (-1, 1), "car_0_3": (0, 3)}


def serie_embi() -> pd.Series:
    payload = json.loads(SRC_EMBI.read_text(encoding="utf-8"))
    datos = pd.DataFrame(payload["serie"])
    serie = pd.Series(
        datos.valor.astype(float).values,
        index=pd.to_datetime(datos.fecha),
        name="embi",
    )
    return serie[~serie.index.duplicated(keep="last")].sort_index()


def construir_diario() -> pd.DataFrame:
    """Panel diario de precios, Brent y riesgo país, con sus retornos."""
    precios = pd.DataFrame(
        {
            "ypf": serie_yahoo(SRC_YPF, "ypf"),
            "vist": serie_yahoo(SRC_VIST, "vist"),
            "pam": serie_yahoo(SRC_PAM, "pam"),
            "brent": serie_yahoo(SRC_BRENT, "brent"),
        }
    )
    # El calendario manda la rueda de NYSE: si YPF no cotizó, no hay evento.
    precios = precios[precios.ypf.notna()].sort_index()
    precios["embi"] = serie_embi().reindex(precios.index).ffill(limit=5)

    retornos = np.log(precios[["ypf", "vist", "pam", "brent"]]).diff()
    retornos.columns = [f"r_{c}" for c in retornos.columns]
    diario = precios.join(retornos)
    diario["d_embi"] = diario.embi.diff()

    log(f"  panel diario: {len(diario):,} ruedas ({diario.index[0].date()} a {diario.index[-1].date()})")
    return diario


def momento_release(accession: str) -> pd.Timestamp | None:
    """Hora de aceptación del filing en EDGAR (hora del Este), del índice crudo."""
    indice = FILINGS / accession / "_index.json"
    if not indice.exists():
        return None
    items = json.loads(indice.read_text(encoding="utf-8"))["directory"]["item"]
    marcas = [i["last-modified"] for i in items if i.get("last-modified")]
    return pd.Timestamp(max(marcas)) if marcas else None


def fechas_de_reporte() -> pd.DataFrame:
    """Trimestre -> release donde es titular, con su hora de aceptación."""
    largo = pd.read_parquet(SRC_LONG)
    titulares = largo[largo.es_titular]
    fechas = (
        titulares.groupby("periodo")
        .agg(fecha_reporte=("filing_date", "min"), accession=("accession", "first"))
        .reset_index()
        .rename(columns={"periodo": "trimestre"})
    )
    fechas["fecha_reporte"] = pd.to_datetime(fechas.fecha_reporte)
    fechas["momento"] = fechas.accession.map(momento_release)
    fechas["momento"] = fechas.momento.fillna(fechas.fecha_reporte)
    return fechas.sort_values("momento", ignore_index=True)


def _dia_evento(diario: pd.DataFrame, momento: pd.Timestamp) -> int | None:
    """Posición de la rueda en la que el mercado pudo operar el balance."""
    dia = momento.normalize()
    if momento.hour >= CIERRE_NYSE:
        candidatas = diario.index[diario.index > dia]  # salió con el mercado cerrado
    else:
        candidatas = diario.index[diario.index >= dia]
    if candidatas.empty:
        return None
    return int(diario.index.get_loc(candidatas[0]))


def _modelo_mercado(ventana: pd.DataFrame) -> tuple[object, list[str]]:
    """Estima r_ypf contra Vista y Brent; cae a Brent solo si falta historia."""
    factores = [f for f in ("r_vist", "r_brent") if ventana[f].notna().sum() >= MIN_ESTIMACION]
    datos = ventana[["r_ypf"] + factores].dropna()
    if len(datos) < MIN_ESTIMACION or not factores:
        return None, factores
    modelo = sm.OLS(datos.r_ypf, sm.add_constant(datos[factores])).fit()
    return modelo, factores


def event_study(diario: pd.DataFrame, eventos: pd.DataFrame) -> pd.DataFrame:
    filas: list[dict] = []

    for fila in eventos.itertuples(index=False):
        pos = _dia_evento(diario, fila.momento)
        if pos is None:
            continue
        inicio = pos - HUECO_PREVIO - VENTANA_ESTIMACION
        if inicio < 0:
            continue

        ventana = diario.iloc[inicio : pos - HUECO_PREVIO]
        modelo, factores = _modelo_mercado(ventana)
        if modelo is None:
            continue

        # Retornos anormales de toda la ventana del evento, de una sola vez.
        alrededor = diario.iloc[max(pos - 5, 0) : pos + 6]
        x = sm.add_constant(alrededor[factores], has_constant="add")
        esperado = pd.Series(modelo.predict(x), index=alrededor.index)
        anormal = alrededor.r_ypf - esperado

        registro = {
            "trimestre": str(fila.trimestre),
            "fecha_reporte": fila.fecha_reporte.date().isoformat(),
            "momento_release": fila.momento.isoformat(sep=" "),
            "fecha_evento": diario.index[pos].date().isoformat(),
            "accession": fila.accession,
            "precio_ypf": round(float(diario.ypf.iloc[pos]), 2),
            "retorno_dia": round(float(diario.r_ypf.iloc[pos]), 4),
            "retorno_anormal_dia": round(float(anormal.iloc[min(5, pos)]), 4),
            "retorno_vist_dia": round(float(diario.r_vist.iloc[pos]), 4)
            if pd.notna(diario.r_vist.iloc[pos])
            else None,
            "retorno_brent_dia": round(float(diario.r_brent.iloc[pos]), 4)
            if pd.notna(diario.r_brent.iloc[pos])
            else None,
            "embi_dia": float(diario.embi.iloc[pos]) if pd.notna(diario.embi.iloc[pos]) else None,
            "factores": "+".join(f.replace("r_", "") for f in factores),
            "r2_estimacion": round(float(modelo.rsquared), 3),
            "volatilidad_estimacion": round(float(np.sqrt(modelo.mse_resid)), 4),
        }

        for nombre, (desde, hasta) in VENTANAS_CAR.items():
            tramo = diario.index[max(pos + desde, 0) : pos + hasta + 1]
            registro[nombre] = round(float(anormal.reindex(tramo).sum()), 4)

        # Cuántas desviaciones de la volatilidad normal fue el movimiento: es lo
        # que separa "reaccionó al balance" de "fue un día más".
        registro["t_estadistico"] = round(
            registro["retorno_anormal_dia"] / registro["volatilidad_estimacion"], 2
        )
        filas.append(registro)

    eventos_out = pd.DataFrame(filas)
    log(f"  event study: {len(eventos_out)} balances con ventana completa")
    return eventos_out


def cruzar_con_fundamentals(eventos: pd.DataFrame) -> pd.DataFrame:
    """Suma a cada evento el dato del trimestre y su variación interanual."""
    fin = pd.read_parquet(SRC_FIN).set_index("trimestre")
    kpis = ["adj_ebitda_musd", "revenues_musd", "net_result_musd", "shale_oil_kbbld", "net_debt_musd"]
    disponibles = [k for k in kpis if k in fin.columns]

    variaciones = fin[disponibles].pct_change(4).add_suffix("_yoy")
    tabla = fin[disponibles].join(variaciones).round(4)

    return eventos.merge(tabla, left_on="trimestre", right_index=True, how="left")


def regresion_riesgo_pais(diario: pd.DataFrame) -> dict:
    """Cuánto del precio de la acción se mueve con el riesgo país.

    Sobre retornos diarios y no niveles: dos series con tendencia siempre
    correlacionan, y eso no dice nada. La pregunta es si el día que el riesgo
    país se mueve, la acción se mueve.
    """
    datos = diario[["r_ypf", "r_brent", "d_embi"]].dropna()
    datos = datos[datos.index >= "2021-01-01"]
    modelo = sm.OLS(datos.r_ypf, sm.add_constant(datos[["r_brent", "d_embi"]])).fit()

    # Efecto de 100 puntos básicos de riesgo país sobre el retorno diario.
    efecto_100pb = float(modelo.params["d_embi"]) * 100

    return {
        "nombre": "r_ypf ~ r_brent + d_embi (retornos diarios, desde 2021)",
        "observaciones": int(modelo.nobs),
        "r2": round(float(modelo.rsquared), 4),
        "beta_brent": round(float(modelo.params["r_brent"]), 4),
        "beta_brent_p": round(float(modelo.pvalues["r_brent"]), 4),
        "efecto_100pb_riesgo_pais": round(efecto_100pb, 4),
        "efecto_100pb_p": round(float(modelo.pvalues["d_embi"]), 4),
        "correlacion_nivel_precio_embi": round(
            float(diario[["ypf", "embi"]].dropna().corr().iloc[0, 1]), 3
        ),
    }


def serie_frontend(diario: pd.DataFrame) -> list[dict]:
    """Serie diaria desde 2021, base 100, para el gráfico del caso."""
    recorte = diario.loc["2021-01-01":, ["ypf", "vist", "pam", "brent", "embi"]].copy()
    base = recorte[["ypf", "vist", "pam", "brent"]].iloc[0]
    normalizado = (recorte[["ypf", "vist", "pam", "brent"]] / base * 100).round(1)
    normalizado["embi"] = recorte.embi.round(0)
    normalizado["precio_ypf"] = recorte.ypf.round(2)

    # Una observación semanal alcanza para el gráfico y pesa cinco veces menos.
    semanal = normalizado.resample("W-FRI").last().dropna(how="all")
    semanal.insert(0, "fecha", semanal.index.strftime("%Y-%m-%d"))
    return semanal.replace({np.nan: None}).to_dict("records")


def main() -> int:
    args = base_parser("Event study de la accion de YPF alrededor de cada balance").parse_args()

    fuentes = (SRC_LONG, SRC_FIN, SRC_YPF, SRC_VIST, SRC_PAM, SRC_BRENT, SRC_EMBI)
    faltantes = [p for p in fuentes if not p.exists()]
    if faltantes:
        log(f"faltan insumos: {', '.join(rel(p) for p in faltantes)}")
        log("correr antes: ingest/stock_prices.py --with-comparables, ingest/country_risk.py")
        return 1

    if OUT_JSON.exists() and not args.force:
        if OUT_JSON.stat().st_mtime > max(p.stat().st_mtime for p in fuentes):
            log(f"{rel(OUT_JSON)} esta al dia, se saltea (--force para rehacer)")
            return 0

    diario = construir_diario()
    eventos = cruzar_con_fundamentals(event_study(diario, fechas_de_reporte()))
    if eventos.empty:
        log("ningun balance con ventana de estimacion completa")
        return 1

    negativos = int((eventos.retorno_anormal_dia < 0).sum())
    log(
        f"  reaccion anormal negativa en {negativos}/{len(eventos)} balances; "
        f"mediana {eventos.retorno_anormal_dia.median():+.2%}"
    )

    payload = {
        "generado": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metodo": (
            "Modelo de mercado r_ypf ~ r_vist + r_brent estimado sobre "
            f"{VENTANA_ESTIMACION} ruedas que terminan {HUECO_PREVIO} dias antes del reporte; "
            "el evento es la primera rueda posterior a la presentacion del 6-K."
        ),
        "resumen": {
            "balances": int(len(eventos)),
            "con_reaccion_negativa": negativos,
            "retorno_anormal_mediano": round(float(eventos.retorno_anormal_dia.median()), 4),
            "car_0_3_mediano": round(float(eventos.car_0_3.median()), 4),
            "peor": eventos.loc[eventos.retorno_anormal_dia.idxmin(), "trimestre"],
            "mejor": eventos.loc[eventos.retorno_anormal_dia.idxmax(), "trimestre"],
        },
        "riesgo_pais": regresion_riesgo_pais(diario),
        "eventos": eventos.replace({np.nan: None}).to_dict("records"),
        "serie_semanal": serie_frontend(diario),
    }

    salidas = [
        (OUT_EVENTS, len(eventos), save_parquet(eventos, OUT_EVENTS)),
        (OUT_JSON, len(payload["serie_semanal"]), save_json(payload, OUT_JSON)),
    ]
    for destino, filas, size in salidas:
        log(f"escrito {rel(destino)} - {filas:,} filas, {human(size)}")

    record(
        "market_reaction",
        sources=[rel(SRC_LONG), rel(SRC_YPF), rel(SRC_EMBI)],
        outputs=[rel(d) for d, _, _ in salidas],
        **payload["resumen"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
