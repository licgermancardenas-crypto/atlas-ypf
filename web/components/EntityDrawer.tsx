'use client';

// El panel de una entidad: sus métricas y con quién está conectada.
//
// La lista de conexiones es la razón de ser del panel, no un adorno al pie. Un
// yacimiento con tres empresas adentro no se lee en una tabla: se lee viendo
// los tres chips y pudiendo saltar a cualquiera. Por eso cada conexión es un
// botón que cambia la selección, y cambiar la selección mueve el grafo y el
// mapa a la vez.

import { fmt } from '@/lib/data';
import {
  COLOR_TIPO,
  ETIQUETA_TIPO,
  produccionDe,
  vecinos,
  type AristaGrafo,
  type NodoGrafo,
  type TipoEntidad,
} from '@/lib/grafo';

/** Qué se muestra de cada tipo, en qué orden y con qué unidad. Está declarado
 *  y no derivado del objeto `props` porque el orden importa: lo primero que
 *  tiene que ver alguien que abre una concesión es cuánto produce, no de qué
 *  cuenca es. */
const CAMPOS: Record<TipoEntidad, { clave: string; etiqueta: string; formato: string }[]> = {
  concesion: [
    { clave: 'produccion_total_bbl_d', etiqueta: 'Producción', formato: 'bbl' },
    { clave: 'produccion_gas_m3d', etiqueta: 'Gas', formato: 'gas' },
    { clave: 'cantidad_pozos', etiqueta: 'Pozos', formato: 'entero' },
    { clave: 'pozos_activos', etiqueta: 'Pozos activos', formato: 'entero' },
    { clave: 'cuenca', etiqueta: 'Cuenca', formato: 'texto' },
    { clave: 'provincia', etiqueta: 'Provincia', formato: 'texto' },
  ],
  yacimiento: [
    { clave: 'produccion_bbl_d', etiqueta: 'Producción', formato: 'bbl' },
    { clave: 'produccion_gas_m3d', etiqueta: 'Gas', formato: 'gas' },
    { clave: 'cantidad_pozos', etiqueta: 'Pozos', formato: 'entero' },
    { clave: 'pozos_activos', etiqueta: 'Pozos activos', formato: 'entero' },
    { clave: 'cantidad_empresas', etiqueta: 'Empresas operando', formato: 'entero' },
    { clave: 'concesion', etiqueta: 'Concesión', formato: 'texto' },
  ],
  empresa: [
    { clave: 'produccion_atribuida_bbl_d', etiqueta: 'Producción operada', formato: 'bbl' },
    { clave: 'pozos_operados', etiqueta: 'Pozos operados', formato: 'entero' },
    { clave: 'concesiones_operadas', etiqueta: 'Concesiones que opera', formato: 'entero' },
    { clave: 'concesiones_participadas', etiqueta: 'Concesiones en las que participa', formato: 'entero' },
    { clave: 'yacimientos_presentes', etiqueta: 'Yacimientos', formato: 'entero' },
  ],
  pozo: [
    { clave: 'produccion_bbl_d', etiqueta: 'Producción', formato: 'bbl' },
    { clave: 'produccion_gas_m3d', etiqueta: 'Gas', formato: 'gas' },
    { clave: 'estado_detalle', etiqueta: 'Estado', formato: 'texto' },
    { clave: 'formacion', etiqueta: 'Formación', formato: 'texto' },
    { clave: 'yacimiento', etiqueta: 'Yacimiento', formato: 'texto' },
    { clave: 'concesion', etiqueta: 'Concesión', formato: 'texto' },
  ],
};

function valor(bruto: unknown, formato: string): string {
  if (bruto === null || bruto === undefined || bruto === '') return '—';
  if (formato === 'texto') return String(bruto);
  const numero = Number(bruto);
  if (!Number.isFinite(numero)) return '—';
  if (formato === 'bbl') return `${fmt.entero(numero)} bbl/d`;
  if (formato === 'gas') return `${fmt.entero(numero)} m³/d`;
  return fmt.entero(numero);
}

function Chip({
  nodo,
  detalle,
  onSelect,
}: {
  nodo: NodoGrafo;
  detalle?: string;
  onSelect: (id: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(nodo.id)}
      title={`${ETIQUETA_TIPO[nodo.type]}: ${nodo.label}`}
      className="group flex max-w-full items-center gap-1.5 rounded-md border border-borde bg-superficie-alta/40 px-2 py-1 text-left text-xs text-texto-suave transition hover:border-azul-claro hover:text-texto"
    >
      <span
        className="h-2 w-2 shrink-0 rounded-full"
        style={{ background: COLOR_TIPO[nodo.type] }}
        aria-hidden="true"
      />
      <span className="truncate">{nodo.label}</span>
      {detalle ? <span className="tabular shrink-0 text-texto-tenue">{detalle}</span> : null}
    </button>
  );
}

