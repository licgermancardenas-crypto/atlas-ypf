'use client';

// El gráfico principal, en cuatro lecturas del mismo dato.
//
//   Producción    el apilado: cuánto sale y de dónde.
//   Crecimiento   la variación contra el mismo período del año anterior.
//   Participación el apilado al 100%: quién le gana lugar a quién.
//   Ranking       el último año, activo por activo, ordenado.
//
// No son cuatro gráficos distintos con cuatro datasets: son cuatro proyecciones
// de las mismas series ya calculadas, y por eso cambiar de vista es instantáneo.
//
// El click sobre una serie, sobre su chip de leyenda o sobre una barra del
// ranking abre la ficha del activo al costado. Es la diferencia entre mirar un
// gráfico y poder investigarlo.

import { useMemo } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { fmt } from '@/lib/data';
import {
  COLOR,
  COLOR_OTROS,
  NOMBRE_OTROS,
  interanual,
  medir,
  type FilaRankingYPF,
  type IdMetrica,
  type IdPeriodo,
  type IdVista,
  type SeriesArmadas,
} from '@/lib/produccion';
import { TooltipProduccion, type DatoTooltip } from './Tooltip';

export interface DatosGrafico {
  armadas: SeriesArmadas;
  /** Participación del shale por período: solo para el tooltip. */
  shalePorPeriodo: (number | null)[];
  colores: Record<string, string>;
}

const EJE = {
  stroke: 'var(--color-texto-suave)',
  tick: { fill: 'var(--color-texto-suave)', fontSize: 11 },
  tickLine: false,
  axisLine: { stroke: 'var(--color-borde)' },
} as const;

function compacto(valor: number): string {
  const absoluto = Math.abs(valor);
  if (absoluto >= 1_000_000) return `${fmt.numero(valor / 1_000_000, 1)}M`;
  if (absoluto >= 1_000) return `${fmt.numero(valor / 1_000, 0)}k`;
  return fmt.entero(valor);
}

