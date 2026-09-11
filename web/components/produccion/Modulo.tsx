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

import { useCallback, useEffect, useMemo, useState } from 'react';

import { fmt } from '@/lib/data';
import {
  agrupar,
  armarSeries,
  clavesDe,
  COLOR_OTROS,
  DIMENSIONES,
  medidaDelRanking,
  medir,
  NOMBRE_OTROS,
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
import { Controles, type EstadoControles } from './Controles';
import { Grafico, Leyenda } from './Grafico';
import { PanelActivo, type ActivoSeleccionado } from './PanelActivo';
import { Senales } from './Senales';
import { TablaProduccion } from './TablaProduccion';

const VISTAS: { id: IdVista; etiqueta: string; ayuda: string }[] = [
  { id: 'produccion', etiqueta: 'Producción', ayuda: 'Cuánto sale y de qué activo.' },
  { id: 'crecimiento', etiqueta: 'Crecimiento', ayuda: 'Variación contra el mismo período del año anterior.' },
  { id: 'participacion', etiqueta: 'Participación', ayuda: 'Quién le gana lugar a quién.' },
  { id: 'ranking', etiqueta: 'Ranking', ayuda: 'El último año, activo por activo.' },
];

export interface EnlacesActivo {
  /** id del grafo de entidades, por dimensión y nombre. Solo los que existen. */
  entidades: Record<string, Record<string, string>>;
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
} as const;

function leerDeUrl(): {
  estado: Partial<EstadoControles>;
  vista?: IdVista;
  modo?: 'grafico' | 'tabla';
  seleccionado?: string;
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

  return {
    estado,
    vista: VISTAS.some((item) => item.id === vista) ? (vista as IdVista) : undefined,
    modo: modo === 'tabla' ? 'tabla' : undefined,
    seleccionado: seleccionado ?? undefined,
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
}: {
  datos: ProduccionYPF;
  enlaces: EnlacesActivo;
}) {
  const { filtros, aplicar } = useFiltros();
  const [estado, setEstado] = useState<EstadoControles>(INICIAL);
  const [vista, setVista] = useState<IdVista>('produccion');
  const [modo, setModo] = useState<'grafico' | 'tabla'>('grafico');
  const [avanzados, setAvanzados] = useState(false);
  const [seleccionado, setSeleccionado] = useState<string | null>(null);
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

    const consulta = params.toString();
    window.history.replaceState(
      null,
      '',
      `${window.location.pathname}${consulta ? `?${consulta}` : ''}${window.location.hash}`,
    );
  }, [estado, vista, modo, seleccionado]);

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
    // seleccionado ya no existe en el nuevo corte.
    if (cambio.dimension) setSeleccionado(null);
  }, []);

  const miembros = dimensiones?.[estado.dimension]?.miembros;
  const claves = useMemo(
    () => clavesDe(estado.fluido, estado.recurso),
    [estado.fluido, estado.recurso],
  );
  const grupos = useMemo(
    () => agrupar(datos.fechas, datos.dias, estado.periodo),
    [datos.fechas, datos.dias, estado.periodo],
  );

  const armadas = useMemo(
    () =>
      armarSeries({
        miembros: miembros ?? [],
        claves,
        grupos,
        top: estado.top,
        desde: filtros.desde,
        hasta: filtros.hasta,
      }),
    [miembros, claves, grupos, estado.top, filtros.desde, filtros.hasta],
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
      mapa[serie.nombre] = serie.nombre === NOMBRE_OTROS ? COLOR_OTROS : RAMPA[indice % RAMPA.length];
    });
    return mapa;
  }, [armadas.series]);

  const rankingCompleto = datos.rankings[estado.dimension] ?? [];
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

  const unidad = unidadDe(estado.fluido, estado.metrica);
  const señales = useMemo(
    () => calcularSenales(datos, estado.dimension),
    [datos, estado.dimension],
  );

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
    };
  }, [seleccionado, miembros, enlaces.entidades, estado.dimension, datos.meta, datos.dias, rankingCompleto, claves]);

  const etiquetaDimension = DIMENSIONES.find((item) => item.id === estado.dimension)!;
  const cargando = dimensiones === null;

  return (
    <>
      <section aria-labelledby="analisis" className="mt-10">
        <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
          <div>
            <h2 id="analisis" className="text-xl font-semibold text-texto">
              Producción operada por {etiquetaDimension.etiqueta.toLowerCase()}
            </h2>
            <p className="mt-1 text-xs text-texto-tenue">
              Evolución temporal · {filtros.desde}–{filtros.hasta} · {datos.cobertura.desde} a{' '}
              {datos.cobertura.hasta} disponibles
            </p>
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
            extra={
              modo === 'grafico' && vista !== 'ranking' && ultimoIndice >= 0 ? (
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
              />
            ) : !armadas.series.length ? (
              <div className="flex min-h-[280px] flex-col items-center justify-center gap-2 rounded-md border border-dashed border-borde px-6 text-center">
                <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
                  Sin producción para este cruce
                </p>
                <p className="max-w-sm text-xs leading-relaxed text-texto-suave">
                  No hay {etiquetaDimension.plural} con producción de este tipo en el rango elegido.
                  Probá con otro tipo de roca o ampliá los años.
                </p>
              </div>
            ) : (
              <>
                {vista !== 'ranking' ? (
                  <div className="mb-3">
                    <Leyenda
                      series={armadas.series}
                      colores={colores}
                      seleccionado={seleccionado}
                      alSeleccionar={setSeleccionado}
                      valores={valoresUltimos}
                      unidad={unidad}
                    />
                    {armadas.agrupados > 0 ? (
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
                  seleccionado={seleccionado}
                  alSeleccionar={setSeleccionado}
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
              <div className="fixed inset-x-0 bottom-0 z-40 p-3 lg:static lg:z-auto lg:p-0">
                <PanelActivo
                  activo={activo}
                  unidad={unidad}
                  alCerrar={() => setSeleccionado(null)}
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
