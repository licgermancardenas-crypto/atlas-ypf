"""El perfil de deuda de YPF: instrumento por instrumento y por año de vencimiento.

Para un emisor argentino, el riesgo no es el nivel de deuda sino cuándo vence.
Un ratio de deuda neta sobre EBITDA de 1,1x dice poco si adentro hay un bono de
mil millones que vence el año que viene y el mercado de crédito está cerrado.
El total ya está en el balance; lo que falta —y está en la nota de préstamos—
es la escalera: qué instrumento, a qué tasa, en qué moneda y contra qué año.

Se lee la última presentación disponible, no la serie histórica: el perfil es
una foto, y la foto que importa es la de hoy.

Entrada:  data/raw/financials/ypf/filings/*/   (los baja ingest/financials_ypf.py)
Salidas:  data/processed/debt_ypf.parquet      (un instrumento por fila)
          data/processed/debt_ypf.json         (escalera por año y resumen)
"""

from __future__ import annotations

import io
import json
import re
import sys
import warnings
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
from statements_ypf import a_numero, limpiar  # noqa: E402

FILINGS = RAW / "financials" / "ypf" / "filings"
OUT_LONG = PROCESSED / "debt_ypf.parquet"
OUT_JSON = PROCESSED / "debt_ypf.json"

# La tabla de la nota de préstamos: un instrumento por fila, con el año de
# vencimiento del capital y el saldo abierto en corriente y no corriente.
COLUMNAS = {
    "month": "mes_emision",
    "year": "anio_emision",
    "principal value": "valor_nominal",
    "class": "clase",
    "interest rate": "tasa",
    "principal maturity": "vencimiento",
    "non-current": "no_corriente",
    "current": "corriente",
}

RE_ANIO = re.compile(r"(20\d{2})")
MESES_EN = (
    "january february march april may june july august september october november december"
).split()


def _numero_suelto(celdas: list[str]) -> float:
    """El primer número de un grupo donde también viaja texto.

    La columna del valor nominal trae la moneda y el importe pegados —"U.S.
    dollar 644"—, así que concatenar el grupo entero no da un número.
    """
    for celda in celdas:
        valor = a_numero([celda])
        if not np.isnan(valor):
            return valor
    return float("nan")


def _moneda_de_celda(celdas: list[str]) -> str | None:
    texto = " ".join(celdas).lower()
    if "dollar" in texto:
        return "USD"
    if "peso" in texto:
        return "ARS"
    return None


def _es_mes(texto: str) -> bool:
    limpio = re.sub(r"[^a-z, ]", "", texto.lower())
    partes = [p.strip() for p in limpio.split(",") if p.strip()]
    return bool(partes) and all(p in MESES_EN for p in partes)


def _encabezado(tabla: pd.DataFrame) -> int | None:
    for i in range(min(6, len(tabla))):
        textos = " ".join(limpiar(v) for v in tabla.iloc[i]).lower()
        if "principal maturity" in textos:
            return i
    return None


def _grupos(tabla: pd.DataFrame, fila_encabezado: int) -> list[tuple[str, list]]:
    """Columnas agrupadas por encabezado, en el orden en que aparecen.

    "Non-current" y "Current" aparecen dos veces —una por cada fecha— y el par
    que vale es el primero, que es el del cierre más reciente.
    """
    grupos: list[tuple[str, list]] = []
    actual, columnas = None, []
    for columna in tabla.columns:
        texto = limpiar(tabla.iloc[fila_encabezado][columna])
        clave = re.sub(r"\(\d+\)", "", texto).strip().lower()
        if clave and clave != actual:
            if actual is not None:
                grupos.append((actual, columnas))
            actual, columnas = clave, [columna]
        elif actual is not None:
            columnas.append(columna)
    if actual is not None:
        grupos.append((actual, columnas))
    return grupos


def leer_tabla(tabla: pd.DataFrame, moneda: str) -> list[dict]:
    tabla = tabla.dropna(axis=1, how="all")
    fila_encabezado = _encabezado(tabla)
    if fila_encabezado is None:
        return []

    grupos = _grupos(tabla, fila_encabezado)
    mapa: dict[str, list] = {}
    vistos: set[str] = set()
    for clave, columnas in grupos:
        nombre = COLUMNAS.get(clave)
        if nombre is None or nombre in vistos:
            continue
        vistos.add(nombre)
        mapa[nombre] = columnas
    if "vencimiento" not in mapa or "no_corriente" not in mapa:
        return []

    primera = tabla.columns[0]
    filas: list[dict] = []
    emisor = "YPF"
    for i in range(fila_encabezado + 1, len(tabla)):
        etiqueta = limpiar(tabla.iloc[i][primera])
        valores = {
            nombre: [limpiar(tabla.iloc[i][c]) for c in columnas]
            for nombre, columnas in mapa.items()
        }
        vencimiento = "".join(valores.get("vencimiento", []))
        no_corriente = a_numero(valores.get("no_corriente", []))
        corriente = a_numero(valores.get("corriente", []))

        # Las filas que solo traen un nombre son el emisor del bloque: la nota
        # separa la deuda de YPF de la de sus controladas. Un mes suelto no es
        # un emisor: es una fila de instrumento que quedó partida.
        if etiqueta and not RE_ANIO.search(vencimiento) and np.isnan(no_corriente):
            if (
                len(etiqueta) < 40
                and not etiqueta.lower().startswith(("total", "class"))
                and not _es_mes(etiqueta)
            ):
                emisor = etiqueta
            continue

        anio = RE_ANIO.search(vencimiento)
        if not anio:
            continue
        if np.isnan(no_corriente) and np.isnan(corriente):
            continue

        filas.append(
            {
                "emisor": emisor,
                "mes_emision": etiqueta,
                "anio_emision": "".join(valores.get("anio_emision", [])),
                "moneda": _moneda_de_celda(valores.get("valor_nominal", [])) or moneda,
                "valor_nominal": _numero_suelto(valores.get("valor_nominal", [])),
                "clase": " ".join(v for v in valores.get("clase", []) if v).strip(),
                "tasa": " ".join(v for v in valores.get("tasa", []) if v).strip(),
                "vencimiento": int(anio.group(1)),
                "no_corriente_musd": 0.0 if np.isnan(no_corriente) else no_corriente,
                "corriente_musd": 0.0 if np.isnan(corriente) else corriente,
            }
        )
    return filas


