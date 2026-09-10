'use client';

// La valuación, con los supuestos en la mano.
//
// Es lo que el Excel no puede hacer: mover el riesgo país y ver los cuatro
// métodos moverse juntos. La cuenta es la misma que la de la hoja Valuación
// —está en lib/libro.ts y se comparte— y los supuestos arrancan donde los deja
// el pipeline: el riesgo país del EMBI de hoy, el valor por barril del modelo
// de economía de pozo, el múltiplo en la mediana de lo que pagó el mercado.

import { useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { fmt } from '@/lib/data';
import { sensibilidad, supuestosIniciales, valuar, type Mercado, type Supuestos } from '@/lib/libro';

const CONTROLES: {
  clave: keyof Supuestos;
  etiqueta: string;
  min: number;
  max: number;
  paso: number;
  formato: 'porcentaje' | 'numero' | 'dolar' | 'multiplo';
  ayuda: string;
}[] = [
  { clave: 'precio', etiqueta: 'Precio del ADR', min: 10, max: 120, paso: 0.5, formato: 'dolar', ayuda: 'El del cierre de ayer; moverlo muestra cuánto habría que creerle a cada método.' },
  { clave: 'riesgoPais', etiqueta: 'Riesgo país', min: 0, max: 0.25, paso: 0.0025, formato: 'porcentaje', ayuda: 'EMBI+ Argentina. Es el supuesto que más mueve el descontado.' },
  { clave: 'tasaLibre', etiqueta: 'Tasa libre de riesgo', min: 0.02, max: 0.07, paso: 0.0025, formato: 'porcentaje', ayuda: 'Tesoro de EE.UU. a diez años.' },
  { clave: 'beta', etiqueta: 'Beta', min: 0.5, max: 2, paso: 0.05, formato: 'numero', ayuda: 'Contra el S&P 500.' },
  { clave: 'prima', etiqueta: 'Prima de mercado', min: 0.03, max: 0.09, paso: 0.0025, formato: 'porcentaje', ayuda: 'Prima histórica de acciones sobre bonos.' },
  { clave: 'crecimiento', etiqueta: 'Crecimiento, años 1 a 5', min: -0.05, max: 0.2, paso: 0.005, formato: 'porcentaje', ayuda: 'Vaca Muerta viene creciendo bastante más que el valor por defecto.' },
  { clave: 'perpetuo', etiqueta: 'Crecimiento perpetuo', min: 0, max: 0.05, paso: 0.0025, formato: 'porcentaje', ayuda: 'A perpetuidad no se le puede pedir más que la inflación del dólar.' },
  { clave: 'impuesto', etiqueta: 'Tasa de impuesto', min: 0.2, max: 0.5, paso: 0.01, formato: 'porcentaje', ayuda: 'Alícuota societaria argentina.' },
  { clave: 'multiplo', etiqueta: 'EV/EBITDA objetivo', min: 2, max: 12, paso: 0.1, formato: 'multiplo', ayuda: 'Arranca en la mediana de lo que el propio papel cotizó desde 2020.' },
  { clave: 'valorBoe', etiqueta: 'Valor por boe de reserva', min: 1, max: 25, paso: 0.25, formato: 'dolar', ayuda: 'Del modelo de economía de pozo: NPV mediano sobre EUR.' },
];

function mostrar(valor: number, formato: string): string {
  if (formato === 'porcentaje') return fmt.porcentaje(valor, 2);
  if (formato === 'dolar') return `US$ ${valor.toFixed(2)}`;
  if (formato === 'multiplo') return `${valor.toFixed(2)}x`;
  return valor.toFixed(2);
}

export function PanelValuacion({ mercado }: { mercado: Mercado }) {
  const [supuestos, setSupuestos] = useState<Supuestos>(() => supuestosIniciales(mercado));
  const valuacion = useMemo(() => valuar(mercado, supuestos), [mercado, supuestos]);

  const cambiar = (clave: keyof Supuestos, valor: number) =>
    setSupuestos((previo) => ({ ...previo, [clave]: valor }));

  const metodos = valuacion.metodos.filter((metodo) => metodo.porAdr !== null);
  const datosGrafico = metodos.map((metodo) => ({
    nombre: metodo.nombre,
    valor: metodo.porAdr as number,
    contra: ((metodo.porAdr as number) / supuestos.precio - 1) * 100,
  }));

  const pasosWacc = [-0.02, -0.01, 0, 0.01, 0.02];
  const pasosPerpetuo = [-0.01, -0.005, 0, 0.005, 0.01];

  return (
    <div className="grid gap-6 lg:grid-cols-[19rem_1fr]">
      <div className="space-y-4">
        <div className="marquesina rounded-lg border border-borde bg-superficie p-4">
          <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
            Supuestos
          </p>
          <div className="mt-3 space-y-3">
            {CONTROLES.map((control) => (
              <label key={control.clave} className="block" title={control.ayuda}>
                <span className="flex items-baseline justify-between text-xs text-texto-suave">
                  {control.etiqueta}
                  <span className="tabular text-azul-claro">
                    {mostrar(supuestos[control.clave], control.formato)}
                  </span>
                </span>
                <input
                  type="range"
                  min={control.min}
                  max={control.max}
                  step={control.paso}
                  value={supuestos[control.clave]}
                  onChange={(evento) => cambiar(control.clave, Number(evento.target.value))}
                  className="mt-1 w-full accent-[#0054eb]"
                />
              </label>
            ))}
          </div>
          <button
            type="button"
            onClick={() => setSupuestos(supuestosIniciales(mercado))}
            className="mt-4 w-full rounded-md border border-borde px-3 py-1.5 text-xs text-texto-suave transition-colors hover:border-azul-claro hover:text-azul-claro"
          >
            Volver a los valores del pipeline
          </button>
        </div>

        <div className="marquesina rounded-lg border border-borde bg-superficie p-4 text-xs">
          <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
            Costo del capital
          </p>
          <dl className="mt-3 space-y-1.5 text-texto-suave">
            {[
              ['Costo del patrimonio', fmt.porcentaje(valuacion.ke)],
              ['Costo de la deuda', fmt.porcentaje(valuacion.kd)],
              ['Peso de la deuda', fmt.porcentaje(valuacion.pesoDeuda)],
              ['WACC', fmt.porcentaje(valuacion.wacc)],
              ['Peso del valor terminal', fmt.porcentaje(valuacion.pesoTerminal)],
            ].map(([etiqueta, valor]) => (
              <div key={etiqueta} className="flex justify-between gap-3">
                <dt>{etiqueta}</dt>
                <dd className="tabular text-texto">{valor}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      <div className="space-y-6">
        <div className="marquesina rounded-lg border border-borde bg-superficie p-4">
          <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
            Valor por ADR según cada método
          </p>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={datosGrafico} layout="vertical" margin={{ left: 8, right: 24, top: 16, bottom: 8 }}>
              <CartesianGrid stroke="var(--color-borde)" horizontal={false} />
              <XAxis
                type="number"
                stroke="var(--color-texto-suave)"
                tick={{ fill: 'var(--color-texto-suave)', fontSize: 11 }}
                tickFormatter={(valor: number) => `${valor.toFixed(0)}`}
              />
              <YAxis
                type="category"
                dataKey="nombre"
                width={150}
                stroke="var(--color-texto-suave)"
                tick={{ fill: 'var(--color-texto-suave)', fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--color-superficie-alta)',
                  border: '1px solid var(--color-borde)',
                  borderRadius: '0.5rem',
                  fontSize: '0.8rem',
                }}
                formatter={(valor, nombre) =>
                  String(nombre) === 'valor'
                    ? [`US$ ${Number(valor).toFixed(1)}`, 'Por ADR']
                    : [`${Number(valor).toFixed(0)}%`, 'Contra el precio']
                }
              />
              <ReferenceLine
                x={supuestos.precio}
                stroke="var(--color-oro)"
                strokeDasharray="4 3"
                label={{ value: 'precio', fill: 'var(--color-oro)', fontSize: 10, position: 'top' }}
              />
              <Bar dataKey="valor" radius={[0, 3, 3, 0]}>
                {datosGrafico.map((punto) => (
                  <Cell
                    key={punto.nombre}
                    fill={punto.valor >= supuestos.precio ? 'var(--color-alza)' : 'var(--color-baja)'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          <table className="mt-2 w-full text-xs">
            <tbody>
              {valuacion.metodos.map((metodo) => (
                <tr key={metodo.nombre} className="border-t border-borde/60">
                  <td className="py-1.5 pr-3 text-texto-suave">{metodo.nombre}</td>
                  <td className="tabular py-1.5 pr-3 text-right text-texto">
                    {metodo.porAdr === null ? '—' : `US$ ${metodo.porAdr.toFixed(1)}`}
                  </td>
                  <td
                    className={`tabular py-1.5 pr-3 text-right ${
                      metodo.porAdr !== null && metodo.porAdr >= supuestos.precio
                        ? 'text-alza'
                        : 'text-baja'
                    }`}
                  >
                    {metodo.porAdr === null
                      ? '—'
                      : fmt.porcentajeConSigno(metodo.porAdr / supuestos.precio - 1, 0)}
                  </td>
                  <td className="py-1.5 text-[0.7rem] text-texto-tenue">{metodo.detalle}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="marquesina rounded-lg border border-borde bg-superficie p-4">
          <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
            Sensibilidad del descontado · WACC contra crecimiento perpetuo
          </p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[34rem] text-xs">
              <thead>
                <tr>
                  <th className="px-2 py-1 text-left font-medium text-texto-tenue">WACC \ g</th>
                  {pasosPerpetuo.map((paso) => (
                    <th key={paso} className="tabular px-2 py-1 text-right font-medium text-texto-tenue">
                      {fmt.porcentaje(supuestos.perpetuo + paso, 1)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pasosWacc.map((pasoWacc) => (
                  <tr key={pasoWacc} className="border-t border-borde/60">
                    <th className="tabular px-2 py-1 text-left font-normal text-texto-suave">
                      {fmt.porcentaje(valuacion.wacc + pasoWacc, 1)}
                    </th>
                    {pasosPerpetuo.map((pasoPerpetuo) => {
                      const valor = sensibilidad(
                        mercado,
                        supuestos,
                        valuacion.wacc + pasoWacc,
                        supuestos.perpetuo + pasoPerpetuo,
                      );
                      const contra = valor === null ? null : valor / supuestos.precio - 1;
                      return (
                        <td
                          key={pasoPerpetuo}
                          className="tabular px-2 py-1 text-right"
                          style={{
                            background:
                              contra === null
                                ? undefined
                                : `rgba(${contra >= 0 ? '63, 185, 138' : '226, 96, 63'}, ${Math.min(
                                    Math.abs(contra),
                                    0.6,
                                  ).toFixed(2)})`,
                          }}
                        >
                          {valor === null ? '—' : valor.toFixed(0)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-[0.7rem] leading-relaxed text-texto-tenue">
            Cada celda es el valor por ADR del flujo descontado. El precio de mercado hoy es US$
            {supuestos.precio.toFixed(2)}: la fila y la columna donde la tabla deja de estar en verde
            son el WACC y el crecimiento que habría que creerle al mercado para justificarlo.
          </p>
        </div>
      </div>
    </div>
  );
}
