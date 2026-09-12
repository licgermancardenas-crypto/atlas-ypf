'use client';

// El explorador territorial: bajar de la compañía a un yacimiento, un nivel por
// vez.
//
// Antes, esta parte de la pantalla eran dos listas —provincias y cuencas— con
// una barra cada una. Contestaban "cuánto produce Neuquén" y ahí se terminaban:
// para saber qué hay adentro de Neuquén había que subir al gráfico, cambiar la
// dimensión y buscar a ojo cuáles de las 52 concesiones eran neuquinas.
//
// Acá el mismo dato es navegable. Se entra a una provincia, se ve su reparto por
// cuenca; se entra a una cuenca, se ven sus concesiones; se entra a una
// concesión, se ven sus yacimientos. En cada nivel el encabezado dice lo mismo
// —caudal, peso, variación, mezcla de roca— así que la lectura no cambia de
// idioma al bajar, solo de escala.
//
// El árbol llega armado desde el servidor (lib/territorio.ts). Este componente
// no calcula producción: elige qué rama mostrar y cómo ordenarla.
//
// Lo que convierte la sección en parte de la investigación y no en un apéndice:
// desde cualquier concesión o yacimiento se salta al análisis de arriba, con la
// dimensión ya cambiada y la ficha abierta. Bajar hasta el activo y después
// verlo en la serie es un recorrido; hasta ahora eran dos pantallas sueltas.

import { useCallback, useEffect, useMemo, useState } from 'react';

import { fmt } from '@/lib/data';
import { COLOR } from '@/lib/produccion';
import { caminoDe, ETIQUETA_NIVEL, type NodoTerritorio } from '@/lib/territorio';
import { Composicion } from './Chispa';
import { useProduccionUI } from './contexto';

type Orden = 'volumen' | 'crecimiento';

function Variacion({ valor, className = '' }: { valor: number | null; className?: string }) {
  if (valor === null) {
    return <span className={`text-texto-tenue ${className}`}>—</span>;
  }
  const sube = valor >= 0;
  return (
    <span className={`${sube ? 'text-alza' : 'text-baja'} ${className}`}>
      {/* La flecha va además del color: el signo tiene que leerse sin
          distinguir verde de naranja. */}
      <span aria-hidden>{sube ? '▲' : '▼'}</span> {fmt.porcentajeConSigno(valor, 1)}
    </span>
  );
}

/** Una fila de hijo: nombre, barra de peso y los tres números. Toda la fila es
 *  el botón, no un ícono al final: el objetivo de clic es la fila entera. */
function Fila({
  nodo,
  alEntrar,
}: {
  nodo: NodoTerritorio;
  alEntrar: (nodo: NodoTerritorio) => void;
}) {
  const abre = nodo.hijos.length > 0;
  const detenido = nodo.actual_bd === 0 || Boolean(nodo.sinDeclararDesde);
  const subtitulo =
    nodo.sinDeclararDesde
      ? `sin declarar desde ${nodo.sinDeclararDesde}`
      : nodo.actual_bd === 0
        ? 'sin producción en los últimos doce meses'
        : nodo.nivel === 'concesion'
      ? `${nodo.hijos.length} ${nodo.hijos.length === 1 ? 'yacimiento' : 'yacimientos'}`
        : nodo.nivel === 'yacimiento'
          ? (nodo.localidad ?? '')
          : nodo.cuenta.concesiones
            ? `${nodo.cuenta.concesiones} concesiones · ${nodo.cuenta.yacimientos} yacimientos`
            : '';

  return (
    <li>
      <button
        type="button"
        onClick={() => alEntrar(nodo)}
        className="group block w-full rounded-md px-2 py-2 text-left transition-colors hover:bg-superficie-alta/70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-azul-claro"
      >
        <div className="flex items-baseline justify-between gap-3">
          <span className="flex min-w-0 items-baseline gap-2">
            <span className="truncate text-sm text-texto group-hover:text-azul-claro">
              {nodo.nombre}
            </span>
            {subtitulo ? (
              <span
                className={`hidden shrink-0 text-[0.7rem] sm:inline ${
                  detenido ? 'text-oro' : 'text-texto-tenue'
                }`}
              >
                {subtitulo}
              </span>
            ) : null}
          </span>
          <span className="flex shrink-0 items-baseline gap-3 text-xs">
            <span className="tabular text-texto">{fmt.entero(nodo.actual_bd)}</span>
            <span className="tabular w-12 text-right text-texto-tenue">
              {fmt.porcentaje(nodo.peso, 0)}
            </span>
            <Variacion valor={nodo.crecimiento} className="tabular w-16 text-right text-[0.72rem]" />
            <span
              aria-hidden
              className={`w-2 text-center ${abre ? 'text-texto-tenue group-hover:text-azul-claro' : 'text-transparent'}`}
            >
              ›
            </span>
          </span>
        </div>
        <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-superficie-alta">
          <span
            className={`block h-full transition-[width] duration-300 ${
              detenido ? 'bg-borde-vivo' : 'bg-azul group-hover:bg-azul-claro'
            }`}
            style={{ width: `${Math.max(nodo.peso * 100, 0.6)}%` }}
          />
        </div>
      </button>
    </li>
  );
}

