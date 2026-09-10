"""Arma los JSON que consume el módulo interactivo del sitio.

El Excel y el sitio miran los mismos parquet, pero piden cosas distintas: el
libro necesita filas y columnas, y el navegador necesita algo liviano, tipado y
partido en pedazos que se puedan bajar cuando se los mira. Este transform hace
esa traducción y no calcula nada nuevo —salvo redondear— para que el sitio no
pueda contradecir al Excel.

Salidas:
  estados_web.json      los tres estados, línea por línea, con el origen de cada
                        celda (reportado o derivado, dólar o peso convertido);
  segmentos_web.json    la apertura por segmento;
  comparables_web.json  YPF contra Vista y Pampa;
  deuda_web.json        instrumentos y escalera de vencimientos;
  mercado_web.json      lo que hace falta para recalcular la valuación en el
                        navegador: precio, acciones, riesgo país, reservas y los
                        agregados de los últimos doce meses.

Uso:
    python pipeline/transform/book_web.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

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
    serie_yahoo,
)

ESTADOS = PROCESSED / "statements_ypf.parquet"
SEGMENTOS = PROCESSED / "segments_ypf.parquet"
PEERS = PROCESSED / "peers.parquet"
PEERS_META = PROCESSED / "peers.json"
DEUDA = PROCESSED / "debt_ypf.parquet"
DEUDA_META = PROCESSED / "debt_ypf.json"
RESERVAS = PROCESSED / "reserves.json"
ECONOMIA = PROCESSED / "well_economics.json"

DESDE = "2020Q1"

TITULOS = {
    "resultados": "Estado de resultados integrales",
    "balance": "Estado de situación patrimonial",
    "flujo": "Estado de flujo de efectivo",
}

# La compañía presenta en inglés y el sitio está en castellano. Se traducen las
# líneas principales —las que alguien busca— y el resto queda como la publicó:
# preferimos un renglón en inglés antes que una traducción inventada de un
# concepto contable.
TRADUCCIONES = {
    "revenues": "Ingresos",
    "costs": "Costos",
    "gross profit": "Resultado bruto",
    "selling expenses": "Gastos de comercialización",
    "administrative expenses": "Gastos de administración",
    "exploration expenses": "Gastos de exploración",
    "impairment reversal of ppe and inventories write down": "Deterioro y reversión de bienes de uso",
    "other net operating results": "Otros resultados operativos",
    "operating profit": "Resultado operativo",
    "income from equity interests in associates and joint ventures": "Resultado de asociadas y negocios conjuntos",
    "financial income": "Ingresos financieros",
    "financial costs": "Costos financieros",
    "other financial results": "Otros resultados financieros",
    "net financial results": "Resultados financieros netos",
    "net profit before income tax": "Resultado antes de impuesto",
    "income tax": "Impuesto a las ganancias",
    "net profit": "Resultado neto",
    "other comprehensive income": "Otro resultado integral",
    "total comprehensive income": "Resultado integral total",
    "basic and diluted": "Resultado por acción, básico y diluido",
    # Balance
    "intangible assets": "Activos intangibles",
    "property plant and equipment": "Bienes de uso",
    "right of use assets": "Activos por derecho de uso",
    "investments in associates and joint ventures": "Inversiones en asociadas y negocios conjuntos",
    "deferred income tax assets net": "Activo por impuesto diferido, neto",
    "total non current assets": "Total del activo no corriente",
    "assets held for sale": "Activos mantenidos para la venta",
    "inventories": "Inventarios",
    "contract assets": "Activos por contratos",
    "total current assets": "Total del activo corriente",
    "total assets": "TOTAL DEL ACTIVO",
    "capital": "Capital",
    "legal reserve": "Reserva legal",
    "reserve for investments": "Reserva para inversiones",
    "other comprehensive income (2)": "Otro resultado integral",
    "unappropriated retained earnings and losses": "Resultados no asignados",
    "shareholders equity attributable to shareholders of the parent company": "Patrimonio atribuible a los accionistas de la controlante",
    "non controlling interest": "Participación no controlante",
    "total shareholders equity": "TOTAL DEL PATRIMONIO",
    "provisions": "Previsiones",
    "contract liabilities": "Pasivos por contratos",
    "deferred income tax liabilities net": "Pasivo por impuesto diferido, neto",
    "income tax liability": "Impuesto a las ganancias a pagar",
    "taxes payable": "Cargas fiscales",
    "salaries and social security": "Remuneraciones y cargas sociales",
    "lease liabilities": "Pasivos por arrendamientos",
    "loans": "Préstamos",
    "other liabilities": "Otros pasivos",
    "accounts payable": "Cuentas por pagar",
    "total non current liabilities": "Total del pasivo no corriente",
    "total current liabilities": "Total del pasivo corriente",
    "total liabilities": "TOTAL DEL PASIVO",
    "total liabilities and shareholders equity": "TOTAL DEL PASIVO Y PATRIMONIO",
    # Flujo
    "depreciation of property plant and equipment": "Depreciación de bienes de uso",
    "amortization of intangible assets": "Amortización de intangibles",
    "depreciation of right of use assets": "Depreciación de activos por derecho de uso",
    "charge on income tax": "Cargo por impuesto a las ganancias",
    "income tax payments": "Pagos de impuesto a las ganancias",
    "net cash flows from operating activities": "Flujo neto de las actividades operativas",
    "acquisition of property plant and equipment and intangible assets": "Adquisición de bienes de uso e intangibles",
    "net cash flows used in investing activities": "Flujo neto de las actividades de inversión",
    "payments of loans": "Pagos de préstamos",
    "proceeds from loans": "Toma de préstamos",
    "payments of interests": "Pagos de intereses",
    "payments of leases": "Pagos de arrendamientos",
    "net cash flows from financing activities": "Flujo neto de las actividades de financiación",
    "effect of changes in exchange rates on cash and cash equivalents": "Efecto del tipo de cambio sobre el efectivo",
    "increase in cash and cash equivalents": "Aumento del efectivo",
    "cash and cash equivalents at the beginning of the fiscal year": "Efectivo al inicio del ejercicio",
    "cash and cash equivalents at the end of the period": "Efectivo al cierre",
    "cash and cash equivalents": "Efectivo y equivalentes",
}

SUFIJOS = {
    "total non current assets": "no corriente",
    "total current assets": "corriente",
    "total non current liabilities": "no corriente",
    "total current liabilities": "corriente",
    "net cash flows from operating activities": "operativo",
    "net cash flows used in investing activities": "inversión",
    "net cash flows from financing activities": "financiación",
}

SEGMENTOS_CONCEPTOS = {
    "ingresos_totales": "Ingresos",
    "ingresos_externos": "Ingresos a terceros",
    "ingresos_intersegmento": "Ingresos intersegmento",
    "resultado_operativo": "Resultado operativo",
    "capex_ppe": "Capex en bienes de uso",
    "depreciacion_ppe": "Depreciación de bienes de uso",
    "activos": "Activos",
}


def traducir(clave: str, etiqueta: str) -> str:
    base = clave.split(" | ")[0]
    seccion = clave.split(" | ")[1] if " | " in clave else None
    nombre = TRADUCCIONES.get(clave) or TRADUCCIONES.get(base)
    if nombre is None:
        return etiqueta
    if seccion and SUFIJOS.get(seccion) and base in {
        "loans", "lease liabilities", "provisions", "accounts payable", "other liabilities",
        "taxes payable", "salaries and social security", "contract liabilities",
        "income tax liability", "trade receivables", "other receivables",
        "investments in financial assets",
    }:
        return f"{nombre} ({SUFIJOS[seccion]})"
    return nombre


def redondear(valor) -> float | None:
    if valor is None or pd.isna(valor):
        return None
    return round(float(valor), 1)


def armar_estados() -> dict:
    datos = pd.read_parquet(ESTADOS)
    trimestres = sorted(p for p in datos.loc[datos["tipo"] == "trimestre", "periodo"].unique() if p >= DESDE)
    anios = sorted(a for a in datos.loc[datos["tipo"] == "anual", "periodo"].unique() if a >= "2019")

    salida: dict = {}
    for estado in ("resultados", "balance", "flujo"):
        sub = datos[datos["estado"] == estado]
        if sub.empty:
            continue
        ultimo = sub["presentado"].max()
        lineas = []
        for clave, grupo in sub.groupby("clave"):
            reciente = grupo.sort_values("presentado").iloc[-1]
            vigente = reciente["presentado"] == ultimo
            por_periodo = grupo.set_index("periodo")
            etiqueta = traducir(clave, reciente["etiqueta"])

            def columna(periodos: list[str]) -> list[float | None]:
                return [
                    redondear(por_periodo["valor_musd"].get(p)) if p in por_periodo.index else None
                    for p in periodos
                ]

            def marcas(periodos: list[str], campo: str, mapa: dict) -> str:
                letras = []
                for periodo in periodos:
                    if periodo not in por_periodo.index:
                        letras.append("-")
                        continue
                    valor = por_periodo[campo].get(periodo)
                    letras.append(mapa.get(str(valor), mapa["otro"]))
                return "".join(letras)

            lineas.append(
                {
                    "clave": clave,
                    "etiqueta": etiqueta,
                    "original": reciente["etiqueta"],
                    "orden": int(reciente["orden"]) + (0 if vigente else 1000),
                    "total": reciente["etiqueta"].strip().lower().startswith("total"),
                    "vigente": bool(vigente),
                    "trimestral": columna(trimestres),
                    "anual": columna(anios),
                    # Una letra por período: R reportado, D derivado; U dólar, A peso convertido.
                    "derivacion": marcas(trimestres, "derivacion", {"reportado": "R", "otro": "D"}),
                    "moneda": marcas(trimestres, "moneda_origen", {"USD": "U", "ARS": "A", "otro": "-"}),
                }
            )
        lineas.sort(key=lambda linea: linea["orden"])
        salida[estado] = {"titulo": TITULOS[estado], "lineas": lineas}

    return {
        "generado": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "moneda": "USD",
        "unidad": "millones",
        "trimestres": trimestres,
        "anios": anios,
        "estados": salida,
    }


def armar_segmentos(trimestres: list[str], anios: list[str]) -> dict:
    if not SEGMENTOS.exists():
        return {}
    datos = pd.read_parquet(SEGMENTOS)
    orden = [
        "Upstream", "Midstream y Downstream", "Downstream", "Industrialización",
        "Comercialización", "Gas y energía", "GNL y gas integrado", "Nuevas energías",
        "Administración central y otros", "Ajustes de consolidación", "Total",
    ]
    presentes = [s for s in orden if s in set(datos["segmento"])]

    bloques = {}
    for concepto, titulo in SEGMENTOS_CONCEPTOS.items():
        sub = datos[datos["concepto"] == concepto]
        if sub.empty:
            continue
        filas = []
        for segmento in presentes:
            grupo = sub[sub["segmento"] == segmento].set_index("periodo")["valor_musd"]
            if grupo.empty:
                continue
            filas.append(
                {
                    "segmento": segmento,
                    "trimestral": [redondear(grupo.get(p)) for p in trimestres],
                    "anual": [redondear(grupo.get(a)) for a in anios],
                }
            )
        bloques[concepto] = {"titulo": titulo, "filas": filas}

    return {
        "trimestres": trimestres,
        "anios": anios,
        "segmentos": presentes,
        "conceptos": bloques,
    }


def armar_comparables() -> dict:
    if not PEERS.exists() or not PEERS_META.exists():
        return {}
    tabla = pd.read_parquet(PEERS)
    meta = json.loads(PEERS_META.read_text(encoding="utf-8"))
    fichas = {f["ticker"]: f for f in meta.get("emisores", [])}

    precios = {}
    for ticker in list(fichas) + ["YPF"]:
        ruta = RAW / "market" / "stock" / f"{ticker}.json"
        if ruta.exists():
            serie = serie_yahoo(ruta, ticker)
            precios[ticker] = {"precio": round(float(serie.iloc[-1]), 2), "fecha": serie.index[-1].date().isoformat()}

    valores = {(f.ticker, f.concepto, int(f.anio)): float(f.valor_usd) for f in tabla.itertuples()}
    anios = sorted({a for _, _, a in valores if a >= 2022})

    emisores = []
    for ticker, ficha in sorted(fichas.items()):
        acciones = ficha.get("acciones")
        por_ads = ficha.get("acciones_por_ads") or 1
        emisores.append(
            {
                "ticker": ticker,
                "nombre": ficha.get("nombre", ticker),
                "adrs": acciones / por_ads if acciones else None,
                "acciones_por_adr": por_ads,
                "precio": precios.get(ticker, {}).get("precio"),
                "fecha_precio": precios.get(ticker, {}).get("fecha"),
                "ultimo_ejercicio": ficha.get("ultimo_20f"),
                "ejercicios": {
                    str(anio): {
                        concepto: round(valores[(ticker, concepto, anio)] / 1e6, 1)
                        for concepto in {c for t, c, a in valores if t == ticker and a == anio}
                        if (ticker, concepto, anio) in valores
                    }
                    for anio in anios
                    if (ticker, "ingresos", anio) in valores
                },
            }
        )

    return {"anios": [str(a) for a in anios], "emisores": emisores, "nota": meta.get("nota", "")}


def armar_deuda() -> dict:
    if not DEUDA.exists():
        return {}
    tabla = pd.read_parquet(DEUDA)
    meta = json.loads(DEUDA_META.read_text(encoding="utf-8")) if DEUDA_META.exists() else {}
    instrumentos = [
        {
            "clase": fila.clase or fila.mes_emision,
            "emitido": f"{fila.mes_emision} {fila.anio_emision}".strip(),
            "moneda": fila.moneda,
            "valor_nominal": redondear(fila.valor_nominal),
            "tasa": fila.tasa,
            "vencimiento": int(fila.vencimiento),
            "no_corriente": redondear(fila.no_corriente_musd),
            "corriente": redondear(fila.corriente_musd),
            "total": redondear(fila.total_musd),
        }
        for fila in tabla.itertuples()
    ]
    escalera = tabla.groupby("vencimiento")["total_musd"].sum().round(1)
    return {
        "presentado": meta.get("presentado"),
        "presentacion": meta.get("presentacion"),
        "total": round(float(tabla["total_musd"].sum()), 1),
        "escalera": [{"anio": int(a), "monto": float(v)} for a, v in escalera.items()],
        "instrumentos": instrumentos,
        "nota": meta.get("nota", ""),
    }


def armar_mercado(estados: dict) -> dict:
    """Lo que el navegador necesita para recalcular la valuación.

    Son los agregados de los últimos doce meses y los saldos del último
    trimestre; el resto —tasas, crecimiento, valor por boe— son supuestos que se
    mueven con los controles de la página.
    """
    datos = pd.read_parquet(ESTADOS)
    trimestres = estados["trimestres"]
    ultimos = trimestres[-4:]
    ultimo = trimestres[-1]

    def serie(estado: str, clave: str) -> pd.Series:
        sub = datos[(datos["estado"] == estado) & (datos["clave"] == clave) & (datos["tipo"] == "trimestre")]
        return sub.groupby("periodo")["valor_musd"].first()

    def udm(estado: str, clave: str) -> float | None:
        valores = serie(estado, clave)
        piezas = [valores.get(p) for p in ultimos]
        if any(p is None or pd.isna(p) for p in piezas):
            return None
        return round(float(sum(piezas)), 1)

    def saldo(clave: str) -> float | None:
        return redondear(serie("balance", clave).get(ultimo))

    depreciaciones = [
        udm("flujo", "depreciation of property plant and equipment | net cash flows from operating activities"),
        udm("flujo", "amortization of intangible assets | net cash flows from operating activities"),
        udm("flujo", "depreciation of right of use assets | net cash flows from operating activities"),
    ]
    ebit = udm("resultados", "operating profit")
    ebitda = round(ebit + sum(d for d in depreciaciones if d), 1) if ebit is not None else None

    precio = serie_yahoo(RAW / "market" / "stock" / "YPF.json", "ypf")
    embi = None
    ruta_embi = RAW / "macro" / "country-risk" / "embi.json"
    if ruta_embi.exists():
        payload = json.loads(ruta_embi.read_text(encoding="utf-8"))
        serie_embi = payload.get("serie") if isinstance(payload, dict) else payload
        if serie_embi:
            embi = float(serie_embi[-1].get("valor") or 0)

    reservas = None
    if RESERVAS.exists():
        payload = json.loads(RESERVAS.read_text(encoding="utf-8"))
        ultimo_anio = payload.get("ultimo_anio")
        for fila in payload.get("por_operador", []):
            if fila.get("anio") == ultimo_anio and str(fila.get("operador", "")).upper().startswith("YPF"):
                reservas = {"anio": ultimo_anio, "mmboe": round(float(fila["comprobadas_mboe"]) / 1000, 1)}
                break

    valor_boe = None
    if ECONOMIA.exists():
        payload = json.loads(ECONOMIA.read_text(encoding="utf-8"))
        for fila in payload.get("por_operador", []):
            if str(fila.get("operador", "")).upper().startswith("YPF") and fila.get("eur_bbl_mediana"):
                valor_boe = round(float(fila["npv_musd_mediano"]) * 1e6 / float(fila["eur_bbl_mediana"]), 2)
                break

    # La serie del múltiplo al que cotizó cada trimestre: es la que da la
    # referencia del método de múltiplo histórico.
    multiplos = []
    for i, periodo in enumerate(trimestres):
        if i < 3:
            continue
        ventana = trimestres[i - 3 : i + 1]
        piezas_ebit = [serie("resultados", "operating profit").get(p) for p in ventana]
        piezas_dep = [
            sum(
                filter(
                    None,
                    [
                        serie("flujo", f"{c} | net cash flows from operating activities").get(p)
                        for c in (
                            "depreciation of property plant and equipment",
                            "amortization of intangible assets",
                            "depreciation of right of use assets",
                        )
                    ],
                )
            )
            for p in ventana
        ]
        if any(v is None or pd.isna(v) for v in piezas_ebit):
            continue
        ebitda_udm = float(sum(piezas_ebit)) + float(sum(piezas_dep))
        deuda = serie("balance", "loans | total non current liabilities").get(periodo)
        deuda_corriente = serie("balance", "loans | total current liabilities").get(periodo)
        caja = serie("balance", "cash and cash equivalents | total current assets").get(periodo)
        if any(v is None or pd.isna(v) for v in (deuda, deuda_corriente, caja)) or ebitda_udm <= 0:
            continue
        cierre = pd.Period(periodo, freq="Q").end_time
        previos = precio[precio.index <= cierre]
        if not len(previos):
            continue
        capitalizacion = float(previos.iloc[-1]) * 393_312_793 / 1e6
        ev = capitalizacion + float(deuda) + float(deuda_corriente) - float(caja)
        multiplos.append({"periodo": periodo, "ev_ebitda": round(ev / ebitda_udm, 2),
                          "precio": round(float(previos.iloc[-1]), 2)})

    return {
        "trimestre": ultimo,
        "precio_adr": round(float(precio.iloc[-1]), 2),
        "fecha_precio": precio.index[-1].date().isoformat(),
        "adrs": 393_312_793,
        "acciones_por_adr": 10,
        "riesgo_pais_pb": embi,
        "reservas": reservas,
        "valor_boe_pozo": valor_boe,
        "udm": {
            "ingresos": udm("resultados", "revenues"),
            "ebit": ebit,
            "ebitda": ebitda,
            "resultado_neto": udm("resultados", "net profit"),
            "antes_impuesto": udm("resultados", "net profit before income tax"),
            "impuesto": udm("resultados", "income tax"),
            "costos_financieros": udm("resultados", "financial costs"),
            "flujo_operativo": udm("flujo", "net cash flows from operating activities"),
            "capex": udm(
                "flujo",
                "acquisition of property plant and equipment and intangible assets | net cash flows used in investing activities",
            ),
        },
        "balance": {
            "deuda_no_corriente": saldo("loans | total non current liabilities"),
            "deuda_corriente": saldo("loans | total current liabilities"),
            "caja": saldo("cash and cash equivalents | total current assets"),
            "inversiones_corrientes": saldo("investments in financial assets | total current assets"),
            "patrimonio": saldo("total shareholders equity"),
            "activos": saldo("total assets"),
        },
        "multiplos": multiplos,
    }


def main() -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.parse_args()

    estados = armar_estados()
    salidas = {
        "estados_web.json": estados,
        "segmentos_web.json": armar_segmentos(estados["trimestres"], estados["anios"]),
        "comparables_web.json": armar_comparables(),
        "deuda_web.json": armar_deuda(),
        "mercado_web.json": armar_mercado(estados),
    }

    total = 0
    for nombre, payload in salidas.items():
        if not payload:
            continue
        tamanio = save_json(payload, PROCESSED / nombre)
        total += tamanio
        log(f"{nombre}: {human(tamanio)}")

    lineas = sum(len(bloque["lineas"]) for bloque in estados["estados"].values())
    record(
        "transform/libro-web",
        rows=int(lineas),
        bytes=int(total),
        outputs=[rel(PROCESSED / nombre) for nombre in salidas],
        source=rel(ESTADOS),
        note=f"{lineas} líneas, {len(estados['trimestres'])} trimestres, para el módulo del sitio",
    )
    log(f"{lineas} líneas de estados · {human(total)} en total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
