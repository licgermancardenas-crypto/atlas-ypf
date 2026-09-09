'use client';

// El armazón de la aplicación: barra lateral fija en escritorio, barra compacta
// arriba en pantallas chicas.
//
// Por qué una barra lateral y no un encabezado: el caso es un argumento de siete
// tramos, cada uno de varios scrolls. Con la navegación arriba, el índice
// desaparece apenas empezás a leer y volver a un dato ya visto es rodar hasta
// encontrarlo. Fija a la izquierda, el índice está siempre y además muestra en
// qué parte del argumento estás parado, que en un documento largo es la mitad de
// la orientación.

import { useEffect, useState, type ReactNode } from 'react';

import { Comandos } from './Comandos';
import { BarraFiltros } from './estado/BarraFiltros';
import { ProveedorFiltros } from './estado/filtros';
import { Franja } from './ui';

const SECCIONES = [
  { id: 'balance', numero: '01', titulo: 'El balance', resumen: 'Los números del trimestre' },
  { id: 'origen', numero: '02', titulo: 'De dónde salió', resumen: 'Precio, volumen y costo' },
  { id: 'mercado', numero: '03', titulo: 'El mercado', resumen: '22 balances medidos' },
  { id: 'activo', numero: '04', titulo: 'El activo', resumen: 'La cuenca, pozo por pozo' },
  { id: 'economia', numero: '05', titulo: 'Economía de pozo', resumen: 'NPV, TIR y breakeven' },
  { id: 'simulador', numero: '06', titulo: 'Simulador', resumen: 'Mové los drivers' },
  { id: 'metodo', numero: '07', titulo: 'Método', resumen: 'Fuentes y advertencias' },
];

function useSeccionActiva() {
  const [activa, setActiva] = useState(SECCIONES[0].id);

  useEffect(() => {
    // El margen inferior de -55% marca la sección cuando su encabezado llega al
    // tercio superior de la pantalla, que es donde el ojo está leyendo, y no
    // cuando apenas asoma por abajo.
    const observador = new IntersectionObserver(
      (entradas) => {
        const visible = entradas
          .filter((entrada) => entrada.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (visible) setActiva(visible.target.id);
      },
      { rootMargin: '-80px 0px -55% 0px', threshold: 0 },
    );
    for (const seccion of SECCIONES) {
      const nodo = document.getElementById(seccion.id);
      if (nodo) observador.observe(nodo);
    }
    return () => observador.disconnect();
  }, []);

  return activa;
}

function Marca() {
  return (
    <div className="flex items-center gap-3">
      {/* El cuadrado azul con las letras es la construcción del logo de YPF:
          blanco sobre el azul de marca, sin caja ni degradado. */}
      <span className="grid h-9 w-9 place-items-center rounded-md bg-azul font-display text-[0.7rem] font-bold tracking-tight text-white">
        ATL
      </span>
      <div>
        <p className="font-display text-sm font-semibold leading-none text-texto">ATLAS-YPF</p>
        <p className="mt-1 font-mono text-[0.65rem] leading-none text-texto-tenue">
          CASO DE ESTUDIO
        </p>
      </div>
    </div>
  );
}

export function Shell({
  children,
  actualizado,
  operadores,
}: {
  children: ReactNode;
  actualizado: string;
  operadores: string[];
}) {
  return (
    <ProveedorFiltros>
      <Armazon actualizado={actualizado} operadores={operadores}>
        {children}
      </Armazon>
    </ProveedorFiltros>
  );
}

function Armazon({
  children,
  actualizado,
  operadores,
}: {
  children: ReactNode;
  actualizado: string;
  operadores: string[];
}) {
  const activa = useSeccionActiva();

  return (
    <div className="lg:grid lg:grid-cols-[15.5rem_1fr]">
      {/* Barra lateral: escritorio */}
      <aside className="hidden lg:block">
        <div className="sticky top-0 flex h-screen flex-col border-r border-borde bg-superficie/60 px-5 py-6">
          <Marca />
          <Franja className="mt-5 w-full" />

          <nav aria-label="Secciones del caso" className="mt-6 flex-1 space-y-0.5">
            {SECCIONES.map((seccion) => {
              const esActiva = activa === seccion.id;
              return (
                <a
                  key={seccion.id}
                  href={`#${seccion.id}`}
                  aria-current={esActiva ? 'true' : undefined}
                  className={`marquesina block rounded-md px-3 py-2 transition-colors ${
                    esActiva ? 'bg-superficie-alta' : 'hover:bg-superficie'
                  }`}
                  data-activa={esActiva}
                >
                  <span className="flex items-baseline gap-2">
                    <span
                      className={`font-mono text-[0.7rem] ${
                        esActiva ? 'text-azul-claro' : 'text-texto-tenue'
                      }`}
                    >
                      {seccion.numero}
                    </span>
                    <span
                      className={`text-sm ${esActiva ? 'text-texto' : 'text-texto-suave'}`}
                    >
                      {seccion.titulo}
                    </span>
                  </span>
                  <span className="mt-0.5 block pl-6 text-[0.7rem] leading-snug text-texto-tenue">
                    {seccion.resumen}
                  </span>
                </a>
              );
            })}
          </nav>

          <div className="space-y-2 border-t border-borde pt-4">
            <Comandos operadores={operadores} />
            <a
              href="/ypf-project/memo"
              className="block rounded-md bg-azul px-3 py-2 text-center text-xs font-medium text-white transition hover:bg-azul-claro"
            >
              Memo ejecutivo
            </a>
            <p className="font-mono text-[0.65rem] leading-relaxed text-texto-tenue">
              Datos al {actualizado}
              <br />
              Refresco semanal automático
            </p>
          </div>
        </div>
      </aside>

      {/* Barra compacta: pantallas chicas */}
      <div className="lg:hidden">
        <div className="sticky top-0 z-40 border-b border-borde bg-fondo/90 backdrop-blur-md">
          <div className="flex items-center justify-between px-5 py-3">
            <Marca />
            <a
              href="/ypf-project/memo"
              className="rounded-md bg-azul px-3 py-1.5 text-xs font-medium text-white"
            >
              Memo
            </a>
          </div>
          <div className="flex gap-1 overflow-x-auto px-5 pb-2.5">
            {SECCIONES.map((seccion) => (
              <a
                key={seccion.id}
                href={`#${seccion.id}`}
                aria-current={activa === seccion.id ? 'true' : undefined}
                className={`shrink-0 rounded-md px-2.5 py-1 text-xs transition-colors ${
                  activa === seccion.id
                    ? 'bg-superficie-alta text-texto'
                    : 'text-texto-tenue hover:text-texto-suave'
                }`}
              >
                <span className="font-mono text-[0.7rem] text-azul-claro">{seccion.numero}</span>{' '}
                {seccion.titulo}
              </a>
            ))}
          </div>
        </div>
      </div>

      <div className="min-w-0">
        <BarraFiltros operadores={operadores} />
        {children}
      </div>
    </div>
  );
}
