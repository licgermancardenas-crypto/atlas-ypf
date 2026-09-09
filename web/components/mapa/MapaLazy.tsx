'use client';

// Carga diferida del mapa.
//
// deck.gl son unos 500 KB de JavaScript y el mapa vive en la cuarta sección,
// bien abajo del pliegue: con la carga normal, alguien que entra a leer el
// titular espera a que baje una librería de gráficos 3D que quizá nunca use.
// Con el import dinámico, el bundle principal no la incluye y el mapa la pide
// cuando le toca.
//
// El envoltorio existe porque `ssr: false` no se puede usar dentro de un Server
// Component, y la página lo es.

import dynamic from 'next/dynamic';

import { Esqueleto } from '../Panel';

const MapaCuenca = dynamic(() => import('./MapaCuenca').then((m) => m.MapaCuenca), {
  ssr: false,
  loading: () => (
    <div className="rounded-lg border border-borde bg-superficie p-5">
      <p className="mb-3 font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
        Cargando el mapa…
      </p>
      <Esqueleto alto={620} />
    </div>
  ),
});

export function MapaLazy() {
  return <MapaCuenca />;
}