export function Territorio({ raiz, nota }: { raiz: NodoTerritorio; nota: string }) {
  // La ruta es el estado entero de esta sección: el nodo actual se deriva de
  // ella y no se guarda aparte, así no hay dos fuentes de verdad que se puedan
  // contradecir.
  const [ruta, setRuta] = useState<string[]>([]);
  const [orden, setOrden] = useState<Orden>('volumen');
  const { enfocar } = useProduccionUI();

  const camino = useMemo(() => caminoDe(raiz, ruta), [raiz, ruta]);
  const actual = camino[camino.length - 1];

  const subir = useCallback(() => setRuta((previa) => previa.slice(0, -1)), []);

  // Escape sube un nivel: es el gesto que ya usa la ficha del activo para
  // cerrarse, y acá significa lo mismo —salir de donde entraste—.
  useEffect(() => {
    if (!ruta.length) return;
    const alTeclear = (evento: KeyboardEvent) => {
      const foco = document.activeElement;
      const escribiendo =
        foco instanceof HTMLInputElement ||
        foco instanceof HTMLTextAreaElement ||
        foco instanceof HTMLSelectElement;
      if (evento.key === 'Escape' && !escribiendo) subir();
    };
    document.addEventListener('keydown', alTeclear);
    return () => document.removeEventListener('keydown', alTeclear);
  }, [ruta.length, subir]);

  const hijos = useMemo(() => {
    const lista = [...actual.hijos];
    if (orden === 'crecimiento') {
      // Los que no tienen base de comparación van al fondo y no arriba: un null
      // ordenado como cero haría parecer que un activo nuevo se estancó.
      return lista.sort((a, b) => {
        if (a.crecimiento === null) return 1;
        if (b.crecimiento === null) return -1;
        return b.crecimiento - a.crecimiento;
      });
    }
    return lista.sort((a, b) => b.actual_bd - a.actual_bd);
  }, [actual.hijos, orden]);

  const etiqueta = ETIQUETA_NIVEL[actual.nivel];
  const entrar = (nodo: NodoTerritorio) => setRuta((previa) => [...previa, nodo.nombre]);

  // Provincia y cuenca cierran exacto —son la suma de sus concesiones—, pero una
  // concesión y sus yacimientos no siempre: un yacimiento se cuelga de la
  // concesión donde más produce, y si produce en dos, la diferencia queda a la
  // vista. Se declara cuando pasa del 1%, que es cuando deja de ser redondeo.
  const sumaHijos = useMemo(
    () => actual.hijos.reduce((suma, hijo) => suma + hijo.actual_bd, 0),
    [actual.hijos],
  );
  const desvio =
    actual.hijos.length && actual.actual_bd > 0 ? sumaHijos / actual.actual_bd - 1 : 0;

  return (
    <div className="marquesina rounded-lg border border-borde bg-superficie p-4">
      {/* Miga de pan. Cada tramo es un botón, así se sube de a varios niveles de
          una vez y no solo de a uno. */}
      <nav aria-label="Ruta territorial" className="flex flex-wrap items-center gap-1 text-xs">
        {camino.map((nodo, indice) => {
          const ultimo = indice === camino.length - 1;
          return (
            <span key={nodo.id || 'raiz'} className="flex items-center gap-1">
              {indice > 0 ? (
                <span aria-hidden className="text-texto-tenue">
                  ›
                </span>
              ) : null}
              {ultimo ? (
                <span aria-current="location" className="rounded px-1.5 py-0.5 text-texto">
                  {nodo.nombre}
                </span>
              ) : (
                <button
                  type="button"
                  onClick={() => setRuta(ruta.slice(0, indice))}
                  className="rounded px-1.5 py-0.5 text-texto-suave transition-colors hover:bg-superficie-alta hover:text-azul-claro focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-azul-claro"
                >
                  {nodo.nombre}
                </button>
              )}
            </span>
          );
        })}
        {ruta.length ? (
          <button
            type="button"
            onClick={subir}
            className="ml-auto rounded border border-borde px-1.5 py-0.5 text-[0.7rem] text-texto-tenue transition-colors hover:border-azul-claro hover:text-azul-claro focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-azul-claro"
          >
            ↑ Subir <span className="hidden sm:inline">· Esc</span>
          </button>
        ) : null}
      </nav>

      {/* El encabezado del nivel: los mismos cuatro datos en los cinco niveles.
          Que no cambie de forma al bajar es lo que hace que bajar se sienta
          como moverse y no como cambiar de pantalla. */}
      <div className="mt-3 border-t border-borde pt-3">
        <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
          <div className="min-w-0">
            <p className="font-mono text-[0.62rem] uppercase tracking-[0.14em] text-texto-tenue">
              {etiqueta.singular}
            </p>
            <p className="mt-1 truncate text-lg font-semibold leading-tight text-texto">
              {actual.nombre}
            </p>
            {actual.sinDeclararDesde ? (
              <p className="mt-1 text-[0.72rem] text-oro">
                Sin producción declarada como operada por YPF desde{' '}
                {actual.sinDeclararDesde}. Los números son de los últimos doce meses e incluyen los
                que ya no declara.
              </p>
            ) : null}
          </div>
          <div className="flex items-baseline gap-4">
            <p className="tabular text-2xl font-semibold leading-none text-texto">
              {fmt.entero(actual.actual_bd)}{' '}
              <span className="text-xs font-normal text-texto-suave">boe/d</span>
            </p>
            <div className="text-right text-[0.72rem]">
              <Variacion valor={actual.crecimiento} />
              <p className="text-texto-tenue">
                {actual.nivel === 'compania'
                  ? 'todo lo operado'
                  : `${fmt.porcentaje(actual.participacion, 1)} de YPF`}
              </p>
            </div>
          </div>
        </div>

        <div className="mt-3 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
          <div>
            <Composicion
              etiqueta={`Composición por tipo de roca de ${actual.nombre}`}
              partes={[
                { nombre: 'Shale', valor: actual.shale_bd, color: COLOR.shale },
                { nombre: 'Convencional', valor: actual.convencional_bd, color: COLOR.convencional },
                { nombre: 'Tight', valor: actual.tight_bd, color: COLOR.tight },
              ]}
            />
            <p className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[0.7rem] text-texto-tenue">
              <span>
                <span className="text-oro">Petróleo</span>{' '}
                <span className="tabular text-texto-suave">{fmt.entero(actual.oil_bd)}</span> bbl/d
              </span>
              <span>
                <span className="text-celeste">Gas</span>{' '}
                <span className="tabular text-texto-suave">{fmt.entero(actual.gas_bd)}</span> boe/d
              </span>
              {actual.actual_bd > 0 ? (
                <span>
                  <span style={{ color: COLOR.shale }}>Shale</span>{' '}
                  <span className="tabular text-texto-suave">
                    {fmt.porcentaje(actual.shale_bd / actual.actual_bd, 0)}
                  </span>
                </span>
              ) : null}
            </p>
          </div>

          {/* El salto al análisis. Solo aparece donde existe de verdad: cuenca y
              provincia tienen su propio corte allá arriba, pero el drill-down a
              los yacimientos de una concesión solo tiene sentido acá. */}
          {actual.dimension ? (
            <div className="flex flex-wrap items-start gap-2 sm:justify-end">
              <button
                type="button"
                onClick={() =>
                  enfocar({ dimension: actual.dimension!, nombre: actual.nombre, dentroDe: null })
                }
                className="rounded-md border border-borde px-2.5 py-1.5 text-xs text-texto-suave transition-colors hover:border-azul-claro hover:text-azul-claro focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-azul-claro"
              >
                Ver la serie
              </button>
              {actual.nivel === 'concesion' && actual.hijos.length > 1 ? (
                <button
                  type="button"
                  onClick={() =>
                    enfocar({ dimension: 'yacimiento', nombre: null, dentroDe: actual.nombre })
                  }
                  className="rounded-md border border-borde px-2.5 py-1.5 text-xs text-texto-suave transition-colors hover:border-azul-claro hover:text-azul-claro focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-azul-claro"
                >
                  Abrir sus yacimientos
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>

      {/* Los hijos */}
      {hijos.length ? (
        <div className="mt-4 border-t border-borde pt-3">
          <div className="flex items-center justify-between gap-3">
            <h4 className="font-mono text-[0.62rem] uppercase tracking-[0.14em] text-texto-tenue">
              {hijos.length} {etiqueta.hijos}
            </h4>
            <div
              role="group"
              aria-label="Orden de la lista"
              className="flex rounded-md border border-borde p-0.5"
            >
              {(
                [
                  { id: 'volumen', etiqueta: 'Volumen' },
                  { id: 'crecimiento', etiqueta: 'Crecimiento' },
                ] as const
              ).map((opcion) => (
                <button
                  key={opcion.id}
                  type="button"
                  aria-pressed={orden === opcion.id}
                  onClick={() => setOrden(opcion.id)}
                  className={`rounded px-2 py-0.5 text-[0.7rem] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-azul-claro ${
                    orden === opcion.id
                      ? 'bg-superficie-alta text-azul-claro'
                      : 'text-texto-tenue hover:text-texto-suave'
                  }`}
                >
                  {opcion.etiqueta}
                </button>
              ))}
            </div>
          </div>

          <ul className="mt-2 max-h-[22rem] space-y-0.5 overflow-y-auto pr-1">
            {hijos.map((nodo) => (
              <Fila key={nodo.id} nodo={nodo} alEntrar={entrar} />
            ))}
          </ul>

          {Math.abs(desvio) > 0.01 ? (
            <p className="mt-2 border-t border-borde pt-2 text-[0.7rem] leading-relaxed text-texto-tenue">
              Los {etiqueta.hijos} de la lista suman{' '}
              <span className="tabular">{fmt.entero(sumaHijos)}</span> boe/d,{' '}
              {fmt.porcentaje(Math.abs(desvio), 0)} {desvio < 0 ? 'menos' : 'más'} que el total de
              arriba: cada uno cuelga de la {actual.nivel === 'concesion' ? 'concesión' : 'rama'}{' '}
              donde más produce, y los que producen en dos aparecen enteros en una sola.
            </p>
          ) : null}
        </div>
      ) : (
        <div className="mt-4 rounded-md border border-dashed border-borde px-4 py-6 text-center">
          <p className="text-xs text-texto-suave">
            {actual.nivel === 'yacimiento'
              ? 'Un yacimiento es el último nivel de la fuente: por debajo están los pozos, que se ven en el mapa y en Relaciones.'
              : 'Este nivel no abre en más partes con los datos publicados.'}
          </p>
        </div>
      )}

      <p className="mt-3 text-[0.7rem] leading-relaxed text-texto-tenue">{nota}</p>
    </div>
  );
}
