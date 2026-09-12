'use client';

// La ficha de un activo, al costado del gráfico.
//
// Es la pieza que convierte la pantalla en una herramienta de investigación: se
// hace clic en una concesión y se abre su ficha sin perder de vista el gráfico,
// que es justamente lo que se estaba mirando. Navegar a otra página en ese
// momento rompe el hilo del análisis; volver cuesta tres clics y el estado se
// pierde.
//
// En pantalla ancha es una columna a la derecha; en una angosta sube desde
// abajo como una hoja. En los dos casos cierra con Escape y devuelve el foco,
// porque quien llegó hasta acá con el teclado tiene que poder salir igual.

import { useEffect, useRef } from 'react';

import { fmt } from '@/lib/data';
import { COLOR, type FichaActivo, type FilaRankingYPF, type IdDimension } from '@/lib/produccion';
import { Chispa, Composicion } from './Chispa';

export interface ActivoSeleccionado {
  nombre: string;
  dimension: IdDimension;
  ficha: FichaActivo | null;
  fila: FilaRankingYPF | null;
  /** Caudal mensual del activo, para la forma de la serie. */
  serie: number[];
  /** Enlaces que existen de verdad: si el activo no está en el grafo, no va. */
  enlaceEntidad: string | null;
  enlaceMapa: string | null;
}

function Campo({ etiqueta, children }: { etiqueta: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="font-mono text-[0.62rem] uppercase tracking-[0.12em] text-texto-tenue">
        {etiqueta}
      </p>
      <p className="mt-0.5 text-sm text-texto">{children}</p>
    </div>
  );
}

