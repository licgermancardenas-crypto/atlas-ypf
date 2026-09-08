---
name: scenario-engine
description: Construye y mantiene el módulo de simulación EBITDA (Brent, FX, producción → EBITDA proyectado) como función pura reusable en pipeline y frontend
---

# scenario-engine

## Instrucciones

A partir de los coeficientes de sensibilidad calculados en `ebitda_sensitivity.py`, expone
una función (Python para validar, y su equivalente TypeScript para el frontend) que dado
`{brent, fx, produccion_mbd}` devuelve `{ebitda_proyectado, margen, delta_vs_real}`.

Mantiene ambas versiones sincronizadas — si cambian los coeficientes en uno, actualiza el
otro.

## Convenciones

- La función es **pura**: mismos inputs → mismos outputs, sin side effects ni I/O.
- El simulador tiene que correr sin llamar a ningún backend: todo client-side.
- Los coeficientes son la única fuente de verdad compartida entre la versión Python y la
  TypeScript; si divergen, es un bug.