export function EntityDrawer({
  nodo,
  nodos,
  aristas,
  onSelect,
  onCerrar,
  onVerPozos,
  pozosVisibles,
  cargandoPozos,
}: {
  nodo: NodoGrafo | null;
  nodos: Map<string, NodoGrafo>;
  aristas: AristaGrafo[];
  onSelect: (id: string) => void;
  onCerrar: () => void;
  onVerPozos?: () => void;
  pozosVisibles?: boolean;
  cargandoPozos?: boolean;
}) {
  if (!nodo) {
    return (
      <aside className="flex h-full flex-col justify-center rounded-lg border border-dashed border-borde bg-superficie p-6 text-center">
        <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
          Nada seleccionado
        </p>
        <p className="mt-2 text-xs leading-relaxed text-texto-suave">
          Hacé clic en cualquier nodo del grafo —o en una concesión del mapa— para ver sus
          métricas y con quién está conectado.
        </p>
      </aside>
    );
  }

  const conectados = vecinos(nodo.id, aristas)
    .map((vecino) => ({ ...vecino, nodo: nodos.get(vecino.id) }))
    .filter((vecino): vecino is typeof vecino & { nodo: NodoGrafo } => Boolean(vecino.nodo));

  // Agrupados por tipo y ordenados por producción: en una concesión con
  // catorce yacimientos, el orden alfabético esconde el que importa.
  const grupos: { tipo: TipoEntidad; titulo: string; items: typeof conectados }[] = (
    ['empresa', 'concesion', 'yacimiento', 'pozo'] as TipoEntidad[]
  )
    .map((tipo) => ({
      tipo,
      titulo:
        tipo === 'empresa'
          ? 'Empresas'
          : tipo === 'concesion'
            ? 'Concesiones'
            : tipo === 'yacimiento'
              ? 'Yacimientos'
              : 'Pozos',
      items: conectados
        .filter((vecino) => vecino.nodo.type === tipo)
        .sort((a, b) => (b.pct ?? produccionDe(b.nodo)) - (a.pct ?? produccionDe(a.nodo))),
    }))
    .filter((grupo) => grupo.items.length > 0);

  const puedeExpandir =
    onVerPozos && (nodo.type === 'concesion' || nodo.type === 'yacimiento');

  return (
    <aside className="flex h-full flex-col overflow-hidden rounded-lg border border-borde bg-superficie">
      <header className="flex items-start justify-between gap-3 border-b border-borde px-5 py-4">
        <div className="min-w-0">
          <p
            className="font-mono text-[0.7rem] uppercase tracking-[0.14em]"
            style={{ color: COLOR_TIPO[nodo.type] }}
          >
            {ETIQUETA_TIPO[nodo.type]}
          </p>
          <h3 className="mt-1 truncate text-base font-semibold text-texto" title={nodo.label}>
            {nodo.label}
          </h3>
        </div>
        <button
          type="button"
          onClick={onCerrar}
          aria-label="Cerrar el panel"
          className="shrink-0 rounded-md border border-borde px-2 py-1 text-xs text-texto-tenue transition hover:border-azul-claro hover:text-azul-claro"
        >
          ✕
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-5 py-4">
        <dl className="space-y-1.5 text-xs">
          {CAMPOS[nodo.type].map((campo) => (
            <div key={campo.clave} className="flex justify-between gap-3">
              <dt className="text-texto-tenue">{campo.etiqueta}</dt>
              <dd className="tabular text-right text-texto">
                {valor(nodo.props[campo.clave], campo.formato)}
              </dd>
            </div>
          ))}
        </dl>

        {nodo.type === 'concesion' && nodo.props.titularidad_conocida === false ? (
          <p className="mt-4 border-l-2 border-oro pl-3 text-[0.7rem] leading-relaxed text-texto-tenue">
            Esta concesión no figura con ese nombre en el padrón de Concesiones de Explotación,
            así que no tiene socios ni porcentajes cargados. No se le asigna la titularidad de un
            área parecida: un match aproximado acá sería inventar quién es dueño de qué.
          </p>
        ) : null}

        {grupos.map((grupo) => (
          <div key={grupo.tipo} className="mt-5">
            <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
              {grupo.titulo}{' '}
              <span className="text-texto-suave">{grupo.items.length}</span>
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {grupo.items.slice(0, 60).map((vecino) => (
                <Chip
                  key={vecino.id}
                  nodo={vecino.nodo}
                  detalle={
                    vecino.relacion === 'titularidad' && vecino.pct !== undefined
                      ? `${fmt.numero(vecino.pct, 0)}%`
                      : undefined
                  }
                  onSelect={onSelect}
                />
              ))}
              {grupo.items.length > 60 ? (
                <span className="self-center text-[0.7rem] text-texto-tenue">
                  y {grupo.items.length - 60} más
                </span>
              ) : null}
            </div>
          </div>
        ))}

        {puedeExpandir ? (
          <button
            type="button"
            onClick={onVerPozos}
            disabled={cargandoPozos}
            className="mt-5 w-full rounded-md border border-borde px-3 py-2 text-xs text-texto-suave transition hover:border-azul-claro hover:text-azul-claro disabled:opacity-50"
          >
            {cargandoPozos
              ? 'Bajando los pozos…'
              : pozosVisibles
                ? 'Ocultar los pozos'
                : `Ver los ${fmt.entero(Number(nodo.props.cantidad_pozos ?? 0))} pozos en el grafo`}
          </button>
        ) : null}
      </div>
    </aside>
  );
}
