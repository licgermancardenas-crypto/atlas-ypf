'use client';

// El módulo de análisis: lo único que corre en el navegador de esta pantalla.
//
// Arriba se pinta en el servidor lo que no cambia —la lectura, los KPI—, así
// que la página se lee entera antes de que baje ninguna serie. Acá abajo vive lo
// que sí cambia: los filtros, las cuatro vistas del gráfico, la tabla, las
// señales y la ficha del activo.
//
// El estado es chico a propósito: seis controles, una vista, un activo
// seleccionado. Todo lo demás se deriva con useMemo de esos seis valores y de
// las series, que se bajan una sola vez. Cambiar de vista o de tipo de roca no
// vuelve a pedir nada ni recalcula lo que no depende de eso.
//
// El rango de años no vive acá: es el filtro global del sitio, el mismo que usan
// el caso y el módulo operativo, y por eso viaja en la URL.
//
// El resto del estado también viaja en la URL, con el mismo criterio que el
// grafo de Relaciones: una vista tiene que ser un link. "Mirá el shale de Loma
// Campana por año" se manda pegando una dirección, no explicando seis clics. Se
// escribe con replaceState y no con el router para no forzar el render del lado
// del cliente de una página que se prerenderiza entera.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { fmt, type AgregadoEconomico } from '@/lib/data';
import type { Traspaso } from '@/lib/produccion';
import {
  agrupar,
  armarSeries,
  clavesDe,
  COLOR_COHORTE,
  COLOR_OTROS,
  curvaDesdeDebut,
  DIMENSIONES,
  medidaDelRanking,
  medir,
  NOMBRE_OTROS,
  normalizarNombre,
  quiebreReciente,
  RAMPA,
  rankingDeSeries,
  senales as calcularSenales,
  serieMensualDe,
  unidadDe,
  type IdVista,
  type MiembroYPF,
  type ProduccionYPF,
} from '@/lib/produccion';
import { useFiltros } from '../estado/filtros';
import { Esqueleto } from '../Panel';
import { useProduccionUI } from './contexto';
import { Controles, type EstadoControles } from './Controles';
import { Grafico, Leyenda } from './Grafico';
import { PanelActivo, type ActivoSeleccionado, type SupuestosEconomia } from './PanelActivo';
import { Senales } from './Senales';
import { TablaProduccion } from './TablaProduccion';

const VISTAS: { id: IdVista; etiqueta: string; ayuda: string }[] = [
  { id: 'produccion', etiqueta: 'Producción', ayuda: 'Cuánto sale y de qué activo.' },
  { id: 'crecimiento', etiqueta: 'Crecimiento', ayuda: 'Variación contra el mismo período del año anterior.' },
  { id: 'participacion', etiqueta: 'Participación', ayuda: 'Quién le gana lugar a quién.' },
  { id: 'ranking', etiqueta: 'Ranking', ayuda: 'El último año, activo por activo.' },
  { id: 'cohortes', etiqueta: 'Cohortes', ayuda: 'De qué época es la producción de hoy.' },
  { id: 'curvas', etiqueta: 'Curvas', ayuda: 'Dos o tres activos alineados a su propio mes uno.' },
];

/** Cuántos activos se pueden comparar a la vez en la vista de curvas. Tres
 *  curvas todavía se distinguen de un vistazo; cinco ya son una madeja. */
const MAX_COMPARADOS = 3;

export interface EnlacesActivo {
  /** id del grafo de entidades, por dimensión y nombre. Solo los que existen. */
  entidades: Record<string, Record<string, string>>;
}

export interface EconomiaPorActivo {
  /** Por nombre normalizado: el padrón de pozos y el de producción no escriben
   *  igual al mismo yacimiento. */
  porYacimiento: Record<string, AgregadoEconomico>;
  supuestos: SupuestosEconomia;
}

const CLAVES = {
  dimension: 'dim',
  fluido: 'prod',
  recurso: 'tipo',
  periodo: 'per',
  metrica: 'met',
  top: 'top',
  vista: 'vista',
  modo: 'modo',
  seleccionado: 'activo',
  foco: 'dentro',
} as const;

