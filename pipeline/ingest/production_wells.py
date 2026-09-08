"""Dataset 3 — Producción por pozo (Vaca Muerta, todas las operadoras).

Fuente: datos.energia.gob.ar, dataset "Producción de petróleo y gas por pozo
(Capítulo IV)" (package c846e79c-026c-4040-897f-1ad3543b407c).

Baja a data/raw/production/. El núcleo del análisis son cuatro recursos:

  no_convencional  producción mensual por pozo de shale/tight — la columna
                   vertebral de Vaca Muerta;
  padron_pozos     fecha de primera producción por pozo — sin esto no hay t=0
                   para fitear las curvas de Arps;
  pozos_cap_iv     atributos de pozo (operadora, yacimiento, cuenca, tipo);
  listado_pozos    listado declarado por las empresas operadoras.

Con --all-years suma la serie anual completa (convencional + no convencional),
que es mucho más pesada y recién hace falta para comparaciones fuera de shale.
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
    human,
    http_session,
    is_fresh,
    log,
    record,
    rel,
    sha256,
)

PACKAGE = "c846e79c-026c-4040-897f-1ad3543b407c"
BASE = f"http://datos.energia.gob.ar/dataset/{PACKAGE}/resource"
DEST = RAW / "production"

CORE = {
    "no_convencional": (
        "b5b58cdc-9e07-41f9-b392-fb9ec68b0725",
        "produccin-de-pozos-de-gas-y-petrleo-no-convencional.csv",
    ),
    "padron_pozos": (
        "5578dd48-d0dd-487e-8ddc-bd3ebb1afef0",
        "padrn-de-pozos-de-captulo-iv-con-fecha-de-primera-produccin.csv",
    ),
    "pozos_cap_iv": (
        "cb5c0f04-7835-45cd-b982-3e25ca7d7751",
        "capitulo-iv-pozos.csv",
    ),
    "listado_pozos_operadoras": (
        "cbfa4d79-ffb3-4096-bab5-eb0dde9a8385",
        "listado-de-pozos-cargados-por-empresas-operadoras.csv",
    ),
}

# Serie anual (convencional + no convencional), solo con --all-years.
BY_YEAR = {
    "2026": ("fb7a47a0-cba9-4667-a004-6f6c1c346c23", "produccin-de-pozos-de-gas-y-petrleo-2026.csv"),
    "2025": ("6f9f63bd-3f7e-43ab-8743-85997ae1380c", "produccin-de-pozos-de-gas-y-petrleo-2025.csv"),
    "2024": ("94d82d18-488b-434c-806d-ee5e053ce1cd", "produccin-de-pozos-de-gas-y-petrleo-2024.csv"),
    "2023": ("231c39b3-e81e-4398-af8d-b115807f2c25", "produccin-de-pozos-de-gas-y-petrleo-2023.csv"),
    "2022": ("876b3746-85e2-4039-adeb-b1354436159f", "produccin-de-pozos-de-gas-y-petrleo-2022.csv"),
    "2021": ("465be754-a372-4c31-b855-81dc5fe3309f", "produccin-de-pozos-de-gas-y-petrleo-2021.csv"),
    "2020": ("c4a4a6a0-e75a-4e12-ae5c-54d53a70348c", "produccin-de-pozos-de-gas-y-petrleo-2020.csv"),
    "2019": ("8bc0d61c-0408-43d4-a7bc-7178fcb5d37e", "produccin-de-pozos-de-gas-y-petrleo-2019.csv"),
    "2018": ("333fd72a-9b83-4bc1-bc94-0f5940b52331", "produccin-de-pozos-de-gas-y-petrleo-2018.csv"),
}


def fetch(name: str, resource_id: str, filename: str, session, args) -> bool:
    key = f"production/{name}"
    if is_fresh(key, args.force, args.max_age_days):
        log(f"{name}: fresco en el manifest, se saltea (--force para rebajar)")
        return False

    url = f"{BASE}/{resource_id}/download/{filename}"
    dest = DEST / f"{name}.csv"
    log(f"{name}: bajando...")
    download(url, dest, session=session)

    size = dest.stat().st_size
    rows = count_csv_rows(dest)
    record(
        key,
        dataset_id=3,
        source="datos.energia.gob.ar",
        package=PACKAGE,
        resource_id=resource_id,
        url=url,
        path=rel(dest),
        rows=rows,
        bytes=size,
        sha256=sha256(dest),
    )
    log(f"{name}: {rows:,} filas, {human(size)} -> {rel(dest)}")
    return True


def main() -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument(
        "--all-years",
        action="store_true",
        help="suma la serie anual completa (convencional incluido), mucho más pesada",
    )
    args = parser.parse_args()

    targets = dict(CORE)
    if args.all_years:
        targets.update({f"anual_{year}": res for year, res in BY_YEAR.items()})

    session = http_session()
    bajados = 0
    for name, (resource_id, filename) in targets.items():
        if fetch(name, resource_id, filename, session, args):
            bajados += 1

    log(f"listo: {bajados}/{len(targets)} recursos bajados")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
