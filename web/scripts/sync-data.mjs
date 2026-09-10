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

// El memo ejecutivo se copia por el mismo camino: vive en docs/ porque es un
// entregable del repo, pero la página lo renderiza y Next solo lee de public/.
const MEMO_ORIGEN = join(RAIZ, 'docs', 'memo_ejecutivo.md');
const MEMO_DESTINO = join(AQUI, '..', 'public', 'memo_ejecutivo.md');

// El libro de estados contables viaja por el mismo camino: el modulo /libro lo
// ofrece para descargar, y para eso tiene que estar servido desde public/.
const LIBRO_ORIGEN = join(RAIZ, 'docs', 'YPF_estados_financieros.xlsx');
const LIBRO_DESTINO = join(AQUI, '..', 'public', 'YPF_estados_financieros.xlsx');

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

if (await existe(MEMO_ORIGEN)) {
  await cp(MEMO_ORIGEN, MEMO_DESTINO);
  console.log('[sync-data] docs/memo_ejecutivo.md -> web/public/');
} else {
  console.warn('[sync-data] falta docs/memo_ejecutivo.md: la ruta /ypf-project/memo va a fallar');
}

if (await existe(LIBRO_ORIGEN)) {
  await cp(LIBRO_ORIGEN, LIBRO_DESTINO);
  const { size } = await stat(LIBRO_DESTINO);
  console.log(`[sync-data] docs/YPF_estados_financieros.xlsx -> web/public/ (${(size / 1024).toFixed(0)} KB)`);
} else {
  console.warn('[sync-data] falta el Excel de estados: el boton de descarga del modulo /libro va a dar 404');
}
