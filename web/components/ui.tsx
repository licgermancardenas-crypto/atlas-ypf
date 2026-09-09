// Primitivas visuales de la página. Están juntas a propósito: son cinco piezas
// chicas que solo tienen sentido en conjunto, y separarlas en cinco archivos
// sería más carpeta que código.

import type { ReactNode } from 'react';

/** Las franjas del logo de YPF anterior a 2008, que acá separan las secciones.
 *  Los `span` vacíos son las bandas: el color lo pone .franja en globals.css. */
export function Franja({ className = '' }: { className?: string }) {
  return (
    <div className={`franja ${className}`} aria-hidden="true">
      <span />
      <span />
      <span />
    </div>
  );
}

export function Seccion({
  id,
  numero,
  titulo,
  bajada,
  children,
}: {
  id: string;
  numero: string;
  titulo: string;
  bajada?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-20 border-t border-borde py-16">
      <div className="mx-auto max-w-6xl px-6">
        <Franja />
        <p className="mt-4 font-mono text-xs tracking-[0.2em] text-azul-claro">
          {numero} <span className="text-texto-tenue">/ 07</span>
        </p>
        <h2 className="mt-2 text-2xl font-semibold sm:text-3xl">{titulo}</h2>
        {bajada ? <div className="mt-3 max-w-3xl leading-relaxed text-texto-suave">{bajada}</div> : null}
        <div className="mt-8">{children}</div>
      </div>
    </section>
  );
}

export function Tarjeta({
  titulo,
  nota,
  children,
  className = '',
}: {
  titulo?: string;
  nota?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-lg border border-borde bg-superficie p-5 ${className}`}
    >
      {titulo ? (
        <h3 className="text-sm font-medium text-texto-suave">{titulo}</h3>
      ) : null}
      <div className={titulo ? 'mt-4' : ''}>{children}</div>
      {nota ? <p className="mt-4 text-xs leading-relaxed text-texto-tenue">{nota}</p> : null}
    </div>
  );
}

/** Chip de variación. Un número solo no dice si está bien o mal; el chip pone el
 *  signo, el color y la referencia en el mismo golpe de vista. */
export function Chip({ valor, referencia }: { valor: number; referencia?: string }) {
  const positivo = valor >= 0;
  return (
    <span
      className={`tabular inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[0.7rem] ${
        positivo ? 'bg-alza/15 text-alza' : 'bg-baja/15 text-baja'
      }`}
    >
      <span aria-hidden="true">{positivo ? '▲' : '▼'}</span>
      {Math.abs(valor * 100).toFixed(0)}%{referencia ? <span className="opacity-70">{referencia}</span> : null}
    </span>
  );
}

export function Dato({
  etiqueta,
  valor,
  detalle,
  delta,
  deltaReferencia,
  tono = 'neutro',
}: {
  etiqueta: string;
  valor: string;
  detalle?: string;
  delta?: number | null;
  deltaReferencia?: string;
  tono?: 'neutro' | 'alza' | 'baja' | 'crudo' | 'marca';
}) {
  const tonos = {
    neutro: 'text-texto',
    alza: 'text-alza',
    baja: 'text-baja',
    crudo: 'text-oro',
    marca: 'text-azul-claro',
  } as const;

  return (
    <div className="rounded-lg border border-borde bg-superficie p-4 transition-colors hover:border-azul/60">
      <p className="font-mono text-[0.7rem] uppercase tracking-[0.12em] text-texto-tenue">
        {etiqueta}
      </p>
      <div className="mt-2 flex flex-wrap items-baseline gap-2">
        <p className={`tabular text-2xl font-semibold ${tonos[tono]}`}>{valor}</p>
        {delta !== undefined && delta !== null ? (
          <Chip valor={delta} referencia={deltaReferencia} />
        ) : null}
      </div>
      {detalle ? <p className="mt-1 text-xs leading-snug text-texto-suave">{detalle}</p> : null}
    </div>
  );
}

/** Advertencia metodológica. Va pegada al gráfico que la necesita, no en un pie
 *  de página que nadie lee. */
export function Nota({ children }: { children: ReactNode }) {
  return (
    <p className="mt-4 border-l-2 border-azul pl-3 text-xs leading-relaxed text-texto-tenue">
      {children}
    </p>
  );
}

export function Tabla({
  columnas,
  filas,
}: {
  columnas: { clave: string; titulo: string; alineacion?: 'izq' | 'der' }[];
  filas: Record<string, ReactNode>[];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[36rem] border-collapse text-sm">
        <thead>
          <tr className="border-b border-borde text-xs uppercase tracking-wider text-texto-tenue">
            {columnas.map((columna) => (
              <th
                key={columna.clave}
                className={`py-2 font-medium ${
                  columna.alineacion === 'der' ? 'text-right' : 'text-left'
                }`}
              >
                {columna.titulo}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((fila, indice) => (
            <tr key={indice} className="border-b border-borde/50 last:border-0">
              {columnas.map((columna) => (
                <td
                  key={columna.clave}
                  className={`py-2.5 ${
                    columna.alineacion === 'der' ? 'tabular text-right' : 'text-left'
                  }`}
                >
                  {fila[columna.clave]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
