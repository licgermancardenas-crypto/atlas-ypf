'use client';

// Intelligence: qué está pasando, en cuatro o cinco señales.
//
// La diferencia entre un dashboard y una herramienta de análisis es quién hace
// la lectura. Un dashboard deja el gráfico y se va; acá abajo quedan escritas
// las cuentas que un analista haría igual —cuánto creció, cuánto pesa el shale,
// qué tan concentrada está la producción, qué activo se movió—, con el período
// de comparación al lado de cada una.
//
// Todas salen de lib/produccion.ts, de los mismos arrays que dibujan el
// gráfico. Ninguna está escrita a mano y las que no se pueden calcular no
// aparecen.

import type { Senal } from '@/lib/produccion';

const TONOS: Record<Senal['tipo'], { borde: string; texto: string; signo: string }> = {
  alza: { borde: 'border-l-alza', texto: 'text-alza', signo: '↑' },
  baja: { borde: 'border-l-baja', texto: 'text-baja', signo: '↓' },
  atencion: { borde: 'border-l-oro', texto: 'text-oro', signo: '!' },
  neutro: { borde: 'border-l-borde-vivo', texto: 'text-texto-suave', signo: '·' },
};

export function Senales({ senales }: { senales: Senal[] }) {
  if (!senales.length) return null;

  return (
    <section aria-labelledby="intelligence" className="mt-10">
      <div className="flex items-baseline justify-between gap-4">
        <h2 id="intelligence" className="text-xl font-semibold text-texto">
          Intelligence
        </h2>
        <p className="text-xs text-texto-tenue">Señales calculadas sobre los datos de esta página</p>
      </div>

      <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {senales.map((senal) => {
          const tono = TONOS[senal.tipo];
          return (
            <li
              key={senal.id}
              className={`rounded-lg border border-borde ${tono.borde} border-l-2 bg-superficie p-4 transition-colors hover:border-borde-vivo`}
            >
              <p className="flex items-center gap-2">
                <span aria-hidden className={`font-mono text-sm ${tono.texto}`}>
                  {tono.signo}
                </span>
                <span className="font-mono text-[0.68rem] uppercase tracking-[0.14em] text-texto-tenue">
                  {senal.titulo}
                </span>
              </p>
              <p className="mt-2 text-sm leading-relaxed text-texto-suave">{senal.cuerpo}</p>
              <p className="mt-2.5 font-mono text-[0.62rem] uppercase tracking-[0.1em] text-texto-tenue">
                {senal.periodo}
              </p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
