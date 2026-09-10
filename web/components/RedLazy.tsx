'use client';

// Carga diferida de la vista de relaciones, con el mismo criterio que el mapa.
//
// react-force-graph son unos 400 KB de JavaScript y la sección vive abajo del
// pliegue. No se baja hasta que la sección se acerca al viewport, y el botón
// queda para el navegador sin IntersectionObserver.

import dynamic from 'next/dynamic';
import { useEffect, useRef, useState } from 'react';

import { Esqueleto } from './Panel';

const RedEntidades = dynamic(() => import('./RedEntidades').then((m) => m.RedEntidades), {
  ssr: false,
  loading: () => <Esqueleto alto={560} />,
});

export function RedLazy() {
  const contenedor = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (visible) return;
    const nodo = contenedor.current;
    if (!nodo || typeof IntersectionObserver === 'undefined') return;

    const observador = new IntersectionObserver(
      (entradas) => {
        if (entradas.some((entrada) => entrada.isIntersecting)) {
          setVisible(true);
          observador.disconnect();
        }
      },
      { rootMargin: '400px 0px' },
    );
    observador.observe(nodo);
    return () => observador.disconnect();
  }, [visible]);

  return (
    <div ref={contenedor}>
      {visible ? (
        <RedEntidades />
      ) : (
        <div className="flex min-h-[320px] flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-borde bg-superficie px-6 text-center">
          <p className="max-w-md text-xs leading-relaxed text-texto-suave">
            El grafo carga cuando llegás hasta acá. Son 288 nodos y la librería que los dibuja;
            los pozos se piden por separado, de a una concesión.
          </p>
          <button
            type="button"
            onClick={() => setVisible(true)}
            className="rounded-md border border-borde px-3 py-1.5 text-xs text-texto-suave transition hover:border-azul-claro hover:text-azul-claro"
          >
            Cargar ahora
          </button>
        </div>
      )}
    </div>
  );
}
