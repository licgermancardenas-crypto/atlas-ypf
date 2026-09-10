"""Catálogo del pipeline: qué datos entran, qué sale y cuándo se actualizó cada cosa.

Entrada: data/raw/_manifest.json, data/processed/_manifest.json y la definición
         de etapas de pipeline/run_all.py
Salida:  data/processed/catalogo.json

Por qué existe. Un caso de estudio que muestra conclusiones y esconde de dónde
salieron pide un acto de fe. Este módulo es lo contrario: la lista completa de
fuentes con su URL, cuántas filas trajo cada una, cuándo se bajó, qué transform
la consume y qué chequeos tiene que pasar antes de publicarse. Es la parte del
trabajo que normalmente no se ve, y en un portfolio es justamente la que
distingue a alguien que armó un pipeline de alguien que bajó un Excel.

Las etapas se leen importando run_all.py en vez de listarlas de nuevo: si mañana
se agrega un ingest, el catálogo lo muestra sin que nadie se acuerde de tocarlo.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    PROCESSED,
    RAW,
    ROOT,
    base_parser,
    human,
    log,
    record,
    rel,
    save_json,
)

MANIFIESTO_CRUDO = RAW / "_manifest.json"
MANIFIESTO_PROCESADO = PROCESSED / "_manifest.json"
SALIDA = PROCESSED / "catalogo.json"

# Nombre legible de cada fuente y de dónde sale. La clave es lo que el manifest
# guarda en `source`, que viene del script de ingesta.
FUENTES = {
    "SEC EDGAR": {
        "organismo": "Securities and Exchange Commission (EE.UU.)",
        "por_que": "Los estados contables de YPF: es emisor en NYSE y presenta 20-F y 6-K.",
    },
    "Yahoo Finance": {
        "organismo": "Yahoo Finance",
        "por_que": "Cotizaciones diarias de la acción, de los comparables, del crudo y del dólar.",
    },
    "datos.energia.gob.ar": {
        "organismo": "Secretaría de Energía de la Nación",
        "por_que": "Producción por pozo, concesiones, ductos y refinerías.",
    },
    "IGN": {
        "organismo": "Instituto Geográfico Nacional",
        "por_que": "Límites, rutas, localidades y cursos de agua del mapa.",
    },
    "Copernicus": {
        "organismo": "Agencia Espacial Europea",
        "por_que": "Modelo de elevación para el relieve de la cuenca.",
    },
    "ArgentinaDatos": {
        "organismo": "ArgentinaDatos (republica el EMBI+ de JP Morgan)",
        "por_que": "Riesgo país diario, para separar el descuento de la compañía del del país.",
    },
}


def familia(fuente: str) -> str:
    """Agrupa las variantes que escribe cada script bajo un nombre de fuente."""
    texto = (fuente or "").lower()
    if "sec" in texto or "edgar" in texto:
        return "SEC EDGAR"
    if "yahoo" in texto:
        return "Yahoo Finance"
    if "energia" in texto or "sesco" in texto or "secretaria" in texto:
        return "datos.energia.gob.ar"
    if "ign" in texto:
        return "IGN"
    if "copernicus" in texto:
        return "Copernicus"
    if "argentinadatos" in texto or "embi" in texto:
        return "ArgentinaDatos"
    return fuente or "Sin clasificar"


def leer(ruta: Path) -> dict:
    if not ruta.exists():
        return {}
    return json.loads(ruta.read_text(encoding="utf-8"))


def etapas_del_pipeline() -> list[dict]:
    """Las etapas tal como las declara run_all.py, sin repetirlas acá."""
    ruta = ROOT / "pipeline" / "run_all.py"
    if not ruta.exists():
        return []

    especificacion = importlib.util.spec_from_file_location("run_all", ruta)
    if not especificacion or not especificacion.loader:
        return []
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)

    etapas = []
    for tipo, lista in (("ingesta", modulo.INGEST_SCRIPTS), ("transform", modulo.TRANSFORM_SCRIPTS)):
        for nombre, script, _ in lista:
            etapas.append({"tipo": tipo, "nombre": nombre, "script": rel(Path(script))})
    return etapas


def nombres_de_chequeos() -> list[dict]:
    ruta = ROOT / "pipeline" / "checks.py"
    if not ruta.exists():
        return []
    especificacion = importlib.util.spec_from_file_location("checks", ruta)
    if not especificacion or not especificacion.loader:
        return []
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    chequeos = []
    for nombre, funcion in modulo.CHEQUEOS:
        doc = (funcion.__doc__ or "").strip().splitlines()
        chequeos.append({"nombre": nombre, "descripcion": doc[0].strip() if doc else ""})
    return chequeos


def main() -> int:
    args = base_parser("Arma el catalogo de datos del proyecto").parse_args()

    crudo = leer(MANIFIESTO_CRUDO)
    procesado = leer(MANIFIESTO_PROCESADO)
    if not crudo and not procesado:
        log("no hay manifiestos que catalogar; correr antes el pipeline")
        return 1

    if SALIDA.exists() and not args.force:
        fuentes_mtime = [p.stat().st_mtime for p in (MANIFIESTO_CRUDO, MANIFIESTO_PROCESADO) if p.exists()]
        if fuentes_mtime and SALIDA.stat().st_mtime > max(fuentes_mtime):
            log(f"{rel(SALIDA)} esta al dia, se saltea (--force para rehacer)")
            return 0

    crudos = []
    for clave, entrada in crudo.items():
        crudos.append(
            {
                "clave": clave,
                "fuente": familia(entrada.get("source", "")),
                "detalle": entrada.get("nombre") or entrada.get("indicador") or entrada.get("symbol"),
                "dataset_id": entrada.get("dataset_id"),
                "filas": entrada.get("rows"),
                "bytes": entrada.get("bytes"),
                "descargado": (entrada.get("downloaded_at") or "")[:19].replace("T", " "),
                "url": entrada.get("url"),
                "ruta": entrada.get("path"),
                # El hash permite verificar que el archivo del que salió una
                # conclusión es el mismo que está hoy en disco.
                "sha256": (entrada.get("sha256") or "")[:12] or None,
                "nota": entrada.get("sustituye"),
            }
        )
    crudos.sort(key=lambda fila: (fila["fuente"], fila["clave"]))

    procesados = []
    for clave, entrada in procesado.items():
        salidas = entrada.get("outputs") or ([entrada["path"]] if entrada.get("path") else [])
        bytes_totales = 0
        for salida in salidas:
            archivo = ROOT / salida
            if archivo.exists():
                bytes_totales += archivo.stat().st_size
        procesados.append(
            {
                "clave": clave,
                "generado": (entrada.get("generated_at") or "")[:19].replace("T", " "),
                "salidas": salidas,
                "bytes": bytes_totales,
                # Todo lo que no sea metadata de archivo es una métrica que el
                # transform decidió dejar registrada: cuántos pozos ajustó, qué
                # R2 le dio, cuántos trimestres cubrió.
                "metricas": {
                    k: v
                    for k, v in entrada.items()
                    if k not in {"generated_at", "outputs", "path", "source", "sources"}
                    and not isinstance(v, (dict, list))
                },
            }
        )
    procesados.sort(key=lambda fila: fila["clave"])

    por_fuente = (
        pd.DataFrame(crudos)
        .groupby("fuente")
        .agg(datasets=("clave", "count"), filas=("filas", "sum"), bytes=("bytes", "sum"))
        .reset_index()
        .sort_values("bytes", ascending=False)
    )
    fuentes = [
        {
            **fila,
            **FUENTES.get(fila["fuente"], {"organismo": fila["fuente"], "por_que": ""}),
        }
        for fila in por_fuente.to_dict("records")
    ]

    payload = {
        "generado": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "resumen": {
            "datasets_crudos": len(crudos),
            "salidas_procesadas": len(procesados),
            "fuentes": len(fuentes),
            "bytes_crudos": int(sum(f["bytes"] or 0 for f in crudos)),
            "bytes_procesados": int(sum(f["bytes"] for f in procesados)),
            "filas_crudas": int(sum(f["filas"] or 0 for f in crudos)),
        },
        "fuentes": fuentes,
        "crudos": crudos,
        "procesados": procesados,
        "etapas": etapas_del_pipeline(),
        "chequeos": nombres_de_chequeos(),
    }

    bytes_salida = save_json(payload, SALIDA)
    log(
        f"escrito {rel(SALIDA)} - {len(crudos)} crudos, {len(procesados)} procesados, "
        f"{human(bytes_salida)}"
    )

    record(
        "catalogo",
        sources=[rel(MANIFIESTO_CRUDO), rel(MANIFIESTO_PROCESADO)],
        outputs=[rel(SALIDA)],
        datasets_crudos=len(crudos),
        salidas_procesadas=len(procesados),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