def leer_filing(carpeta: Path) -> tuple[list[dict], dict]:
    from bs4 import BeautifulSoup

    meta = json.loads((carpeta / "_meta.json").read_text(encoding="utf-8"))
    for doc in sorted(carpeta.glob("*.htm"), key=lambda p: p.stat().st_size, reverse=True):
        if doc.stat().st_size < 300_000:
            continue
        sopa = BeautifulSoup(doc.read_text(encoding="utf-8", errors="replace"), "lxml")
        texto_documento = limpiar(sopa.get_text(" ")).lower()
        en_dolares = "expressed in millions of united states dollars" in texto_documento

        for tabla_html in sopa.find_all("table"):
            texto = limpiar(tabla_html.get_text(" "))
            if "Principal maturity" not in texto or "Class" not in texto:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    marcos = pd.read_html(io.StringIO(str(tabla_html)), flavor="lxml")
                except ValueError:
                    continue
            filas = leer_tabla(marcos[0], "USD" if en_dolares else "ARS")
            if filas:
                # La primera tabla que cierra es la de dólares: la de pesos
                # viene después y repite los mismos instrumentos.
                return filas, meta
    return [], meta


def recolectar() -> tuple[pd.DataFrame, dict]:
    """La nota de la presentación más reciente que la tenga."""
    carpetas = sorted(
        (p for p in FILINGS.iterdir() if (p / "_meta.json").exists()),
        key=lambda p: json.loads((p / "_meta.json").read_text(encoding="utf-8")).get("filing_date", ""),
        reverse=True,
    )
    for carpeta in carpetas:
        filas, meta = leer_filing(carpeta)
        if filas:
            log(f"{carpeta.name} ({meta.get('filing_date')}): {len(filas)} instrumentos")
            return pd.DataFrame(filas), meta
    raise SystemExit("no se encontró la nota de préstamos en ninguna presentación")


def main() -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.parse_args()

    tabla, meta = recolectar()
    tabla["total_musd"] = tabla["no_corriente_musd"] + tabla["corriente_musd"]
    tabla = tabla.sort_values(["vencimiento", "total_musd"], ascending=[True, False]).reset_index(drop=True)

    escalera = (
        tabla.groupby("vencimiento")["total_musd"].sum().round(1).astype(float).to_dict()
    )
    bytes_parquet = save_parquet(tabla, OUT_LONG)
    payload = {
        "generado": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "moneda": "USD",
        "unidad": "millones",
        "presentacion": meta.get("accession"),
        "presentado": meta.get("filing_date"),
        "instrumentos": int(len(tabla)),
        "total_musd": float(tabla["total_musd"].sum()),
        "corriente_musd": float(tabla["corriente_musd"].sum()),
        "escalera_por_anio": {str(k): v for k, v in escalera.items()},
        "emisores": sorted(tabla["emisor"].unique()),
        "nota": (
            "El año es el del vencimiento del capital del instrumento. Los bonos "
            "que amortizan en cuotas figuran enteros contra su último vencimiento, "
            "así que la escalera es un techo por año, no un calendario de pagos."
        ),
    }
    bytes_json = save_json(payload, OUT_JSON, indent=2)

    log(
        f"{len(tabla)} instrumentos, {tabla['total_musd'].sum():,.0f} MUSD, "
        f"vencimientos {tabla['vencimiento'].min()}–{tabla['vencimiento'].max()}"
    )
    record(
        "transform/deuda",
        rows=int(len(tabla)),
        bytes=int(bytes_parquet + bytes_json),
        outputs=[rel(OUT_LONG), rel(OUT_JSON)],
        source=rel(FILINGS),
        note=f"nota de préstamos de {meta.get('filing_date')}",
    )
    log(f"{rel(OUT_LONG)} ({human(bytes_parquet)}) · {rel(OUT_JSON)} ({human(bytes_json)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
