'use client';

// La tabla del ranking: el mismo dato del gráfico, para leerlo fila por fila.
//
// Un gráfico contesta "qué está pasando"; una tabla contesta "cuánto,
// exactamente, y en qué orden". Las dos cosas hacen falta, y por eso la tabla no
// es un apéndice: ordena por cualquier columna, busca, pagina, se copia a una
// planilla y baja en CSV con todas las filas, no con la página que se ve.
//
// Las columnas dependen de la dimensión elegida. Una concesión tiene provincia,
// cuenca y cantidad de yacimientos; una cuenca no tiene nada de eso, y mostrar
// tres columnas vacías sería peor que no mostrarlas.

import { useMemo, useState } from 'react';

import { fmt } from '@/lib/data';
import {
  DIMENSIONES,
  type FichaActivo,
  type FilaRankingYPF,
  type IdDimension,
} from '@/lib/produccion';

type Clave =
  | 'nombre'
  | 'provincia'
  | 'cuenca'
  | 'contexto'
  | 'tipo'
  | 'oil_bd'
  | 'gas_bd'
  | 'actual_bd'
  | 'crecimiento'
  | 'participacion';

interface FilaTabla extends Record<string, string | number | null> {
  nombre: string;
  provincia: string | null;
  cuenca: string | null;
  contexto: string | null;
  tipo: string;
  oil_bd: number | null;
  gas_bd: number | null;
  actual_bd: number;
  crecimiento: number | null;
  participacion: number | null;
}

const COLUMNAS: { clave: Clave; titulo: string; numerica?: boolean; ancho?: string }[] = [
  { clave: 'nombre', titulo: 'Activo' },
  { clave: 'provincia', titulo: 'Provincia' },
  { clave: 'cuenca', titulo: 'Cuenca' },
  { clave: 'contexto', titulo: 'Contexto' },
  { clave: 'tipo', titulo: 'Tipo' },
  { clave: 'oil_bd', titulo: 'Petróleo bbl/d', numerica: true },
  { clave: 'gas_bd', titulo: 'Gas boe/d', numerica: true },
  { clave: 'actual_bd', titulo: 'Total boe/d', numerica: true },
  { clave: 'crecimiento', titulo: 'Var. i.a.', numerica: true },
  { clave: 'participacion', titulo: 'De YPF', numerica: true },
];

const POR_PAGINA = 15;

/** El tipo de roca dominante del activo. Es derivado y se declara como tal: sale
 *  de comparar las tres columnas del último año, no de un campo de la fuente. */
function tipoDominante(fila: FilaRankingYPF): string {
  const partes: [string, number][] = [
    ['Shale', fila.shale_bd ?? 0],
    ['Convencional', fila.convencional_bd ?? 0],
    ['Tight', fila.tight_bd ?? 0],
  ];
  const [nombre, valor] = partes.sort((a, b) => b[1] - a[1])[0];
  return valor > 0 ? nombre : '—';
}

function aTexto(fila: FilaTabla, clave: Clave): string {
  const valor = fila[clave];
  if (valor === null || valor === undefined || valor === '') return '—';
  if (clave === 'crecimiento') return fmt.porcentajeConSigno(Number(valor), 1);
  if (clave === 'participacion') return fmt.porcentaje(Number(valor), 1);
  if (typeof valor === 'number') return fmt.entero(valor);
  return String(valor);
}

