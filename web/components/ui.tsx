// Primitivas visuales de la página. Están juntas a propósito: son cinco piezas
// chicas que solo tienen sentido en conjunto, y separarlas en cinco archivos
// sería más carpeta que código.

import type { ReactNode } from 'react';

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
    <section id={id} className="scroll-mt-16 border-t border-borde py-14">
      <div className="mx-auto max-w-6xl px-6">
        <p className="font-mono text-xs tracking-[0.2em] text-crudo">{numero}</p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">{titulo}</h2>
        {bajada ? <div className="mt-3 max-w-3xl text-texto-suave">{bajada}</div> : null}
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
      className={`rounded-xl border border-borde bg-superficie p-5 ${className}`}
    >
      {titulo ? (
        <h3 className="text-sm font-medium tracking-wide text-texto-suave">{titulo}</h3>
      ) : null}
      <div className={titulo ? 'mt-4' : ''}>{children}</div>
      {nota ? <p className="mt-4 text-xs leading-relaxed text-texto-tenue">{nota}</p> : null}
    </div>
  );
}

export function Dato({
  etiqueta,
  valor,
  detalle,
  tono = 'neutro',
}: {
  etiqueta: string;
  valor: string;
  detalle?: string;
  tono?: 'neutro' | 'alza' | 'baja' | 'crudo';
}) {
  const tonos = {
    neutro: 'text-texto',
    alza: 'text-alza',
    baja: 'text-baja',
    crudo: 'text-crudo',
  } as const;

  return (
    <div className="rounded-xl border border-borde bg-superficie p-4">
      <p className="text-xs uppercase tracking-wider text-texto-tenue">{etiqueta}</p>
      <p className={`tabular mt-2 text-2xl font-semibold ${tonos[tono]}`}>{valor}</p>
      {detalle ? <p className="mt-1 text-xs text-texto-suave">{detalle}</p> : null}
    </div>
  );
}

/** Advertencia metodológica. Va pegada al gráfico que la necesita, no en un pie
 *  de página que nadie lee. */
export function Nota({ children }: { children: ReactNode }) {
  return (
    <p className="mt-4 border-l-2 border-crudo-suave/50 pl-3 text-xs leading-relaxed text-texto-tenue">
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
