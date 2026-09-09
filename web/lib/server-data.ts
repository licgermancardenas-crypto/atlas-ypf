// Lectura de los JSON del pipeline. Solo servidor: importa node:fs y por eso
// está separado de lib/data.ts, que comparten los componentes del cliente.
//
// Se leen del disco y no por HTTP porque durante el build todavía no hay
// servidor al que pedirle nada. Los archivos salen de data/processed/ y los
// copia scripts/sync-data.mjs a public/data/ antes de cada build.

import 'server-only';

import { readFile } from 'node:fs/promises';
import { join } from 'node:path';

const DIRECTORIO = join(process.cwd(), 'public', 'data');

export async function cargar<T>(archivo: string): Promise<T> {
  const ruta = join(DIRECTORIO, archivo);
  try {
    return JSON.parse(await readFile(ruta, 'utf-8')) as T;
  } catch (error) {
    throw new Error(
      `No se pudo leer public/data/${archivo}. ` +
        'Correr "npm run sync-data" (y antes "python pipeline/run_all.py"). ' +
        `Detalle: ${(error as Error).message}`,
    );
  }
}
