'use client';

// La vista de relaciones: el grafo, el panel y lo que los mantiene sincronizados.
//
// Acá vive la política de carga, que es lo que decide si esta sección se siente
// rápida o pesada:
//
//   1. Al abrir se baja el grafo agregado (128 KB, 288 nodos). Sin pozos.
//   2. Cuando alguien expande una concesión o un yacimiento, se baja el archivo
//      de pozos de esa concesión y de ninguna otra. Entre 5 y 200 KB.
//   3. Lo ya bajado queda en memoria: expandir, colapsar y volver a expandir no
//      pide nada de nuevo.
//
// Es el mismo criterio que el del mapa, y por el mismo motivo: bajar 2,5 MB
// para que alguien mire cuatro concesiones es hacerle pagar por adelantado un
// detalle que quizá no mire nunca.

import { useCallback, useEffect, useMemo, useState } from 'react';

import { EntityDrawer } from './EntityDrawer';
import { EntityGraph, type Dimension } from './EntityGraph';
import { aSlug, useEntidad } from './estado/entidad';
import { Esqueleto, SinDatos } from './Panel';
import { fmt } from '@/lib/data';
import type { AristaGrafo, FragmentoPozos, Grafo, NodoGrafo } from '@/lib/grafo';

const RUTA_AGREGADO = '/data/graph/entities_agregado.json';
const RUTA_POZOS = '/data/graph/pozos';

/** De qué concesión hay que pedir los pozos para expandir este nodo. Un
 *  yacimiento se resuelve con el archivo de su concesión, que ya los trae. */
function concesionDe(nodo: NodoGrafo): string | null {
  if (nodo.type === 'concesion') return nodo.id.slice('concesion:'.length);
  if (nodo.type === 'yacimiento' && typeof nodo.props.concesion === 'string') {
    return aSlug(nodo.props.concesion);
  }
  return null;
}

