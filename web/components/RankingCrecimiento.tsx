'use client';

// Quién está ganando la carrera adentro de la cuenca.
//
// El caso venía mirando agregados: el país, la compañía, la cuenca. Pero la
// pregunta que se hace alguien que sigue el sector es más chica y más concreta:
// qué áreas se están moviendo. Este panel la contesta y, cuando el área existe
// como polígono, manda el mapa hasta ahí.
//
// Se ordena por variación absoluta y no por porcentual: un área que arrancó de
// cero el año pasado siempre encabezaría un ranking porcentual sin mover la
// aguja de nadie.

import { useState } from 'react';

import { fmt } from '@/lib/data';
import { useFiltros } from './estado/filtros';

export interface FilaRanking {
  nombre: string;
  actual_bd: number;
  previo_bd: number;
  delta_bd: number;
  crecimiento: number | null;
  participacion: number | null;
}

type IdDimension = 'concesion' | 'yacimiento' | 'empresa' | 'cuenca' | 'provincia';

const DIMENSIONES: { id: IdDimension; etiqueta: string; navegable: boolean }[] = [
  { id: 'concesion', etiqueta: 'Concesión', navegable: true },
  { id: 'yacimiento', etiqueta: 'Yacimiento', navegable: true },
  { id: 'empresa', etiqueta: 'Empresa', navegable: false },
  { id: 'cuenca', etiqueta: 'Cuenca', navegable: false },
  { id: 'provincia', etiqueta: 'Provincia', navegable: false },
];

export function RankingCrecimiento({
  rankings,
}: {
  rankings: Record<string, FilaRanking[] | undefined>;
}) {
  const [dimension, setDimension] = useState<IdDimension>('concesion');
  const [orden, setOrden] = useState<'crecen' | 'caen'>('crecen');
  const { filtros, aplicar } = useFiltros();

  const definicion = DIMENSIONES.find((d) => d.id === dimension)!;
  const todas = rankings[dimension] ?? [];
  const filas = [...todas]
    .sort((a, b) => (orden === 'crecen' ? b.delta_bd - a.delta_bd : a.delta_bd - b.delta_bd))
    .slice(0, 12);

  // La escala de las barras es común a las que crecen y a las que caen, para que
  // el largo se pueda comparar entre las dos vistas.
  const maximo = Math.max(...todas.map((fila) => Math.abs(fila.delta_bd)), 1);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex rounded-md border border-borde p-0.5">
          {DIMENSIONES.map((opcion) => (
            <button
              key={opcion.id}
              type="button"
              onClick={() => setDimension(opcion.id)}
              className={`rounded px-2.5 py-1 text-xs transition ${
                dimension === opcion.id
                  ? 'bg-superficie-alta text-azul-claro'
                  : 'text-texto-tenue hover:text-texto-suave'
              }`}
            >
              {opcion.etiqueta}
            </button>
          ))}
        </div>

        <div className="flex rounded-md border border-borde p-0.5">
          {(
            [
              ['crecen', 'Las que crecen'],
              ['caen', 'Las que caen'],
            ] as const
          ).map(([id, etiqueta]) => (
            <button
              key={id}
              type="button"
              onClick={() => setOrden(id)}
              className={`rounded px-2.5 py-1 text-xs transition ${
                orden === id
                  ? 'bg-superficie-alta text-azul-claro'
                  : 'text-texto-tenue hover:text-texto-suave'
              }`}
            >
              {etiqueta}
            </button>
          ))}
        </div>

        <span className="ml-auto font-mono text-[0.65rem] text-texto-tenue">
          últimos 12 meses vs. los 12 anteriores
        </span>
      </div>

      <ul className="space-y-1">
        {filas.map((fila) => {
          const positivo = fila.delta_bd >= 0;
          const ancho = (Math.abs(fila.delta_bd) / maximo) * 100;
          const seleccionada = filtros.zona === fila.nombre;

          const contenido = (
            <>
              <div className="flex items-baseline justify-between gap-3">
                <span className={`truncate text-sm ${seleccionada ? 'text-azul-claro' : 'text-texto'}`}>
                  {fila.nombre}
                </span>
                <span className="tabular shrink-0 text-xs text-texto-suave">
                  {fmt.entero(fila.actual_bd)} bbl/d
                  <span className={`ml-2 ${positivo ? 'text-alza' : 'text-baja'}`}>
                    {positivo ? '+' : ''}
                    {fmt.entero(fila.delta_bd)}
                  </span>
                  {fila.crecimiento !== null ? (
                    <span className="ml-1.5 text-texto-tenue">
                      ({fmt.porcentajeConSigno(fila.crecimiento, 0)})
                    </span>
                  ) : null}
                </span>
              </div>
              <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-superficie-alta">
                <div
                  className={`h-full rounded-full ${positivo ? 'bg-alza' : 'bg-baja'}`}
                  style={{ width: `${ancho}%` }}
                />
              </div>
            </>
          );

          return (
            <li key={fila.nombre}>
              {definicion.navegable ? (
                <button
                  type="button"
                  onClick={() =>
                    aplicar({ zona: filtros.zona === fila.nombre ? null : fila.nombre })
                  }
                  className={`w-full rounded-md px-2 py-1.5 text-left transition hover:bg-superficie-alta ${
                    seleccionada ? 'bg-superficie-alta' : ''
                  }`}
                  title={`Ver ${fila.nombre} en el mapa`}
                >
                  {contenido}
                </button>
              ) : (
                <div className="px-2 py-1.5">{contenido}</div>
              )}
            </li>
          );
        })}
      </ul>

      <p className="mt-3 text-xs leading-relaxed text-texto-tenue">
        {definicion.navegable
          ? 'Clic en un área para que el mapa vuele hasta ahí.'
          : 'Esta dimensión no tiene polígono propio, así que no se puede navegar en el mapa.'}{' '}
        La comparación es contra el mismo período del año anterior y no contra el mes previo: la
        producción tiene estacionalidad de mantenimiento, y un ranking mes contra mes ordena por
        quién paró la planta, no por quién crece.
      </p>
    </div>
  );
}
