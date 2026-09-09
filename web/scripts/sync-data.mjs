// Copia data/processed/ a web/public/data/ antes de cada dev y de cada build.
//
// Por qué una copia y no leer la carpeta directamente: el frontend tiene que
// consumir data/processed (la convención del proyecto) pero esa carpeta vive
// fuera de web/, y Next sirve archivos estáticos solo desde public/. Un enlace
// simbólico funcionaría en local y no en el build de Vercel; copiar es explícito
// y funciona igual en los dos lados.
//
// La copia es material generado: web/public/data está en .gitignore y se rehace
// en cada build a partir del pipeline.

import { cp, mkdir, readdir, rm, stat } from 'node:fs/promises';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const AQUI = dirname(fileURLToPath(import.meta.url));
const RAIZ = join(AQUI, '..', '..');
const ORIGEN = join(RAIZ, 'data', 'processed');
const DESTINO = join(AQUI, '..', 'public', 'data');

// Solo lo que el navegador puede leer: los .parquet son intermedios del pipeline.
const EXTENSIONES = ['.json', '.geojson', '.png'];

async function existe(ruta) {
  try {
    await stat(ruta);
    return true;
  } catch {
    return false;
  }
}

async function copiar(origen, destino) {
  let copiados = 0;
  let bytes = 0;

  for (const entrada of await readdir(origen, { withFileTypes: true })) {
    const desde = join(origen, entrada.name);
    const hacia = join(destino, entrada.name);

    if (entrada.isDirectory()) {
      const resultado = await copiar(desde, hacia);
      copiados += resultado.copiados;
      bytes += resultado.bytes;
      continue;
    }
    if (!EXTENSIONES.some((ext) => entrada.name.endsWith(ext))) continue;
    if (entrada.name.startsWith('_')) continue; // manifiestos y resúmenes del pipeline

    await mkdir(dirname(hacia), { recursive: true });
    await cp(desde, hacia);
    copiados += 1;
    bytes += (await stat(hacia)).size;
  }

  return { copiados, bytes };
}

if (!(await existe(ORIGEN))) {
  console.error(
    `[sync-data] no existe ${relative(RAIZ, ORIGEN)}.\n` +
      '[sync-data] correr antes: python pipeline/run_all.py',
  );
  process.exit(1);
}

await rm(DESTINO, { recursive: true, force: true });
await mkdir(DESTINO, { recursive: true });

const { copiados, bytes } = await copiar(ORIGEN, DESTINO);
console.log(
  `[sync-data] ${copiados} archivos, ${(bytes / 1024 / 1024).toFixed(1)} MB -> web/public/data/`,
);
