'use client';

// El envoltorio de cada panel: gráfico, tabla y descarga.
//
// Poder ver la tabla detrás del gráfico y bajarla en CSV es lo más usado de
// Power BI después de los visuales, y acá cumple una función extra: un caso de
// portfolio que te deja bajar los números está diciendo que no tiene nada que
// esconder. Los datos ya están en el navegador; negarlos sería una decisión.

import { useState, type ReactNode } from 'react';

import { fmt } from '@/lib/data';
import { useFiltros } from './estado/filtros';
import { Tabla } from './ui';

/** Los formatos van por nombre y no como función: las columnas las declara la
 *  página, que es un Server Component, y React no puede mandar funciones a un
 *  componente de cliente. Un nombre viaja; una función no. */
export type FormatoCelda = 'entero' | 'decimal' | 'porcentaje' | 'porcentaje0' | 'signo2' | 'musd';

const FORMATOS: Record<FormatoCelda, (valor: number) => string> = {
  entero: (v) => fmt.entero(v),
  decimal: (v) => fmt.numero(v, 1),
  porcentaje: (v) => fmt.porcentaje(v),
  porcentaje0: (v) => fmt.porcentaje(v, 0),
  signo2: (v) => fmt.porcentajeConSigno(v, 2),
  musd: (v) => fmt.musd(v),
};

export interface ColumnaPanel {
  clave: string;
  titulo: string;
  alineacion?: 'izq' | 'der';
  /** Cómo se muestra en pantalla. El CSV siempre lleva el valor crudo. */
  formato?: FormatoCelda;
}

interface Props {
  titulo: string;
  children: ReactNode;
  nota?: ReactNode;
  columnas?: ColumnaPanel[];
  datos?: Record<string, unknown>[];
  /** Nombre del archivo CSV, sin extensión. */
  archivo?: string;
  /** Cuando el filtro deja al panel sin nada que decir, se explica por qué. */
  inhabilitado?: string | null;
  /** Nombre del único operador del que este panel tiene datos. Si el filtro
   *  global elige otro, el panel se apaga solo y dice por qué. */
  soloPara?: string;
  className?: string;
}

function aCsv(columnas: ColumnaPanel[], datos: Record<string, unknown>[]): string {
  const escapar = (valor: unknown) => {
    if (valor === null || valor === undefined) return '';
    const texto = String(valor);
    return /[",;\n]/.test(texto) ? `"${texto.replace(/"/g, '""')}"` : texto;
  };
  const cabecera = columnas.map((c) => escapar(c.titulo)).join(',');
  const filas = datos.map((fila) => columnas.map((c) => escapar(fila[c.clave])).join(','));
  return [cabecera, ...filas].join('\n');
}

function descargar(nombre: string, contenido: string) {
  // El BOM es para que Excel en Windows abra las tildes bien: sin él, "Neuquén"
  // llega como "NeuquÃ©n" y el CSV parece roto aunque esté perfecto.
  const blob = new Blob([`﻿${contenido}`], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement('a');
  enlace.href = url;
  enlace.download = `${nombre}.csv`;
  enlace.click();
  URL.revokeObjectURL(url);
}

export function Panel({
  titulo,
  children,
  nota,
  columnas,
  datos,
  archivo = 'atlas-ypf',
  inhabilitado = null,
  soloPara,
  className = '',
}: Props) {
  const [vista, setVista] = useState<'grafico' | 'tabla'>('grafico');
  const { filtros } = useFiltros();
  const hayTabla = Boolean(columnas?.length && datos?.length);

  const apagado =
    inhabilitado ??
    (soloPara && filtros.operador !== 'todos' && filtros.operador !== soloPara
      ? `Este panel se arma con los estados contables de ${soloPara}, la única de las tres ` +
        `comparables con serie trimestral reconstruida. Con ${filtros.operador} filtrado no hay ` +
        `nada equivalente que mostrar: el dato de esa compañía existe a nivel pozo, en el mapa y ` +
        `en la economía de pozo.`
      : null);

  return (
    <div
      className={`marquesina rounded-lg border border-borde bg-superficie p-5 ${
        apagado ? 'opacity-60' : ''
      } ${className}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h3 className="text-sm font-medium text-texto-suave">{titulo}</h3>

        {hayTabla && !apagado ? (
          <div className="flex items-center gap-1.5">
            <div className="flex rounded-md border border-borde p-0.5">
              {(['grafico', 'tabla'] as const).map((modo) => (
                <button
                  key={modo}
                  type="button"
                  onClick={() => setVista(modo)}
                  className={`rounded px-2 py-0.5 text-[0.7rem] transition ${
                    vista === modo
                      ? 'bg-superficie-alta text-azul-claro'
                      : 'text-texto-tenue hover:text-texto-suave'
                  }`}
                >
                  {modo === 'grafico' ? 'Gráfico' : 'Tabla'}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => descargar(archivo, aCsv(columnas!, datos!))}
              className="rounded-md border border-borde px-2 py-1 text-[0.7rem] text-texto-tenue transition hover:border-azul-claro hover:text-azul-claro"
              title={`Bajar ${datos!.length} filas en CSV`}
            >
              CSV
            </button>
          </div>
        ) : null}
      </div>

      <div className="mt-4">
        {apagado ? (
          <SinDatos motivo={apagado} />
        ) : vista === 'tabla' && hayTabla ? (
          <Tabla
            columnas={columnas!}
            filas={datos!.map((fila) =>
              Object.fromEntries(
                columnas!.map((columna) => [
                  columna.clave,
                  formatear(fila[columna.clave], columna.formato),
                ]),
              ),
            )}
          />
        ) : (
          children
        )}
      </div>

      {nota && !apagado ? (
        <p className="mt-4 text-xs leading-relaxed text-texto-tenue">{nota}</p>
      ) : null}
    </div>
  );
}

function formatear(valor: unknown, formato?: FormatoCelda): string {
  if (valor === null || valor === undefined || valor === '') return '—';
  if (formato && typeof valor === 'number') return FORMATOS[formato](valor);
  return typeof valor === 'number' ? fmt.numero(valor, 1) : String(valor);
}

/** Un panel vacío tiene que decir por qué lo está: el lector aprende algo del
 *  filtro que aplicó en vez de encontrarse un hueco. */
export function SinDatos({ motivo }: { motivo: string }) {
  return (
    <div className="flex min-h-[180px] flex-col items-center justify-center gap-2 rounded-md border border-dashed border-borde px-6 text-center">
      <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
        Sin datos para este filtro
      </p>
      <p className="max-w-sm text-xs leading-relaxed text-texto-suave">{motivo}</p>
    </div>
  );
}

/** Esqueleto de carga. Ocupa el lugar exacto de lo que viene, para que la página
 *  no salte cuando el dato llega. */
export function Esqueleto({ alto = 320 }: { alto?: number }) {
  return (
    <div
      className="animate-pulse rounded-md border border-borde bg-superficie-alta/40"
      style={{ height: alto }}
      aria-hidden="true"
    />
  );
}
