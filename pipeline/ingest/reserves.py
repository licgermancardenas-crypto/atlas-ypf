"""Dataset 15 — Reservas comprobadas, probables y posibles.

Fuente: Secretaría de Energía, "Reservas de Petróleo y Gas". Un Excel por año,
con el detalle por operador, cuenca, provincia, concesión y yacimiento, abierto
en convencional / no convencional y en reservas comprobadas, probables, posibles
y recursos contingentes.

Para qué: con la producción sola se puede decir cuánto sale hoy; con las
reservas se puede decir cuánto queda, que es la pregunta que sigue. El cociente
entre las dos —la vida de reservas— es la métrica que separa a una compañía que
está creciendo de una que se está consumiendo el inventario, y es de lo primero
que mira alguien que analiza una petrolera.

Los archivos son chicos (unos 300 KB por año) pero cada uno es un Excel con
encabezados combinados de cuatro niveles: el trabajo está en el transform, no
acá.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    RAW,
    base_parser,
    download,
    http_session,
    human,
    is_fresh,
    log,
    record,
    rel,
    sha256,
)

DEST = RAW / "reserves"
BASE = (
    "http://www.energia.gob.ar/contenidos/archivos/Reorganizacion/informacion_del_mercado"
    "/mercado_hidrocarburos/informacion_estadistica/reservas"
)

# El nombre del archivo cambia de un año a otro: no hay convención, hay historia.
ARCHIVOS = {
    2024: "reservas_al_31-12-2024.zip",
    2023: "reservas_al_31-12-2023.zip",
    2022: "reservas_al_31-12-2022.zip",
    2021: "reservas_al_31-12-2021.zip",
    2020: "reservas_al_31-12-2020.zip",
    2019: "reservas_cpcy_al_31_12_2019.zip",
    2018: "reservas_hfvuy_31122018.zip",
    2017: "Reservas_HFVUY_31122017.zip",
    2016: "Reservas_HFVUY_31122016.zip",
}


def bajar(anio: int, archivo: str, args) -> bool:
    key = f"reserves/{anio}"
    # Las reservas se publican una vez al año: pedirlas cada semana no tiene
    # sentido, así que el umbral de frescura es de medio año.
    if is_fresh(key, args.force, max(args.max_age_days, 180)):
        log(f"{anio}: fresco en el manifest, se saltea (--force para rebajar)")
        return False

    url = f"{BASE}/{archivo}"
    destino = DEST / f"{anio}.zip"
    download(url, destino, session=http_session())
    size = destino.stat().st_size

    record(
        key,
        dataset_id=15,
        source="Secretaria de Energia, Reservas de Petroleo y Gas",
        anio=anio,
        url=url,
        path=rel(destino),
        bytes=size,
        sha256=sha256(destino),
    )
    log(f"{anio}: {human(size)} -> {rel(destino)}")
    return True


def main() -> int:
    args = base_parser("Baja los informes anuales de reservas").parse_args()

    bajados, fallidos = 0, []
    for anio, archivo in ARCHIVOS.items():
        try:
            if bajar(anio, archivo, args):
                bajados += 1
        except Exception as exc:  # noqa: BLE001 - un año roto no corta el resto
            log(f"{anio}: FALLO {exc}")
            fallidos.append(str(anio))

    log(f"listo: {bajados}/{len(ARCHIVOS)} años bajados")
    if fallidos:
        log(f"ATENCION: fallaron {', '.join(fallidos)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
