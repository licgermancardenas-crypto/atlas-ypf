'use client';

// Barra de secciones. La página es un argumento largo —siete tramos, varios
// scrolls cada uno— y sin esto la única forma de volver a un dato ya leído es
// rodar hasta encontrarlo.
//
// Los números no son decoración: el caso se lee en orden (qué pasó, de dónde
// salió, cómo reaccionó el mercado, qué dice el activo, cuánto vale, qué pasa
// si movés los supuestos, cómo está hecho). El índice deja ver esa secuencia.

import { useEffect, useState } from 'react';

const SECCIONES = [
  { id: 'balance', numero: '01', titulo: 'El balance' },
  { id: 'origen', numero: '02', titulo: 'De dónde salió' },
  { id: 'mercado', numero: '03', titulo: 'El mercado' },
  { id: 'activo', numero: '04', titulo: 'El activo' },
  { id: 'economia', numero: '05', titulo: 'Economía de pozo' },
  { id: 'simulador', numero: '06', titulo: 'Simulador' },
  { id: 'metodo', numero: '07', titulo: 'Método' },
];

export function NavSecciones() {
  const [activa, setActiva] = useState<string>(SECCIONES[0].id);

  useEffect(() => {
    // El margen inferior de -55% hace que una sección se marque como activa
    // cuando su encabezado llega al tercio superior de la pantalla, que es
    // donde el ojo está leyendo, y no cuando apenas asoma por abajo.
    const observador = new IntersectionObserver(
      (entradas) => {
        const visible = entradas
          .filter((entrada) => entrada.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (visible) setActiva(visible.target.id);
      },
      { rootMargin: '-72px 0px -55% 0px', threshold: 0 },
    );

    for (const seccion of SECCIONES) {
      const nodo = document.getElementById(seccion.id);
      if (nodo) observador.observe(nodo);
    }
    return () => observador.disconnect();
  }, []);

  return (
    <nav
      aria-label="Secciones del caso"
      className="sticky top-0 z-40 border-b border-borde bg-fondo/85 backdrop-blur-md"
    >
      <div className="mx-auto flex max-w-6xl items-center gap-1 overflow-x-auto px-6 py-2.5">
        <span className="mr-3 shrink-0 font-mono text-[0.7rem] tracking-[0.18em] text-azul-claro">
          ATLAS-YPF
        </span>
        {SECCIONES.map((seccion) => {
          const esActiva = activa === seccion.id;
          return (
            <a
              key={seccion.id}
              href={`#${seccion.id}`}
              aria-current={esActiva ? 'true' : undefined}
              className={`shrink-0 rounded-md px-2.5 py-1 text-xs transition-colors ${
                esActiva
                  ? 'bg-superficie-alta text-texto'
                  : 'text-texto-tenue hover:text-texto-suave'
              }`}
            >
              <span className="font-mono text-[0.7rem] text-azul-claro">{seccion.numero}</span>{' '}
              {seccion.titulo}
            </a>
          );
        })}
      </div>
    </nav>
  );
}
