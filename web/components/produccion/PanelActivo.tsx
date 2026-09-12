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

import { fmt, type AgregadoEconomico } from '@/lib/data';
import {
  COLOR,
  type FichaActivo,
  type FilaRankingYPF,
  type IdDimension,
  type Traspaso,
} from '@/lib/produccion';
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
  /** La economía de pozo del yacimiento, cuando el pipeline la calculó. */
  economia: AgregadoEconomico | null;
  /** Si el área dejó de declarar producción operada por YPF. */
  traspaso: Traspaso | null;
}

/** Los supuestos con los que se calculó esa economía. Van siempre al lado del
 *  número: un breakeven sin el capex que lo produjo no se puede discutir. */
export interface SupuestosEconomia {
  capex_usd: number;
  opex_usd_bbl: number;
  diferencial_usd_bbl: number;
  wacc_anual: number;
  brent_base: number;
  advertencia: string;
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
  supuestos,
}: {
  activo: ActivoSeleccionado;
  unidad: string;
  alCerrar: () => void;
  supuestos?: SupuestosEconomia;
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

      {/* El aviso va antes que los números y no al pie, porque cambia cómo se
          leen: el caudal de los últimos doce meses de un área traspasada está
          promediando meses en los que el área ya no era de YPF. */}
      {activo.traspaso ? (
        <p className="mt-3 rounded-md border border-oro/40 bg-oro/5 px-3 py-2 text-[0.72rem] leading-relaxed text-texto-suave">
          <span className="font-medium text-oro">Sin producción declarada desde{' '}
          {activo.traspaso.ultimo_mes}.</span>{' '}
          {activo.traspaso.sigue_en_el_pais
            ? `El área sigue produciendo en el archivo del país —${fmt.entero(
                activo.traspaso.bd_pais ?? 0,
              )} boe/d— así que cambió de operador y no dejó de producir.`
            : 'La fuente no dice por qué, y el archivo del país no publica esta área por separado, así que no se puede verificar si sigue produciendo bajo otro operador.'}{' '}
          Los números de abajo son de los últimos doce meses e incluyen los que ya no declara.
        </p>
      ) : null}

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

      {/* La economía del activo. No se calcula acá: sale del módulo de pozo del
          pipeline, que ajusta una curva de Arps por pozo y la descuenta. Solo
          existe para los yacimientos con al menos diez pozos ajustados, así que
          la mayoría de los activos convencionales no la tienen —y que no la
          tengan también dice algo: hace años que nadie perfora ahí—. */}
      {activo.economia ? (
        <div className="mt-4 border-t border-borde pt-4">
          <div className="flex items-baseline justify-between gap-2">
            <p className="font-mono text-[0.62rem] uppercase tracking-[0.12em] text-texto-tenue">
              Economía de pozo
            </p>
            <p className="text-[0.66rem] text-texto-tenue">
              {fmt.entero(activo.economia.pozos)} pozos ajustados
            </p>
          </div>

          <div className="mt-2.5 grid grid-cols-2 gap-3">
            <Campo etiqueta="Breakeven Brent">
              <span className="tabular text-texto">
                {activo.economia.breakeven_brent_mediano !== null &&
                activo.economia.breakeven_brent_mediano !== undefined
                  ? `US$ ${fmt.numero(activo.economia.breakeven_brent_mediano, 0)}`
                  : '—'}
              </span>{' '}
              <span className="text-xs text-texto-suave">/bbl</span>
            </Campo>
            <Campo etiqueta="NPV mediano">
              <span
                className={`tabular ${activo.economia.npv_musd_mediano >= 0 ? 'text-alza' : 'text-baja'}`}
              >
                US$ {fmt.numero(activo.economia.npv_musd_mediano, 1)}M
              </span>
            </Campo>
            <Campo etiqueta="TIR mediana">
              <span
                className={`tabular ${(activo.economia.irr_mediana ?? 0) >= 0 ? 'text-alza' : 'text-baja'}`}
              >
                {fmt.porcentaje(activo.economia.irr_mediana, 0)}
              </span>
            </Campo>
            <Campo etiqueta="EUR mediana">
              <span className="tabular text-texto">
                {activo.economia.eur_bbl_mediana
                  ? `${fmt.entero(activo.economia.eur_bbl_mediana / 1000)} kbbl`
                  : '—'}
              </span>
            </Campo>
          </div>

          {/* Lo que hace honesta a la mediana: sobre cuántos pozos se calculó.
              El breakeven no existe para el pozo que no llega a NPV cero a
              ningún precio, y sin este renglón un yacimiento donde la mitad de
              los pozos no cierra nunca muestra un breakeven cómodo al lado de un
              NPV negativo, que parece un error y no lo es. */}
          {activo.economia.pozos_con_breakeven !== undefined &&
          activo.economia.pozos_con_breakeven < activo.economia.pozos ? (
            <p className="mt-2 text-[0.7rem] leading-relaxed text-texto-tenue">
              El breakeven es la mediana de los{' '}
              <span className="tabular">{activo.economia.pozos_con_breakeven}</span> pozos que
              alguna vez cierran; a los{' '}
              <span className="tabular">
                {activo.economia.pozos - activo.economia.pozos_con_breakeven}
              </span>{' '}
              restantes no les da positivo a ningún precio de Brent.
            </p>
          ) : null}

          {activo.economia.pozos_con_npv_positivo !== undefined ? (
            <div className="mt-2">
              <div className="flex items-baseline justify-between text-[0.7rem]">
                <span className="text-texto-tenue">Pozos con NPV positivo</span>
                <span className="tabular text-texto-suave">
                  {fmt.porcentaje(activo.economia.pozos_con_npv_positivo, 0)}
                </span>
              </div>
              <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-superficie-alta">
                <span
                  className="block h-full bg-alza"
                  style={{ width: `${activo.economia.pozos_con_npv_positivo * 100}%` }}
                />
              </div>
            </div>
          ) : null}

          {supuestos ? (
            <p className="mt-2.5 text-[0.68rem] leading-relaxed text-texto-tenue">
              Con capex de US$ {fmt.numero(supuestos.capex_usd / 1e6, 0)}M por pozo, opex US${' '}
              {fmt.numero(supuestos.opex_usd_bbl, 0)}/bbl, diferencial US${' '}
              {fmt.numero(supuestos.diferencial_usd_bbl, 0)}/bbl, WACC{' '}
              {fmt.porcentaje(supuestos.wacc_anual, 0)} y Brent US${' '}
              {fmt.numero(supuestos.brent_base, 1)}. {supuestos.advertencia}{' '}
              <a
                href="/ypf-project#economia"
                className="text-azul-claro underline-offset-2 hover:underline"
              >
                Ver el módulo de economía de pozo
              </a>
              .
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
