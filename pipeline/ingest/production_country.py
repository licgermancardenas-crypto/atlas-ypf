"""Dataset 14 — Producción nacional de petróleo y gas (SESCO + capítulo IV).

Fuente: datos.energia.gob.ar, series "Producción sesco + Tight y Shale capítulo
IV", abiertas por cuenca, provincia, empresa y yacimiento, más el total país.

Qué agrega sobre lo que ya había: el pipeline venía ingiriendo solo el no
convencional. Estas series suman la producción **convencional**, y traen el
campo `concepto`, que separa convencional, shale y tight en la misma fila. Eso
es lo que permite contestar la pregunta incómoda del caso: cuando el shale de
YPF crece 47%, ¿la compañía crece o está compensando la caída de sus áreas
viejas?

Las series por yacimiento pesan unos 100 MB cada una. Se bajan igual: el crudo
nunca se commitea y en el refresco semanal vive en el caché de Actions, así que
el costo se paga una vez. Lo que llega al frontend son agregados de pocos cientos
de kilobytes.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    RAW,
    base_parser,
    count_csv_rows,
    download,
    http_session,
    human,
    is_fresh,
    log,
    record,
    rel,
    sha256,
)

DEST = RAW / "production" / "sesco"
PAQUETE = "590d1284-fd6d-4686-afd8-b3da5d90a6e9"
BASE = f"http://datos.energia.gob.ar/dataset/{PAQUETE}/resource"

# slug -> (id del recurso, nombre del archivo en el portal)
SERIES = {
    "oil_pais": (
        "f640943b-c049-4124-925c-6463c67b2e9a",
        "produccin-petrleo-sesco-tight-y-shale-captulo-iv-total-pais.csv",
    ),
    "oil_cuenca": (
        "aa524d41-f6b7-42dc-ae24-3b4a895002ab",
        "produccin-petrleo-sesco-tight-y-shale-captulo-iv-por-cuenca.csv",
    ),
    "oil_provincia": (
        "86270da2-6292-4719-b7c1-20671ff9ae40",
        "produccin-petrleo-sesco-tight-y-shale-captulo-iv-por-provincia.csv",
    ),
    "oil_empresa": (
        "4cc61040-aa44-440d-a912-91bd6c26b8a7",
        "produccin-petrleo-sesco-tight-y-shale-captulo-iv-por-empresa.csv",
    ),
    "oil_yacimiento": (
        "83a2b597-b087-4815-b17d-cd70990d6a79",
        "produccin-petrleo-sesco-tight-y-shale-captulo-iv-por-yacimiento.csv",
    ),
    "gas_pais": (
        "39eff4aa-dac1-4df0-bd0a-7e6d2853d169",
        "produccin-gas-sesco-tight-y-shale-captulo-iv-total-pais.csv",
    ),
    "gas_cuenca": (
        "f44d3962-08ce-48e8-b2e3-88f65e1dcb77",
        "produccin-gas-sesco-tight-y-shale-captulo-iv-por-cuenca.csv",
    ),
    "gas_provincia": (
        "ad1b9472-a370-47e7-8de3-b742495ec7f1",
        "produccin-gas-sesco-tight-y-shale-captulo-iv-por-provincia.csv",
    ),
    "gas_empresa": (
        "63129e00-6a96-4d6e-9ce1-9e6c60287e16",
        "produccin-gas-sesco-tight-y-shale-captulo-iv-por-empresa.csv",
    ),
    "gas_yacimiento": (
        "931cfb07-37b7-414a-ae8b-528dff6f9f14",
        "produccin-gas-sesco-tight-y-shale-captulo-iv-por-yacimiento.csv",
    ),
}


def bajar(slug: str, recurso: str, archivo: str, args) -> bool:
    key = f"production/sesco/{slug}"
    if is_fresh(key, args.force, args.max_age_days):
        log(f"{slug}: fresco en el manifest, se saltea (--force para rebajar)")
        return False

    url = f"{BASE}/{recurso}/download/{archivo}"
    destino = DEST / f"{slug}.csv"
    download(url, destino, session=http_session())

    filas = count_csv_rows(destino)
    size = destino.stat().st_size
    record(
        key,
        dataset_id=14,
        source="datos.energia.gob.ar (SESCO + capitulo IV)",
        package=PAQUETE,
        resource_id=recurso,
        url=url,
        path=rel(destino),
        rows=filas,
        bytes=size,
        sha256=sha256(destino),
    )
    log(f"{slug}: {filas:,} filas, {human(size)} -> {rel(destino)}")
    return True


def main() -> int:
    args = base_parser("Baja las series SESCO de produccion nacional").parse_args()

    bajados, fallidos = 0, []
    for slug, (recurso, archivo) in SERIES.items():
        try:
            if bajar(slug, recurso, archivo, args):
                bajados += 1
        except Exception as exc:  # noqa: BLE001 - una serie rota no corta el resto
            log(f"{slug}: FALLO {exc}")
            fallidos.append(slug)

    log(f"listo: {bajados}/{len(SERIES)} series bajadas")
    if fallidos:
        log(f"ATENCION: fallaron {', '.join(fallidos)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
