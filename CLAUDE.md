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