export function RedEntidades({ altura = 560 }: { altura?: number }) {
  const { entidad, seleccionar } = useEntidad();

  const [grafo, setGrafo] = useState<Grafo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dimension, setDimension] = useState<Dimension>('produccion');

  const [fragmentos, setFragmentos] = useState<Record<string, FragmentoPozos>>({});
  const [expandidas, setExpandidas] = useState<Set<string>>(new Set());
  const [bajando, setBajando] = useState<string | null>(null);

  useEffect(() => {
    let vigente = true;
    fetch(RUTA_AGREGADO)
      .then((respuesta) => {
        if (!respuesta.ok) throw new Error(`HTTP ${respuesta.status}`);
        return respuesta.json();
      })
      .then((datos: Grafo) => vigente && setGrafo(datos))
      .catch((causa) => vigente && setError((causa as Error).message));
    return () => {
      vigente = false;
    };
  }, []);

  // Lo agregado más lo que se haya expandido. El orden importa poco, pero que
  // los ids no se repitan importa mucho: un nodo duplicado hace que la
  // simulación lo trate como dos cuerpos y el grafo tiemble sin converger.
  const { nodos, aristas, indice } = useMemo(() => {
    const listaNodos: NodoGrafo[] = grafo ? [...grafo.nodes] : [];
    const listaAristas: AristaGrafo[] = grafo ? [...grafo.edges] : [];

    for (const clave of expandidas) {
      const fragmento = fragmentos[clave];
      if (!fragmento) continue;
      listaNodos.push(...fragmento.nodes);
      listaAristas.push(...fragmento.edges);
    }

    const mapa = new Map(listaNodos.map((nodo) => [nodo.id, nodo]));
    // Las aristas de un fragmento pueden tocar nodos de otro que no está
    // cargado (el `operado_por` de un pozo hacia una empresa siempre existe,
    // pero no al revés): se descartan las que no tienen los dos extremos.
    const limpias = listaAristas.filter(
      (arista) => mapa.has(arista.source) && mapa.has(arista.target),
    );
    return { nodos: [...mapa.values()], aristas: limpias, indice: mapa };
  }, [grafo, fragmentos, expandidas]);

  const seleccionado = entidad ? (indice.get(entidad.id) ?? null) : null;
  const seleccionAusente = Boolean(entidad && !seleccionado && bajando === null);

  const pedirFragmento = useCallback(
    async (clave: string) => {
      if (fragmentos[clave]) return;
      setBajando(clave);
      try {
        const respuesta = await fetch(`${RUTA_POZOS}/${clave}.json`);
        if (!respuesta.ok) throw new Error(`HTTP ${respuesta.status}`);
        const fragmento: FragmentoPozos = await respuesta.json();
        setFragmentos((previo) => ({ ...previo, [clave]: fragmento }));
      } catch (causa) {
        setError(`No se pudieron traer los pozos de ${clave}: ${(causa as Error).message}`);
      } finally {
        setBajando(null);
      }
    },
    [fragmentos],
  );

  // Qué concesión está expandida viaja en la URL, aparte de la entidad.
  //
  // Hace falta para que un link a un pozo funcione. El id de un pozo es
  // `pozo:126808` y no dice de qué concesión es, así que al abrir la página no
  // hay forma de saber qué archivo pedir: el nodo simplemente no existiría y el
  // panel quedaría vacío sin explicar por qué. Con `?conc=agua-del-cajon` al
  // lado, la página sabe qué bajar antes de buscar el nodo.
  //
  // La alternativa era un índice de 5.062 pozos a su concesión, o meter la
  // concesión adentro del id. Un parámetro de más en la URL es más barato que
  // las dos.
  useEffect(() => {
    const clave = new URLSearchParams(window.location.search).get('conc');
    if (!clave) return;
    void pedirFragmento(clave);
    setExpandidas((previo) => new Set(previo).add(clave));
    // Solo al montar: después manda lo que el usuario expande.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const primera = [...expandidas][0];
    if (primera) params.set('conc', primera);
    else params.delete('conc');
    const consulta = params.toString();
    window.history.replaceState(
      null,
      '',
      `${window.location.pathname}${consulta ? `?${consulta}` : ''}${window.location.hash}`,
    );
  }, [expandidas]);

  const alternarPozos = useCallback(async () => {
    if (!seleccionado) return;
    const clave = concesionDe(seleccionado);
    if (!clave) return;

    if (expandidas.has(clave)) {
      setExpandidas((previo) => {
        const copia = new Set(previo);
        copia.delete(clave);
        return copia;
      });
      return;
    }
    await pedirFragmento(clave);
    setExpandidas((previo) => new Set(previo).add(clave));
  }, [seleccionado, expandidas, pedirFragmento]);

  const claveActual = seleccionado ? concesionDe(seleccionado) : null;
  const pozosVisibles = Boolean(claveActual && expandidas.has(claveActual));

  if (error && !grafo) {
    return <SinDatos motivo={`No se pudo cargar el grafo de entidades. ${error}`} />;
  }
  if (!grafo) {
    return <Esqueleto alto={altura} />;
  }

  const totales = grafo.nodes.reduce<Record<string, number>>((cuenta, nodo) => {
    cuenta[nodo.type] = (cuenta[nodo.type] ?? 0) + 1;
    return cuenta;
  }, {});
  const pozosEnPantalla = nodos.length - grafo.nodes.length;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-texto-tenue">
          {fmt.entero(totales.concesion ?? 0)} concesiones · {fmt.entero(totales.yacimiento ?? 0)}{' '}
          yacimientos · {fmt.entero(totales.empresa ?? 0)} empresas
          {pozosEnPantalla > 0 ? (
            <span className="text-oro"> · {fmt.entero(pozosEnPantalla)} pozos expandidos</span>
          ) : null}{' '}
          · datos de {grafo.mes_referencia}
        </p>

        <div className="flex items-center gap-1.5">
          <span className="text-[0.7rem] text-texto-tenue">Tamaño por</span>
          <div className="flex rounded-md border border-borde p-0.5">
            {(
              [
                ['produccion', 'Producción'],
                ['conexiones', 'Conexiones'],
              ] as const
            ).map(([clave, etiqueta]) => (
              <button
                key={clave}
                type="button"
                onClick={() => setDimension(clave)}
                className={`rounded px-2 py-0.5 text-[0.7rem] transition ${
                  dimension === clave
                    ? 'bg-superficie-alta text-azul-claro'
                    : 'text-texto-tenue hover:text-texto-suave'
                }`}
              >
                {etiqueta}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-[1fr_20rem]">
        <EntityGraph
          nodos={nodos}
          aristas={aristas}
          seleccion={entidad?.id ?? null}
          onSeleccionar={seleccionar}
          dimension={dimension}
          altura={altura}
        />
        <div style={{ height: altura }}>
          <EntityDrawer
            nodo={seleccionado}
            nodos={indice}
            aristas={aristas}
            onSelect={seleccionar}
            onCerrar={() => seleccionar(null)}
            onVerPozos={alternarPozos}
            pozosVisibles={pozosVisibles}
            cargandoPozos={bajando !== null}
          />
        </div>
      </div>

      {seleccionAusente ? (
        <p className="text-xs text-texto-tenue">
          El link apunta a <span className="text-texto-suave">{entidad?.id}</span>, que no está
          entre los nodos cargados. Si es un pozo, al link le falta la concesión
          (<span className="font-mono">&amp;conc=…</span>): expandila desde su ficha y volvé a
          copiar la dirección.
        </p>
      ) : null}

      {error ? <p className="text-xs text-baja">{error}</p> : null}
    </div>
  );
}
