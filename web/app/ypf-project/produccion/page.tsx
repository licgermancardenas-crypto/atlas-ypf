import { LeyendaMapa, Mapa } from '@/components/ilustraciones/mapa';
import { Kpis } from '@/components/produccion/Kpis';
import type { Reservas } from '@/components/Reservas';
import { ProveedorProduccion } from '@/components/produccion/contexto';
import {
  ModuloProduccion,
  type EconomiaPorActivo,
  type EnlacesActivo,
} from '@/components/produccion/Modulo';
import { SenalEjecutiva } from '@/components/produccion/SenalEjecutiva';
import { Territorio } from '@/components/produccion/Territorio';
import { Shell } from '@/components/Shell';
import { Franja } from '@/components/ui';
import { fmt, type Economia, type Financieros } from '@/lib/data';
import { normalizarNombre, type ProduccionYPF } from '@/lib/produccion';
import { cargar } from '@/lib/server-data';
import { armarTerritorio } from '@/lib/territorio';

// El módulo de la compañía sola.
//
// Todo lo demás del sitio mira a YPF contra algo: contra el país, contra sus
// comparables, contra su balance. Acá no hay contra nadie. Es qué produce, de
// dónde sale y cómo cambia según la lupa.
//
// La página está ordenada como se investiga, no como se archiva:
//
//   lectura      qué está pasando, en dos frases calculadas
//   indicadores  los cuatro números, con su variación y su forma
//   análisis     el gráfico, sus filtros y la ficha del activo
//   intelligence las señales que un analista sacaría de esos mismos datos
//   territorio   dónde queda todo eso
//
// Lo de arriba se pinta en el servidor y no espera a ninguna descarga; lo único
// que corre en el navegador es el bloque de análisis, que es lo que se toca.
//
// La aclaración que gobierna el módulo está en el encabezado y no al pie: esta
// producción es bruta operada. Es lo que sale de las áreas que YPF opera, socios
// incluidos, y por eso es mayor que la que consolida en su balance. Un lector
// que compare este número con el del estado de resultados sin saberlo se va con
// una conclusión equivocada.

export const metadata = {
  title: 'Producción — ATLAS-YPF',
  description:
    'Producción operada de YPF por cuenca, provincia, concesión, yacimiento y localidad, por mes, trimestre y año, separando convencional, shale y tight.',
};

interface NodoGrafo {
  id: string;
  type: string;
  label: string;
}

/** Los enlaces a la ficha de Relaciones, resueltos en el build.
 *
 *  Se comprueba que la entidad exista en el grafo antes de ofrecer el botón: un
 *  link que abre un panel vacío es peor que no tener el link. El padrón del
 *  grafo y las series de producción no siempre nombran igual al mismo activo,
 *  así que el cruce se hace normalizado. */
async function enlacesDeEntidades(datos: ProduccionYPF): Promise<EnlacesActivo> {
  const normalizar = (texto: string) =>
    texto
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/\s+/g, ' ')
      .trim()
      .toUpperCase();

  try {
    // El agregado y no el grafo completo: trae las mismas concesiones y
    // yacimientos sin los cinco mil pozos, que acá no sirven de nada. 126 KB
    // contra 2,5 MB por cada render.
    const grafo = await cargar<{ nodes: NodoGrafo[] }>('graph/entities_agregado.json');
    const porTipo: Record<string, Map<string, string>> = { concesion: new Map(), yacimiento: new Map() };
    for (const nodo of grafo.nodes) {
      const mapa = porTipo[nodo.type];
      if (mapa) mapa.set(normalizar(nodo.label), nodo.id);
    }

    const entidades: Record<string, Record<string, string>> = {};
    for (const dimension of ['concesion', 'yacimiento'] as const) {
      const mapa = porTipo[dimension];
      const encontrados: Record<string, string> = {};
      for (const fila of datos.rankings[dimension] ?? []) {
        const id = mapa.get(normalizar(fila.nombre));
        if (id) encontrados[fila.nombre] = id;
      }
      entidades[dimension] = encontrados;
    }
    return { entidades };
  } catch {
    // Sin grafo, la ficha del activo simplemente no ofrece ese botón.
    return { entidades: {} };
  }
}

/** La economía de pozo, indexada por nombre normalizado de yacimiento.
 *
 *  El pipeline la calcula donde hay al menos diez pozos con curva ajustada: 25
 *  yacimientos de los 111 que producen, que son la mayor parte del volumen no
 *  convencional. Los otros no llevan un número estimado ni un guion que parezca
 *  un error de carga: la ficha simplemente no muestra el bloque.
 *
 *  El cruce se hace normalizado porque el padrón de pozos escribe los nombres en
 *  mayúsculas y sin tildes, y el de producción no. */
