'use client';

// El explorador de producción nacional: la misma serie abierta por cuenca,
// provincia, empresa o yacimiento, y separada en convencional, shale y tight.
//
// Es el panel que contesta lo que viene después del titular. "El shale de YPF
// creció 47%" es un hecho; "YPF creció 6% porque el shale tapó la caída del
// convencional" es un análisis, y hasta que no entró el convencional al pipeline
// no se podía decir ninguna de las dos con el mismo dato.
//
// La vista de participación existe por la misma razón: en nivel, todo lo que
// crece parece bueno. En porcentaje se ve quién le está ganando lugar a quién.

import { useMemo, useState } from 'react';
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

import { fmt, type PuntoPais } from '@/lib/data';
import { useFiltros } from './estado/filtros';
import type { FilaRanking } from './RankingCrecimiento';

export interface MiembroProduccion {
  nombre: string;
  oil_total: number[];
  oil_convencional: number[];
  oil_shale: number[];
  oil_tight: number[];
  gas_total: number[];
  gas_convencional: number[];
  gas_shale: number[];
  gas_tight: number[];
}

export interface DimensionProduccion {
  fechas: string[];
  miembros: MiembroProduccion[];
  ranking: FilaRanking[];
}

export interface ProduccionPais {
  fuente: string;
  nota: string;
  cobertura: { desde: string; hasta: string };
  pais: PuntoPais[];
  dimensiones: Record<string, DimensionProduccion>;
}

type IdDimension = 'cuenca' | 'provincia' | 'empresa' | 'concesion' | 'yacimiento';
type IdFluido = 'oil' | 'gas';
type IdConcepto = 'total' | 'convencional' | 'shale' | 'tight';

const DIMENSIONES: { id: IdDimension; etiqueta: string }[] = [
  { id: 'cuenca', etiqueta: 'Cuenca' },
  { id: 'provincia', etiqueta: 'Provincia' },
  { id: 'empresa', etiqueta: 'Empresa' },
  { id: 'concesion', etiqueta: 'Concesión' },
  { id: 'yacimiento', etiqueta: 'Yacimiento' },
];

const CONCEPTOS: { id: IdConcepto; etiqueta: string; ayuda: string }[] = [
  { id: 'total', etiqueta: 'Todo', ayuda: 'Convencional, shale y tight sumados.' },
  {
    id: 'convencional',
    etiqueta: 'Convencional',
    ayuda: 'Los campos viejos. Es la parte que declina y que el shale tiene que compensar.',
  },
  { id: 'shale', etiqueta: 'Shale', ayuda: 'Vaca Muerta, casi en su totalidad.' },
  { id: 'tight', etiqueta: 'Tight', ayuda: 'No convencional de roca compacta: Lajas, Mulichinco.' },
];

// Trece colores que se distinguen entre sí sobre fondo oscuro, con el azul de
// marca al frente: el primer miembro del ranking es el protagonista.
const COLORES = [
  '#0054eb',
  '#f0a830',
  '#3fb98a',
  '#75aadb',
  '#e2603f',
  '#8e6fd8',
  '#4d90ff',
  '#c9a227',
  '#2f8f72',
  '#a86a4d',
  '#6d80a8',
  '#d46fa0',
  '#41546f',
];