function leerDeUrl(): {
  estado: Partial<EstadoControles>;
  vista?: IdVista;
  modo?: 'grafico' | 'tabla';
  seleccionado?: string;
  foco?: string;
} {
  const params = new URLSearchParams(window.location.search);
  const estado: Partial<EstadoControles> = {};
  const dimension = params.get(CLAVES.dimension);
  if (DIMENSIONES.some((item) => item.id === dimension)) {
    estado.dimension = dimension as EstadoControles['dimension'];
  }
  const fluido = params.get(CLAVES.fluido);
  if (fluido === 'oil' || fluido === 'gas' || fluido === 'boe') estado.fluido = fluido;
  const recurso = params.get(CLAVES.recurso);
  if (recurso === 'todo' || recurso === 'shale' || recurso === 'convencional' || recurso === 'tight') {
    estado.recurso = recurso;
  }
  const periodo = params.get(CLAVES.periodo);
  if (periodo === 'mes' || periodo === 'trimestre' || periodo === 'anio') estado.periodo = periodo;
  const metrica = params.get(CLAVES.metrica);
  if (metrica === 'caudal' || metrica === 'volumen') estado.metrica = metrica;
  const top = params.get(CLAVES.top);
  if (top !== null && Number.isFinite(Number(top))) estado.top = Number(top);

  const vista = params.get(CLAVES.vista);
  const modo = params.get(CLAVES.modo);
  const seleccionado = params.get(CLAVES.seleccionado);
  const foco = params.get(CLAVES.foco);

  return {
    estado,
    vista: VISTAS.some((item) => item.id === vista) ? (vista as IdVista) : undefined,
    modo: modo === 'tabla' ? 'tabla' : undefined,
    seleccionado: seleccionado ?? undefined,
    foco: foco ?? undefined,
  };
}

const INICIAL: EstadoControles = {
  dimension: 'concesion',
  fluido: 'boe',
  recurso: 'todo',
  periodo: 'trimestre',
  metrica: 'caudal',
  top: 5,
};

