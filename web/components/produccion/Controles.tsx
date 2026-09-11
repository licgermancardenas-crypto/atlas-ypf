'use client';

// Los controles del análisis.
//
// La versión anterior de esta pantalla tenía nueve botones sueltos en dos filas:
// todo estaba a la vista y nada tenía jerarquía, así que la primera decisión del
// lector era leer una botonera en vez de mirar un gráfico. Acá hay cinco
// selectores etiquetados —los que cambian la pregunta— y el resto vive detrás de
// "Más filtros", que es donde tiene que estar lo que se toca una vez cada diez.
//
// Selects nativos y no menús propios: se abren con el teclado, se navegan con
// las flechas, los lee cualquier lector de pantalla y en un teléfono usan el
// selector del sistema. Un combo hecho a mano tendría que ganarse esas cuatro
// cosas de nuevo.

import { useId, type ReactNode } from 'react';

import { RANGO_ANIOS } from '@/components/estado/filtros';
import {
  DIMENSIONES,
  FLUIDOS,
  METRICAS,
  PERIODOS,
  RECURSOS,
  type IdDimension,
  type IdFluido,
  type IdMetrica,
  type IdPeriodo,
  type IdRecurso,
} from '@/lib/produccion';

export interface EstadoControles {
  dimension: IdDimension;
  fluido: IdFluido;
  recurso: IdRecurso;
  periodo: IdPeriodo;
  metrica: IdMetrica;
  top: number;
}

function Campo({
  etiqueta,
  valor,
  opciones,
  alCambiar,
  ancho = 'w-40',
}: {
  etiqueta: string;
  valor: string;
  opciones: { id: string; etiqueta: string }[];
  alCambiar: (id: string) => void;
  ancho?: string;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={id}
        className="font-mono text-[0.62rem] uppercase tracking-[0.14em] text-texto-tenue"
      >
        {etiqueta}
      </label>
      <select
        id={id}
        value={valor}
        onChange={(evento) => alCambiar(evento.target.value)}
        className={`${ancho} rounded-md border border-borde bg-superficie px-2.5 py-1.5 text-xs text-texto transition-colors hover:border-borde-vivo focus:border-azul-claro focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-azul-claro`}
      >
        {opciones.map((opcion) => (
          <option key={opcion.id} value={opcion.id}>
            {opcion.etiqueta}
          </option>
        ))}
      </select>
    </div>
  );
}

export function Controles({
  estado,
  alCambiar,
  avanzados,
  alternarAvanzados,
  anios,
  alCambiarAnios,
  extra,
}: {
  estado: EstadoControles;
  alCambiar: (cambio: Partial<EstadoControles>) => void;
  avanzados: boolean;
  alternarAvanzados: () => void;
  anios: { desde: number; hasta: number };
  alCambiarAnios: (cambio: { desde?: number; hasta?: number }) => void;
  /** Lo que la pantalla quiera meter a la derecha: el total del período, casi
   *  siempre. */
  extra?: ReactNode;
}) {
  const listaAnios = Array.from(
    { length: RANGO_ANIOS.max - RANGO_ANIOS.min + 1 },
    (_, indice) => RANGO_ANIOS.min + indice,
  );

  return (
    <div className="rounded-lg border border-borde bg-superficie/40 p-3">
      <div className="flex flex-wrap items-end gap-x-3 gap-y-3">
        <Campo
          etiqueta="Dimensión"
          valor={estado.dimension}
          opciones={DIMENSIONES.map((item) => ({ id: item.id, etiqueta: item.etiqueta }))}
          alCambiar={(id) => alCambiar({ dimension: id as IdDimension })}
        />
        <Campo
          etiqueta="Producto"
          valor={estado.fluido}
          opciones={FLUIDOS}
          alCambiar={(id) => alCambiar({ fluido: id as IdFluido })}
          ancho="w-36"
        />
        <Campo
          etiqueta="Tipo"
          valor={estado.recurso}
          opciones={RECURSOS.map((item) => ({ id: item.id, etiqueta: item.etiqueta }))}
          alCambiar={(id) => alCambiar({ recurso: id as IdRecurso })}
          ancho="w-36"
        />
        <Campo
          etiqueta="Período"
          valor={estado.periodo}
          opciones={PERIODOS.map((item) => ({ id: item.id, etiqueta: item.etiqueta }))}
          alCambiar={(id) => alCambiar({ periodo: id as IdPeriodo })}
          ancho="w-32"
        />
        <Campo
          etiqueta="Métrica"
          valor={estado.metrica}
          opciones={METRICAS}
          alCambiar={(id) => alCambiar({ metrica: id as IdMetrica })}
          ancho="w-36"
        />

        <button
          type="button"
          onClick={alternarAvanzados}
          aria-expanded={avanzados}
          className="rounded-md border border-borde px-2.5 py-1.5 text-xs text-texto-suave transition-colors hover:border-azul-claro hover:text-azul-claro focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-azul-claro"
        >
          {avanzados ? '− Menos filtros' : '+ Más filtros'}
        </button>

        {extra ? <div className="ml-auto">{extra}</div> : null}
      </div>

      {avanzados ? (
        <div className="mt-3 flex flex-wrap items-end gap-x-3 gap-y-3 border-t border-borde pt-3">
          <Campo
            etiqueta="Desde"
            valor={String(anios.desde)}
            opciones={listaAnios.map((anio) => ({ id: String(anio), etiqueta: String(anio) }))}
            alCambiar={(id) => alCambiarAnios({ desde: Number(id) })}
            ancho="w-24"
          />
          <Campo
            etiqueta="Hasta"
            valor={String(anios.hasta)}
            opciones={listaAnios.map((anio) => ({ id: String(anio), etiqueta: String(anio) }))}
            alCambiar={(id) => alCambiarAnios({ hasta: Number(id) })}
            ancho="w-24"
          />
          <Campo
            etiqueta="Series visibles"
            valor={String(estado.top)}
            opciones={[
              { id: '5', etiqueta: 'Top 5 + otros' },
              { id: '8', etiqueta: 'Top 8 + otros' },
              { id: '0', etiqueta: 'Todas' },
            ]}
            alCambiar={(id) => alCambiar({ top: Number(id) })}
            ancho="w-40"
          />
          <p className="max-w-md text-[0.7rem] leading-relaxed text-texto-tenue">
            El rango de años es el mismo de la barra de arriba: cambiarlo acá cambia toda la página
            y queda guardado en el link.
          </p>
        </div>
      ) : null}
    </div>
  );
}