function economiaPorYacimiento(economia: Economia): EconomiaPorActivo {
  const porYacimiento: EconomiaPorActivo['porYacimiento'] = {};
  for (const fila of economia.por_yacimiento ?? []) {
    if (fila.yacimiento) porYacimiento[normalizarNombre(fila.yacimiento)] = fila;
  }
  return {
    porYacimiento,
    supuestos: {
      capex_usd: Number(economia.supuestos.capex_usd ?? 0),
      opex_usd_bbl: Number(economia.supuestos.opex_usd_bbl ?? 0),
      diferencial_usd_bbl: Number(economia.supuestos.diferencial_usd_bbl ?? 0),
      wacc_anual: Number(economia.supuestos.wacc_anual ?? 0),
      brent_base: Number(economia.supuestos.brent_base ?? 0),
      advertencia: economia.advertencia,
    },
  };
}

/** La última declaración de reservas de YPF.
 *
 *  Es de la Secretaría de Energía y no del 20-F: son las comprobadas hasta el
 *  fin de la concesión vigente, que es otra definición y da otro número. Va
 *  igual porque contesta la pregunta que la producción sola no puede contestar
 *  —cuánto tiempo puede sostenerse este caudal— y porque el año de corte, dos
 *  atrás del último mes de producción, se declara al lado. */
function ultimaFilaDeYPF(reservas: Reservas) {
  const filas = (reservas.por_operador ?? []).filter((fila) => fila.operador === 'YPF');
  return filas.length ? filas[filas.length - 1] : null;
}

