'use client';

// El módulo de segmentos: la cadena de valor con los números adentro.
//
// El consolidado de YPF promedia tres negocios que no se parecen: uno que saca
// petróleo de la roca, otro que lo refina y lo vende en la esquina, y un
// tercero que está construyendo un negocio de gas que todavía casi no factura.
// Un trimestre récord puede venir de cualquiera de los tres, y del consolidado
// no se deduce cuál.
//
// La página está armada alrededor de una idea que el dato hace evidente: casi
// todo lo que Upstream produce se lo vende a la propia compañía, y el que le
// vende al mercado es Downstream. Por eso la vista principal es la cadena —de
// dónde sale el barril, por dónde pasa y quién lo cobra— y no una tabla.

import { useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { IlustracionSegmento } from '@/components/ilustraciones/escenas';
import { COLOR, QUE_HACE } from '@/components/segmentos/negocios';
import { fmt } from '@/lib/data';
import type { Segmentos } from '@/lib/libro';

const METRICAS = [
  { clave: 'ingresos_totales', etiqueta: 'Ingresos', unidad: 'musd' },
  { clave: 'resultado_operativo', etiqueta: 'Resultado operativo', unidad: 'musd' },
  { clave: 'capex_ppe', etiqueta: 'Capex', unidad: 'musd' },
  { clave: 'activos', etiqueta: 'Activos', unidad: 'musd' },
] as const;

const ejeComun = {
  stroke: 'var(--color-texto-suave)',
  tick: { fill: 'var(--color-texto-suave)', fontSize: 11 },
  tickLine: false,
};

const tooltipComun = {
  contentStyle: {
    background: 'var(--color-superficie-alta)',
    border: '1px solid var(--color-borde)',
    borderRadius: '0.5rem',
    fontSize: '0.8rem',
  },
  labelStyle: { color: 'var(--color-texto)' },
};

export function ModuloSegmentos({ segmentos }: { segmentos: Segmentos }) {
  const trimestres = segmentos.trimestres;
  const [indice, setIndice] = useState(trimestres.length - 1);
  const [metrica, setMetrica] = useState<(typeof METRICAS)[number]['clave']>('ingresos_totales');

  // Un acceso directo por concepto y segmento, que es como se lo consulta acá.
  const valores = useMemo(() => {
    const mapa: Record<string, Record<string, (number | null)[]>> = {};
    Object.entries(segmentos.conceptos).forEach(([concepto, bloque]) => {
      mapa[concepto] = {};
      bloque.filas.forEach((fila) => {
        mapa[concepto][fila.segmento] = fila.trimestral;
      });
    });
    return mapa;
  }, [segmentos]);

  const leer = (concepto: string, segmento: string, posicion = indice): number | null =>
    valores[concepto]?.[segmento]?.[posicion] ?? null;

  // Los segmentos que la compañía publicó en ese trimestre, sin el total ni la
  // eliminación: son los que forman la cadena.
  const activos = useMemo(
    () =>
      segmentos.segmentos.filter(
        (segmento) =>
          segmento !== 'Total' &&
          segmento !== 'Ajustes de consolidación' &&
          leer('ingresos_totales', segmento) !== null,
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [segmentos, indice, valores],
  );

  const [seleccionado, setSeleccionado] = useState('Upstream');
  const elegido = activos.includes(seleccionado) ? seleccionado : activos[0] ?? 'Upstream';

  const total = leer('ingresos_totales', 'Total') ?? 0;
  const capexTotal = leer('capex_ppe', 'Total') ?? 0;
  const activosTotal = leer('activos', 'Total') ?? 0;
  const eliminacion = leer('ingresos_intersegmento', 'Ajustes de consolidación');

  const serieEvolucion = trimestres.map((trimestre, posicion) => {
    const punto: Record<string, string | number | null> = { trimestre: fmt.trimestre(trimestre) };
    activos.forEach((segmento) => {
      punto[segmento] = leer(metrica, segmento, posicion);
    });
    return punto;
  });

  const serieDetalle = trimestres.map((trimestre, posicion) => ({
    trimestre: fmt.trimestre(trimestre),
    externos: leer('ingresos_externos', elegido, posicion),
    intersegmento: leer('ingresos_intersegmento', elegido, posicion),
    margen: (() => {
      const ingresos = leer('ingresos_totales', elegido, posicion);
      const operativo = leer('resultado_operativo', elegido, posicion);
      return ingresos && operativo !== null ? operativo / ingresos : null;
    })(),
  }));

  const ficha = QUE_HACE[elegido];

  return (
    <div>
      {/* ---------------------------------------------------------------- */}
      {/* El trimestre que se está mirando                                  */}
      {/* ---------------------------------------------------------------- */}
      <div className="marquesina flex flex-wrap items-center gap-4 rounded-lg border border-borde bg-superficie p-4">
        <div>
          <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
            Trimestre
          </p>
          <p className="mt-1 text-2xl font-bold text-texto">{fmt.trimestre(trimestres[indice])}</p>
        </div>
        <label className="min-w-[14rem] flex-1">
          <input
            type="range"
            min={0}
            max={trimestres.length - 1}
            value={indice}
            onChange={(evento) => setIndice(Number(evento.target.value))}
            className="w-full accent-[#0054eb]"
            aria-label="Trimestre"
          />
          <span className="mt-1 flex justify-between text-[0.65rem] text-texto-tenue">
            <span>{fmt.trimestre(trimestres[0])}</span>
            <span>{fmt.trimestre(trimestres[trimestres.length - 1])}</span>
          </span>
        </label>
        <div className="flex gap-6 text-right">
          <div>
            <p className="text-[0.7rem] text-texto-tenue">Ingresos consolidados</p>
            <p className="tabular text-lg text-texto">{fmt.musd(total)}</p>
          </div>
          <div>
            <p className="text-[0.7rem] text-texto-tenue">Se elimina entre segmentos</p>
            <p className="tabular text-lg text-oro">{fmt.musd(eliminacion)}</p>
          </div>
        </div>
      </div>

      {/* ---------------------------------------------------------------- */}
      {/* La cadena                                                         */}
      {/* ---------------------------------------------------------------- */}
      <h2 className="mt-10 text-xl font-semibold text-texto">La cadena, en ese trimestre</h2>
      <p className="mt-2 max-w-3xl text-sm leading-relaxed text-texto-suave">
        Cada tarjeta es un negocio. La barra muestra a quién le factura: lo azul es lo que le vende
        al mercado y lo dorado lo que le vende a otro segmento de la propia YPF. Tocá una tarjeta
        para ver ese negocio abajo.
      </p>

      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {activos.map((segmento) => {
          const ingresos = leer('ingresos_totales', segmento) ?? 0;
          const externos = leer('ingresos_externos', segmento) ?? 0;
          const intersegmento = leer('ingresos_intersegmento', segmento) ?? 0;
          const operativo = leer('resultado_operativo', segmento);
          const capex = leer('capex_ppe', segmento);
          const activosSegmento = leer('activos', segmento);
          const proporcionExterna = ingresos > 0 ? Math.max(0, externos) / ingresos : 0;
          const esElegido = segmento === elegido;

          return (
            <button
              key={segmento}
              type="button"
              onClick={() => setSeleccionado(segmento)}
              aria-pressed={esElegido}
              data-activa={esElegido}
              className={`marquesina rounded-lg border p-4 text-left transition-colors ${
                esElegido
                  ? 'border-azul-claro bg-superficie-alta'
                  : 'border-borde bg-superficie hover:border-azul-claro/60'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-texto">{segmento}</p>
                  <p className="tabular mt-1 text-2xl font-bold" style={{ color: COLOR[segmento] }}>
                    {fmt.musd(ingresos)}
                  </p>
                </div>
                <IlustracionSegmento segmento={segmento} className="h-16 w-28 shrink-0 opacity-90" />
              </div>

              <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-borde">
                <div
                  className="h-full bg-azul-claro"
                  style={{ width: `${(proporcionExterna * 100).toFixed(1)}%` }}
                />
              </div>
              <p className="mt-1.5 flex justify-between text-[0.7rem] text-texto-tenue">
                <span>
                  <span className="text-azul-claro">{fmt.porcentaje(proporcionExterna, 0)}</span> al
                  mercado
                </span>
                <span>
                  <span className="text-oro">{fmt.musd(intersegmento)}</span> a la propia YPF
                </span>
              </p>

              <dl className="mt-3 grid grid-cols-3 gap-2 border-t border-borde/60 pt-3 text-[0.7rem]">
                <div>
                  <dt className="text-texto-tenue">Margen</dt>
                  <dd className="tabular text-texto">
                    {ingresos && operativo !== null ? fmt.porcentaje(operativo / ingresos, 0) : '—'}
                  </dd>
                </div>
                <div>
                  <dt className="text-texto-tenue">Capex</dt>
                  <dd className="tabular text-texto">
                    {capex !== null && capexTotal ? fmt.porcentaje(capex / capexTotal, 0) : '—'}
                  </dd>
                </div>
                <div>
                  <dt className="text-texto-tenue">Activos</dt>
                  <dd className="tabular text-texto">
                    {activosSegmento !== null && activosTotal
                      ? fmt.porcentaje(activosSegmento / activosTotal, 0)
                      : '—'}
                  </dd>
                </div>
              </dl>
            </button>
          );
        })}

        {/* El final de la cadena: lo que efectivamente sale a la calle. */}
        <div className="marquesina rounded-lg border border-dashed border-borde bg-superficie p-4">
          <p className="text-sm font-medium text-texto">El mercado</p>
          <p className="tabular mt-1 text-2xl font-bold text-texto">{fmt.musd(total)}</p>
          <p className="mt-3 text-[0.7rem] leading-relaxed text-texto-suave">
            Es la suma de lo que cada segmento le factura a terceros, que es exactamente el ingreso
            del estado de resultados. Las ventas entre segmentos —{fmt.musd(Math.abs(eliminacion ?? 0))} en
            este trimestre— se eliminan: contarlas sería cobrar dos veces el mismo barril.
          </p>
        </div>
      </div>

      {/* ---------------------------------------------------------------- */}
      {/* Evolución                                                         */}
      {/* ---------------------------------------------------------------- */}
      <h2 className="mt-12 text-xl font-semibold text-texto">Cómo evolucionó cada negocio</h2>
      <div className="mt-3 flex flex-wrap gap-2">
        {METRICAS.map((opcion) => (
          <button
            key={opcion.clave}
            type="button"
            onClick={() => setMetrica(opcion.clave)}
            className={`rounded-md border px-3 py-1.5 text-xs transition-colors ${
              metrica === opcion.clave
                ? 'border-azul-claro bg-superficie-alta text-texto'
                : 'border-borde text-texto-suave hover:text-texto'
            }`}
          >
            {opcion.etiqueta}
          </button>
        ))}
      </div>

      <div className="marquesina mt-4 rounded-lg border border-borde bg-superficie p-4">
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={serieEvolucion} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid stroke="var(--color-borde)" vertical={false} />
            <XAxis dataKey="trimestre" {...ejeComun} interval={3} />
            <YAxis {...ejeComun} tickFormatter={(valor: number) => fmt.entero(valor)} width={58} />
            <Tooltip
              {...tooltipComun}
              formatter={(valor, nombre) => [fmt.musd(Number(valor)), String(nombre)]}
            />
            <Legend wrapperStyle={{ fontSize: '0.7rem' }} />
            {activos.map((segmento) => (
              <Bar
                key={segmento}
                dataKey={segmento}
                stackId="segmentos"
                fill={COLOR[segmento] ?? 'var(--color-neutro)'}
                fillOpacity={segmento === elegido ? 1 : 0.45}
                onClick={() => setSeleccionado(segmento)}
                cursor="pointer"
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
        <p className="mt-2 text-[0.7rem] leading-relaxed text-texto-tenue">
          El segmento elegido se dibuja lleno y el resto atenuado. Las barras cambian de composición
          en 2023 y 2025 porque la compañía reordenó sus segmentos: cada trimestre se muestra con la
          apertura que usó para ese período, y por eso los negocios viejos se cortan donde el
          negocio se reordenó.
        </p>
      </div>

      {/* ---------------------------------------------------------------- */}
      {/* El segmento elegido                                               */}
      {/* ---------------------------------------------------------------- */}
      <h2 className="mt-12 text-xl font-semibold text-texto">{elegido}</h2>
      {ficha ? <p className="mt-1 text-sm text-texto-suave">{ficha.titulo}</p> : null}

      <div className="mt-5 grid gap-6 lg:grid-cols-[1fr_20rem]">
        <div className="space-y-6">
          <div className="marquesina rounded-lg border border-borde bg-superficie p-4">
            <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
              A quién le factura, trimestre a trimestre
            </p>
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={serieDetalle} margin={{ top: 12, right: 16, bottom: 8, left: 8 }}>
                <CartesianGrid stroke="var(--color-borde)" vertical={false} />
                <XAxis dataKey="trimestre" {...ejeComun} interval={3} />
                <YAxis {...ejeComun} tickFormatter={(valor: number) => fmt.entero(valor)} width={58} />
                <Tooltip
                  {...tooltipComun}
                  formatter={(valor, nombre) => [
                    fmt.musd(Number(valor)),
                    String(nombre) === 'externos' ? 'Al mercado' : 'A otro segmento',
                  ]}
                />
                <Area
                  type="monotone"
                  dataKey="externos"
                  stackId="ingresos"
                  stroke="var(--color-azul-claro)"
                  fill="var(--color-azul)"
                  fillOpacity={0.55}
                />
                <Area
                  type="monotone"
                  dataKey="intersegmento"
                  stackId="ingresos"
                  stroke="var(--color-oro)"
                  fill="var(--color-oro)"
                  fillOpacity={0.35}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="marquesina rounded-lg border border-borde bg-superficie p-4">
            <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
              Margen operativo
            </p>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={serieDetalle} margin={{ top: 12, right: 16, bottom: 8, left: 8 }}>
                <CartesianGrid stroke="var(--color-borde)" vertical={false} />
                <XAxis dataKey="trimestre" {...ejeComun} interval={3} />
                <YAxis
                  {...ejeComun}
                  width={48}
                  tickFormatter={(valor: number) => `${(valor * 100).toFixed(0)}%`}
                />
                <Tooltip
                  {...tooltipComun}
                  formatter={(valor) => [fmt.porcentaje(Number(valor)), 'Margen operativo']}
                />
                <Line
                  type="monotone"
                  dataKey="margen"
                  stroke={COLOR[elegido] ?? 'var(--color-azul-claro)'}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="space-y-4">
          <div className="marquesina rounded-lg border border-borde bg-superficie p-4">
            <IlustracionSegmento segmento={elegido} className="h-24 w-full" />
            {ficha ? (
              <p className="mt-3 text-xs leading-relaxed text-texto-suave">{ficha.texto}</p>
            ) : null}
            {ficha?.datos.length ? (
              <ul className="mt-3 space-y-1.5 border-t border-borde/60 pt-3 text-[0.7rem] leading-relaxed text-texto-tenue">
                {ficha.datos.map((dato) => (
                  <li key={dato}>· {dato}</li>
                ))}
              </ul>
            ) : null}
          </div>

          <div className="marquesina rounded-lg border border-borde bg-superficie p-4">
            <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
              En {fmt.trimestre(trimestres[indice])}
            </p>
            <dl className="mt-3 space-y-2 text-xs">
              {[
                ['Ingresos totales', fmt.musd(leer('ingresos_totales', elegido))],
                ['Al mercado', fmt.musd(leer('ingresos_externos', elegido))],
                ['A otro segmento', fmt.musd(leer('ingresos_intersegmento', elegido))],
                ['Resultado operativo', fmt.musd(leer('resultado_operativo', elegido))],
                ['Capex', fmt.musd(leer('capex_ppe', elegido))],
                ['Depreciación', fmt.musd(leer('depreciacion_ppe', elegido))],
                ['Activos', fmt.musd(leer('activos', elegido))],
              ].map(([etiqueta, valor]) => (
                <div key={etiqueta} className="flex justify-between gap-3 border-b border-borde/40 pb-1.5">
                  <dt className="text-texto-suave">{etiqueta}</dt>
                  <dd className="tabular text-texto">{valor}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </div>
    </div>
  );
}