export function ModuloProduccion({
  datos,
  enlaces,
  economia,
}: {
  datos: ProduccionYPF;
  enlaces: EnlacesActivo;
  economia: EconomiaPorActivo;
}) {
  const { filtros, aplicar } = useFiltros();
  const [estado, setEstado] = useState<EstadoControles>(INICIAL);
  const [vista, setVista] = useState<IdVista>('produccion');
  const [modo, setModo] = useState<'grafico' | 'tabla'>('grafico');
  const [avanzados, setAvanzados] = useState(false);
  const [seleccionado, setSeleccionado] = useState<string | null>(null);
  // El drill-down: cuando se mira "los yacimientos de Loma Campana", acá está
  // Loma Campana. Solo tiene sentido con la dimensión en yacimiento, que es el
  // único nivel que cuelga de una concesión.
  const [foco, setFoco] = useState<string | null>(null);
  // Los activos que se comparan en la vista de curvas. Vacío quiere decir "los
  // que el ranking pone primero", que es lo que alguien quiere ver sin elegir.
  const [comparados, setComparados] = useState<string[]>([]);
  const seccion = useRef<HTMLElement>(null);
  const { pedido } = useProduccionUI();
  const [dimensiones, setDimensiones] = useState<Record<string, { miembros: MiembroYPF[] }> | null>(
    null,
  );

  // Se lee al montar y no en el estado inicial: el servidor no tiene
  // querystring y pintaría otra cosa que el cliente, que es un error de
  // hidratación.
  useEffect(() => {
    const leido = leerDeUrl();
    if (Object.keys(leido.estado).length) setEstado((previo) => ({ ...previo, ...leido.estado }));
    if (leido.vista) setVista(leido.vista);
    if (leido.modo) setModo(leido.modo);
    if (leido.seleccionado) setSeleccionado(leido.seleccionado);
    if (leido.foco) setFoco(leido.foco);
  }, []);

  // Y se escribe en cada cambio: lo que se ve es lo que se comparte.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const poner = (clave: string, valor: string | null, porDefecto: string) => {
      if (valor === null || valor === porDefecto) params.delete(clave);
      else params.set(clave, valor);
    };
    poner(CLAVES.dimension, estado.dimension, INICIAL.dimension);
    poner(CLAVES.fluido, estado.fluido, INICIAL.fluido);
    poner(CLAVES.recurso, estado.recurso, INICIAL.recurso);
    poner(CLAVES.periodo, estado.periodo, INICIAL.periodo);
    poner(CLAVES.metrica, estado.metrica, INICIAL.metrica);
    poner(CLAVES.top, String(estado.top), String(INICIAL.top));
    poner(CLAVES.vista, vista, 'produccion');
    poner(CLAVES.modo, modo, 'grafico');
    poner(CLAVES.seleccionado, seleccionado, '');
    poner(CLAVES.foco, foco, '');

    const consulta = params.toString();
    window.history.replaceState(
      null,
      '',
      `${window.location.pathname}${consulta ? `?${consulta}` : ''}${window.location.hash}`,
    );
  }, [estado, vista, modo, seleccionado, foco]);

  // El pedido que llega del explorador territorial: "abrí esto acá arriba".
  // Cambia el corte, abre la ficha y sube la pantalla hasta el gráfico, porque
  // un cambio que ocurre fuera de la vista es un cambio que no ocurrió.
  useEffect(() => {
    if (!pedido) return;
    setEstado((previo) => ({ ...previo, dimension: pedido.dimension }));
    setFoco(pedido.dentroDe);
    setSeleccionado(pedido.nombre);
    setModo('grafico');
    if (!pedido.nombre) setVista('produccion');
    seccion.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [pedido]);

  // Las series mensuales son 250 KB y no hacen falta para leer los números de
  // arriba: se bajan cuando este bloque se monta, no con la página.
  useEffect(() => {
    let vigente = true;
    fetch('/data/ypf_dimensiones.json')
      .then((respuesta) => respuesta.json())
      .then((payload: { dimensiones: Record<string, { miembros: MiembroYPF[] }> }) => {
        if (vigente) setDimensiones(payload.dimensiones);
      })
      .catch(() => {
        if (vigente) setDimensiones({});
      });
    return () => {
      vigente = false;
    };
  }, []);

  const cambiar = useCallback((cambio: Partial<EstadoControles>) => {
    setEstado((previo) => ({ ...previo, ...cambio }));
    // Cambiar de dimensión cambia el universo de activos: el que estaba
    // seleccionado ya no existe en el nuevo corte, y el drill-down tampoco
    // —solo los yacimientos cuelgan de una concesión—.
    if (cambio.dimension) {
      setSeleccionado(null);
      if (cambio.dimension !== 'yacimiento') setFoco(null);
    }
  }, []);

  // El drill-down filtra por la concesión dominante que ya trae la ficha de
  // cada yacimiento: no hace falta un cruce nuevo ni un dato nuevo, solo mirar
  // una rama del padrón que el pipeline ya publicó.
  const dentroDe = estado.dimension === 'yacimiento' ? foco : null;
  const miembrosBase = dimensiones?.[estado.dimension]?.miembros;
  const miembros = useMemo(() => {
    if (!miembrosBase || !dentroDe) return miembrosBase;
    const fichas = datos.meta?.yacimiento ?? {};
    return miembrosBase.filter((miembro) => fichas[miembro.nombre]?.concesion === dentroDe);
  }, [miembrosBase, dentroDe, datos.meta]);
  const claves = useMemo(
    () => clavesDe(estado.fluido, estado.recurso),
    [estado.fluido, estado.recurso],
  );
  const grupos = useMemo(
    () => agrupar(datos.fechas, datos.dias, estado.periodo),
    [datos.fechas, datos.dias, estado.periodo],
  );

  // Las cohortes vienen armadas del pipeline como una dimensión más, con los
  // 274 yacimientos del archivo adentro. Calcularlas acá habría tomado los
  // dieciséis miembros que el archivo publica con serie propia y metido toda la
  // cola en la cohorte más vieja, que es exactamente la conclusión equivocada.
  const cohortes = vista === 'cohortes' ? (dimensiones?.cohorte?.miembros ?? []) : null;

  // Las áreas que cambiaron de operador, por nombre: el gráfico las sigue
  // mostrando —produjeron de verdad hasta ese mes— pero la ficha lo avisa y la
  // señal de quiebre no las confunde con un derrumbe.
  const traspasadas = useMemo(() => {
    const mapa = new Map<string, Traspaso>();
    for (const fila of datos.traspasos ?? []) {
      if (fila.dimension === estado.dimension) mapa.set(fila.nombre, fila);
    }
    return mapa;
  }, [datos.traspasos, estado.dimension]);

  const armadas = useMemo(
    () =>
      armarSeries({
        miembros: cohortes ?? miembros ?? [],
        claves,
        grupos,
        // Las cohortes son cinco y ninguna es cola larga: agruparlas en "Otros"
        // sería esconder justamente la que interesa, que es la más nueva.
        top: cohortes ? 0 : estado.top,
        desde: filtros.desde,
        hasta: filtros.hasta,
      }),
    [cohortes, miembros, claves, grupos, estado.top, filtros.desde, filtros.hasta],
  );

  // La participación del shale por período: se calcula aparte porque el tooltip
  // la muestra siempre, incluso cuando el gráfico está filtrado a un solo tipo
  // de roca —ahí el dato deja de ser deducible de lo que se ve—.
  const shalePorPeriodo = useMemo(() => {
    const shale = clavesDe(estado.fluido, 'shale');
    const todo = clavesDe(estado.fluido, 'todo');
    const sumar = (grupo: number, lista: typeof shale) => {
      let total = 0;
      datos.fechas.forEach((_, indice) => {
        if (grupos.grupoDe[indice] !== grupo) return;
        for (const clave of lista) total += datos.total[clave]?.[indice] ?? 0;
      });
      return total;
    };
    return armadas.etiquetas.map((etiqueta) => {
      const grupo = grupos.etiquetas.indexOf(etiqueta);
      if (grupo < 0) return null;
      const denominador = sumar(grupo, todo);
      return denominador > 0 ? sumar(grupo, shale) / denominador : null;
    });
  }, [armadas.etiquetas, datos.fechas, datos.total, estado.fluido, grupos]);

  const colores = useMemo(() => {
    const mapa: Record<string, string> = {};
    armadas.series.forEach((serie, indice) => {
      mapa[serie.nombre] = cohortes
        ? (COLOR_COHORTE[serie.nombre] ?? COLOR_OTROS)
        : serie.nombre === NOMBRE_OTROS
          ? COLOR_OTROS
          : RAMPA[indice % RAMPA.length];
    });
    return mapa;
  }, [armadas.series, cohortes]);

  const rankingCompleto = useMemo(() => {
    // El ranking del pipeline trae también las áreas que produjeron en la
    // ventana previa y ya no producen: están para que los agregados del árbol
    // territorial cierren contra la serie de la compañía. Acá arriba el corte
    // son los últimos doce meses, así que las filas en cero no entran: el
    // encabezado de la página cuenta 52 concesiones y la tabla tiene que contar
    // las mismas.
    const base = (datos.rankings[estado.dimension] ?? []).filter((fila) => fila.actual_bd > 0);
    if (!dentroDe) return base;
    const fichas = datos.meta?.yacimiento ?? {};
    return base.filter((fila) => fichas[fila.nombre]?.concesion === dentroDe);
  }, [datos.rankings, datos.meta, estado.dimension, dentroDe]);
  const medida = medidaDelRanking(estado.fluido, estado.recurso);
  const rankingVista = useMemo(() => {
    if (medida.clave) {
      return [...rankingCompleto]
        .map((fila) => ({
          nombre: fila.nombre,
          valor: Number(fila[medida.clave!] ?? 0),
          delta: fila.delta_bd,
        }))
        .filter((fila) => fila.valor > 0)
        .sort((a, b) => b.valor - a.valor);
    }
    return rankingDeSeries(miembros ?? [], claves, datos.dias);
  }, [medida.clave, rankingCompleto, miembros, claves, datos.dias]);

  // Los activos que se comparan: los elegidos, o el podio del ranking mientras
  // nadie elija. El candidato tiene que existir como serie propia, así que
  // "Otros" queda afuera: no es un activo.
  const candidatos = useMemo(
    () => rankingVista.map((fila) => fila.nombre).filter((nombre) => nombre !== NOMBRE_OTROS),
    [rankingVista],
  );
  const elegidos = comparados.length ? comparados : candidatos.slice(0, MAX_COMPARADOS);
  const curvas = useMemo(() => {
    if (vista !== 'curvas' || !miembros) return [];
    return elegidos
      .map((nombre) => miembros.find((miembro) => miembro.nombre === nombre))
      .filter((miembro): miembro is MiembroYPF => Boolean(miembro))
      .map((miembro) => curvaDesdeDebut(miembro, claves, datos.dias, datos.fechas));
  }, [vista, miembros, elegidos, claves, datos.dias, datos.fechas]);

  const unidad = unidadDe(estado.fluido, estado.metrica);
  const señales = useMemo(() => {
    const base = calcularSenales(datos, estado.dimension);
    // El quiebre necesita las series mensuales, que llegan después que la
    // página: mientras no estén, la sección muestra las otras cuatro señales y
    // esta aparece cuando se puede calcular. Nunca un placeholder.
    const quiebre = miembros
      ? quiebreReciente(
          miembros,
          datos.fechas,
          datos.dias,
          claves,
          DIMENSIONES.find((item) => item.id === estado.dimension)!.etiqueta.toLowerCase(),
          new Set(traspasadas.keys()),
        )
      : null;
    return quiebre ? [...base, quiebre] : base;
  }, [datos, estado.dimension, miembros, claves, traspasadas]);

  const ultimoIndice = armadas.etiquetas.length - 1;
  const valoresUltimos = useMemo(() => {
    const salida: Record<string, number> = {};
    if (ultimoIndice < 0) return salida;
    const dias = armadas.dias[ultimoIndice] || 1;
    for (const serie of armadas.series) {
      salida[serie.nombre] = medir(serie.valores[ultimoIndice] ?? 0, dias, estado.metrica);
    }
    return salida;
  }, [armadas, ultimoIndice, estado.metrica]);

  const totalUltimo = Object.values(valoresUltimos).reduce((suma, valor) => suma + valor, 0);

  const activo: ActivoSeleccionado | null = useMemo(() => {
    if (!seleccionado) return null;
    const miembro = miembros?.find((item) => item.nombre === seleccionado);
    const enlacesDimension = enlaces.entidades[estado.dimension] ?? {};
    const ubicable = estado.dimension === 'concesion' || estado.dimension === 'yacimiento';
    return {
      nombre: seleccionado,
      dimension: estado.dimension,
      ficha: datos.meta[estado.dimension]?.[seleccionado] ?? null,
      fila: rankingCompleto.find((fila) => fila.nombre === seleccionado) ?? null,
      serie: miembro ? serieMensualDe(miembro, claves, datos.dias) : [],
      enlaceEntidad: enlacesDimension[seleccionado]
        ? `/ypf-project/red?entidad=${encodeURIComponent(enlacesDimension[seleccionado])}`
        : null,
      enlaceMapa:
        ubicable && seleccionado !== NOMBRE_OTROS
          ? `/ypf-project?zona=${encodeURIComponent(seleccionado)}#activo`
          : null,
      // La economía existe por yacimiento y solo donde hay pozos ajustados.
      // Para una concesión o una provincia no se muestra nada: sumar medianas
      // de pozo de yacimientos distintos no da la mediana de nada.
      economia:
        estado.dimension === 'yacimiento'
          ? (economia.porYacimiento[normalizarNombre(seleccionado)] ?? null)
          : null,
      traspaso: traspasadas.get(seleccionado) ?? null,
    };
  }, [
    seleccionado,
    miembros,
    enlaces.entidades,
    estado.dimension,
    datos.meta,
    datos.dias,
    rankingCompleto,
    claves,
    economia.porYacimiento,
    traspasadas,
  ]);

  const etiquetaDimension = DIMENSIONES.find((item) => item.id === estado.dimension)!;
  const cargando = dimensiones === null;

  return (
    <>
      <section ref={seccion} aria-labelledby="analisis" className="mt-10 scroll-mt-6">
        <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
          <div>
            <h2 id="analisis" className="text-xl font-semibold text-texto">
              Producción operada por {etiquetaDimension.etiqueta.toLowerCase()}
              {dentroDe ? (
                <span className="text-texto-suave"> de {dentroDe}</span>
              ) : null}
            </h2>
            <p className="mt-1 text-xs text-texto-tenue">
              Evolución temporal · {filtros.desde}–{filtros.hasta} · {datos.cobertura.desde} a{' '}
              {datos.cobertura.hasta} disponibles
            </p>
            {/* La marca del drill-down. Va acá y no adentro de los filtros
                porque no es un filtro más: cambia de qué universo habla toda la
                sección, y tiene que poder deshacerse de un clic. */}
            {dentroDe ? (
              <p className="mt-2">
                <button
                  type="button"
                  onClick={() => setFoco(null)}
                  className="inline-flex items-center gap-1.5 rounded-full border border-azul-claro/50 bg-superficie-alta px-2.5 py-1 text-[0.7rem] text-azul-claro transition-colors hover:border-azul-claro focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-azul-claro"
                >
                  Dentro de {dentroDe}
                  <span aria-hidden>✕</span>
                  <span className="sr-only">Volver a todos los yacimientos</span>
                </button>
              </p>
            ) : null}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div
              role="tablist"
              aria-label="Vista del análisis"
              className="flex rounded-md border border-borde p-0.5"
            >
              {VISTAS.map((item) => (
                <button
                  key={item.id}
                  role="tab"
                  type="button"
                  aria-selected={vista === item.id && modo === 'grafico'}
                  title={item.ayuda}
                  onClick={() => {
                    setVista(item.id);
                    setModo('grafico');
                  }}
                  className={`rounded px-2.5 py-1 text-xs transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-azul-claro ${
                    vista === item.id && modo === 'grafico'
                      ? 'bg-superficie-alta text-azul-claro'
                      : 'text-texto-tenue hover:text-texto-suave'
                  }`}
                >
                  {item.etiqueta}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => setModo(modo === 'tabla' ? 'grafico' : 'tabla')}
              aria-pressed={modo === 'tabla'}
              className={`rounded-md border px-2.5 py-1 text-xs transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-azul-claro ${
                modo === 'tabla'
                  ? 'border-azul-claro bg-superficie-alta text-azul-claro'
                  : 'border-borde text-texto-tenue hover:border-azul-claro hover:text-azul-claro'
              }`}
            >
              Tabla
            </button>
          </div>
        </div>

        <div className="mt-4">
          <Controles
            estado={estado}
            alCambiar={cambiar}
            avanzados={avanzados}
            alternarAvanzados={() => setAvanzados((previo) => !previo)}
            anios={{ desde: filtros.desde, hasta: filtros.hasta }}
            alCambiarAnios={(cambio) => aplicar(cambio)}
            alRestablecer={
              (Object.keys(INICIAL) as (keyof EstadoControles)[]).some(
                (clave) => estado[clave] !== INICIAL[clave],
              ) || dentroDe
                ? () => {
                    setEstado(INICIAL);
                    setFoco(null);
                    setSeleccionado(null);
                  }
                : undefined
            }
            extra={
              modo === 'grafico' && vista !== 'ranking' && vista !== 'curvas' && ultimoIndice >= 0 ? (
                <p className="text-right text-xs text-texto-tenue">
                  <span className="font-mono text-[0.62rem] uppercase tracking-[0.12em]">
                    {armadas.etiquetas[ultimoIndice]}
                    {armadas.completo[ultimoIndice] ? '' : ' · parcial'}
                  </span>
                  <br />
                  <span className="tabular text-sm text-texto">
                    {vista === 'participacion' ? '100%' : `${fmt.entero(totalUltimo)} ${unidad}`}
                  </span>
                </p>
              ) : null
            }
          />
        </div>

        <div
          className={`mt-4 grid gap-4 ${activo ? 'lg:grid-cols-[minmax(0,1fr)_20rem]' : 'grid-cols-1'}`}
        >
          <div className="marquesina rounded-lg border border-borde bg-superficie p-4">
            {cargando ? (
              <>
                <p className="mb-3 font-mono text-[0.68rem] uppercase tracking-[0.14em] text-texto-tenue">
                  Bajando las series por {etiquetaDimension.etiqueta.toLowerCase()}…
                </p>
                <Esqueleto alto={400} />
              </>
            ) : modo === 'tabla' ? (
              <TablaProduccion
                dimension={estado.dimension}
                ranking={rankingCompleto}
                meta={datos.meta[estado.dimension]}
                seleccionado={seleccionado}
                alSeleccionar={setSeleccionado}
                traspasadas={new Set(traspasadas.keys())}
              />
            ) : !armadas.series.length ? (
              <div className="flex min-h-[280px] flex-col items-center justify-center gap-2 rounded-md border border-dashed border-borde px-6 text-center">
                <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
                  Sin producción para este cruce
                </p>
                <p className="max-w-sm text-xs leading-relaxed text-texto-suave">
                  No hay {etiquetaDimension.plural}
                  {dentroDe ? ` de ${dentroDe}` : ''} con producción de este tipo en el rango
                  elegido. Probá con otro tipo de roca o ampliá los años.
                </p>
                {dentroDe ? (
                  <button
                    type="button"
                    onClick={() => setFoco(null)}
                    className="text-xs text-azul-claro underline-offset-2 hover:underline"
                  >
                    Salir de {dentroDe}
                  </button>
                ) : null}
              </div>
            ) : (
              <>
                {vista === 'curvas' ? (
                  /* El selector de comparación. Es una lista de chips y no un
                     multiselect: con tres activos como tope, ver los candidatos
                     y lo elegido en el mismo lugar cuesta menos que abrir un
                     menú, elegir y cerrarlo. */
                  <div className="mb-3">
                    <p className="font-mono text-[0.62rem] uppercase tracking-[0.14em] text-texto-tenue">
                      Comparar hasta {MAX_COMPARADOS} {etiquetaDimension.plural}
                    </p>
                    <ul className="mt-1.5 flex flex-wrap gap-1.5">
                      {candidatos.slice(0, 14).map((nombre) => {
                        const puesto = elegidos.includes(nombre);
                        const lleno = !puesto && elegidos.length >= MAX_COMPARADOS;
                        return (
                          <li key={nombre}>
                            <button
                              type="button"
                              aria-pressed={puesto}
                              disabled={lleno}
                              onClick={() =>
                                setComparados(
                                  puesto
                                    ? elegidos.filter((item) => item !== nombre)
                                    : [...elegidos, nombre],
                                )
                              }
                              className={`rounded-md border px-2 py-1 text-[0.72rem] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-azul-claro ${
                                puesto
                                  ? 'border-azul-claro bg-superficie-alta text-texto'
                                  : lleno
                                    ? 'cursor-not-allowed border-borde/60 text-texto-tenue/60'
                                    : 'border-borde text-texto-suave hover:border-borde-vivo hover:text-texto'
                              }`}
                            >
                              <span className="max-w-[11rem] truncate">{nombre}</span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ) : vista !== 'ranking' ? (
                  <div className="mb-3">
                    <Leyenda
                      series={armadas.series}
                      colores={colores}
                      seleccionado={seleccionado}
                      alSeleccionar={setSeleccionado}
                      valores={valoresUltimos}
                      unidad={unidad}
                      interactiva={!cohortes}
                    />
                    {cohortes ? (
                      <p className="mt-2 text-[0.7rem] leading-relaxed text-texto-tenue">
                        Cada yacimiento entra en la cohorte del año en que empezó a producir, y las
                        cohortes se arman sobre los 274 yacimientos del archivo, no sobre los que
                        tienen serie propia en el gráfico. De lo que ya producía en el primer mes
                        de la serie no sabemos cuándo arrancó: se lo nombra por lo que se sabe. La
                        dimensión elegida arriba no cambia este corte.
                      </p>
                    ) : armadas.agrupados > 0 ? (
                      <p className="mt-2 text-[0.7rem] text-texto-tenue">
                        &ldquo;{NOMBRE_OTROS}&rdquo; junta {armadas.agrupados}{' '}
                        {etiquetaDimension.plural} más
                        {armadas.incluyeResto ? ' y la cola que el pipeline ya agrupaba' : ''}.{' '}
                        <button
                          type="button"
                          onClick={() => cambiar({ top: 0 })}
                          className="text-azul-claro underline-offset-2 hover:underline"
                        >
                          Ver todas
                        </button>
                      </p>
                    ) : estado.top === 0 ? (
                      <p className="mt-2 text-[0.7rem] text-texto-tenue">
                        Todas las series a la vista.{' '}
                        <button
                          type="button"
                          onClick={() => cambiar({ top: 5 })}
                          className="text-azul-claro underline-offset-2 hover:underline"
                        >
                          Volver al top 5
                        </button>
                      </p>
                    ) : null}
                  </div>
                ) : null}

                <Grafico
                  vista={vista}
                  datos={{ armadas, shalePorPeriodo, colores }}
                  metrica={estado.metrica}
                  unidad={unidad}
                  periodo={estado.periodo}
                  ranking={rankingVista}
                  alcanceRanking={medida.alcance}
                  curvas={curvas}
                  seleccionado={seleccionado}
                  // Una cohorte no es un activo y no tiene ficha: en esa vista
                  // el gráfico se mira, no se selecciona.
                  alSeleccionar={cohortes ? () => {} : setSeleccionado}
                />

                <p className="mt-3 text-[0.7rem] leading-relaxed text-texto-tenue">
                  {datos.nota}
                  {estado.dimension === 'localidad' ? ` ${datos.nota_localidad}` : ''}
                  {armadas.hayParciales
                    ? ' El último período está incompleto: la fuente todavía no publicó todos sus meses.'
                    : ''}
                </p>
              </>
            )}
          </div>

          {activo ? (
            <>
              {/* En pantalla angosta la ficha sube desde abajo; en ancha es la
                  columna de la derecha y el gráfico se angosta, no se tapa. */}
              <div
                className="fixed inset-0 z-30 bg-fondo/70 lg:hidden"
                onClick={() => setSeleccionado(null)}
                aria-hidden
              />
              <div className="hoja fixed inset-x-0 bottom-0 z-40 p-3 lg:static lg:z-auto lg:p-0">
                <PanelActivo
                  activo={activo}
                  unidad={unidad}
                  alCerrar={() => setSeleccionado(null)}
                  supuestos={economia.supuestos}
                  alAbrirYacimientos={
                    // El drill-down desde la ficha: de la concesión a los
                    // yacimientos que tiene adentro, sin salir de la pantalla.
                    estado.dimension === 'concesion' && (activo.ficha?.yacimientos ?? 0) > 1
                      ? () => {
                          const nombre = activo.nombre;
                          setEstado((previo) => ({ ...previo, dimension: 'yacimiento' }));
                          setFoco(nombre);
                          setSeleccionado(null);
                        }
                      : undefined
                  }
                />
              </div>
            </>
          ) : null}
        </div>
      </section>

      <Senales senales={señales} />
    </>
  );
}
