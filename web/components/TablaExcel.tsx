'use client';

// La tabla del módulo financiero, con el comportamiento de una planilla.
//
// Un analista de finanzas no lee un gráfico: lee una grilla con los conceptos
// en las filas y los períodos en las columnas, y compara con el dedo. Este
// componente le da eso: encabezado y primera columna fijos al hacer scroll,
// números monoespaciados alineados a la derecha, líneas de grilla en los dos
// ejes, y resaltado cruzado de fila y columna al pasar el mouse, que es lo que
// evita perder el renglón en una tabla de veintisiete columnas.
//
// El mapa de calor es opcional y por fila, no global: en una fila de márgenes y
// otra de millones de dólares, una escala común no diría nada.

import { useMemo, useState } from 'react';

import { fmt } from '@/lib/data';

export type FormatoExcel =
  | 'entero'
  | 'decimal'
  | 'porcentaje'
  | 'porcentaje0'
  | 'signo'
  | 'musd'
  | 'texto';

export interface FilaExcel {
  /** Lo que va en la primera columna, fija. */
  concepto: string;
  /** Sangría para conceptos derivados: 0 es una línea principal. */
  nivel?: number;
  formato?: FormatoExcel;
  /** Una línea de subtotal se dibuja con línea arriba y en negrita. */
  subtotal?: boolean;
  /** Pinta el fondo según el valor, comparando dentro de esta misma fila. */
  mapaCalor?: boolean;
  /** Nota corta que aparece al pasar el mouse por el concepto. */
  ayuda?: string;
  valores: (number | string | null)[];
}

function formatear(valor: number | string | null, formato: FormatoExcel = 'decimal'): string {
  if (valor === null || valor === undefined || valor === '') return '—';
  if (typeof valor === 'string') return valor;
  switch (formato) {
    case 'entero':
      return fmt.entero(valor);
    case 'porcentaje':
      return fmt.porcentaje(valor);
    case 'porcentaje0':
      return fmt.porcentaje(valor, 0);
    case 'signo':
      return fmt.porcentajeConSigno(valor, 1);
    case 'musd':
      return fmt.musd(valor);
    case 'texto':
      return String(valor);
    default:
      return fmt.numero(valor, 1);
  }
}

/** Fondo proporcional al valor dentro de la fila: azul para arriba, rojo para
 *  abajo. La opacidad máxima es baja a propósito; el color tiene que ayudar a
 *  encontrar el extremo, no a leer el número por el color. */
function fondoCalor(valor: number | string | null, maximo: number): string | undefined {
  if (typeof valor !== 'number' || !maximo) return undefined;
  const intensidad = Math.min(Math.abs(valor) / maximo, 1) * 0.42;
  const color = valor >= 0 ? '77, 144, 255' : '226, 96, 63';
  return `rgba(${color}, ${intensidad.toFixed(3)})`;
}

export function TablaExcel({
  columnas,
  filas,
  etiquetaPrimera = '',
  anchoPrimera = '15rem',
}: {
  columnas: string[];
  filas: FilaExcel[];
  etiquetaPrimera?: string;
  anchoPrimera?: string;
}) {
  const [cruz, setCruz] = useState<{ fila: number; columna: number } | null>(null);

  const maximos = useMemo(
    () =>
      filas.map((fila) =>
        fila.mapaCalor
          ? Math.max(...fila.valores.map((v) => (typeof v === 'number' ? Math.abs(v) : 0)), 0)
          : 0,
      ),
    [filas],
  );

  return (
    <div className="relative overflow-auto rounded-md border border-borde" style={{ maxHeight: 560 }}>
      <table className="w-full border-collapse text-xs" onMouseLeave={() => setCruz(null)}>
        <thead>
          <tr>
            <th
              className="sticky left-0 top-0 z-30 border-b border-r border-borde bg-superficie-alta px-3 py-2 text-left font-medium text-texto-suave"
              style={{ minWidth: anchoPrimera }}
            >
              {etiquetaPrimera}
            </th>
            {columnas.map((columna, indice) => (
              <th
                key={columna}
                className={`sticky top-0 z-20 border-b border-borde px-3 py-2 text-right font-mono text-[0.7rem] font-medium transition-colors ${
                  cruz?.columna === indice
                    ? 'bg-superficie-alta text-azul-claro'
                    : 'bg-superficie-alta text-texto-tenue'
                }`}
              >
                {columna}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((fila, indiceFila) => (
            <tr
              key={fila.concepto}
              className={
                indiceFila % 2 === 1 ? 'bg-superficie-alta/25' : undefined
              }
            >
              <th
                scope="row"
                title={fila.ayuda}
                className={`sticky left-0 z-10 border-r border-borde px-3 py-1.5 text-left font-normal ${
                  fila.subtotal ? 'border-t border-t-borde font-semibold text-texto' : 'text-texto-suave'
                } ${indiceFila % 2 === 1 ? 'bg-[#0a1836]' : 'bg-superficie'} ${
                  cruz?.fila === indiceFila ? 'text-azul-claro' : ''
                }`}
                style={{ paddingLeft: `${0.75 + (fila.nivel ?? 0) * 0.85}rem` }}
              >
                {fila.concepto}
              </th>
              {fila.valores.map((valor, indiceColumna) => {
                const enCruz = cruz?.fila === indiceFila || cruz?.columna === indiceColumna;
                return (
                  <td
                    key={indiceColumna}
                    onMouseEnter={() => setCruz({ fila: indiceFila, columna: indiceColumna })}
                    className={`tabular border-l border-borde/40 px-3 py-1.5 text-right transition-colors ${
                      fila.subtotal ? 'border-t border-t-borde font-semibold text-texto' : 'text-texto'
                    } ${enCruz ? 'bg-azul/10' : ''}`}
                    style={{
                      background: fila.mapaCalor
                        ? fondoCalor(valor, maximos[indiceFila])
                        : undefined,
                    }}
                  >
                    {formatear(valor, fila.formato)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
