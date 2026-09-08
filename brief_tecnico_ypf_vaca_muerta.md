# Brief técnico — Proyecto YPF / Vaca Muerta Intelligence

**Uso de este documento:** está pensado para pegarlo en tu repo y trabajarlo fase por fase con Claude Code en terminal. Cada fase tiene objetivo, inputs, outputs y el prompt que le tirás a Claude Code para arrancarla. Al final hay 5 skills reutilizables para crear en `.claude/skills/`.

---

## 0. La narrativa (no perder de vista esto)

Pregunta central: **¿por qué el mercado castigó a la acción de YPF pese al balance récord del Q2 2026?** (EBITDA US$2.804M, producción de shale oil +47% a 213.000 bbl/d, deuda en mínimo de 11 años, pero la acción cayó ~3,5% en Wall Street el día del reporte).

La respuesta se construye cruzando tres capas — financiera, operativa, mercado — más dos capas de contexto — macro/comercio exterior y geoespacial — y se remata con dos piezas de "producto": un simulador de escenarios interactivo y una economía de pozo (NPV/IRR). Todo esto vive en tu portfolio Next.js ya desplegado en Vercel, más una versión en Power BI para el público de finanzas.

---

## 1. Estructura de repo sugerida

```
atlas-ypf/
├── CLAUDE.md                     # contexto persistente del proyecto (ver sección 2)
├── .claude/
│   └── skills/                   # skills del proyecto (ver sección 6)
├── pipeline/
│   ├── ingest/                   # un script por fuente de datos
│   │   ├── financials_ypf.py
│   │   ├── financials_vista_pampa.py
│   │   ├── production_wells.py
│   │   ├── stock_prices.py
│   │   ├── brent_wti.py
│   │   ├── fx_ars_usd.py
│   │   ├── trade_balance_energy.py
│   │   ├── country_risk.py
│   │   └── geo_layers.py
│   ├── transform/                 # limpieza, joins, cálculo de métricas derivadas
│   │   ├── decline_curves.py       # Arps por pozo
│   │   ├── well_economics.py       # NPV/IRR/payback
│   │   ├── ebitda_sensitivity.py
│   │   └── scenario_engine.py
│   └── run_all.py                 # orquesta ingest + transform, es lo que corre GitHub Actions
├── data/
│   ├── raw/                       # nunca se commitea (gitignore)
│   └── processed/                 # JSON/Parquet livianos que consume el frontend
├── web/                           # app Next.js (o el módulo dentro de tu portfolio existente)
│   ├── app/ypf-project/           # ruta del caso de estudio
│   └── components/                # charts (Recharts), mapa (deck.gl/Mapbox)
├── powerbi/
│   └── ypf_dashboard.pbix
└── docs/
    └── memo_ejecutivo.md          # la "equity research note" de 1 página
```

---

## 2. `CLAUDE.md` — pegar en la raíz del repo

```markdown
# ATLAS-YPF

## Objetivo
Caso de estudio de portfolio: analizar por qué el mercado castigó a la acción de YPF
pese al balance récord del Q2 2026, cruzando datos financieros, operativos (producción
de Vaca Muerta), de mercado, macro y geoespaciales.

## Stack
- Pipeline de datos: Python (pandas, geopandas, statsmodels/prophet)
- Frontend: Next.js + React, Recharts para charts, deck.gl/Mapbox GL para el mapa 3D
- Deploy: Vercel (dentro del portfolio personal existente, ruta /ypf-project)
- Paralelo: Power BI para versión "corporativa"
- Automatización: GitHub Actions corriendo pipeline/run_all.py semanalmente

## Convenciones
- Los scripts de ingesta van uno por fuente en pipeline/ingest/, nunca mezclados
- Los datos crudos jamás se commitean (data/raw/ está en .gitignore)
- El frontend consume solo data/processed/*.json — nunca pega directo a las APIs
- Todo cálculo financiero (NPV/IRR/sensibilidad) vive en pipeline/transform/, testeado
  aparte del frontend
- Competidores de benchmark: solo YPF, Vista Energy (VIST) y Pampa Energía (PAM/PAMP)
  — son los únicos tres con disclosure financiero comparable

## Fuentes de datos (ver tabla completa en el brief)
Financieros: SEC EDGAR (20-F/6-K) + CNV
Producción por pozo: datos.gob.ar (Secretaría de Energía)
Geoespacial: IGN (MDE-Ar, límites), datos.gob.ar (concesiones/cuencas)
Mercado: Yahoo Finance (acción, Brent/WTI)
Macro: INDEC (comercio exterior energético), EMBI Argentina (riesgo país)
```

