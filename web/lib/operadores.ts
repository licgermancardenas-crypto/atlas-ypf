// Identidad de los operadores entre las rutas y los datos.
//
// El nombre comercial ("Pan American Energy") es lo que se muestra; el slug
// ("pan-american-energy") es lo que va en la URL. La conversión vive acá y no
// repartida por la página porque un slug que no coincide con el de la ruta es
// un 404 silencioso, y son dos lugares distintos los que lo generan: el que
// arma los links y el que declara las rutas estáticas.

export function aSlug(operador: string): string {
  return operador
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

/** Encuentra el operador cuyo slug coincide, sin depender de mayúsculas ni acentos. */
export function desdeSlug(slug: string, operadores: string[]): string | undefined {
  return operadores.find((operador) => aSlug(operador) === slug);
}
