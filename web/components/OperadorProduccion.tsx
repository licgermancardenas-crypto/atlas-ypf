'use client';

// La producción de un operador, separada en convencional, shale y tight.
//
// Es el gráfico que contesta si la compañía crece o compensa. Apilado y no en
// líneas superpuestas a propósito: lo que importa es la composición del total,
// no comparar tres series entre sí. Cuando el bloque de convencional se achica
// mientras el total se mantiene, el gráfico lo muestra sin que haya que decirlo.

import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { fmt } from '@/lib/data';

export interface PuntoOperador {
  fecha: string;
  convencional: number;
  shale: number;
  tight: number;
}

const CONCEPTOS = [
  { clave: 'convencional', etiqueta: 'Convencional', color: 'var(--color-neutro)' },
  { clave: 'tight', etiqueta: 'Tight', color: 'var(--color-celeste)' },
  { clave: 'shale', etiqueta: 'Shale', color: 'var(--color-azul)' },
] as const;

export function OperadorProduccion({
  serie,
  unidad,
}: {
  serie: PuntoOperador[];
  unidad: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={320}>
      <AreaChart data={serie} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="var(--color-borde)" strokeDasharray="2 4" vertical={false} />
        <XAxis
          dataKey="fecha"
          stroke="var(--color-texto-suave)"
          tick={{ fill: 'var(--color-texto-suave)', fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: 'var(--color-borde)' }}
          minTickGap={44}
        />
        <YAxis
          stroke="var(--color-texto-suave)"
          tick={{ fill: 'var(--color-texto-suave)', fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: 'var(--color-borde)' }}
          width={60}
        />
        <Tooltip
          contentStyle={{
            background: 'var(--color-superficie-alta)',
            border: '1px solid var(--color-borde)',
            borderRadius: '0.5rem',
            fontSize: '0.8rem',
            fontFamily: 'var(--font-mono)',
          }}
          labelStyle={{ color: 'var(--color-texto)', marginBottom: '0.25rem' }}
          formatter={(valor, nombre) => [`${fmt.entero(Number(valor))} ${unidad}`, String(nombre)]}
        />
        <Legend wrapperStyle={{ fontSize: '0.75rem', color: 'var(--color-texto-suave)' }} />
        {CONCEPTOS.map((concepto) => (
          <Area
            key={concepto.clave}
            type="monotone"
            dataKey={concepto.clave}
            name={concepto.etiqueta}
            stackId="produccion"
            stroke={concepto.color}
            fill={concepto.color}
            fillOpacity={0.75}
            strokeWidth={0.5}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}
