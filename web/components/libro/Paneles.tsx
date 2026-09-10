'use client';

// Los tres paneles que acompañan a los estados: segmentos, comparables y deuda.
//
// Van juntos porque son la misma idea repetida —una tabla y un gráfico que la
// explica— y separados de la tabla de estados, que tiene su propio
// comportamiento de planilla.

import { useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { TablaExcel, type FilaExcel } from '@/components/TablaExcel';
import { fmt } from '@/lib/data';
import type { Comparables, Deuda, Segmentos } from '@/lib/libro';

const PALETA = [
  'var(--color-azul)',
  'var(--color-oro)',
  'var(--color-alza)',
  'var(--color-celeste)',
  'var(--color-neutro)',
  'var(--color-baja)',
];

const tooltipComun = {
  contentStyle: {
    background: 'var(--color-superficie-alta)',
    border: '1px solid var(--color-borde)',
    borderRadius: '0.5rem',
    fontSize: '0.8rem',
  },
  labelStyle: { color: 'var(--color-texto)' },
};

const ejeComun = {
  stroke: 'var(--color-texto-suave)',
  tick: { fill: 'var(--color-texto-suave)', fontSize: 11 },
  tickLine: false,
};

// --------------------------------------------------------------------------- //
// Segmentos
// --------------------------------------------------------------------------- //
export function PanelSegmentos({ segmentos }: { segmentos: Segmentos }) {
  const [concepto, setConcepto] = useState('ingresos_totales');
  const bloque = segmentos.conceptos[concepto];
  const conceptos = Object.entries(segmentos.conceptos);

  // Los segmentos que hoy existen: los de las aperturas viejas quedan en la
  // tabla pero no en el gráfico, donde apilarlos contaría dos veces el negocio.
  const vigentes = (bloque?.filas ?? []).filter((fila) =>
    fila.trimestral.slice(-4).some((valor) => valor !== null),
  );

  const datos = segmentos.trimestres.map((trimestre, indice) => {
    const punto: Record<string, string | number | null> = { trimestre: fmt.trimestre(trimestre) };
    vigentes
      .filter((fila) => fila.segmento !== 'Total')
      .forEach((fila) => {
        punto[fila.segmento] = fila.trimestral[indice];
      });
    return punto;
  });

  const filas: FilaExcel[] = (bloque?.filas ?? []).map((fila) => ({
    concepto: fila.segmento,
    subtotal: fila.segmento === 'Total',
    formato: 'entero' as const,
    valores: fila.trimestral,
  }));

  const margen: FilaExcel[] =
    concepto === 'resultado_operativo'
      ? (segmentos.conceptos.ingresos_totales?.filas ?? []).map((ingresos) => {
          const operativo = bloque?.filas.find((fila) => fila.segmento === ingresos.segmento);
          return {
            concepto: `Margen · ${ingresos.segmento}`,
            formato: 'porcentaje' as const,
            valores: ingresos.trimestral.map((valor, indice) => {
              const arriba = operativo?.trimestral[indice];
              return valor && arriba !== null && arriba !== undefined ? arriba / valor : null;
            }),
          };
        })
      : [];

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {conceptos.map(([clave, valor]) => (
          <button
            key={clave}
            type="button"
            onClick={() => setConcepto(clave)}
            className={`rounded-md border px-3 py-1.5 text-xs transition-colors ${
              concepto === clave
                ? 'border-azul-claro bg-superficie-alta text-texto'
                : 'border-borde text-texto-suave hover:text-texto'
            }`}
          >
            {valor.titulo}
          </button>
        ))}
      </div>

      <div className="mt-4 marquesina rounded-lg border border-borde bg-superficie p-4">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={datos} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid stroke="var(--color-borde)" vertical={false} />
            <XAxis dataKey="trimestre" {...ejeComun} interval={3} />
            <YAxis {...ejeComun} tickFormatter={(valor: number) => fmt.entero(valor)} />
            <Tooltip {...tooltipComun} formatter={(valor, nombre) => [fmt.musd(Number(valor)), String(nombre)]} />
            <Legend wrapperStyle={{ fontSize: '0.7rem' }} />
            {vigentes
              .filter((fila) => fila.segmento !== 'Total')
              .map((fila, indice) => (
                <Bar
                  key={fila.segmento}
                  dataKey={fila.segmento}
                  stackId="segmentos"
                  fill={PALETA[indice % PALETA.length]}
                />
              ))}
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4">
        <TablaExcel
          columnas={segmentos.trimestres.map((trimestre) => fmt.trimestre(trimestre))}
          filas={[...filas, ...margen]}
          etiquetaPrimera="US$ millones"
          anchoPrimera="18rem"
        />
      </div>
      <p className="mt-2 text-[0.7rem] leading-relaxed text-texto-tenue">
        La compañía reordenó sus segmentos dos veces desde 2020. Cada trimestre se muestra con la
        apertura que la compañía usó para ese período, y por eso las filas viejas se cortan donde el
        negocio se reordenó. El 4T22 no tiene apertura: es el trimestre en el que cambió.
      </p>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Comparables
// --------------------------------------------------------------------------- //
const METRICAS: { clave: string; etiqueta: string; formato: FilaExcel['formato'] }[] = [
  { clave: 'ingresos', etiqueta: 'Ingresos', formato: 'entero' },
  { clave: 'ebitda', etiqueta: 'EBITDA', formato: 'entero' },
  { clave: 'margen', etiqueta: 'Margen EBITDA', formato: 'porcentaje' },
  { clave: 'resultado_neto', etiqueta: 'Resultado neto', formato: 'entero' },
  { clave: 'capex', etiqueta: 'Capex', formato: 'entero' },
  { clave: 'deuda_neta', etiqueta: 'Deuda financiera neta', formato: 'entero' },
  { clave: 'apalancamiento', etiqueta: 'Deuda neta / EBITDA', formato: 'decimal' },
  { clave: 'ev_ebitda', etiqueta: 'EV / EBITDA', formato: 'decimal' },
  { clave: 'precio_libro', etiqueta: 'Precio / valor libro', formato: 'decimal' },
];

export function PanelComparables({
  comparables,
  ypf,
}: {
  comparables: Comparables;
  ypf: { titulo: string; valores: Record<string, number | null> };
}) {
  const columnas: { titulo: string; valores: Record<string, number | null> }[] = [ypf];

  comparables.emisores.forEach((emisor) => {
    Object.entries(emisor.ejercicios).forEach(([anio, datos]) => {
      const ebitda =
        datos.resultado_operativo !== undefined && datos.depreciacion_y_amortizacion !== undefined
          ? datos.resultado_operativo + datos.depreciacion_y_amortizacion
          : null;
      const deudaNeta =
        datos.deuda_financiera !== undefined && datos.caja !== undefined
          ? datos.deuda_financiera - datos.caja
          : null;
      const capitalizacion =
        emisor.precio && emisor.adrs ? (emisor.precio * emisor.adrs) / 1_000_000 : null;
      const ev = capitalizacion !== null && deudaNeta !== null ? capitalizacion + deudaNeta : null;
      columnas.push({
        titulo: `${emisor.ticker} FY${anio.slice(-2)}`,
        valores: {
          ingresos: datos.ingresos ?? null,
          ebitda,
          margen: ebitda !== null && datos.ingresos ? ebitda / datos.ingresos : null,
          resultado_neto: datos.resultado_neto ?? null,
          capex: datos.capex ?? null,
          deuda_neta: deudaNeta,
          apalancamiento: ebitda && deudaNeta !== null ? deudaNeta / ebitda : null,
          ev_ebitda: ev !== null && ebitda ? ev / ebitda : null,
          precio_libro:
            capitalizacion !== null && datos.patrimonio ? capitalizacion / datos.patrimonio : null,
        },
      });
    });
  });

  const filas: FilaExcel[] = METRICAS.map((metrica) => ({
    concepto: metrica.etiqueta,
    formato: metrica.formato,
    valores: columnas.map((columna) => columna.valores[metrica.clave] ?? null),
  }));

  const datosGrafico = columnas
    .map((columna) => ({ nombre: columna.titulo, valor: columna.valores.ev_ebitda ?? null }))
    .filter((punto) => punto.valor !== null);

  return (
    <div>
      <div className="marquesina rounded-lg border border-borde bg-superficie p-4">
        <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
          EV / EBITDA
        </p>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={datosGrafico} margin={{ top: 16, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid stroke="var(--color-borde)" vertical={false} />
            <XAxis dataKey="nombre" {...ejeComun} />
            <YAxis {...ejeComun} tickFormatter={(valor: number) => `${valor.toFixed(0)}x`} />
            <Tooltip {...tooltipComun} formatter={(valor) => [`${Number(valor).toFixed(2)}x`, "EV / EBITDA"]} />
            <Bar dataKey="valor" radius={[3, 3, 0, 0]}>
              {datosGrafico.map((punto) => (
                <Cell
                  key={punto.nombre}
                  fill={punto.nombre.startsWith('YPF') ? 'var(--color-azul)' : 'var(--color-neutro)'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4">
        <TablaExcel
          columnas={columnas.map((columna) => columna.titulo)}
          filas={filas}
          etiquetaPrimera="US$ millones"
          anchoPrimera="16rem"
        />
      </div>
      <p className="mt-2 text-[0.7rem] leading-relaxed text-texto-tenue">
        {comparables.nota} Los precios son los de hoy para los tres, aunque el balance de cada uno
        sea de distinta fecha: es el precio al que cotizan esos números.
      </p>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Deuda
// --------------------------------------------------------------------------- //
export function PanelDeuda({ deuda }: { deuda: Deuda }) {
  const datos = deuda.escalera.map((punto) => ({
    anio: String(punto.anio),
    monto: punto.monto,
  }));

  return (
    <div>
      <div className="marquesina rounded-lg border border-borde bg-superficie p-4">
        <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
          Escalera de vencimientos · US$ {fmt.entero(deuda.total)} millones
        </p>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={datos} margin={{ top: 16, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid stroke="var(--color-borde)" vertical={false} />
            <XAxis dataKey="anio" {...ejeComun} />
            <YAxis {...ejeComun} tickFormatter={(valor: number) => fmt.entero(valor)} />
            <Tooltip {...tooltipComun} formatter={(valor, nombre) => [fmt.musd(Number(valor)), String(nombre)]} />
            <Bar dataKey="monto" fill="var(--color-baja)" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4 overflow-auto rounded-md border border-borde" style={{ maxHeight: 420 }}>
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr>
              {['Instrumento', 'Emitido', 'Moneda', 'Tasa', 'Vence', 'No corriente', 'Corriente', 'Total'].map(
                (titulo, indice) => (
                  <th
                    key={titulo}
                    className={`sticky top-0 z-10 border-b border-borde bg-superficie-alta px-3 py-2 font-medium text-texto-tenue ${
                      indice > 3 ? 'text-right' : 'text-left'
                    }`}
                  >
                    {titulo}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {deuda.instrumentos.map((instrumento, indice) => (
              <tr key={`${instrumento.clase}-${indice}`} className={indice % 2 ? 'bg-superficie-alta/25' : undefined}>
                <td className="px-3 py-1.5 text-texto">{instrumento.clase}</td>
                <td className="px-3 py-1.5 text-texto-suave">{instrumento.emitido}</td>
                <td className="px-3 py-1.5 text-texto-suave">{instrumento.moneda}</td>
                <td className="px-3 py-1.5 text-texto-suave">{instrumento.tasa}</td>
                <td className="tabular px-3 py-1.5 text-right text-texto">{instrumento.vencimiento}</td>
                <td className="tabular px-3 py-1.5 text-right text-texto">{fmt.entero(instrumento.no_corriente)}</td>
                <td className="tabular px-3 py-1.5 text-right text-texto">{fmt.entero(instrumento.corriente)}</td>
                <td className="tabular px-3 py-1.5 text-right font-semibold text-texto">
                  {fmt.entero(instrumento.total)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[0.7rem] leading-relaxed text-texto-tenue">{deuda.nota}</p>
    </div>
  );
}
