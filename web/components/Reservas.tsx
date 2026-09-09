'use client';

// Reservas comprobadas y vida de reservas.
//
// Es el contrapeso del resto del caso. Toda la página habla de producción, que
// es un flujo; esto es el stock. Una compañía puede crecer producción mientras
// se le acorta el inventario, y eso no es crecer: es adelantar. La vida de
// reservas —cuántos años dura lo comprobado al ritmo actual— es la métrica que
// distingue una cosa de la otra, y no aparece en ningún titular de balance.

import { useState } from 'react';
import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { fmt } from '@/lib/data';
import { useFiltros } from './estado/filtros';

export interface FilaReservas {
  anio: number;
  operador: string;
  comprobadas_mboe: number;
  petroleo_mboe: number;
  no_convencional_mboe: number;
  produccion_mboe: number | null;
  vida_reservas: number | null;
  share_no_convencional: number | null;
}

export interface Reservas {
  fuente: string;
  advertencia: string;
  anios: number[];
  ultimo_anio: number;
  por_operador: FilaReservas[];
  ranking_ultimo: FilaReservas[];
}

const COLORES = {
  azul: 'var(--color-azul)',
  azulClaro: 'var(--color-azul-claro)',
  oro: 'var(--color-oro)',
  alza: 'var(--color-alza)',
  baja: 'var(--color-baja)',
  grilla: 'var(--color-borde)',
  texto: 'var(--color-texto-suave)',
};

const PALETA = [
  'var(--color-azul-claro)',
  'var(--color-oro)',
  'var(--color-alza)',
  'var(--color-celeste)',
  'var(--color-baja)',
  'var(--color-neutro)',
];

const ejes = {
  stroke: COLORES.texto,
  tick: { fill: COLORES.texto, fontSize: 11 },
  tickLine: false,
  axisLine: { stroke: COLORES.grilla },
};

const tooltip = {
  contentStyle: {
    background: 'var(--color-superficie-alta)',
    border: '1px solid var(--color-borde)',
    borderRadius: '0.5rem',
    fontSize: '0.8rem',
    fontFamily: 'var(--font-mono)',
  },
  labelStyle: { color: 'var(--color-texto)', marginBottom: '0.25rem' },
};

export function PanelReservas({ datos }: { datos: Reservas }) {
  const [vista, setVista] = useState<'hoy' | 'evolucion'>('hoy');
  const { filtros } = useFiltros();

  const ranking = datos.ranking_ultimo.filter((fila) => fila.comprobadas_mboe > 0).slice(0, 10);

  // La evolución se muestra de los seis más grandes de hoy: con veinte líneas
  // no se sigue ninguna.
  const seguidos = datos.ranking_ultimo.slice(0, 6).map((fila) => fila.operador);
  const porAnio = new Map<number, Record<string, number | string>>();
  for (const fila of datos.por_operador) {
    if (!seguidos.includes(fila.operador) || fila.vida_reservas === null) continue;
    const registro = porAnio.get(fila.anio) ?? { anio: fila.anio };
    registro[fila.operador] = fila.vida_reservas;
    porAnio.set(fila.anio, registro);
  }
  const evolucion = [...porAnio.values()].sort((a, b) => Number(a.anio) - Number(b.anio));

  const resaltado = (operador: string) =>
    filtros.operador === 'todos' || filtros.operador === operador;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex rounded-md border border-borde p-0.5">
          {(
            [
              ['hoy', `Reservas ${datos.ultimo_anio}`],
              ['evolucion', 'Vida de reservas en el tiempo'],
            ] as const
          ).map(([id, etiqueta]) => (
            <button
              key={id}
              type="button"
              onClick={() => setVista(id)}
              className={`rounded px-2.5 py-1 text-xs transition ${
                vista === id
                  ? 'bg-superficie-alta text-azul-claro'
                  : 'text-texto-tenue hover:text-texto-suave'
              }`}
            >
              {etiqueta}
            </button>
          ))}
        </div>
        <span className="ml-auto font-mono text-[0.65rem] text-texto-tenue">
          reservas comprobadas, miles de boe
        </span>
      </div>

      {vista === 'hoy' ? (
        <ResponsiveContainer width="100%" height={360}>
          <ComposedChart
            data={ranking}
            margin={{ top: 8, right: 8, left: 0, bottom: 44 }}
          >
            <CartesianGrid stroke={COLORES.grilla} strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="operador" {...ejes} angle={-32} textAnchor="end" height={72} interval={0} />
            <YAxis yAxisId="reservas" {...ejes} width={64} />
            <YAxis yAxisId="vida" orientation="right" {...ejes} width={42} unit=" a" />
            <Tooltip
              {...tooltip}
              formatter={(valor, nombre) =>
                String(nombre) === 'Vida de reservas'
                  ? [`${fmt.numero(Number(valor), 1)} años`, 'Vida de reservas']
                  : [`${fmt.entero(Number(valor))} Mboe`, String(nombre)]
              }
            />
            <Legend wrapperStyle={{ fontSize: '0.75rem', color: COLORES.texto }} />
            <Bar
              yAxisId="reservas"
              dataKey="comprobadas_mboe"
              name="Reservas comprobadas"
              radius={[2, 2, 0, 0]}
            >
              {ranking.map((fila) => (
                <Cell
                  key={fila.operador}
                  fill={COLORES.azul}
                  fillOpacity={resaltado(fila.operador) ? 1 : 0.3}
                />
              ))}
            </Bar>
            <Scatter
              yAxisId="vida"
              dataKey="vida_reservas"
              name="Vida de reservas"
              fill={COLORES.oro}
              shape="circle"
            />
          </ComposedChart>
        </ResponsiveContainer>
      ) : (
        <ResponsiveContainer width="100%" height={360}>
          <LineChart data={evolucion} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke={COLORES.grilla} strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="anio" {...ejes} />
            <YAxis {...ejes} width={48} unit=" a" />
            <Tooltip
              {...tooltip}
              formatter={(valor, nombre) => [`${fmt.numero(Number(valor), 1)} años`, String(nombre)]}
            />
            <Legend wrapperStyle={{ fontSize: '0.75rem', color: COLORES.texto }} />
            {seguidos.map((operador, indice) => (
              <Line
                key={operador}
                type="monotone"
                dataKey={operador}
                stroke={PALETA[indice % PALETA.length]}
                strokeWidth={operador === 'YPF' ? 2.5 : 1.5}
                strokeOpacity={resaltado(operador) ? 1 : 0.25}
                dot={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}

      <p className="mt-3 text-xs leading-relaxed text-texto-tenue">
        {vista === 'hoy'
          ? 'Las barras son el stock; los puntos, cuántos años dura al ritmo de producción de ese año. Un operador puede tener muchas reservas y poca vida si produce rápido.'
          : 'La vida de reservas se mueve por dos motivos: porque se incorporan reservas o porque cambia el ritmo al que se las consume.'}{' '}
        {datos.advertencia}
      </p>
    </div>
  );
}