export default async function ModuloProduccionPagina() {
  const [produccion, financieros, economia, reservas] = await Promise.all([
    cargar<ProduccionYPF>('ypf_produccion.json'),
    cargar<Financieros>('financials_ypf.json'),
    cargar<Economia>('well_economics.json'),
    cargar<Reservas>('reserves.json'),
  ]);
  const enlaces = await enlacesDeEntidades(produccion);
  const economiaDeActivos = economiaPorYacimiento(economia);
  const reservasYPF = ultimaFilaDeYPF(reservas);

  const { resumen, cobertura } = produccion;
  const cuencas = produccion.rankings.cuenca ?? [];
  // El árbol se arma en el build: el navegador recibe la rama ya cruzada y no
  // vuelve a mezclar 52 concesiones con 111 yacimientos en cada render.
  const territorio = armarTerritorio(produccion);
  const neuquina = cuencas.find((fila) => fila.nombre === 'Neuquina');
  const mejorConcesion = produccion.rankings.concesion?.[0];
  const mejorLocalidad = produccion.rankings.localidad?.[0];

  return (
    <Shell
      actualizado={financieros.generado.slice(0, 10)}
      operadores={economia.por_operador.map((fila) => fila.operador!).filter(Boolean)}
      modulo="produccion"
    >
      <main className="mx-auto max-w-6xl px-6 py-10">
        {/* ------------------------------------------------------------- */}
        {/* Encabezado: qué es esta pantalla y de cuándo son los datos      */}
        {/* ------------------------------------------------------------- */}
        <header>
          <Franja className="w-20" />
          <h1 className="mt-4 font-mono text-[0.7rem] uppercase tracking-[0.22em] text-azul-claro">
            Producción
          </h1>
          <p className="mt-2 max-w-3xl text-2xl font-bold leading-tight sm:text-3xl">
            Producción operada de YPF
          </p>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-texto-suave">
            Evolución de petróleo, gas y shale por activo y por período. Es producción{' '}
            <span className="text-texto">bruta operada</span>: incluye la parte de los socios en las
            áreas que YPF opera, así que es mayor que la que consolida en su balance.
          </p>
          <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1 font-mono text-[0.66rem] uppercase tracking-[0.1em] text-texto-tenue">
            <li>Datos al {financieros.generado.slice(0, 10)}</li>
            <li>Fuente: Secretaría de Energía</li>
            <li>
              Cobertura: {cobertura.desde.slice(0, 4)}–{cobertura.hasta.slice(0, 4)} ·{' '}
              {cobertura.meses} meses
            </li>
          </ul>
        </header>

        <div className="mt-6">
          <SenalEjecutiva datos={produccion} />
        </div>

        <div className="mt-6">
          <Kpis datos={produccion} />
        </div>

        {/* El análisis y el territorio comparten un contexto: bajar por el
            mapa hasta una concesión y abrirla en el gráfico de arriba es un
            solo recorrido, no dos pantallas. */}
        <ProveedorProduccion>
          <ModuloProduccion
            datos={produccion}
            enlaces={enlaces}
            economia={economiaDeActivos}
          />

          {/* ------------------------------------------------------------- */}
          {/* Territorio                                                     */}
          {/* ------------------------------------------------------------- */}
          <section id="donde" aria-labelledby="titulo-donde" className="mt-14 scroll-mt-6">
            <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
              <h2 id="titulo-donde" className="text-xl font-semibold text-texto">
                Dónde produce YPF
              </h2>
              <p className="text-xs text-texto-tenue">
                {resumen.provincias} provincias · {resumen.cuencas} cuencas ·{' '}
                {resumen.concesiones} concesiones · {resumen.yacimientos} yacimientos
              </p>
            </div>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-texto-suave">
              La misma producción, mirada como territorio. Se baja un nivel por vez —provincia,
              cuenca, concesión, yacimiento— y desde cualquier activo se vuelve al gráfico de
              arriba con la ficha abierta.
            </p>

            <div className="mt-5 grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_23rem]">
              <Territorio
                raiz={territorio}
                nota="Cada nivel suma las concesiones que cuelgan de él, y una concesión que cruza el límite de una provincia o de una cuenca cuenta entera en la de mayor volumen: por eso las ramas cierran exactas contra el total de la compañía, pero un límite jurisdiccional puede correrse unos pocos boe/d."
              />

              <div className="space-y-4">
                <div className="marquesina rounded-lg border border-borde bg-superficie p-4">
                  <Mapa
                    className="w-full"
                    capas={[
                      'provincias',
                      'rios',
                      'cuenca',
                      'concesiones',
                      'areas_ypf',
                      'rutas',
                      'gasoductos',
                      'ductos',
                    ]}
                    foco="areas_ypf"
                    etiqueta="Mapa de la cuenca neuquina con las áreas concesionadas en las que participa YPF"
                  />
                  <div className="mt-4 border-t border-borde pt-4">
                    <LeyendaMapa
                      capas={['areas_ypf', 'concesiones', 'ductos', 'gasoductos']}
                      puntos={['pozos', 'refinerias']}
                    />
                  </div>
                  <p className="mt-3 border-t border-borde pt-3 text-[0.7rem] leading-relaxed text-texto-tenue">
                    El mapa es de la cuenca neuquina, de donde sale{' '}
                    {fmt.porcentaje(neuquina?.participacion ?? null, 0)} de la producción. El Golfo
                    San Jorge y el Austral no se dibujan acá, pero sí se exploran en el árbol de al
                    lado.
                  </p>
                </div>

                {reservasYPF ? (
                  <div className="marquesina rounded-lg border border-borde bg-superficie p-4">
                    <div className="flex items-baseline justify-between gap-3">
                      <h3 className="font-mono text-[0.66rem] uppercase tracking-[0.14em] text-texto-tenue">
                        Cuánto puede durar
                      </h3>
                      <span className="font-mono text-[0.62rem] text-texto-tenue">
                        {reservasYPF.anio}
                      </span>
                    </div>
                    <p className="tabular mt-3 text-2xl font-semibold leading-none text-texto">
                      {fmt.numero(reservasYPF.vida_reservas, 1)}{' '}
                      <span className="text-xs font-normal text-texto-suave">
                        años de vida de reservas
                      </span>
                    </p>
                    <ul className="mt-3 space-y-1 text-xs text-texto-suave">
                      <li className="flex items-baseline justify-between gap-3">
                        <span>Comprobadas</span>
                        <span className="tabular text-texto">
                          {fmt.entero(reservasYPF.comprobadas_mboe / 1000)} MMboe
                        </span>
                      </li>
                      <li className="flex items-baseline justify-between gap-3">
                        <span>No convencional</span>
                        <span className="tabular" style={{ color: 'var(--color-shale)' }}>
                          {fmt.porcentaje(reservasYPF.share_no_convencional, 0)}
                        </span>
                      </li>
                      <li className="flex items-baseline justify-between gap-3">
                        <span>Producción del año</span>
                        <span className="tabular text-texto">
                          {fmt.entero((reservasYPF.produccion_mboe ?? 0) / 1000)} MMboe
                        </span>
                      </li>
                    </ul>
                    <p className="mt-3 text-[0.7rem] leading-relaxed text-texto-tenue">
                      Reservas comprobadas hasta el fin de la concesión vigente, declaradas por el
                      operador a la Secretaría de Energía. No son las certificadas del 20-F, que se
                      calculan con otra definición y dan otro número, y el corte es{' '}
                      {reservasYPF.anio}: dos años antes que el último mes de producción de esta
                      pantalla. La fuente no las abre por concesión, así que este dato es de la
                      compañía entera y no baja al árbol de al lado.
                    </p>
                  </div>
                ) : null}

                <div className="marquesina rounded-lg border border-borde bg-superficie p-4">
                  <h3 className="font-mono text-[0.66rem] uppercase tracking-[0.14em] text-texto-tenue">
                    La escala real
                  </h3>
                  <ul className="mt-3 space-y-2 text-xs leading-relaxed text-texto-suave">
                    <li>
                      La concesión que más produce es{' '}
                      <span className="text-texto">{mejorConcesion?.nombre}</span>:{' '}
                      {fmt.entero(mejorConcesion?.actual_bd ?? 0)} boe/d,{' '}
                      {fmt.porcentaje(mejorConcesion?.participacion ?? null, 0)} de la compañía.
                    </li>
                    <li>
                      Medido por pueblo más cercano, la producción se concentra alrededor de{' '}
                      <span className="text-texto">{mejorLocalidad?.nombre}</span>:{' '}
                      {fmt.porcentaje(mejorLocalidad?.participacion ?? null, 0)} del total. Un
                      pueblo de la meseta detrás de una compañía que cotiza en Nueva York.
                    </li>
                    <li className="text-texto-tenue">{produccion.nota_localidad}</li>
                  </ul>
                </div>
              </div>
            </div>
          </section>
        </ProveedorProduccion>

        {/* ------------------------------------------------------------- */}
        {/* Método                                                          */}
        {/* ------------------------------------------------------------- */}
        <section aria-labelledby="metodo" className="mt-12">
          <h2 id="metodo" className="sr-only">
            Cómo leer estos datos
          </h2>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="marquesina rounded-lg border border-borde bg-superficie p-5">
              <h3 className="text-sm font-medium text-texto-suave">Sobre el tiempo</h3>
              <ul className="mt-4 space-y-2 text-xs leading-relaxed text-texto-suave">
                <li>
                  La fuente es mensual. <span className="text-texto">No hay dato diario</span>: lo
                  que el selector llama &ldquo;por día&rdquo; es el caudal promedio del período, que
                  es el volumen dividido por los días que ese período tiene.
                </li>
                <li>
                  Por eso el pipeline guarda volumen y no caudal. El volumen se suma para armar un
                  trimestre o un año; promediar caudales de meses de distinta duración da un número
                  que no es el de nadie.
                </li>
                <li>
                  El crecimiento se mide contra el mismo período del año anterior y no contra el
                  período previo: si no, la estacionalidad se lee como tendencia.
                </li>
              </ul>
            </div>

            <div className="marquesina rounded-lg border border-borde bg-superficie p-5">
              <h3 className="text-sm font-medium text-texto-suave">Sobre el espacio</h3>
              <ul className="mt-4 space-y-2 text-xs leading-relaxed text-texto-suave">
                <li>
                  Cuenca, provincia, concesión y yacimiento vienen declarados en la fuente. Una
                  concesión puede tener varios yacimientos, y por eso los dos rankings no coinciden.
                </li>
                <li>
                  La <span className="text-texto">localidad no viene en la fuente</span>: se asigna
                  buscando el pueblo más cercano al centro de cada yacimiento. Es una referencia
                  geográfica y no una jurisdicción; ninguna regalía se reparte así.
                </li>
                <li>
                  Los yacimientos de fuera de la cuenca neuquina no tienen polígono en las capas del
                  proyecto y quedan agrupados como tales, en vez de mezclarse con los ubicados.
                </li>
              </ul>
            </div>
          </div>
        </section>

        <p className="mt-8 text-xs leading-relaxed text-texto-tenue">
          Fuente: {produccion.fuente}. El mismo dato para todos los operadores —y el ranking del
          país— está en{' '}
          <a href="/ypf-project/operativo" className="text-azul-claro hover:underline">
            el módulo operativo
          </a>
          ; las series de este módulo, en{' '}
          <a href="/data/ypf_produccion.json" className="text-azul-claro hover:underline">
            ypf_produccion.json
          </a>{' '}
          y{' '}
          <a href="/data/ypf_dimensiones.json" className="text-azul-claro hover:underline">
            ypf_dimensiones.json
          </a>
          .
        </p>
      </main>
    </Shell>
  );
}
