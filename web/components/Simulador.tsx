'use client';

// El simulador de escenarios. Todo el cálculo es la función pura generada por
// pipeline/transform/scenario_engine.py: no hay fetch, no hay backend, el
// resultado cambia en el mismo frame que el slider.

import { useMemo, useState } from 'react';

import { fmt } from '@/lib/data';
import { COEFICIENTES, proyectar, type Escenario } from '@/lib/scenarioEngine';

const BASE = COEFICIENTES.caso_base;

interface Control {
  clave: keyof Escenario;
  etiqueta: string;
  unidad: string;
  min: number;
  max: number;
  paso: number;
  formato: (valor: number) => string;
  ayuda: string;
}

const CONTROLES: Control[] = [
  {
    clave: 'brent_usd',
    etiqueta: 'Brent',
    unidad: 'US$/bbl',
    min: 40,
    max: 130,
    paso: 1,
    formato: (valor) => `US$ ${fmt.entero(valor)}`,
    ayuda: 'El precio internacional del crudo, que es lo único de esta lista que YPF no maneja.',
  },
  {
    clave: 'produccion_kboed',
    etiqueta: 'Producción',
    unidad: 'Kboe/d',
    min: 420,
    max: 650,
    paso: 5,
    formato: (valor) => `${fmt.entero(valor)} Kboe/d`,
    ayuda: 'Producción total de hidrocarburos de la compañía, no solo shale.',
  },
  {
    clave: 'lifting_cost_usd_boe',
    etiqueta: 'Lifting cost',
    unidad: 'US$/boe',
    min: 6,
    max: 18,
    paso: 0.2,
    formato: (valor) => `US$ ${fmt.numero(valor, 1)}`,
    ayuda: 'Costo de extracción. Cayó de 16 a 8,4 entre 2024 y 2026: es la mitad de la historia.',
  },
  {
    clave: 'crudo_procesado_kbbld',
    etiqueta: 'Crudo procesado',
    unidad: 'Kbbl/d',
    min: 240,
    max: 400,
    paso: 5,
    formato: (valor) => `${fmt.entero(valor)} Kbbl/d`,
    ayuda: 'Carga de las refinerías: el lado downstream del negocio.',
  },
];

export function Simulador() {
  const [escenario, setEscenario] = useState<Escenario>({});

  const valores = useMemo(
    () => ({
      brent_usd: escenario.brent_usd ?? BASE.brent_usd,
      produccion_kboed: escenario.produccion_kboed ?? BASE.produccion_kboed,
      lifting_cost_usd_boe: escenario.lifting_cost_usd_boe ?? BASE.lifting_cost_usd_boe,
      crudo_procesado_kbbld: escenario.crudo_procesado_kbbld ?? BASE.crudo_procesado_kbbld,
    }),
    [escenario],
  );

  const resultado = useMemo(() => proyectar(escenario), [escenario]);
  const sinTocar = Object.keys(escenario).length === 0;
  const delta = resultado.delta_vs_real_musd;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
      <div className="rounded-xl border border-borde bg-superficie p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-sm font-medium tracking-wide text-texto-suave">
            Drivers del trimestre
          </h3>
          <button
            type="button"
            onClick={() => setEscenario({})}
            disabled={sinTocar}
            className="rounded-md border border-borde px-2.5 py-1 text-xs text-texto-suave transition hover:border-crudo hover:text-crudo disabled:cursor-not-allowed disabled:opacity-40"
          >
            Volver al {fmt.trimestre(BASE.trimestre)}
          </button>
        </div>

        <div className="mt-5 space-y-6">
          {CONTROLES.map((control) => {
            const valor = valores[control.clave as keyof typeof valores];
            const real = BASE[control.clave as keyof typeof BASE] as number;
            return (
              <div key={control.clave}>
                <div className="flex items-baseline justify-between">
                  <label htmlFor={control.clave} className="text-sm text-texto">
                    {control.etiqueta}
                  </label>
                  <span className="tabular text-sm font-medium text-crudo">
                    {control.formato(valor)}
                  </span>
                </div>
                <input
                  id={control.clave}
                  type="range"
                  min={control.min}
                  max={control.max}
                  step={control.paso}
                  value={valor}
                  onChange={(evento) =>
                    setEscenario((previo) => ({
                      ...previo,
                      [control.clave]: Number(evento.target.value),
                    }))
                  }
                  className="mt-2 w-full accent-[oklch(0.76_0.15_62)]"
                />
                <p className="mt-1 text-xs text-texto-tenue">
                  {control.ayuda} Real en {fmt.trimestre(BASE.trimestre)}:{' '}
                  <span className="tabular">{control.formato(real)}</span>.
                </p>
              </div>
            );
          })}
        </div>

        <p className="mt-6 border-l-2 border-crudo-suave/50 pl-3 text-xs leading-relaxed text-texto-tenue">
          El tipo de cambio se probó como quinto driver y no resultó significativo (p{' '}
          {fmt.numero(COEFICIENTES.fx.p_valor)}), así que no tiene slider: con estos datos su efecto
          no se distingue de cero. {COEFICIENTES.fx.nota}
        </p>
      </div>

      <div className="space-y-4">
        <div className="rounded-xl border border-borde bg-superficie-alta p-5">
          <p className="text-xs uppercase tracking-wider text-texto-tenue">EBITDA proyectado</p>
          <p className="tabular mt-2 text-3xl font-semibold text-crudo">
            {fmt.musd(resultado.ebitda_proyectado_musd)}
          </p>
          <p className="tabular mt-1 text-sm text-texto-suave">
            banda 95%: {fmt.musd(resultado.banda_95_musd[0])} a{' '}
            {fmt.musd(resultado.banda_95_musd[1])}
          </p>
          <div className="mt-4 border-t border-borde pt-4">
            <p className="text-xs uppercase tracking-wider text-texto-tenue">
              Contra el {fmt.trimestre(BASE.trimestre)} real
            </p>
            <p
              className={`tabular mt-1 text-xl font-semibold ${
                delta >= 0 ? 'text-alza' : 'text-baja'
              }`}
            >
              {delta >= 0 ? '+' : ''}
              {fmt.entero(delta)} MUSD ({fmt.porcentajeConSigno(resultado.delta_vs_real_pct)})
            </p>
          </div>
        </div>

        <div className="rounded-xl border border-borde bg-superficie p-5">
          <dl className="space-y-3 text-sm">
            <div className="flex items-baseline justify-between">
              <dt className="text-texto-suave">Ingresos proyectados</dt>
              <dd className="tabular font-medium">
                {fmt.musd(resultado.ingresos_proyectados_musd)}
              </dd>
            </div>
            <div className="flex items-baseline justify-between">
              <dt className="text-texto-suave">Margen EBITDA</dt>
              <dd className="tabular font-medium">{fmt.porcentaje(resultado.margen)}</dd>
            </div>
            <div className="flex items-baseline justify-between">
              <dt className="text-texto-suave">R² del modelo</dt>
              <dd className="tabular font-medium">{fmt.numero(COEFICIENTES.r2_ebitda)}</dd>
            </div>
          </dl>
          <p className="mt-4 text-xs leading-relaxed text-texto-tenue">
            {COEFICIENTES.advertencia}
          </p>
        </div>
      </div>
    </div>
  );
}
