'use client';

// La barra de filtros: el slicer que gobierna toda la página.
//
// Va pegada arriba porque un filtro que no se ve mientras leés es un filtro que
// te hace desconfiar de lo que estás mirando. Cuando hay algo aplicado, la barra
// se enciende y ofrece limpiarlo: el estado activo tiene que ser evidente sin
// tener que buscarlo.

import { RANGO_ANIOS, useFiltros } from './filtros';
import { fmt } from '@/lib/data';

export function BarraFiltros({ operadores }: { operadores: string[] }) {
  const { filtros, aplicar, limpiar, activos } = useFiltros();

  return (
    <div
      className="marquesina sticky top-0 z-30 border-b border-borde bg-fondo/92 backdrop-blur-md lg:top-0"
      data-activa={activos}
    >
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-5 gap-y-2 px-6 py-2.5">
        <span className="font-mono text-[0.65rem] uppercase tracking-[0.16em] text-texto-tenue">
          Filtros
        </span>

        <label className="flex items-center gap-2 text-xs text-texto-suave">
          Operador
          <select
            value={filtros.operador}
            onChange={(evento) => aplicar({ operador: evento.target.value })}
            className="rounded-md border border-borde bg-superficie px-2 py-1 text-xs text-texto"
          >
            <option value="todos">Todos</option>
            {operadores.map((nombre) => (
              <option key={nombre} value={nombre}>
                {nombre}
              </option>
            ))}
          </select>
        </label>

        <span className="flex items-center gap-2 text-xs text-texto-suave">
          Período
          <select
            value={filtros.desde}
            onChange={(evento) => aplicar({ desde: Number(evento.target.value) })}
            aria-label="Año desde"
            className="rounded-md border border-borde bg-superficie px-2 py-1 text-xs text-texto"
          >
            {anios().map((anio) => (
              <option key={anio} value={anio}>
                {anio}
              </option>
            ))}
          </select>
          <span className="text-texto-tenue">a</span>
          <select
            value={filtros.hasta}
            onChange={(evento) => aplicar({ hasta: Number(evento.target.value) })}
            aria-label="Año hasta"
            className="rounded-md border border-borde bg-superficie px-2 py-1 text-xs text-texto"
          >
            {anios().map((anio) => (
              <option key={anio} value={anio}>
                {anio}
              </option>
            ))}
          </select>
        </span>

        <label className="flex items-center gap-2 text-xs text-texto-suave">
          <input
            type="checkbox"
            checked={filtros.soloVacaMuerta}
            onChange={(evento) => aplicar({ soloVacaMuerta: evento.target.checked })}
            className="accent-[#0054eb]"
          />
          Solo Vaca Muerta
        </label>

        {filtros.foco ? (
          <button
            type="button"
            onClick={() => aplicar({ foco: null })}
            className="flex items-center gap-1.5 rounded-md bg-azul/20 px-2 py-1 text-xs text-azul-claro transition hover:bg-azul/30"
          >
            Foco: {fmt.trimestre(filtros.foco)}
            <span aria-hidden="true">×</span>
            <span className="sr-only">quitar el foco del trimestre</span>
          </button>
        ) : null}

        {filtros.zona ? (
          <button
            type="button"
            onClick={() => aplicar({ zona: null })}
            className="flex items-center gap-1.5 rounded-md bg-azul/20 px-2 py-1 text-xs text-azul-claro transition hover:bg-azul/30"
          >
            Área: {filtros.zona}
            <span aria-hidden="true">×</span>
            <span className="sr-only">quitar el área señalada</span>
          </button>
        ) : null}

        {activos ? (
          <button
            type="button"
            onClick={limpiar}
            className="ml-auto rounded-md border border-borde px-2.5 py-1 text-xs text-texto-suave transition hover:border-azul-claro hover:text-azul-claro"
          >
            Limpiar filtros
          </button>
        ) : (
          <span className="ml-auto hidden font-mono text-[0.65rem] text-texto-tenue sm:block">
            los filtros se guardan en el link
          </span>
        )}
      </div>
    </div>
  );
}

function anios(): number[] {
  return Array.from({ length: RANGO_ANIOS.max - RANGO_ANIOS.min + 1 }, (_, i) => RANGO_ANIOS.min + i);
}