export function Grafico({
  vista,
  datos,
  metrica,
  unidad,
  periodo,
  ranking,
  alcanceRanking,
  seleccionado,
  alSeleccionar,
  alto = 400,
}: {
  vista: IdVista;
  datos: DatosGrafico;
  metrica: IdMetrica;
  unidad: string;
  periodo: IdPeriodo;
  ranking: { nombre: string; valor: number; delta: number | null }[];
  alcanceRanking: 'completo' | 'principales';
  seleccionado: string | null;
  alSeleccionar: (nombre: string | null) => void;
  alto?: number;
}) {
  const { armadas, shalePorPeriodo, colores } = datos;
  const participacion = vista === 'participacion';

  // Una sola pasada arma la tabla que consumen las tres vistas temporales: con
  // doscientos períodos por diecisiete series, rehacerla en cada render se nota.
  const filas = useMemo(() => {
    return armadas.etiquetas.map((etiqueta, indice) => {
      const dias = armadas.dias[indice] || 1;
      const fila: Record<string, string | number> = {
        periodo: etiqueta,
        __completo: armadas.completo[indice] ? 1 : 0,
      };
      const total = armadas.series.reduce((suma, serie) => suma + (serie.valores[indice] ?? 0), 0);
      for (const serie of armadas.series) {
        const volumen = serie.valores[indice] ?? 0;
        fila[serie.nombre] = participacion
          ? total > 0
            ? Number(((volumen / total) * 100).toFixed(2))
            : 0
          : Math.round(medir(volumen, dias, metrica));
      }
      fila.__total = participacion ? 100 : Math.round(medir(total, dias, metrica));
      return fila;
    });
  }, [armadas, metrica, participacion]);

  const crecimiento = useMemo(() => {
    const totales = armadas.etiquetas.map((_, indice) =>
      armadas.series.reduce((suma, serie) => suma + (serie.valores[indice] ?? 0), 0),
    );
    // Sobre caudal y no sobre volumen: comparar el volumen de un trimestre de 90
    // días con uno de 92 mete dos puntos de crecimiento que no existieron.
    const caudales = totales.map((valor, indice) => valor / (armadas.dias[indice] || 1));
    const variaciones = interanual(caudales, periodo);
    return armadas.etiquetas
      .map((etiqueta, indice) => ({
        periodo: etiqueta,
        variacion: variaciones[indice] === null ? null : Number((variaciones[indice]! * 100).toFixed(1)),
        completo: armadas.completo[indice],
      }))
      .filter((fila) => fila.variacion !== null);
  }, [armadas, periodo]);

  const contenidoTooltip = useMemo(
    () =>
      function Contenido({ active, label }: { active?: boolean; label?: string | number }) {
        if (!active || label === undefined) return null;
        const indice = armadas.etiquetas.indexOf(String(label));
        if (indice < 0) return null;
        const fila = filas[indice];

        const activos = armadas.series
          .map((serie) => ({
            nombre: serie.nombre,
            valor: Number(fila[serie.nombre] ?? 0),
            color: colores[serie.nombre] ?? COLOR_OTROS,
          }))
          .filter((activo) => activo.valor > 0)
          .sort((a, b) => b.valor - a.valor);

        const visibles = activos.slice(0, 5);
        const resto = activos.slice(5);
        const dato: DatoTooltip = {
          periodo: String(label),
          completo: Boolean(fila.__completo),
          total: Number(fila.__total ?? 0),
          unidad,
          shale: shalePorPeriodo[indice] ?? null,
          activos: visibles,
          resto: resto.length
            ? {
                cantidad: resto.length,
                valor: resto.reduce((suma, activo) => suma + activo.valor, 0),
              }
            : null,
          participacion,
        };
        return <TooltipProduccion dato={dato} />;
      },
    [armadas.etiquetas, armadas.series, colores, filas, participacion, shalePorPeriodo, unidad],
  );

  if (vista === 'ranking') {
    const filasRanking = ranking.slice(0, 14);
    const maximo = Math.max(...filasRanking.map((fila) => fila.valor), 1);

    return (
      <div>
        <ResponsiveContainer width="100%" height={Math.max(alto, filasRanking.length * 26)}>
          <BarChart
            data={filasRanking}
            layout="vertical"
            margin={{ top: 4, right: 56, left: 4, bottom: 4 }}
            onClick={(evento: { activeLabel?: string | number }) => {
              if (evento?.activeLabel !== undefined) alSeleccionar(String(evento.activeLabel));
            }}
          >
            <CartesianGrid stroke="var(--color-borde)" strokeDasharray="2 4" horizontal={false} />
            <XAxis type="number" domain={[0, maximo]} {...EJE} tickFormatter={compacto} />
            <YAxis
              type="category"
              dataKey="nombre"
              width={168}
              {...EJE}
              tick={{ fill: 'var(--color-texto-suave)', fontSize: 11 }}
            />
            <Tooltip
              cursor={{ fill: 'var(--color-superficie-alta)', fillOpacity: 0.35 }}
              contentStyle={{
                background: 'var(--color-superficie-alta)',
                border: '1px solid var(--color-borde)',
                borderRadius: '0.5rem',
                fontSize: '0.75rem',
                fontFamily: 'var(--font-mono)',
              }}
              labelStyle={{ color: 'var(--color-texto)' }}
              formatter={(valor: unknown) => [`${fmt.entero(Number(valor))} ${unidad}`, 'Últimos 12m']}
            />
            <Bar dataKey="valor" radius={[0, 3, 3, 0]} maxBarSize={16} cursor="pointer">
              {filasRanking.map((fila) => (
                <Cell
                  key={fila.nombre}
                  fill={
                    seleccionado === fila.nombre
                      ? 'var(--color-azul-claro)'
                      : fila.nombre === NOMBRE_OTROS
                        ? COLOR_OTROS
                        : 'var(--color-azul)'
                  }
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <p className="mt-2 text-[0.7rem] text-texto-tenue">
          Promedio diario de los últimos doce meses. Clic en una barra para abrir la ficha del
          activo.{' '}
          {alcanceRanking === 'principales'
            ? 'Con este cruce de producto y tipo de roca el ranking se calcula sobre los activos con serie propia, no sobre todos.'
            : null}
        </p>
      </div>
    );
  }

  if (vista === 'crecimiento') {
    return (
      <div>
        <ResponsiveContainer width="100%" height={alto}>
          <BarChart data={crecimiento} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--color-borde)" strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="periodo" {...EJE} minTickGap={40} />
            <YAxis {...EJE} width={52} unit="%" />
            <ReferenceLine y={0} stroke="var(--color-borde-vivo)" />
            <Tooltip
              cursor={{ fill: 'var(--color-superficie-alta)', fillOpacity: 0.35 }}
              contentStyle={{
                background: 'var(--color-superficie-alta)',
                border: '1px solid var(--color-borde)',
                borderRadius: '0.5rem',
                fontSize: '0.75rem',
                fontFamily: 'var(--font-mono)',
              }}
              labelStyle={{ color: 'var(--color-texto)' }}
              formatter={(valor: unknown) => [
                `${fmt.numero(Number(valor), 1)}%`,
                'Variación interanual',
              ]}
            />
            <Bar dataKey="variacion" radius={[2, 2, 0, 0]} maxBarSize={22}>
              {crecimiento.map((fila) => (
                <Cell
                  key={fila.periodo}
                  fill={(fila.variacion ?? 0) >= 0 ? COLOR.alza : COLOR.baja}
                  fillOpacity={fila.completo ? 0.9 : 0.45}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <p className="mt-2 text-[0.7rem] text-texto-tenue">
          Variación del caudal contra el mismo período del año anterior —no contra el período
          previo—, para que la estacionalidad no se lea como tendencia. Las barras claras son
          períodos todavía incompletos.
        </p>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={alto}>
      <AreaChart
        data={filas}
        margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
        onClick={(evento: { activeLabel?: string | number }) => {
          // Clic en el área: si hay un activo seleccionado, un clic al vacío lo
          // suelta. Seleccionar se hace desde la leyenda o el ranking, que son
          // objetivos precisos; un apilado no lo es.
          if (evento?.activeLabel === undefined) alSeleccionar(null);
        }}
      >
        <CartesianGrid stroke="var(--color-borde)" strokeDasharray="2 4" vertical={false} />
        <XAxis dataKey="periodo" {...EJE} minTickGap={40} />
        <YAxis
          {...EJE}
          width={58}
          tickFormatter={(valor: number) =>
            participacion ? `${valor}%` : compacto(Number(valor))
          }
        />
        <Tooltip
          cursor={{ stroke: 'var(--color-borde-vivo)', strokeWidth: 1 }}
          content={contenidoTooltip}
          isAnimationActive={false}
        />
        {armadas.series.map((serie) => {
          const color = colores[serie.nombre] ?? COLOR_OTROS;
          const apagada = seleccionado !== null && seleccionado !== serie.nombre;
          return (
            <Area
              key={serie.nombre}
              type="monotone"
              dataKey={serie.nombre}
              stackId="produccion"
              stroke={color}
              fill={color}
              fillOpacity={apagada ? 0.18 : 0.72}
              strokeOpacity={apagada ? 0.35 : 1}
              strokeWidth={seleccionado === serie.nombre ? 1.6 : 0.5}
              isAnimationActive={false}
              onClick={() => alSeleccionar(serie.nombre)}
              style={{ cursor: 'pointer' }}
            />
          );
        })}
      </AreaChart>
    </ResponsiveContainer>
  );
}

/** La leyenda: un chip por serie, y cada chip es un botón.
 *
 *  Va arriba del gráfico y no abajo porque acá no es un pie de página: es el
 *  control con el que se elige qué activo investigar. */
export function Leyenda({
  series,
  colores,
  seleccionado,
  alSeleccionar,
  valores,
  unidad,
}: {
  series: { nombre: string }[];
  colores: Record<string, string>;
  seleccionado: string | null;
  alSeleccionar: (nombre: string | null) => void;
  /** Valor del último período, para que el chip diga algo además del nombre. */
  valores: Record<string, number>;
  unidad: string;
}) {
  return (
    <ul className="flex flex-wrap gap-1.5">
      {series.map((serie) => {
        const activo = seleccionado === serie.nombre;
        const color = colores[serie.nombre] ?? COLOR_OTROS;
        return (
          <li key={serie.nombre}>
            <button
              type="button"
              onClick={() => alSeleccionar(activo ? null : serie.nombre)}
              aria-pressed={activo}
              title={`${serie.nombre}: ${fmt.entero(valores[serie.nombre] ?? 0)} ${unidad} en el último período`}
              className={`flex items-center gap-1.5 rounded-md border px-2 py-1 text-[0.72rem] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-azul-claro ${
                activo
                  ? 'border-azul-claro bg-superficie-alta text-texto'
                  : 'border-borde text-texto-suave hover:border-borde-vivo hover:text-texto'
              }`}
            >
              <span
                aria-hidden
                className="h-2 w-2 rounded-[2px]"
                style={{ background: color }}
              />
              <span className="max-w-[11rem] truncate">{serie.nombre}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
