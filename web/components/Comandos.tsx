'use client';

// Paleta de comandos (⌘K / Ctrl+K): saltar a una sección o aplicar un filtro sin
// levantar las manos del teclado.
//
// En un documento de siete secciones es más señal de producto que utilidad
// diaria, y vale la pena decirlo. Se gana el lugar por otra razón: es el único
// sitio donde conviven la navegación y los filtros, así que funciona como índice
// de todo lo que la página sabe hacer — algo que ni la barra lateral ni el
// slicer muestran por separado.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useFiltros } from './estado/filtros';

interface Comando {
  id: string;
  etiqueta: string;
  grupo: 'Ir a' | 'Filtrar' | 'Ver';
  pista?: string;
  ejecutar: () => void;
}

const SECCIONES = [
  ['balance', 'El balance'],
  ['origen', 'De dónde salió el récord'],
  ['mercado', 'La reacción del mercado'],
  ['activo', 'El activo, pozo por pozo'],
  ['economia', 'Economía de pozo'],
  ['simulador', 'Simulador de escenarios'],
  ['metodo', 'Método y fuentes'],
] as const;

export function Comandos({ operadores }: { operadores: string[] }) {
  const [abierto, setAbierto] = useState(false);
  const [consulta, setConsulta] = useState('');
  const [indice, setIndice] = useState(0);
  const campo = useRef<HTMLInputElement>(null);
  const { aplicar, limpiar } = useFiltros();

  const cerrar = useCallback(() => {
    setAbierto(false);
    setConsulta('');
    setIndice(0);
  }, []);

  const comandos = useMemo<Comando[]>(() => {
    const ir = SECCIONES.map(([id, etiqueta]) => ({
      id: `ir-${id}`,
      etiqueta,
      grupo: 'Ir a' as const,
      ejecutar: () => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' }),
    }));

    const filtrar: Comando[] = [
      {
        id: 'limpiar',
        etiqueta: 'Limpiar todos los filtros',
        grupo: 'Filtrar',
        ejecutar: limpiar,
      },
      {
        id: 'vm',
        etiqueta: 'Solo pozos de Vaca Muerta',
        grupo: 'Filtrar',
        ejecutar: () => aplicar({ soloVacaMuerta: true }),
      },
      {
        id: 'foco-record',
        etiqueta: 'Enfocar el trimestre récord (2T 2026)',
        grupo: 'Filtrar',
        pista: 'el balance que el mercado castigó',
        ejecutar: () => aplicar({ foco: '2026Q2' }),
      },
      ...operadores.slice(0, 8).map((operador) => ({
        id: `op-${operador}`,
        etiqueta: `Filtrar por ${operador}`,
        grupo: 'Filtrar' as const,
        ejecutar: () => aplicar({ operador }),
      })),
    ];

    const ver: Comando[] = [
      {
        id: 'memo',
        etiqueta: 'Abrir el memo ejecutivo',
        grupo: 'Ver',
        ejecutar: () => {
          window.location.href = '/ypf-project/memo';
        },
      },
      {
        id: 'copiar',
        etiqueta: 'Copiar el link de esta vista',
        grupo: 'Ver',
        pista: 'con los filtros aplicados',
        ejecutar: () => navigator.clipboard?.writeText(window.location.href),
      },
    ];

    return [...ir, ...filtrar, ...ver];
  }, [aplicar, limpiar, operadores]);

  const filtrados = useMemo(() => {
    const texto = consulta.trim().toLowerCase();
    if (!texto) return comandos;
    return comandos.filter((comando) => comando.etiqueta.toLowerCase().includes(texto));
  }, [comandos, consulta]);

  useEffect(() => {
    const alTeclear = (evento: KeyboardEvent) => {
      if ((evento.metaKey || evento.ctrlKey) && evento.key.toLowerCase() === 'k') {
        evento.preventDefault();
        setAbierto((previo) => !previo);
        return;
      }
      if (!abierto) return;
      if (evento.key === 'Escape') cerrar();
      if (evento.key === 'ArrowDown') {
        evento.preventDefault();
        setIndice((previo) => Math.min(previo + 1, filtrados.length - 1));
      }
      if (evento.key === 'ArrowUp') {
        evento.preventDefault();
        setIndice((previo) => Math.max(previo - 1, 0));
      }
      if (evento.key === 'Enter' && filtrados[indice]) {
        evento.preventDefault();
        filtrados[indice].ejecutar();
        cerrar();
      }
    };
    window.addEventListener('keydown', alTeclear);
    return () => window.removeEventListener('keydown', alTeclear);
  }, [abierto, cerrar, filtrados, indice]);

  useEffect(() => {
    if (abierto) campo.current?.focus();
  }, [abierto]);

  if (!abierto) {
    return (
      <button
        type="button"
        onClick={() => setAbierto(true)}
        className="flex w-full items-center justify-between rounded-md border border-borde px-3 py-1.5 text-xs text-texto-tenue transition hover:border-azul-claro hover:text-texto-suave"
      >
        Buscar o filtrar
        <kbd className="font-mono text-[0.65rem] text-texto-tenue">⌘K</kbd>
      </button>
    );
  }

  let grupoActual = '';

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-fondo/70 px-4 pt-[12vh] backdrop-blur-sm"
      onClick={cerrar}
      role="presentation"
    >
      <div
        className="marquesina w-full max-w-lg overflow-hidden rounded-lg border border-borde-vivo bg-superficie shadow-2xl"
        data-activa="true"
        onClick={(evento) => evento.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Paleta de comandos"
      >
        <input
          ref={campo}
          value={consulta}
          onChange={(evento) => {
            setConsulta(evento.target.value);
            setIndice(0);
          }}
          placeholder="Ir a una sección, filtrar por operador, copiar el link…"
          className="w-full border-b border-borde bg-transparent px-4 py-3 text-sm text-texto outline-none placeholder:text-texto-tenue"
        />

        <ul className="max-h-80 overflow-y-auto py-1">
          {filtrados.length === 0 ? (
            <li className="px-4 py-6 text-center text-xs text-texto-tenue">
              Nada coincide con “{consulta}”.
            </li>
          ) : (
            filtrados.map((comando, posicion) => {
              const encabezado = comando.grupo !== grupoActual ? comando.grupo : null;
              grupoActual = comando.grupo;
              return (
                <li key={comando.id}>
                  {encabezado ? (
                    <p className="px-4 pb-1 pt-3 font-mono text-[0.65rem] uppercase tracking-[0.14em] text-texto-tenue">
                      {encabezado}
                    </p>
                  ) : null}
                  <button
                    type="button"
                    onMouseEnter={() => setIndice(posicion)}
                    onClick={() => {
                      comando.ejecutar();
                      cerrar();
                    }}
                    className={`flex w-full items-baseline justify-between px-4 py-2 text-left text-sm transition ${
                      posicion === indice
                        ? 'bg-superficie-alta text-texto'
                        : 'text-texto-suave hover:bg-superficie-alta/60'
                    }`}
                  >
                    {comando.etiqueta}
                    {comando.pista ? (
                      <span className="ml-3 text-[0.7rem] text-texto-tenue">{comando.pista}</span>
                    ) : null}
                  </button>
                </li>
              );
            })
          )}
        </ul>
      </div>
    </div>
  );
}