---

## 3. Tabla de datasets

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

---

## 4. Fases de construcción (el orden importa)

### Fase 0 — Setup
**Objetivo:** repo, CLAUDE.md, estructura de carpetas, skills creadas (vacías).
**Prompt para Claude Code:** *"Armá la estructura de carpetas de la sección 1 de este brief, creá el CLAUDE.md de la sección 2, y generá los 5 archivos SKILL.md de la sección 6 en `.claude/skills/`."*

### Fase 1 — Ingesta de datos
**Objetivo:** un script por fuente que baja y guarda crudo en `data/raw/`.
**Output:** 13 datasets crudos disponibles.
**Prompt:** *"Usá la skill fetch-datasets. Empezá por producción por pozo (dataset 3) y financieros de YPF (dataset 1) — son la columna vertebral del análisis."*
**Nota:** no bajes todo de una. Priorizá 1, 3, 4, 5 primero (financiero + operativo + mercado core); el resto puede esperar a la Fase 4-5.

### Fase 2 — Motor financiero y operativo
**Objetivo:** limpiar financieros, calcular EBITDA/márgenes por segmento, sensibilidad a Brent/FX; fitear curvas de Arps por pozo.
**Prompt:** *"Con los datos de production_wells.py ya bajados, usá la skill well-economics para fitear Arps por pozo y calcular NPV/IRR/payback con estos supuestos de capex/opex: [completar]. En paralelo, armá ebitda_sensitivity.py cruzando financials_ypf con brent_wti y fx_ars_usd."*

### Fase 3 — Motor de mercado y macro
**Objetivo:** cruzar movimiento de la acción con fechas de balance; EBITDA en USD vs. riesgo país; producción vs. balanza energética.
**Prompt:** *"Armá el cruce entre stock_prices y las fechas de reporte trimestral de financials_ypf (ventana de ±3 días). Después cruzá country_risk contra el spread de deuda de YPF que sacaste del 20-F."*

### Fase 4 — Motor geoespacial
**Objetivo:** procesar MDE-Ar, concesiones y pozos en capas listas para deck.gl.
**Prompt:** *"Usá la skill geo-layer-builder para generar el hillshade del MDE-Ar recortado a la cuenca Neuquina, y un GeoJSON de concesiones + pozos con producción como propiedad para colorear por volumen."*

### Fase 5 — Simulador de escenarios
**Objetivo:** módulo reusable que recalcula EBITDA proyectado en función de sliders (Brent, FX, producción).
**Prompt:** *"Usá la skill scenario-engine para exponer una función pura (inputs: brent, fx, produccion_mbd → output: ebitda_proyectado, margen) que el frontend pueda llamar en cada movimiento de slider sin ir al backend."*

### Fase 6 — Frontend integrador
**Objetivo:** página `/ypf-project` en tu portfolio Next.js, con: KPIs arriba, gráfico EBITDA vs. Brent, mapa 3D, simulador de escenarios, y el memo ejecutivo como sección final.
**Prompt:** *"Integrá los JSON de data/processed/ en una página nueva del portfolio en web/app/ypf-project/. Usá Recharts para los gráficos financieros y deck.gl para el mapa. Seguí la paleta y componentes que ya usás en el resto del portfolio."*

### Fase 7 — Automatización y cierre
**Objetivo:** GitHub Action que corre `pipeline/run_all.py` semanalmente; memo ejecutivo de una página; deploy final.
**Prompt:** *"Usá la skill refresh-pipeline para armar el workflow de GitHub Actions. Después escribí docs/memo_ejecutivo.md con la conclusión del análisis, en formato equity research note."*

---

## 5. Qué queda afuera (a propósito, no te desvíes)

