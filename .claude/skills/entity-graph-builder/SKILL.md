---
name: entity-graph-builder
description: Construye y valida el grafo de concesiones, yacimientos, empresas y pozos que consume la vista de relaciones del frontend
---

# entity-graph-builder

## Instrucciones

Correr `pipeline/transform/entity_graph.py` y verificar que el grafo salió sano antes de
darlo por bueno.

1. **Correr el transform.** `python pipeline/transform/entity_graph.py` (agregar `--force`
   si el archivo ya existe y el panel no cambió). Escribe dos salidas:
   - `data/processed/graph/entities.json` — el grafo completo, con los pozos.
   - `data/processed/graph/entities_agregado.json` — el mismo grafo sin pozos, que es lo
     que la web carga por defecto.

2. **Validar integridad referencial.** El transform ya la corre antes de escribir y aborta
   con exit code 1 si falla, pero hay que confirmar que efectivamente corrió:
   - ninguna arista puede apuntar a un `source` o `target` que no esté en `nodes`;
   - ningún `id` de nodo puede repetirse;
   - tienen que existir nodos de los cuatro tipos (`concesion`, `yacimiento`, `empresa`,
     `pozo`).

3. **Reportar el conteo de nodos por tipo y las aristas por tipo.** El transform lo
   imprime al final; si los números se mueven fuerte contra la corrida anterior, decirlo
   en vez de dejarlo pasar. Referencia de la corrida de 2026-07: 5.350 nodos
   (5.062 pozos, 141 yacimientos, 102 concesiones, 45 empresas) y 10.403 aristas.

4. **Reportar aristas huérfanas si las hay.** Si aparece alguna, el archivo no se escribe:
   el trabajo es arreglar la causa, no bajar la validación.

5. **Fallar con mensaje claro si no está el dataset de titularidad.** Si
   `data/raw/geo/concessions/*.zip` no existe, el grafo se arma igual pero sin ninguna
   arista de tipo `titularidad`, y eso hay que decirlo explícitamente: un grafo de
   relaciones sin las participaciones cruzadas no contesta la pregunta para la que se
   hizo. La solución es correr antes `python pipeline/ingest/geo_layers.py`.

## Convenciones

- **La titularidad sale del padrón de Concesiones de Explotación que ya bajamos**
  (`data/raw/geo/concessions/`, campo `PARTICIPAC`). No hace falta un ingest nuevo, y
  agregarlo violaría la convención de un script por fuente.
- **El cruce de nombres es exacto, nunca difuso.** De las 102 concesiones con producción,
  88 pegan contra el padrón y 14 no. Los candidatos aproximados son áreas distintas
  ("BAJO DEL TORO" contra "BAJO DEL TORO NORTE", "CERRO ARENA" contra "CERRO BANDERA").
  Las que no pegan quedan sin aristas de titularidad, se listan en
  `advertencias.concesiones_sin_titularidad` y valen el 0,5% de la producción del mes.
  Si alguien propone bajar el umbral y usar fuzzy matching, la respuesta es no: este repo
  ya tuvo un bug así y le costó las reservas del país entero asignadas a un solo operador.
- **Un pozo sin empresa operadora se excluye y se loguea.** No entra al grafo con la
  empresa en null: una arista `operado_por` que apunta a la nada es exactamente lo que la
  validación de integridad existe para impedir.
- **El nombre de empresa pasa siempre por `canon_empresa`**, venga del panel de producción
  o del padrón de concesiones. La tabla de canonización se importa de
  `transform/production_wells.py`, no se copia: si las dos divergen, la misma compañía
  entra como dos nodos y el grafo miente sin dar síntoma.
- **Las métricas son del último mes del panel**, en bruto operado. La participación de los
  socios está incluida en el total del operador, igual que en el resto del proyecto.
- El chequeo `grafo de entidades` de `pipeline/checks.py` repite la validación sobre el
  archivo publicado y además verifica que las participaciones de cada concesión sumen
  100%. Si ese chequeo falla, el pipeline entero termina en rojo.
