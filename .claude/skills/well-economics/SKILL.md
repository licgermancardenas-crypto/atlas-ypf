---
name: well-economics
description: Fitea curvas de declive de Arps por pozo y calcula NPV, IRR y payback dado un set de supuestos de capex/opex/precio
---

# well-economics

## Instrucciones

Toma `data/processed/production_wells.parquet`, agrupa por pozo, fitea Arps (hiperbólica o
exponencial según mejor ajuste), y con los supuestos que le pases (capex inicial, opex/bbl,
precio) calcula el flujo de fondos y NPV/IRR/payback.

Output a `data/processed/well_economics.json`, con métricas también agregadas por yacimiento
y por operador.

## Detalle

1. **Curvas de declive (Arps)** — para cada pozo, ajustar el modelo de Arps:
   `q(t) = qi / (1 + b * Di * t) ^ (1/b)`
   - `b = 0` → exponencial, `0 < b < 1` → hiperbólica.
   - Elegir el mejor ajuste por criterio de error (RMSE/R²) y dejar registrados los
     parámetros `qi`, `Di`, `b` junto con la métrica de ajuste.
2. **Flujo de fondos** — proyectar producción con la curva ajustada, valuar a precio dado,
   restar opex/bbl y el capex inicial en t=0.
3. **Métricas** — NPV (a la tasa de descuento que se pase como supuesto), IRR y payback.
4. **Agregación** — repetir los agregados por yacimiento y por operador.

## Convenciones

- Todo el cálculo financiero vive en `pipeline/transform/`, testeado aparte del frontend.
- Los supuestos (capex, opex/bbl, precio, tasa de descuento) son parámetros explícitos,
  nunca constantes escondidas en el código.
