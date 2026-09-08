---
name: geo-layer-builder
description: Procesa el MDE-Ar, las concesiones/cuencas y los pozos geolocalizados en capas GeoJSON/raster listas para deck.gl
---

# geo-layer-builder

## Instrucciones

- Recorta el MDE-Ar a la extensión de la cuenca Neuquina y genera el hillshade.
- Convierte los shapefiles de concesiones y límites a GeoJSON (EPSG:4326).
- Une la tabla de producción con las coordenadas de pozo para generar un GeoJSON de puntos
  con producción acumulada como propiedad (para colorear por volumen).

Todo a `data/processed/geo/`.

## Convenciones

- Salida siempre en EPSG:4326 — es lo que consume deck.gl / Mapbox GL.
- El mapa tiene que cargar en menos de 3 segundos: si el GeoJSON de pozos queda muy pesado,
  simplificar geometría o clusterizar.
- El frontend consume solo lo que quede en `data/processed/` — nunca pega directo a las
  fuentes.
