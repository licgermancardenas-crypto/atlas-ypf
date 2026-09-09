'use client';

// El panel financiero: la serie trimestral con selector de métrica y superposición
// de Brent.
//
// El gráfico dejó de ser una lámina: la misma serie contesta cuatro preguntas
// distintas según qué se mire, y obligar a mirar solo el EBITDA porque es lo que
// alguien eligió al escribir la página desperdicia el resto del panel, que ya
// está cargado en el navegador.

import { useState } from 'react';
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { fmt, type PuntoSerieEbitda } from '@/lib/data';

const COLORES = {
  azul: 'var(--color-azul)',
  azulClaro: 'var(--color-azul-claro)',
  oro: 'var(--color-oro)',
  alza: 'var(--color-alza)',
  baja: 'var(--color-baja)',
  grilla: 'var(--color-borde)',
  texto: 'var(--color-texto-suave)',
};

type IdMetrica = 'adj_ebitda_musd' | 'revenues_musd' | 'margen_ebitda' | 'produccion_kboed';

interface Metrica {
  id: IdMetrica;
  etiqueta: string;
  unidad: string;
  formato: (valor: number | null) => string;
  ayuda: string;
}

const METRICAS: Metrica[] = [
  {
    id: 'adj_ebitda_musd',
    etiqueta: 'EBITDA aj.',
    unidad: 'US$ M',
    formato: (v) => fmt.musd(v),
    ayuda: 'La métrica titular: lo que el mercado mira primero.',
  },
  {
    id: 'revenues_musd',
    etiqueta: 'Ingresos',
    unidad: 'US$ M',
    formato: (v) => fmt.musd(v),
    ayuda: 'La línea de arriba, antes de costos.',
  },
  {
    id: 'margen_ebitda',
    etiqueta: 'Margen',
    unidad: '%',
    formato: (v) => fmt.porcentaje(v),
    ayuda: 'EBITDA sobre ingresos: separa el precio del volumen.',
  },
  {
    id: 'produccion_kboed',
    etiqueta: 'Producción',
    unidad: 'Kboe/d',
    formato: (v) => `${fmt.decimal(v)} Kboe/d`,
    ayuda: 'Lo único de esta lista que no depende del precio del crudo.',
  },
];

export function PanelFinanciero({ serie }: { serie: PuntoSerieEbitda[] }) {
  const [metricaId, setMetricaId] = useState<IdMetrica>('adj_ebitda_musd');
  const [conBrent, setConBrent] = useState(true);

  const metrica = METRICAS.find((m) => m.id === metricaId)!;
  const datos = serie
    .filter((punto) => punto[metricaId] !== null && punto[metricaId] !== undefined)
    .map((punto) => ({
      ...punto,
      etiqueta: fmt.trimestre(punto.trimestre),
      valor: metricaId === 'margen_ebitda' ? (punto.margen_ebitda ?? 0) * 100 : punto[metricaId],
    }));

  const ultimo = datos[datos.length - 1];
  const previoAnual = datos[datos.length - 5];
  const variacion =
    ultimo && previoAnual && Number(previoAnual.valor) !== 0
      ? Number(ultimo.valor) / Number(previoAnual.valor) - 1
      : null;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex rounded-md border border-borde p-0.5">
          {METRICAS.map((opcion) => (
            <button
              key={opcion.id}
              type="button"
              onClick={() => setMetricaId(opcion.id)}
              className={`rounded px-2.5 py-1 text-xs transition ${
                metricaId === opcion.id
                  ? 'bg-superficie-alta text-azul-claro'
                  : 'text-texto-tenue hover:text-texto-suave'
              }`}
            >
              {opcion.etiqueta}
            </button>
          ))}
        </div>

        <label className="flex items-center gap-2 text-xs text-texto-suave">
          <input
            type="checkbox"
            checked={conBrent}
            onChange={(evento) => setConBrent(evento.target.checked)}
            className="accent-[#0054eb]"
          />
          Superponer Brent
        </label>

        {variacion !== null ? (
          <span className="tabular ml-auto text-xs text-texto-tenue">
            {fmt.trimestre(ultimo.trimestre)}:{' '}
            <span className="text-texto">{metrica.formato(Number(ultimo.valor) / (metricaId === 'margen_ebitda' ? 100 : 1))}</span>{' '}
            <span className={variacion >= 0 ? 'text-alza' : 'text-baja'}>
              {fmt.porcentajeConSigno(variacion, 0)} i.a.
            </span>
          </span>
        ) : null}
      </div>

      <ResponsiveContainer width="100%" height={340}>
        <ComposedChart data={datos} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={COLORES.grilla} strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="etiqueta"
            stroke={COLORES.texto}
            tick={{ fill: COLORES.texto, fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: COLORES.grilla }}
            interval={3}
          />
          <YAxis
            yAxisId="metrica"
            stroke={COLORES.texto}
            tick={{ fill: COLORES.texto, fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: COLORES.grilla }}
            width={56}
          />
          {conBrent ? (
            <YAxis
              yAxisId="brent"
              orientation="right"
              stroke={COLORES.texto}
              tick={{ fill: COLORES.texto, fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: COLORES.grilla }}
              width={44}
            />
          ) : null}
          <Tooltip
            contentStyle={{
              background: 'var(--color-superficie-alta)',
              border: '1px solid var(--color-borde)',
              borderRadius: '0.5rem',
              fontSize: '0.8rem',
              fontFamily: 'var(--font-mono)',
            }}
            labelStyle={{ color: 'var(--color-texto)', marginBottom: '0.25rem' }}
            formatter={(valor, nombre) =>
              String(nombre) === 'Brent'
                ? [`US$ ${fmt.decimal(Number(valor))}/bbl`, 'Brent']
                : [
                    metricaId === 'margen_ebitda'
                      ? `${fmt.numero(Number(valor), 1)}%`
                      : metrica.formato(Number(valor)),
                    metrica.etiqueta,
                  ]
            }
          />
          <Legend wrapperStyle={{ fontSize: '0.75rem', color: COLORES.texto }} />
          {metricaId === 'margen_ebitda' ? (
            <ReferenceLine yAxisId="metrica" y={0} stroke={COLORES.texto} />
          ) : null}
          <Bar
            yAxisId="metrica"
            dataKey="valor"
            name={metrica.etiqueta}
            fill={COLORES.azul}
            radius={[2, 2, 0, 0]}
          />
          {conBrent ? (
            <Line
              yAxisId="brent"
              type="monotone"
              dataKey="brent_usd"
              name="Brent"
              stroke={COLORES.oro}
              strokeWidth={2}
              dot={false}
            />
          ) : null}
        </ComposedChart>
      </ResponsiveContainer>

      <p className="mt-2 text-xs text-texto-tenue">{metrica.ayuda}</p>
    </div>
  );
}