export function TablaProduccion({
  dimension,
  ranking,
  meta,
  seleccionado,
  alSeleccionar,
}: {
  dimension: IdDimension;
  ranking: FilaRankingYPF[];
  meta: Record<string, FichaActivo> | undefined;
  seleccionado: string | null;
  alSeleccionar: (nombre: string) => void;
}) {
  const [busqueda, setBusqueda] = useState('');
  const [orden, setOrden] = useState<{ clave: Clave; descendente: boolean }>({
    clave: 'actual_bd',
    descendente: true,
  });
  const [pagina, setPagina] = useState(0);
  const [copiado, setCopiado] = useState(false);

  const territorial = dimension === 'concesion' || dimension === 'yacimiento' || dimension === 'localidad';
  const columnas = useMemo(
    () =>
      COLUMNAS.filter((columna) => {
        if (!territorial && ['provincia', 'cuenca', 'contexto'].includes(columna.clave)) return false;
        if (columna.clave === 'contexto' && dimension === 'localidad') return true;
        return true;
      }),
    [territorial, dimension],
  );

  const filas = useMemo<FilaTabla[]>(() => {
    return ranking.map((fila) => {
      const ficha = meta?.[fila.nombre];
      const contexto =
        dimension === 'concesion'
          ? ficha?.yacimientos
            ? `${ficha.yacimientos} yacimiento${ficha.yacimientos === 1 ? '' : 's'}`
            : null
          : dimension === 'yacimiento'
            ? (ficha?.concesion ?? null)
            : dimension === 'localidad'
              ? ficha?.yacimientos
                ? `${ficha.yacimientos} yacimientos`
                : null
              : null;
      return {
        nombre: fila.nombre,
        provincia: ficha?.provincia ?? null,
        cuenca: ficha?.cuenca ?? null,
        contexto,
        tipo: tipoDominante(fila),
        oil_bd: fila.oil_bd ?? null,
        gas_bd: fila.gas_bd ?? null,
        actual_bd: fila.actual_bd,
        crecimiento: fila.crecimiento,
        participacion: fila.participacion,
      };
    });
  }, [ranking, meta, dimension]);

  const filtradas = useMemo(() => {
    const texto = busqueda.trim().toLowerCase();
    const base = texto
      ? filas.filter((fila) =>
          [fila.nombre, fila.provincia, fila.cuenca, fila.contexto, fila.tipo]
            .filter(Boolean)
            .some((valor) => String(valor).toLowerCase().includes(texto)),
        )
      : filas;

    const signo = orden.descendente ? -1 : 1;
    return [...base].sort((a, b) => {
      const va = a[orden.clave];
      const vb = b[orden.clave];
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * signo;
      return String(va).localeCompare(String(vb), 'es') * signo;
    });
  }, [filas, busqueda, orden]);

  const paginas = Math.max(1, Math.ceil(filtradas.length / POR_PAGINA));
  const actual = Math.min(pagina, paginas - 1);
  const visibles = filtradas.slice(actual * POR_PAGINA, (actual + 1) * POR_PAGINA);

  const descargar = () => {
    const escapar = (valor: string) => (/[",;\n]/.test(valor) ? `"${valor.replace(/"/g, '""')}"` : valor);
    const lineas = [
      columnas.map((columna) => escapar(columna.titulo)).join(','),
      ...filtradas.map((fila) =>
        columnas
          .map((columna) => {
            const valor = fila[columna.clave];
            return escapar(valor === null || valor === undefined ? '' : String(valor));
          })
          .join(','),
      ),
    ];
    // El BOM es para que Excel en Windows abra las tildes bien.
    const blob = new Blob([`﻿${lineas.join('\n')}`], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const enlace = document.createElement('a');
    enlace.href = url;
    enlace.download = `atlas-ypf-produccion-${dimension}.csv`;
    enlace.click();
    URL.revokeObjectURL(url);
  };

  const copiar = async () => {
    // Separado por tabulaciones: así se pega directo en una planilla, que es lo
    // que alguien hace con una tabla cuando quiere seguir trabajando.
    const texto = [
      columnas.map((columna) => columna.titulo).join('\t'),
      ...filtradas.map((fila) => columnas.map((columna) => aTexto(fila, columna.clave)).join('\t')),
    ].join('\n');
    try {
      await navigator.clipboard.writeText(texto);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      setCopiado(false);
    }
  };

  const etiqueta = DIMENSIONES.find((item) => item.id === dimension)!;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <label className="sr-only" htmlFor="buscar-activo">
          Buscar
        </label>
        <input
          id="buscar-activo"
          type="search"
          value={busqueda}
          onChange={(evento) => {
            setBusqueda(evento.target.value);
            setPagina(0);
          }}
          placeholder={`Buscar entre ${filas.length} ${etiqueta.plural}…`}
          className="w-56 rounded-md border border-borde bg-superficie px-2.5 py-1.5 text-xs text-texto placeholder:text-texto-tenue focus:border-azul-claro focus:outline-none"
        />
        <span className="text-[0.7rem] text-texto-tenue">
          {filtradas.length} de {filas.length} · últimos doce meses
        </span>
        <div className="ml-auto flex items-center gap-1.5">
          <button
            type="button"
            onClick={copiar}
            className="rounded-md border border-borde px-2 py-1 text-[0.7rem] text-texto-tenue transition-colors hover:border-azul-claro hover:text-azul-claro"
          >
            {copiado ? 'Copiado' : 'Copiar'}
          </button>
          <button
            type="button"
            onClick={descargar}
            className="rounded-md border border-borde px-2 py-1 text-[0.7rem] text-texto-tenue transition-colors hover:border-azul-claro hover:text-azul-claro"
            title={`Bajar ${filtradas.length} filas en CSV`}
          >
            CSV
          </button>
        </div>
      </div>

      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[52rem] border-collapse text-xs">
          <thead>
            <tr className="border-b border-borde">
              {columnas.map((columna) => {
                const activa = orden.clave === columna.clave;
                return (
                  <th
                    key={columna.clave}
                    scope="col"
                    aria-sort={activa ? (orden.descendente ? 'descending' : 'ascending') : 'none'}
                    className={`py-2 font-normal ${columna.numerica ? 'text-right' : 'text-left'}`}
                  >
                    <button
                      type="button"
                      onClick={() =>
                        setOrden((previo) =>
                          previo.clave === columna.clave
                            ? { clave: columna.clave, descendente: !previo.descendente }
                            : { clave: columna.clave, descendente: Boolean(columna.numerica) },
                        )
                      }
                      className={`font-mono text-[0.66rem] uppercase tracking-[0.1em] transition-colors hover:text-azul-claro ${
                        activa ? 'text-azul-claro' : 'text-texto-tenue'
                      }`}
                    >
                      {columna.titulo}
                      <span aria-hidden className="ml-1">
                        {activa ? (orden.descendente ? '↓' : '↑') : ''}
                      </span>
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {visibles.map((fila) => {
              const elegida = seleccionado === fila.nombre;
              return (
                <tr
                  key={fila.nombre}
                  onClick={() => alSeleccionar(fila.nombre)}
                  className={`cursor-pointer border-b border-borde/60 transition-colors hover:bg-superficie-alta/60 ${
                    elegida ? 'bg-superficie-alta' : ''
                  }`}
                >
                  {columnas.map((columna) => (
                    <td
                      key={columna.clave}
                      className={`py-1.5 pr-3 ${
                        columna.numerica ? 'tabular text-right text-texto' : 'text-texto-suave'
                      } ${columna.clave === 'nombre' ? 'font-medium text-texto' : ''} ${
                        columna.clave === 'crecimiento' && fila.crecimiento !== null
                          ? fila.crecimiento >= 0
                            ? 'text-alza'
                            : 'text-baja'
                          : ''
                      }`}
                    >
                      {aTexto(fila, columna.clave)}
                    </td>
                  ))}
                </tr>
              );
            })}
            {!visibles.length ? (
              <tr>
                <td colSpan={columnas.length} className="py-8 text-center text-texto-tenue">
                  Ningún activo coincide con “{busqueda}”.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      {paginas > 1 ? (
        <div className="mt-3 flex items-center justify-end gap-2 text-[0.7rem] text-texto-tenue">
          <button
            type="button"
            onClick={() => setPagina(Math.max(0, actual - 1))}
            disabled={actual === 0}
            className="rounded-md border border-borde px-2 py-1 transition-colors hover:border-azul-claro hover:text-azul-claro disabled:opacity-40 disabled:hover:border-borde disabled:hover:text-texto-tenue"
          >
            Anterior
          </button>
          <span className="tabular">
            {actual + 1} / {paginas}
          </span>
          <button
            type="button"
            onClick={() => setPagina(Math.min(paginas - 1, actual + 1))}
            disabled={actual >= paginas - 1}
            className="rounded-md border border-borde px-2 py-1 transition-colors hover:border-azul-claro hover:text-azul-claro disabled:opacity-40 disabled:hover:border-borde disabled:hover:text-texto-tenue"
          >
            Siguiente
          </button>
        </div>
      ) : null}
    </div>
  );
}
