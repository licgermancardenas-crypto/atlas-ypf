'use client';

// El grafo de relaciones.
//
// Force-directed y no jerárquico a propósito: la estructura real no es un
// árbol. Una empresa participa de concesiones que opera otra, y esa es
// justamente la relación que ninguna de las otras vistas del proyecto muestra.
// Un layout de árbol tendría que elegir un padre y romper todos los cruces, que
// es lo único interesante que hay acá.
//
// Sobre la carga: por defecto entran concesiones, yacimientos y empresas —288
// nodos, 128 KB— y los pozos no. Los pozos son el 95% del grafo y el 95% del
// peso, y con la vista entera a la escala de la cuenca no se distingue uno de
// otro. Se piden de a una concesión cuando alguien la expande, que es la misma
// lección que ya se aplicó en el mapa.

import dynamic from 'next/dynamic';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  COLOR_TIPO,
  ETIQUETA_TIPO,
  grados,
  produccionDe,
  type AristaGrafo,
  type NodoGrafo,
  type TipoEntidad,
} from '@/lib/grafo';

const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { ssr: false });

export type Dimension = 'produccion' | 'conexiones';

interface NodoPintado {
  id: string;
  type: TipoEntidad;
  label: string;
  radio: number;
  x?: number;
  y?: number;
}

const FONDO = '#000d2d';

export function EntityGraph({
  nodos,
  aristas,
  seleccion,
  onSeleccionar,
  dimension,
  altura = 560,
}: {
  nodos: NodoGrafo[];
  aristas: AristaGrafo[];
  seleccion: string | null;
  onSeleccionar: (id: string | null) => void;
  dimension: Dimension;
  altura?: number;
}) {
  const contenedor = useRef<HTMLDivElement>(null);
  const [ancho, setAncho] = useState(0);

  useEffect(() => {
    const nodo = contenedor.current;
    if (!nodo) return;
    const medir = () => setAncho(nodo.clientWidth);
    medir();
    if (typeof ResizeObserver === 'undefined') return;
    const observador = new ResizeObserver(medir);
    observador.observe(nodo);
    return () => observador.disconnect();
  }, []);

  // El grafo se copia antes de entregárselo a la librería: force-graph le
  // escribe x/y/vx/vy a cada objeto que recibe, y si le pasáramos los nodos del
  // JSON estaríamos ensuciando la misma estructura que después usa el panel
  // para calcular vecinos.
  const datos = useMemo(() => {
    const conexiones = grados(aristas);
    const produccion = nodos.map(produccionDe);
    const maxProduccion = Math.max(...produccion, 1);
    const maxConexiones = Math.max(...conexiones.values(), 1);

    return {
      nodes: nodos.map((nodo, indice): NodoPintado => {
        const bruto =
          dimension === 'produccion'
            ? produccion[indice] / maxProduccion
            : (conexiones.get(nodo.id) ?? 0) / maxConexiones;
        return {
          id: nodo.id,
          type: nodo.type,
          label: nodo.label,
          // Raíz cuadrada: el área del círculo queda proporcional al valor. Con
          // escala lineal sobre el radio, Loma Campana taparía la mitad del
          // lienzo y el resto sería polvo.
          radio: 2.5 + Math.sqrt(Math.max(bruto, 0)) * 9,
        };
      }),
      links: aristas.map((arista) => ({
        source: arista.source,
        target: arista.target,
        type: arista.type,
      })),
    };
  }, [nodos, aristas, dimension]);

  // Los vecinos del seleccionado: lo demás se dibuja apagado. Es lo que
  // convierte una maraña en una respuesta.
  const resaltados = useMemo(() => {
    if (!seleccion) return null;
    const cerca = new Set<string>([seleccion]);
    for (const arista of aristas) {
      if (arista.source === seleccion) cerca.add(arista.target);
      else if (arista.target === seleccion) cerca.add(arista.source);
    }
    return cerca;
  }, [seleccion, aristas]);

  const pintarNodo = useCallback(
    (nodo: NodoPintado, ctx: CanvasRenderingContext2D, escala: number) => {
      const apagado = resaltados ? !resaltados.has(nodo.id) : false;
      const esSeleccion = nodo.id === seleccion;

      ctx.globalAlpha = apagado ? 0.15 : 1;
      ctx.beginPath();
      ctx.arc(nodo.x ?? 0, nodo.y ?? 0, nodo.radio, 0, 2 * Math.PI);
      ctx.fillStyle = COLOR_TIPO[nodo.type];
      ctx.fill();

      if (esSeleccion) {
        ctx.lineWidth = 2 / escala;
        ctx.strokeStyle = '#eef3ff';
        ctx.stroke();
      }

      // El nombre solo aparece cuando hay lugar para leerlo: con la vista
      // entera son 288 etiquetas encimadas que no dicen nada.
      const legible = escala > 1.6 || esSeleccion || nodo.radio > 7;
      if (legible && !apagado) {
        const cuerpo = Math.max(10 / escala, 1.5);
        ctx.font = `${cuerpo}px var(--font-mono), monospace`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillStyle = '#c8d6f0';
        ctx.fillText(nodo.label, nodo.x ?? 0, (nodo.y ?? 0) + nodo.radio + 1.5 / escala);
      }
      ctx.globalAlpha = 1;
    },
    [resaltados, seleccion],
  );

  const colorArista = useCallback(
    (arista: { source: unknown; target: unknown; type: string }) => {
      if (!resaltados) return 'rgba(95,112,153,0.28)';
      const id = (extremo: unknown) =>
        typeof extremo === 'string' ? extremo : ((extremo as { id?: string })?.id ?? '');
      const tocado = resaltados.has(id(arista.source)) && resaltados.has(id(arista.target));
      return tocado ? 'rgba(117,170,219,0.75)' : 'rgba(95,112,153,0.07)';
    },
    [resaltados],
  );

  return (
    <div
      ref={contenedor}
      className="relative overflow-hidden rounded-lg border border-borde"
      style={{ height: altura, background: FONDO }}
    >
      {ancho > 0 ? (
        <ForceGraph2D
          width={ancho}
          height={altura}
          graphData={datos}
          backgroundColor={FONDO}
          nodeRelSize={1}
          nodeCanvasObject={pintarNodo as never}
          nodePointerAreaPaint={
            ((nodo: NodoPintado, color: string, ctx: CanvasRenderingContext2D) => {
              ctx.fillStyle = color;
              ctx.beginPath();
              ctx.arc(nodo.x ?? 0, nodo.y ?? 0, nodo.radio + 2, 0, 2 * Math.PI);
              ctx.fill();
            }) as never
          }
          linkColor={colorArista as never}
          linkWidth={0.6}
          cooldownTicks={90}
          onNodeClick={((nodo: NodoPintado) => onSeleccionar(nodo.id)) as never}
          onBackgroundClick={() => onSeleccionar(null)}
          nodeLabel={((nodo: NodoPintado) =>
            `${ETIQUETA_TIPO[nodo.type]}: ${nodo.label}`) as never}
        />
      ) : null}

      <div className="pointer-events-none absolute left-3 top-3 flex flex-wrap gap-x-3 gap-y-1 rounded-md bg-[#000d2d]/80 px-2.5 py-1.5">
        {(Object.keys(COLOR_TIPO) as TipoEntidad[]).map((tipo) => (
          <span key={tipo} className="flex items-center gap-1.5 text-[0.7rem] text-texto-tenue">
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: COLOR_TIPO[tipo] }}
              aria-hidden="true"
            />
            {ETIQUETA_TIPO[tipo]}
          </span>
        ))}
      </div>
    </div>
  );
}
