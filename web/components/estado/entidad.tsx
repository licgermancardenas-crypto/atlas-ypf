'use client';

// La entidad seleccionada: el estado que comparten el grafo y el mapa.
//
// Es deliberadamente chico —un tipo y un id— porque es la única forma de que
// dos vistas que dibujan cosas distintas se entiendan. El grafo sabe de nodos y
// aristas; el mapa, de polígonos y puntos. Lo único que tienen en común es de
// qué entidad están hablando, y eso es exactamente lo que viaja acá.
//
// Va en la URL por la misma razón que los filtros: una vista tiene que ser un
// link. `?entity=yacimiento:loma-campana-loma-campana` abre la página con ese
// nodo seleccionado, el panel abierto y el mapa centrado, sin que nadie tenga
// que explicar dónde hacer clic.
//
// Se usa history.replaceState y no el router, igual que en filtros.tsx:
// useSearchParams obligaría a renderizar la página del lado del cliente y esta
// se prerenderiza entera.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { tipoDe, type TipoEntidad } from '@/lib/grafo';

export interface Entidad {
  type: TipoEntidad;
  id: string;
}

interface Contexto {
  entidad: Entidad | null;
  seleccionar: (id: string | null) => void;
  /** Lo pide el mapa: seleccionar por nombre cuando no se tiene el id armado. */
  seleccionarPorNombre: (tipo: TipoEntidad, nombre: string) => void;
}

const EntidadContexto = createContext<Contexto | null>(null);

const CLAVE = 'entity';

/** Mismo algoritmo que `slug()` en pipeline/transform/entity_graph.py.
 *
 *  Está duplicado a propósito y no es un descuido: el id lo genera Python y lo
 *  tiene que poder reconstruir el navegador cuando el mapa —que trae nombres,
 *  no ids— quiere seleccionar algo. La alternativa era mandar el id dentro de
 *  cada feature del GeoJSON, que son 5.000 strings repetidos para evitar diez
 *  líneas. Si una de las dos cambia, el síntoma es que el mapa deja de abrir el
 *  panel, y el chequeo `grafo de entidades` no lo ve: por eso queda anotado en
 *  los dos lados. */
export function aSlug(texto: string): string {
  return (
    texto
      .normalize('NFKD')
      // Tirar todo lo que no sea ASCII es exactamente lo que hace el
      // encode('ascii', 'ignore') del lado de Python. Después de la
      // descomposición NFKD eso deja "COMPAÑIA" como "COMPANIA": la eñe ya se
      // partió en N + tilde combinante, y acá se va la tilde sola.
      .replace(/[^\x00-\x7F]/g, '')
      .replace(/[^a-zA-Z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .toLowerCase() || 'sin-dato'
  );
}

export function idDe(tipo: TipoEntidad, nombre: string): string {
  return `${tipo}:${aSlug(nombre)}`;
}

function leerDeUrl(): Entidad | null {
  const valor = new URLSearchParams(window.location.search).get(CLAVE);
  if (!valor) return null;
  const tipo = tipoDe(valor);
  return tipo ? { type: tipo, id: valor } : null;
}

function escribirEnUrl(entidad: Entidad | null) {
  const params = new URLSearchParams(window.location.search);
  if (entidad) params.set(CLAVE, entidad.id);
  else params.delete(CLAVE);

  const consulta = params.toString();
  window.history.replaceState(
    null,
    '',
    `${window.location.pathname}${consulta ? `?${consulta}` : ''}${window.location.hash}`,
  );
}

export function ProveedorEntidad({ children }: { children: ReactNode }) {
  const [entidad, setEntidad] = useState<Entidad | null>(null);

  // Se lee al montar y no en el estado inicial: el servidor no tiene
  // querystring y pintaría otra cosa que el cliente, que es un error de
  // hidratación.
  useEffect(() => {
    const desdeUrl = leerDeUrl();
    if (desdeUrl) setEntidad(desdeUrl);
  }, []);

  const seleccionar = useCallback((id: string | null) => {
    setEntidad(() => {
      if (!id) {
        escribirEnUrl(null);
        return null;
      }
      const tipo = tipoDe(id);
      if (!tipo) return null;
      const siguiente = { type: tipo, id };
      escribirEnUrl(siguiente);
      return siguiente;
    });
  }, []);

  const seleccionarPorNombre = useCallback(
    (tipo: TipoEntidad, nombre: string) => seleccionar(idDe(tipo, nombre)),
    [seleccionar],
  );

  const valor = useMemo(
    () => ({ entidad, seleccionar, seleccionarPorNombre }),
    [entidad, seleccionar, seleccionarPorNombre],
  );

  return <EntidadContexto.Provider value={valor}>{children}</EntidadContexto.Provider>;
}

/** El hook no explota si no hay proveedor: devuelve un contexto inerte.
 *
 *  Es a propósito. El mapa lo usa y el mapa vive también en pantallas donde el
 *  grafo no está montado; hacer que reviente ahí obligaría a envolver medio
 *  árbol por una funcionalidad opcional. */
export function useEntidad(): Contexto {
  return (
    useContext(EntidadContexto) ?? {
      entidad: null,
      seleccionar: () => {},
      seleccionarPorNombre: () => {},
    }
  );
}
