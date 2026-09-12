// El árbol territorial: provincia → cuenca → concesión → yacimiento.
//
// La pantalla ya podía contestar "cuánto produce cada provincia" y "cuánto
// produce cada concesión", pero como dos listas separadas: para saber qué hay
// adentro de Neuquén había que cambiar la dimensión, leer 52 concesiones y
// acordarse de cuáles eran neuquinas. Eso no es explorar un territorio, es
// consultar dos rankings y hacer el join a mano.
//
// Acá se arma el join una sola vez, en el servidor, con los mismos datos que ya
// publica el pipeline: las filas del ranking de concesiones y de yacimientos, y
// la ficha de cada una —que dice en qué provincia y en qué cuenca cae—.
//
// Dos decisiones que gobiernan el archivo:
//
//   · la concesión es la unidad atómica del árbol. Provincia y cuenca no toman
//     sus números del ranking propio sino de la suma de sus concesiones, aunque
//     el ranking propio exista. Es para que la rama cierre: si un nivel dice
//     420k boe/d, sus hijos tienen que sumar 420k y no 418k. Un árbol donde el
//     padre no es la suma de los hijos es un árbol en el que no se puede
//     confiar, y la diferencia —concesiones que cruzan un límite— es justamente
//     lo que el pie de la sección declara.
//   · el crecimiento de un nodo se recalcula desde los caudales sumados, actual
//     contra previo, y no promediando los crecimientos de los hijos. Un
//     promedio de porcentajes le da el mismo peso a un yacimiento de 300 boe/d
//     que a Loma Campana.

import type { FichaActivo, FilaRankingYPF, IdDimension, ProduccionYPF } from './produccion';

export type NivelTerritorio = 'compania' | 'provincia' | 'cuenca' | 'concesion' | 'yacimiento';

export interface NodoTerritorio {
  /** La ruta completa, que es lo que identifica al nodo: dos provincias pueden
   *  tener un yacimiento con el mismo nombre. */
  id: string;
  nombre: string;
  nivel: NivelTerritorio;
  actual_bd: number;
  previo_bd: number;
  delta_bd: number;
  crecimiento: number | null;
  oil_bd: number;
  gas_bd: number;
  shale_bd: number;
  convencional_bd: number;
  tight_bd: number;
  /** Sobre el total de la compañía, no sobre el padre. */
  participacion: number;
  /** Sobre el nodo que lo contiene: es lo que se dibuja en la barra. */
  peso: number;
  /** La dimensión del módulo de análisis que corresponde a este nodo, cuando
   *  existe: es lo que permite saltar del territorio a la ficha del activo. */
  dimension: IdDimension | null;
  localidad: string | null;
  /** Cuántos activos de cada clase cuelgan de acá abajo. Para el subtítulo. */
  cuenta: { concesiones: number; yacimientos: number };
  hijos: NodoTerritorio[];
}

const SIN_DATO = 'Sin declarar';

function numero(valor: number | null | undefined): number {
  return typeof valor === 'number' && Number.isFinite(valor) ? valor : 0;
}

/** Las cinco columnas que se suman igual en todos los niveles. */
function acumular(destino: NodoTerritorio, fila: NodoTerritorio) {
  destino.actual_bd += fila.actual_bd;
  destino.previo_bd += fila.previo_bd;
  destino.oil_bd += fila.oil_bd;
  destino.gas_bd += fila.gas_bd;
  destino.shale_bd += fila.shale_bd;
  destino.convencional_bd += fila.convencional_bd;
  destino.tight_bd += fila.tight_bd;
}

function vacio(id: string, nombre: string, nivel: NivelTerritorio): NodoTerritorio {
  return {
    id,
    nombre,
    nivel,
    actual_bd: 0,
    previo_bd: 0,
    delta_bd: 0,
    crecimiento: null,
    oil_bd: 0,
    gas_bd: 0,
    shale_bd: 0,
    convencional_bd: 0,
    tight_bd: 0,
    participacion: 0,
    peso: 0,
    dimension: null,
    localidad: null,
    cuenta: { concesiones: 0, yacimientos: 0 },
    hijos: [],
  };
}

function desdeFila(
  fila: FilaRankingYPF,
  ficha: FichaActivo | undefined,
  id: string,
  nivel: NivelTerritorio,
  dimension: IdDimension,
): NodoTerritorio {
  const nodo = vacio(id, fila.nombre, nivel);
  nodo.actual_bd = numero(fila.actual_bd);
  nodo.previo_bd = numero(fila.previo_bd);
  nodo.oil_bd = numero(fila.oil_bd);
  nodo.gas_bd = numero(fila.gas_bd);
  nodo.shale_bd = numero(fila.shale_bd);
  nodo.convencional_bd = numero(fila.convencional_bd);
  nodo.tight_bd = numero(fila.tight_bd);
  nodo.dimension = dimension;
  nodo.localidad = ficha?.localidad ?? null;
  return nodo;
}

