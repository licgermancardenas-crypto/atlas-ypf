---
name: refresh-pipeline
description: Arma y mantiene el workflow de GitHub Actions que corre pipeline/run_all.py periódicamente para mantener los datos actualizados
---

# refresh-pipeline

## Instrucciones

Genera `.github/workflows/refresh-data.yml` corriendo semanalmente (cron), ejecutando
`pipeline/run_all.py`, y si hay cambios en `data/processed/`, commiteándolos automáticamente
con un mensaje `chore: refresh data [skip ci]`.

Alertá si algún script de ingesta falla (exit code ≠ 0) dejando el job en rojo en vez de
fallar silenciosamente.

## Convenciones

- Solo se commitea `data/processed/`; `data/raw/` está en `.gitignore` y nunca entra al repo.
- Nada de `|| true` ni de swallow de errores: un ingest que falla tiene que romper el job.
