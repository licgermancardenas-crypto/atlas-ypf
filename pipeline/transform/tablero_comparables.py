"""YPF contra Vista y Pampa, con las mismas cuentas para los tres.

Por qué importa: el caso pregunta por qué la acción cayó con un balance récord,
y la respuesta no está solo adentro de YPF. Si el mercado paga menos múltiplo
por el mismo EBITDA que a un competidor, la diferencia es la historia. Para que
la comparación valga, las tres compañías tienen que estar medidas igual: EBITDA
como resultado operativo más depreciaciones, deuda neta como deuda financiera
menos caja, y el capex del estado de flujo.

Los tres son los únicos comparables con disclosure equivalente: Vista y Pampa
presentan 20-F ante la SEC, igual que YPF.

Sobre el múltiplo: el valor de la empresa se arma con el precio del ADR de hoy
por la cantidad de ADR, más la deuda neta del último ejercicio cerrado. Mezcla
un precio de hoy con un balance de diciembre, que es lo que hace cualquier
pantalla de mercado, y por eso se publica con esa etiqueta.

Entradas: data/processed/statements_ypf.parquet   (YPF, de sus estados)
          data/processed/comparables_web.json     (Vista y Pampa, de transform/peers.py)
          data/raw/market/stock/YPF.json          (precio del ADR)
Salida:   data/processed/tablero_comparables.parquet + .json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, RAW, base_parser, human, log, record, rel, save_json, save_parquet, serie_yahoo  # noqa: E402

ESTADOS = PROCESSED / "statements_ypf.parquet"
COMPARABLES = PROCESSED / "comparables_web.json"
SALIDA = PROCESSED / "tablero_comparables.parquet"
SALIDA_JSON = PROCESSED / "tablero_comparables.json"

# El split de 2026 no cambió la cantidad de ADR ni su precio: cada ADR pasó a
# representar diez acciones. Por eso el libro y este transform razonan en ADR.
ADRS_YPF = 393_312_793
NOMBRES = {"YPF": "YPF S.A.", "VIST": "Vista Energy", "PAM": "Pampa Energía"}

CLAVES_YPF = {
    "ingresos": ("resultados", "revenues"),
    "resultado_operativo": ("resultados", "operating profit"),
    "resultado_neto": ("resultados", "net profit"),
    "flujo_operativo": ("flujo", "net cash flows from operating activities"),
    "capex": ("flujo", "acquisition of property plant and equipment and intangible assets | "
                       "net cash flows used in investing activities"),
    "patrimonio": ("balance", "total shareholders equity"),
    "activos": ("balance", "total assets"),
}
DEPRECIACIONES_YPF = [
    "depreciation of property plant and equipment | net cash flows from operating activities",
    "amortization of intangible assets | net cash flows from operating activities",
    "depreciation of right of use assets | net cash flows from operating activities",
]
DEUDA_YPF = ["loans | total non current liabilities", "loans | total current liabilities"]
CAJA_YPF = ["cash and cash equivalents | total current assets",
            "investments in financial assets | total current assets"]


def anuales_ypf() -> pd.DataFrame:
    datos = pd.read_parquet(ESTADOS)
    anual = datos[datos["tipo"] == "anual"]
    ancho = anual.pivot_table(index="periodo", columns=["estado", "clave"], values="valor_musd", aggfunc="first")

    def linea(estado: str, clave: str) -> pd.Series:
        return ancho[(estado, clave)] if (estado, clave) in ancho.columns else pd.Series(0.0, index=ancho.index)

    filas = pd.DataFrame(index=ancho.index)
    for nombre, (estado, clave) in CLAVES_YPF.items():
        filas[nombre] = linea(estado, clave)
    filas["capex"] = -filas["capex"]  # en el flujo viene con signo negativo
    filas["depreciaciones"] = sum(linea("flujo", c) for c in DEPRECIACIONES_YPF)
    filas["deuda_financiera"] = sum(linea("balance", c) for c in DEUDA_YPF)
    filas["caja"] = sum(linea("balance", c) for c in CAJA_YPF)
    filas["ticker"] = "YPF"
    return filas.reset_index().rename(columns={"periodo": "anio"})


def anuales_peers() -> pd.DataFrame:
    if not COMPARABLES.exists():
        return pd.DataFrame()
    datos = json.loads(COMPARABLES.read_text(encoding="utf-8"))
    filas = []
    for emisor in datos.get("emisores", []):
        for anio, valores in emisor.get("ejercicios", {}).items():
            filas.append({
                "anio": anio,
                "ticker": emisor["ticker"],
                "ingresos": valores.get("ingresos"),
                "resultado_operativo": valores.get("resultado_operativo"),
                "resultado_neto": valores.get("resultado_neto"),
                "flujo_operativo": valores.get("flujo_operativo"),
                "capex": valores.get("capex"),
                "depreciaciones": valores.get("depreciacion_y_amortizacion"),
                "deuda_financiera": valores.get("deuda_financiera"),
                "caja": valores.get("caja"),
                "patrimonio": valores.get("patrimonio"),
                "activos": valores.get("activos"),
            })
    return pd.DataFrame(filas)


def precios() -> dict[str, dict]:
    """Precio del ADR y cantidad de ADR de cada compañía."""
    fichas: dict[str, dict] = {}
    if COMPARABLES.exists():
        datos = json.loads(COMPARABLES.read_text(encoding="utf-8"))
        for emisor in datos.get("emisores", []):
            fichas[emisor["ticker"]] = {"precio": emisor.get("precio"), "adrs": emisor.get("adrs"),
                                        "fecha_precio": emisor.get("fecha_precio")}
    serie = serie_yahoo(RAW / "market" / "stock" / "YPF.json", "ypf")
    if serie is not None and len(serie):
        fichas["YPF"] = {"precio": float(serie.iloc[-1]), "adrs": ADRS_YPF,
                         "fecha_precio": str(serie.index[-1].date())}
    return fichas


def main() -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.parse_args()
    if not ESTADOS.exists():
        raise SystemExit("falta statements_ypf.parquet")

    tabla = pd.concat([anuales_ypf(), anuales_peers()], ignore_index=True)
    tabla["anio"] = tabla["anio"].astype(str)
    tabla = tabla[tabla["ingresos"].notna()]
    tabla["ebitda"] = tabla["resultado_operativo"].fillna(0) + tabla["depreciaciones"].fillna(0)
    tabla["margen_ebitda"] = tabla["ebitda"] / tabla["ingresos"]
    tabla["deuda_neta"] = tabla["deuda_financiera"] - tabla["caja"]
    tabla["deuda_neta_ebitda"] = tabla["deuda_neta"] / tabla["ebitda"]
    tabla["capex_sobre_ebitda"] = tabla["capex"] / tabla["ebitda"]
    tabla["flujo_libre"] = tabla["flujo_operativo"] - tabla["capex"]
    tabla["retorno_patrimonio"] = tabla["resultado_neto"] / tabla["patrimonio"]
    tabla["empresa"] = tabla["ticker"].map(NOMBRES)

    # Solo los años en los que están los tres: comparar contra un año que le
    # falta a alguno es comparar contra un hueco.
    completos = [anio for anio, grupo in tabla.groupby("anio") if grupo["ticker"].nunique() == tabla["ticker"].nunique()]
    tabla["comparable"] = tabla["anio"].isin(completos)

    fichas = precios()
    ultimo_comun = max(completos) if completos else tabla["anio"].max()
    resumen = []
    for ticker, grupo in tabla.groupby("ticker"):
        ficha = fichas.get(ticker, {})
        fila = grupo[grupo["anio"] == ultimo_comun]
        if fila.empty or not ficha.get("precio") or not ficha.get("adrs"):
            continue
        fila = fila.iloc[0]
        capitalizacion = ficha["precio"] * ficha["adrs"] / 1e6  # en millones de dólares
        valor_empresa = capitalizacion + float(fila["deuda_neta"])
        resumen.append({
            "ticker": ticker,
            "empresa": NOMBRES.get(ticker, ticker),
            "precio_adr": ficha["precio"],
            "fecha_precio": ficha.get("fecha_precio"),
            "capitalizacion_musd": capitalizacion,
            "deuda_neta_musd": float(fila["deuda_neta"]),
            "valor_empresa_musd": valor_empresa,
            "ebitda_musd": float(fila["ebitda"]),
            "ev_ebitda": valor_empresa / float(fila["ebitda"]) if fila["ebitda"] else None,
            "precio_valor_libro": capitalizacion / float(fila["patrimonio"]) if fila["patrimonio"] else None,
            "ejercicio": ultimo_comun,
        })

    bytes_parquet = save_parquet(tabla.reset_index(drop=True), SALIDA)
    payload = {
        "generado": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "moneda": "USD",
        "unidad": "millones",
        "metodo": ("EBITDA = resultado operativo + depreciaciones; deuda neta = deuda financiera − caja; "
                   "capex del estado de flujo. Las tres compañías, con la misma cuenta."),
        "advertencia": ("El múltiplo mezcla el precio del ADR de hoy con el balance del último ejercicio cerrado, "
                        "que es como lo arma cualquier pantalla de mercado."),
        "anios_comparables": sorted(completos),
        "ultimo_ejercicio_comun": ultimo_comun,
        "multiplos": resumen,
    }
    bytes_json = save_json(payload, SALIDA_JSON, indent=2)
    record(
        "transform/tablero-comparables",
        rows=int(len(tabla)),
        bytes=int(bytes_parquet + bytes_json),
        outputs=[rel(SALIDA), rel(SALIDA_JSON)],
        note=f"YPF, VIST y PAM; ejercicios comparables {', '.join(sorted(completos))}",
    )
    log(f"{rel(SALIDA)} ({human(bytes_parquet)}) · {len(tabla)} filas · "
        f"{len(resumen)} múltiplos sobre {ultimo_comun}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
