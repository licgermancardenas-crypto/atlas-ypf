'use client';

// Carga diferida del mapa, en dos tiempos.
//
// El primero es el bundle: deck.gl son unos 500 KB de JavaScript y el mapa vive
// en la cuarta sección, bien abajo del pliegue. Con el import dinámico el
// bundle principal no lo incluye.
//
// El segundo es el momento. Un `dynamic()` a secas empieza a bajar todo apenas
// monta el componente, o sea apenas carga la página: el visitante que entra a
// leer el titular ya está pagando la librería 3D, el hillshade y los polígonos
// que quizá nunca mire, y los está pagando compitiendo con lo que sí está
// mirando. Por eso el mapa no existe hasta que la sección se acerca al
// viewport: un IntersectionObserver con 400 px de anticipación, suficiente para
// que empiece a bajar mientras el lector todavía viene scrolleando y llegue
// armado, pero no antes.
//
// Si el navegador no tiene IntersectionObserver, el botón hace el trabajo a
// mano. Nunca queda un hueco sin explicación.

import dynamic from 'next/dynamic';
import { useEffect, useRef, useState } from 'react';

import { Esqueleto } from '../Panel';

const MapaCuenca = dynamic(() => import('./MapaCuenca').then((m) => m.MapaCuenca), {
  ssr: false,
  loading: () => <Marco titulo="Cargando el mapa…" />,
});

function Marco({ titulo, children }: { titulo: string; children?: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-borde bg-superficie p-5">
      <p className="mb-3 font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
        {titulo}
      </p>
      {children ?? <Esqueleto alto={620} />}
    </div>
  );
}

export function MapaLazy() {
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
        <MapaCuenca />
      ) : (
        <Marco titulo="Mapa de la cuenca">
          <div className="flex min-h-[320px] flex-col items-center justify-center gap-3 rounded-md border border-dashed border-borde px-6 text-center">
            <p className="max-w-md text-xs leading-relaxed text-texto-suave">
              El mapa carga solo cuando llegás hasta acá: son 4.893 pozos, la red de ductos y el
              relieve de la cuenca, y no tiene sentido bajarlos mientras leés las secciones de
              arriba.
            </p>
            <button
              type="button"
              onClick={() => setVisible(true)}
              className="rounded-md border border-borde px-3 py-1.5 text-xs text-texto-suave transition hover:border-azul-claro hover:text-azul-claro"
            >
              Cargar ahora
            </button>
          </div>
        </Marco>
      )}
    </div>
  );
}