export function PanelActivo({
  activo,
  unidad,
  alCerrar,
  alAbrirYacimientos,
}: {
  activo: ActivoSeleccionado;
  unidad: string;
  alCerrar: () => void;
  /** Bajar un nivel: de la concesión a sus yacimientos, en el mismo gráfico.
   *  Se ofrece solo cuando hay más de uno; con uno solo el drill-down devuelve
   *  la misma curva con otro nombre. */
  alAbrirYacimientos?: () => void;
}) {
  const contenedor = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const alTeclear = (evento: KeyboardEvent) => {
      if (evento.key === 'Escape') alCerrar();
    };
    document.addEventListener('keydown', alTeclear);
    contenedor.current?.focus();
    return () => document.removeEventListener('keydown', alTeclear);
  }, [alCerrar]);

  const { fila, ficha } = activo;
  const etiquetaDimension =
    activo.dimension === 'concesion'
      ? 'Concesión'
      : activo.dimension === 'yacimiento'
        ? 'Yacimiento'
        : activo.dimension === 'localidad'
          ? 'Localidad'
          : activo.dimension === 'provincia'
            ? 'Provincia'
            : 'Cuenca';

  const contexto = [ficha?.provincia, ficha?.cuenca].filter(Boolean).join(' · ');

  return (
    <aside
      ref={contenedor}
      tabIndex={-1}
      role="dialog"
      aria-modal="false"
      aria-label={`Ficha de ${activo.nombre}`}
      className="flex max-h-[80vh] flex-col overflow-y-auto rounded-lg border border-borde-vivo bg-superficie p-4 focus:outline-none lg:max-h-none"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-[0.62rem] uppercase tracking-[0.12em] text-texto-tenue">
            {etiquetaDimension}
          </p>
          <h3 className="mt-1 text-lg font-semibold leading-tight text-texto">{activo.nombre}</h3>
          {contexto ? <p className="mt-1 text-xs text-texto-suave">{contexto}</p> : null}
        </div>
        <button
          type="button"
          onClick={alCerrar}
          aria-label="Cerrar la ficha"
          className="shrink-0 rounded-md border border-borde px-2 py-1 text-xs text-texto-tenue transition-colors hover:border-azul-claro hover:text-azul-claro focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-azul-claro"
        >
          ✕
        </button>
      </div>

      {fila ? (
        <>
          <p className="tabular mt-4 text-2xl font-semibold leading-none text-texto">
            {fmt.entero(fila.actual_bd)}{' '}
            <span className="text-xs font-normal text-texto-suave">boe/d</span>
          </p>
          <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
            {fila.crecimiento !== null ? (
              <span className={fila.crecimiento >= 0 ? 'text-alza' : 'text-baja'}>
                <span aria-hidden>{fila.crecimiento >= 0 ? '▲' : '▼'}</span>{' '}
                {fmt.porcentajeConSigno(fila.crecimiento, 1)} i.a.
              </span>
            ) : (
              <span className="text-texto-tenue">sin base de comparación</span>
            )}
            <span className="text-texto-tenue">
              {fmt.entero(fila.delta_bd)} boe/d contra los doce meses previos
            </span>
          </p>
        </>
      ) : (
        <p className="mt-4 text-sm text-texto-suave">
          Este agregado no tiene fila propia en el ranking: es el resto de los activos, sumado.
        </p>
      )}

      {activo.serie.length > 1 ? (
        <div className="mt-4">
          <p className="font-mono text-[0.62rem] uppercase tracking-[0.12em] text-texto-tenue">
            Producción · últimos {activo.serie.length} meses
          </p>
          <div className="mt-1.5">
            <Chispa
              valores={activo.serie}
              color="var(--color-azul-claro)"
              alto={44}
              etiqueta={`Evolución mensual de ${activo.nombre}`}
            />
          </div>
        </div>
      ) : null}

      {fila ? (
        <div className="mt-4 space-y-3 border-t border-borde pt-4">
          <div className="grid grid-cols-2 gap-3">
            <Campo etiqueta="Petróleo">
              <span className="tabular text-oro">{fmt.entero(fila.oil_bd ?? null)}</span>{' '}
              <span className="text-xs text-texto-suave">bbl/d</span>
            </Campo>
            <Campo etiqueta="Gas">
              <span className="tabular text-celeste">{fmt.entero(fila.gas_bd ?? null)}</span>{' '}
              <span className="text-xs text-texto-suave">boe/d</span>
            </Campo>
          </div>

          {fila.shale_share !== null && fila.shale_share !== undefined ? (
            <div>
              <div className="flex items-baseline justify-between text-xs">
                <span className="font-mono text-[0.62rem] uppercase tracking-[0.12em] text-texto-tenue">
                  Tipo de roca
                </span>
                <span className="tabular" style={{ color: COLOR.shale }}>
                  {fmt.porcentaje(fila.shale_share, 0)} shale
                </span>
              </div>
              <div className="mt-1.5">
                <Composicion
                  etiqueta="Shale, convencional y tight"
                  partes={[
                    { nombre: 'Shale', valor: fila.shale_bd ?? 0, color: COLOR.shale },
                    {
                      nombre: 'Convencional',
                      valor: fila.convencional_bd ?? 0,
                      color: COLOR.convencional,
                    },
                    { nombre: 'Tight', valor: fila.tight_bd ?? 0, color: COLOR.tight },
                  ]}
                />
              </div>
            </div>
          ) : null}

          <div className="grid grid-cols-2 gap-3">
            <Campo etiqueta="De la compañía">{fmt.porcentaje(fila.participacion, 1)}</Campo>
            <Campo etiqueta="Operador">YPF</Campo>
            {ficha?.concesion ? <Campo etiqueta="Concesión">{ficha.concesion}</Campo> : null}
            {ficha?.yacimientos ? (
              <Campo etiqueta="Yacimientos">{fmt.entero(ficha.yacimientos)}</Campo>
            ) : null}
            {ficha?.localidad ? <Campo etiqueta="Localidad cercana">{ficha.localidad}</Campo> : null}
          </div>

          {ficha?.provincias || ficha?.cuencas || ficha?.concesiones ? (
            <p className="text-[0.7rem] leading-relaxed text-texto-tenue">
              El activo cruza más de una{' '}
              {[
                ficha.provincias ? 'provincia' : null,
                ficha.cuencas ? 'cuenca' : null,
                ficha.concesiones ? 'concesión' : null,
              ]
                .filter(Boolean)
                .join(' y más de una ')}
              ; arriba figura la de mayor volumen.
            </p>
          ) : null}
        </div>
      ) : null}

      {alAbrirYacimientos ? (
        <div className="mt-4 border-t border-borde pt-4">
          <button
            type="button"
            onClick={alAbrirYacimientos}
            className="w-full rounded-md border border-azul-claro/50 bg-superficie-alta px-2.5 py-2 text-xs text-azul-claro transition-colors hover:border-azul-claro focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-azul-claro"
          >
            Abrir sus {activo.ficha?.yacimientos} yacimientos en el gráfico →
          </button>
        </div>
      ) : null}

      {activo.enlaceEntidad || activo.enlaceMapa ? (
        <div className="mt-4 flex flex-wrap gap-2 border-t border-borde pt-4">
          {activo.enlaceMapa ? (
            <a
              href={activo.enlaceMapa}
              className="rounded-md border border-borde px-2.5 py-1.5 text-xs text-texto-suave transition-colors hover:border-azul-claro hover:text-azul-claro"
            >
              Ver en el mapa
            </a>
          ) : null}
          {activo.enlaceEntidad ? (
            <a
              href={activo.enlaceEntidad}
              className="rounded-md border border-borde px-2.5 py-1.5 text-xs text-texto-suave transition-colors hover:border-azul-claro hover:text-azul-claro"
            >
              Ver en Relaciones
            </a>
          ) : null}
        </div>
      ) : null}

      <p className="mt-4 text-[0.68rem] leading-relaxed text-texto-tenue">
        Producción bruta operada de los últimos doce meses. La ficha no se cierra al cambiar de
        filtro: el activo sigue seleccionado mientras se mueve el gráfico.
      </p>
    </aside>
  );
}
