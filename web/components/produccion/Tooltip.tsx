'use client';

// El tooltip del gráfico.
//
// El de Recharts lista todas las series en el orden en que están apiladas, con
// un cuadradito de color por fila. Con diecisiete activos eso es una columna
// ilegible que además tapa medio gráfico. Este contesta lo que se pregunta al
// pasar el mouse por un período: cuánto fue el total, qué activos lo explican y
// cuánto de eso es shale.
//
// Muestra los cinco primeros y resume el resto en una línea. El detalle completo
// está a un clic, en la tabla, que es el lugar donde mirar cuarenta filas tiene
// sentido.

import { fmt } from '@/lib/data';
import { COLOR } from '@/lib/produccion';

export interface DatoTooltip {
  periodo: string;
  completo: boolean;
  total: number;
  unidad: string;
  /** Participación del shale en ese período, si se pudo calcular. */
  shale: number | null;
  activos: { nombre: string; valor: number; color: string }[];
  /** Cuántos activos quedaron fuera del listado y cuánto suman. */
  resto: { cantidad: number; valor: number } | null;
  participacion: boolean;
}

export function TooltipProduccion({ dato }: { dato: DatoTooltip | null }) {
  if (!dato) return null;

  const valor = (numero: number) =>
    dato.participacion ? `${fmt.numero(numero, 1)}%` : `${fmt.entero(numero)} ${dato.unidad}`;

  return (
    <div className="w-60 rounded-lg border border-borde-vivo bg-superficie-alta/95 p-3 shadow-lg backdrop-blur-sm">
      <div className="flex items-baseline justify-between gap-2">
        <p className="font-mono text-[0.7rem] uppercase tracking-[0.12em] text-texto">
          {dato.periodo}
        </p>
        {!dato.completo ? (
          <span className="font-mono text-[0.6rem] uppercase tracking-[0.1em] text-oro">
            parcial
          </span>
        ) : null}
      </div>

      {!dato.participacion ? (
        <p className="tabular mt-2 text-lg font-semibold leading-none text-texto">
          {fmt.entero(dato.total)}{' '}
          <span className="text-xs font-normal text-texto-suave">{dato.unidad}</span>
        </p>
      ) : null}

      <ul className="mt-3 space-y-1.5">
        {dato.activos.map((activo) => (
          <li key={activo.nombre} className="flex items-baseline justify-between gap-3 text-xs">
            <span className="flex min-w-0 items-center gap-1.5">
              <span
                aria-hidden
                className="h-2 w-2 shrink-0 rounded-[2px]"
                style={{ background: activo.color }}
              />
              <span className="truncate text-texto-suave">{activo.nombre}</span>
            </span>
            <span className="tabular shrink-0 text-texto">{valor(activo.valor)}</span>
          </li>
        ))}
        {dato.resto ? (
          <li className="flex items-baseline justify-between gap-3 text-xs text-texto-tenue">
            <span>+ {dato.resto.cantidad} más</span>
            <span className="tabular">{valor(dato.resto.valor)}</span>
          </li>
        ) : null}
      </ul>

      {dato.shale !== null ? (
        <p className="mt-3 flex items-baseline justify-between border-t border-borde pt-2 text-[0.7rem]">
          <span className="text-texto-tenue">Shale</span>
          <span className="tabular" style={{ color: COLOR.shale }}>
            {fmt.porcentaje(dato.shale, 1)}
          </span>
        </p>
      ) : null}
    </div>
  );
}