/** Cierra un nodo: deltas, crecimiento, participaciones y orden de los hijos.
 *
 *  Se hace al final y no a medida que se acumula porque el crecimiento de un
 *  agregado no es acumulable: hay que tener los dos caudales completos. */
function cerrar(nodo: NodoTerritorio, totalCompania: number) {
  nodo.delta_bd = nodo.actual_bd - nodo.previo_bd;
  nodo.crecimiento = nodo.previo_bd > 0 ? nodo.actual_bd / nodo.previo_bd - 1 : null;
  nodo.participacion = totalCompania > 0 ? nodo.actual_bd / totalCompania : 0;
  nodo.hijos.sort((a, b) => b.actual_bd - a.actual_bd);
  for (const hijo of nodo.hijos) {
    hijo.peso = nodo.actual_bd > 0 ? hijo.actual_bd / nodo.actual_bd : 0;
    cerrar(hijo, totalCompania);
    // La cuenta sube desde abajo: una provincia no sabe cuántos yacimientos
    // tiene, sus concesiones sí.
    nodo.cuenta.concesiones += hijo.nivel === 'concesion' ? 1 : hijo.cuenta.concesiones;
    nodo.cuenta.yacimientos += hijo.nivel === 'yacimiento' ? 1 : hijo.cuenta.yacimientos;
  }
}

/** Arma el árbol completo desde los rankings y las fichas del pipeline.
 *
 *  Es una función pura y corre en el servidor: el cliente recibe el árbol ya
 *  hecho y no vuelve a cruzar 52 concesiones contra 111 yacimientos en cada
 *  render. */
export function armarTerritorio(datos: ProduccionYPF): NodoTerritorio {
  const concesiones = datos.rankings.concesion ?? [];
  const yacimientos = datos.rankings.yacimiento ?? [];
  const fichaConcesion = datos.meta?.concesion ?? {};
  const fichaYacimiento = datos.meta?.yacimiento ?? {};

  // Los yacimientos cuelgan de su concesión dominante, que es la que la ficha
  // ya eligió por volumen. Los que no la declaran quedan aparte y se ven: no se
  // reparten en silencio entre las demás.
  const porConcesion = new Map<string, FilaRankingYPF[]>();
  for (const fila of yacimientos) {
    const clave = fichaYacimiento[fila.nombre]?.concesion ?? SIN_DATO;
    const lista = porConcesion.get(clave);
    if (lista) lista.push(fila);
    else porConcesion.set(clave, [fila]);
  }

  const raiz = vacio('', datos.empresa || 'YPF', 'compania');

  for (const fila of concesiones) {
    const ficha = fichaConcesion[fila.nombre];
    const provinciaNombre = ficha?.provincia ?? SIN_DATO;
    const cuencaNombre = ficha?.cuenca ?? SIN_DATO;

    let provincia = raiz.hijos.find((nodo) => nodo.nombre === provinciaNombre);
    if (!provincia) {
      provincia = vacio(provinciaNombre, provinciaNombre, 'provincia');
      raiz.hijos.push(provincia);
    }
    let cuenca = provincia.hijos.find((nodo) => nodo.nombre === cuencaNombre);
    if (!cuenca) {
      cuenca = vacio(`${provinciaNombre}/${cuencaNombre}`, cuencaNombre, 'cuenca');
      provincia.hijos.push(cuenca);
    }

    const nodo = desdeFila(fila, ficha, `${cuenca.id}/${fila.nombre}`, 'concesion', 'concesion');
    for (const hijo of porConcesion.get(fila.nombre) ?? []) {
      nodo.hijos.push(
        desdeFila(
          hijo,
          fichaYacimiento[hijo.nombre],
          `${nodo.id}/${hijo.nombre}`,
          'yacimiento',
          'yacimiento',
        ),
      );
    }

    cuenca.hijos.push(nodo);
    acumular(cuenca, nodo);
    acumular(provincia, nodo);
    acumular(raiz, nodo);
  }

  cerrar(raiz, raiz.actual_bd);
  raiz.peso = 1;
  return raiz;
}

/** Sigue una ruta desde la raíz. Devuelve la cadena de nodos —que es la miga de
 *  pan— y no solo el último, porque la pantalla necesita las dos cosas. */
export function caminoDe(raiz: NodoTerritorio, ruta: string[]): NodoTerritorio[] {
  const camino = [raiz];
  let actual = raiz;
  for (const nombre of ruta) {
    const siguiente = actual.hijos.find((nodo) => nodo.nombre === nombre);
    if (!siguiente) break;
    camino.push(siguiente);
    actual = siguiente;
  }
  return camino;
}

export const ETIQUETA_NIVEL: Record<NivelTerritorio, { singular: string; hijos: string }> = {
  compania: { singular: 'Compañía', hijos: 'provincias' },
  provincia: { singular: 'Provincia', hijos: 'cuencas' },
  cuenca: { singular: 'Cuenca', hijos: 'concesiones' },
  concesion: { singular: 'Concesión', hijos: 'yacimientos' },
  yacimiento: { singular: 'Yacimiento', hijos: '' },
};
