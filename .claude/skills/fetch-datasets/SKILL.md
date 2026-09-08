---
name: fetch-datasets
description: Descarga y actualiza los datasets crudos del proyecto YPF (financieros, producción, mercado, macro, geoespaciales) hacia data/raw/
---

# fetch-datasets

## Instrucciones

Por cada dataset de la tabla de datasets del brief (sección 3), correr o crear el script
correspondiente en `pipeline/ingest/`, guardar en la ruta indicada, y loguear fecha de
descarga + nº de filas en `data/raw/_manifest.json`.

Si un script ya existe y el dataset tiene menos de 7 días de antigüedad según el manifest,
no lo vuelve a bajar salvo que se pida `--force`.

## Tabla de datasets

| # | Dataset | Fuente | Formato | Va a |
|---|---|---|---|---|
| 1 | Financieros YPF S.A. (trimestral) | SEC EDGAR 20-F/6-K + CNV | HTML/XBRL | `data/raw/financials/ypf/` |
| 2 | Financieros Vista Energy y Pampa Energía | SEC EDGAR + CNV | HTML/XBRL | `data/raw/financials/{vista,pampa}/` |
| 3 | Producción por pozo (Vaca Muerta, todas las operadoras) | datos.gob.ar / datos.energia.gob.ar | CSV | `data/raw/production/` |
| 4 | Precio acción YPF/YPFD | Yahoo Finance API | JSON/CSV | `data/raw/market/stock/` |
| 5 | Brent/WTI | Yahoo Finance o EIA | CSV | `data/raw/market/oil/` |
| 6 | Tipo de cambio ARS/USD | BCRA o Yahoo Finance | CSV | `data/raw/macro/fx/` |
| 7 | Comercio exterior energético | INDEC / Secretaría de Energía | CSV/XLSX | `data/raw/macro/trade/` |
| 8 | Riesgo país (EMBI Argentina) | Ámbito/JP Morgan (scraping o serie pública) | CSV | `data/raw/macro/country-risk/` |
| 9 | Concesiones, cuencas y pozos geolocalizados | datos.gob.ar (mapa de hidrocarburos) | Shapefile/GeoJSON | `data/raw/geo/concessions/` |
| 10 | Límites provinciales/departamentales | IGN | Shapefile | `data/raw/geo/boundaries/` |
| 11 | MDE-Ar (relieve) | IGN | GeoTIFF | `data/raw/geo/dem/` |
| 12 (opcional) | Luces nocturnas VIIRS | NASA/NOAA (eogdata.mines.edu) | Raster | `data/raw/geo/nightlights/` |
| 13 (opcional) | Producción Permian Basin (benchmark) | EIA | CSV | `data/raw/benchmark/permian/` |

## Prioridad de ingesta

No bajar todo de una. Priorizar los datasets 1, 3, 4 y 5 (financiero + operativo + mercado
core); el resto puede esperar a las fases 4-5 del proyecto.

## Convenciones

- Un script por fuente en `pipeline/ingest/`, nunca mezclados.
- Los datos crudos jamás se commitean: `data/raw/` está en `.gitignore`.
- Cada script deja el crudo tal cual lo devuelve la fuente; la limpieza vive en
  `pipeline/transform/`.
