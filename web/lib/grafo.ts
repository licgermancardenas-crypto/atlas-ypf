// Tipos y helpers del grafo de entidades.
//
// Sin imports de node: lo consumen componentes de cliente. La carga del JSON se
// hace por fetch desde el navegador y no por `cargar()` en el servidor, por la
// misma razón que el mapa: el grafo agregado son 128 KB que no tienen por qué
// viajar dentro del HTML de una página que quizá nadie scrollee hasta acá.

export type TipoEntidad = 'concesion' | 'yacimiento' | 'empresa' | 'pozo';

export interface NodoGrafo {
  id: string;
  type: TipoEntidad;
  label: string;
  props: Record<string, unknown>;
}

export interface AristaGrafo {
  source: string;
  target: string;
  type: 'titularidad' | 'contiene' | 'tiene_pozo' | 'operado_por';
  props?: { participacion_pct?: number };
}

export interface Grafo {
  generado: string;
  mes_referencia: string;
  unidades: Record<string, string>;
  advertencias: {
    pozos_sin_operadora_excluidos: number;
    concesiones_sin_titularidad: string[];
    criterio_match: string;
    produccion: string;
  };
  nodes: NodoGrafo[];
  edges: AristaGrafo[];
}

/** Fragmento con los pozos de una concesión, que se pide de a uno. */
export interface FragmentoPozos {
  concesion: string;
  nodes: NodoGrafo[];
  edges: AristaGrafo[];
}

// Un color por tipo, y son los mismos que usa el mapa para las mismas cosas:
// el oro es el pozo en los dos lados, el azul de marca la concesión. Que un
// yacimiento cambie de color al pasar del mapa al grafo obligaría a releer la
// leyenda dos veces para mirar lo mismo.
export const COLOR_TIPO: Record<TipoEntidad, string> = {
  concesion: '#0054eb',
  yacimiento: '#4d90ff',
  empresa: '#3fb98a',
  pozo: '#f0a830',
};

export const ETIQUETA_TIPO: Record<TipoEntidad, string> = {
  concesion: 'Concesión',
  yacimiento: 'Yacimiento',
  empresa: 'Empresa',
  pozo: 'Pozo',
};

export const ETIQUETA_ARISTA: Record<AristaGrafo['type'], string> = {
  titularidad: 'Titular',
  contiene: 'Contiene',
  tiene_pozo: 'Pozo',
  operado_por: 'Operado por',
};

export function tipoDe(id: string): TipoEntidad | null {
  const tipo = id.split(':')[0];
  return tipo in COLOR_TIPO ? (tipo as TipoEntidad) : null;
}

/** Los vecinos directos de un nodo, con el tipo de relación que los une.
 *
 *  Es una pasada lineal sobre las aristas y no un índice precalculado: con
 *  10.400 aristas cuesta menos que mantener el índice sincronizado, y se
 *  recalcula solo cuando cambia el nodo seleccionado. */
export function vecinos(
  id: string,
  aristas: AristaGrafo[],
): { id: string; relacion: AristaGrafo['type']; pct?: number }[] {
  const salida: { id: string; relacion: AristaGrafo['type']; pct?: number }[] = [];
  const vistos = new Set<string>();

  for (const arista of aristas) {
    const otro =
      arista.source === id ? arista.target : arista.target === id ? arista.source : null;
    if (!otro || vistos.has(otro)) continue;
    vistos.add(otro);
    salida.push({ id: otro, relacion: arista.type, pct: arista.props?.participacion_pct });
  }
  return salida;
}

/** El grado de un nodo: cuántas aristas lo tocan. Es lo que dimensiona el
 *  círculo cuando la métrica elegida es "conexiones". */
export function grados(aristas: AristaGrafo[]): Map<string, number> {
  const cuenta = new Map<string, number>();
  for (const arista of aristas) {
    cuenta.set(arista.source, (cuenta.get(arista.source) ?? 0) + 1);
    cuenta.set(arista.target, (cuenta.get(arista.target) ?? 0) + 1);
  }
  return cuenta;
}

/** Producción del nodo en bbl/d, mirando la prop que corresponde a su tipo.
 *  Cada tipo la guarda con otro nombre porque significan cosas distintas: lo
 *  de una empresa es atribuido, lo de un área es total. */
export function produccionDe(nodo: NodoGrafo): number {
  const props = nodo.props;
  const valor =
    props.produccion_total_bbl_d ??
    props.produccion_bbl_d ??
    props.produccion_atribuida_bbl_d ??
    0;
  return typeof valor === 'number' ? valor : 0;
}