export function ExploradorProduccion({ datos }: { datos: ProduccionPais }) {
  const [dimension, setDimension] = useState<IdDimension>('cuenca');
  const [fluido, setFluido] = useState<IdFluido>('oil');
  const [concepto, setConcepto] = useState<IdConcepto>('total');
  const [participacion, setParticipacion] = useState(false);
  const { filtros } = useFiltros();

  const definicionConcepto = CONCEPTOS.find((c) => c.id === concepto)!;
  const bloque = datos.dimensiones[dimension];

  const { filas, miembros } = useMemo(() => {
    if (!bloque) return { filas: [], miembros: [] as string[] };

    const clave = `${fluido}_${concepto}` as keyof MiembroProduccion;
    const visibles =
      dimension === 'empresa' && filtros.operador !== 'todos'
        ? bloque.miembros.filter((m) => m.nombre === filtros.operador)
        : bloque.miembros;

    const nombres = visibles.map((m) => m.nombre);
    const armadas = bloque.fechas
      .map((fecha, indice) => {
        const fila: Record<string, string | number> = { fecha };
        let suma = 0;
        for (const miembro of visibles) {
          const valor = (miembro[clave] as number[])?.[indice] ?? 0;
          fila[miembro.nombre] = valor;
          suma += valor;
        }
        if (participacion && suma > 0) {
          for (const nombre of nombres) {
            fila[nombre] = Number((((fila[nombre] as number) / suma) * 100).toFixed(1));
          }
        }
        return fila;
      })
      .filter((fila) => {
        const anio = Number(String(fila.fecha).slice(0, 4));
        return anio >= filtros.desde && anio <= filtros.hasta;
      });

    return { filas: armadas, miembros: nombres };
  }, [bloque, fluido, concepto, dimension, participacion, filtros.operador, filtros.desde, filtros.hasta]);

  const ultimaFila = filas[filas.length - 1];
  const totalUltimo = miembros.reduce(
    (suma, nombre) => suma + ((ultimaFila?.[nombre] as number) ?? 0),
    0,
  );

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2">
        <Segmentado
          opciones={DIMENSIONES.map((d) => ({ id: d.id, etiqueta: d.etiqueta }))}
          valor={dimension}
          alCambiar={(id) => setDimension(id as IdDimension)}
        />
        <Segmentado
          opciones={[
            { id: 'oil', etiqueta: 'Petróleo' },
            { id: 'gas', etiqueta: 'Gas' },
          ]}
          valor={fluido}
          alCambiar={(id) => setFluido(id as IdFluido)}
        />
        <Segmentado
          opciones={CONCEPTOS.map((c) => ({ id: c.id, etiqueta: c.etiqueta }))}
          valor={concepto}
          alCambiar={(id) => setConcepto(id as IdConcepto)}
        />
        <label className="flex items-center gap-2 text-xs text-texto-suave">
          <input
            type="checkbox"
            checked={participacion}
            onChange={(evento) => setParticipacion(evento.target.checked)}
            className="accent-[#0054eb]"
          />
          Ver participación
        </label>
        {ultimaFila ? (
          <span className="tabular ml-auto text-xs text-texto-tenue">
            {String(ultimaFila.fecha)}:{' '}
            <span className="text-texto">
              {participacion ? '100%' : `${fmt.entero(totalUltimo)} ${fluido === 'oil' ? 'bbl/d' : 'boe/d'}`}
            </span>
          </span>
        ) : null}
      </div>

      <ResponsiveContainer width="100%" height={360}>
        <AreaChart data={filas} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
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
            width={56}
            unit={participacion ? '%' : ''}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--color-superficie-alta)',
              border: '1px solid var(--color-borde)',
              borderRadius: '0.5rem',
              fontSize: '0.75rem',
              fontFamily: 'var(--font-mono)',
              maxHeight: 260,
              overflow: 'auto',
            }}
            labelStyle={{ color: 'var(--color-texto)', marginBottom: '0.25rem' }}
            formatter={(valor, nombre) => [
              participacion
                ? `${fmt.numero(Number(valor), 1)}%`
                : `${fmt.entero(Number(valor))} ${fluido === 'oil' ? 'bbl/d' : 'boe/d'}`,
              String(nombre),
            ]}
          />
          <Legend wrapperStyle={{ fontSize: '0.7rem', color: 'var(--color-texto-suave)' }} />
          {miembros.map((nombre, indice) => (
            <Area
              key={nombre}
              type="monotone"
              dataKey={nombre}
              stackId="produccion"
              stroke={COLORES[indice % COLORES.length]}
              fill={COLORES[indice % COLORES.length]}
              fillOpacity={0.72}
              strokeWidth={0.5}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>

      <p className="mt-2 text-xs text-texto-tenue">
        {definicionConcepto.ayuda} {datos.nota}
      </p>
    </div>
  );
}

function Segmentado({
  opciones,
  valor,
  alCambiar,
}: {
  opciones: { id: string; etiqueta: string }[];
  valor: string;
  alCambiar: (id: string) => void;
}) {
  return (
    <div className="flex rounded-md border border-borde p-0.5">
      {opciones.map((opcion) => (
        <button
          key={opcion.id}
          type="button"
          onClick={() => alCambiar(opcion.id)}
          className={`rounded px-2.5 py-1 text-xs transition ${
            valor === opcion.id
              ? 'bg-superficie-alta text-azul-claro'
              : 'text-texto-tenue hover:text-texto-suave'
          }`}
        >
          {opcion.etiqueta}
        </button>
      ))}
    </div>
  );
}