- Financieros de Tecpetrol, PAE, Shell, Chevron (sin disclosure comparable)
- Imágenes satelitales ópticas (Sentinel-2, detección de cambios) — mucho esfuerzo para el objetivo actual
- Datos climáticos — solo si en el futuro hacés una v2 sobre el segmento de gas
- Radios censales — solo si sumás el "efecto Añelo" como sección extra

---

## 6. Skills para `.claude/skills/`

### `fetch-datasets/SKILL.md`
```yaml
name: fetch-datasets
description: Descarga y actualiza los datasets crudos del proyecto YPF (financieros, producción, mercado, macro, geoespaciales) hacia data/raw/
```
Instrucciones: por cada dataset de la tabla de la sección 3, correr o crear el script correspondiente en `pipeline/ingest/`, guardar en la ruta indicada, y loguear fecha de descarga + nº de filas en `data/raw/_manifest.json`. Si un script ya existe y el dataset tiene menos de 7 días de antigüedad según el manifest, no lo vuelve a bajar salvo que se pida `--force`.

### `well-economics/SKILL.md`
```yaml
name: well-economics
description: Fitea curvas de declive de Arps por pozo y calcula NPV, IRR y payback dado un set de supuestos de capex/opex/precio
```
Instrucciones: toma `data/processed/production_wells.parquet`, agrupa por pozo, fitea Arps (hiperbólica/exponencial según mejor ajuste), y con los supuestos que le pases (capex inicial, opex/bbl, precio) calcula el flujo de fondos y NPV/IRR/payback. Output a `data/processed/well_economics.json`, con métricas también agregadas por yacimiento y por operador.

### `geo-layer-builder/SKILL.md`
```yaml
name: geo-layer-builder
description: Procesa el MDE-Ar, las concesiones/cuencas y los pozos geolocalizados en capas GeoJSON/raster listas para deck.gl
```
Instrucciones: recorta el MDE-Ar a la extensión de la cuenca Neuquina, genera hillshade; convierte los shapefiles de concesiones y límites a GeoJSON (EPSG:4326); une la tabla de producción con las coordenadas de pozo para generar un GeoJSON de puntos con producción acumulada como propiedad. Todo a `data/processed/geo/`.

### `scenario-engine/SKILL.md`
```yaml
name: scenario-engine
description: Construye y mantiene el módulo de simulación EBITDA (Brent, FX, producción → EBITDA proyectado) como función pura reusable en pipeline y frontend
```
Instrucciones: a partir de los coeficientes de sensibilidad calculados en `ebitda_sensitivity.py`, expone una función (Python para validar, y su equivalente TypeScript para el frontend) que dado `{brent, fx, produccion_mbd}` devuelve `{ebitda_proyectado, margen, delta_vs_real}`. Mantiene ambas versiones sincronizadas — si cambian los coeficientes en uno, actualiza el otro.

### `refresh-pipeline/SKILL.md`
```yaml
name: refresh-pipeline
description: Arma y mantiene el workflow de GitHub Actions que corre pipeline/run_all.py periódicamente para mantener los datos actualizados
```
Instrucciones: genera `.github/workflows/refresh-data.yml` corriendo semanalmente (cron), ejecutando `pipeline/run_all.py`, y si hay cambios en `data/processed/`, commiteándolos automáticamente con un mensaje `chore: refresh data [skip ci]`. Alertá si algún script de ingesta falla (exit code ≠ 0) dejando el job en rojo en vez de fallar silenciosamente.

---

## 7. Checklist de cierre antes de mostrarlo

- [ ] Los 3 comparables (YPF, Vista, Pampa) tienen los mismos períodos fiscales alineados
- [ ] El simulador de escenarios corre sin llamar a ningún backend (todo client-side)
- [ ] El mapa carga en menos de 3 segundos (si el GeoJSON de pozos es muy pesado, simplificar geometría o clusterizar)
- [ ] El memo ejecutivo de una página está escrito y linkeado desde la página principal del caso
- [ ] El GitHub Action de refresh corrió al menos una vez sin errores
- [ ] Versión Power BI y versión web muestran los mismos números (reconciliar antes de publicar)
