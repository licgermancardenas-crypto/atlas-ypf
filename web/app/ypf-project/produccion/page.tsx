import { EscenaUpstream } from '@/components/ilustraciones/escenas';
import { LeyendaMapa, Mapa } from '@/components/ilustraciones/mapa';
import { ExploradorYPF, type ProduccionYPF } from '@/components/ProduccionYPF';
import { Shell } from '@/components/Shell';
import { Dato, Franja } from '@/components/ui';
import { fmt, type Economia, type Financieros } from '@/lib/data';
import { cargar } from '@/lib/server-data';

// El módulo de la compañía sola.
//
// Todo lo demás del sitio mira a YPF contra algo: contra el país, contra sus
// comparables, contra su propio balance. Acá no hay contra nadie. Es qué
// produce, de dónde sale y cómo cambia según la lupa: cinco dimensiones —cuenca,
// provincia, concesión, yacimiento y el pueblo más cercano— y tres escalas de
// tiempo, que no son un adorno: en el mes se ve el ruido operativo, en el
// trimestre se ve lo que la compañía reporta y en el año se ve la tendencia.
//
// La aclaración que gobierna todo el módulo está arriba de todo y no al pie:
// esta producción es bruta operada. Es lo que sale de las áreas que YPF opera,
// socios incluidos, y por eso es mayor que la que consolida en su balance. Un
// lector que compare este número con el del estado de resultados sin saberlo se
// va con una conclusión equivocada, y evitar eso vale una línea en el encabezado.

export const metadata = {
  title: 'Lo que produce YPF — ATLAS-YPF',
  description:
    'Producción de YPF por cuenca, provincia, concesión, yacimiento y localidad, por mes, trimestre y año, separando convencional, shale y tight.',
};

export default async function ModuloProduccion() {
  const [produccion, financieros, economia] = await Promise.all([
    cargar<ProduccionYPF>('ypf_produccion.json'),
    cargar<Financieros>('financials_ypf.json'),
    cargar<Economia>('well_economics.json'),
  ]);

  const { resumen, cobertura } = produccion;
  const totalBoed = resumen.petroleo_bd + resumen.gas_boed;
  const shale = totalBoed ? resumen.shale_bd / totalBoed : null;
  const mejorConcesion = produccion.rankings.concesion?.[0];
  const mejorLocalidad = produccion.rankings.localidad?.[0];

  return (
    <Shell
      actualizado={financieros.generado.slice(0, 10)}
      operadores={economia.por_operador.map((fila) => fila.operador!).filter(Boolean)}
      modulo="produccion"
    >
      <main className="mx-auto max-w-6xl px-6 py-12">
        <div className="flex items-start justify-between gap-10">
          <div>
            <Franja className="w-24" />
            <h1 className="mt-5 text-3xl font-bold sm:text-4xl">Lo que produce YPF</h1>
            <p className="mt-3 max-w-3xl leading-relaxed text-texto-suave">
              Solo la compañía, sin comparaciones: cuánto petróleo y cuánto gas salen de sus áreas,
              abierto por cuenca, provincia, concesión, yacimiento y el pueblo más cercano, y medido
              por mes, por trimestre, por año o por día. Datos de {cobertura.desde} a{' '}
              {cobertura.hasta}, declarados área por área ante la Secretaría de Energía.
            </p>
            <p className="mt-3 max-w-3xl text-xs leading-relaxed text-texto-tenue">
              Es producción <span className="text-texto-suave">bruta operada</span>: todo lo que sale
              de las áreas que YPF opera, incluida la parte de sus socios. Es mayor que la que la
              compañía consolida en su balance, así que este número y el del estado de resultados no
              tienen por qué coincidir.
            </p>
          </div>
          <EscenaUpstream className="hidden h-32 w-56 shrink-0 lg:block" />
        </div>

        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Dato
            etiqueta="Petróleo · últimos 12 meses"
            valor={`${fmt.entero(resumen.petroleo_bd)} bbl/d`}
            detalle="promedio diario de los últimos doce meses"
            tono="crudo"
          />
          <Dato
            etiqueta="Gas · últimos 12 meses"
            valor={`${fmt.entero(resumen.gas_boed)} boe/d`}
            detalle={`${fmt.entero(totalBoed)} boe/d entre los dos`}
            tono="marca"
          />
          <Dato
            etiqueta="Shale sobre el total"
            valor={fmt.porcentaje(shale, 0)}
            detalle={`convencional ${fmt.entero(resumen.convencional_bd)} boe/d · tight ${fmt.entero(
              resumen.tight_bd,
            )} boe/d`}
            tono="alza"
          />
          <Dato
            etiqueta="Dónde"
            valor={`${resumen.concesiones} concesiones`}
            detalle={`${resumen.yacimientos} yacimientos, ${resumen.cuencas} cuencas, ${resumen.provincias} provincias`}
          />
        </div>

        <div className="mt-8">
          <ExploradorYPF datos={produccion} />
        </div>

        {/* ------------------------------------------------------------- */}
        {/* La misma producción, sobre el terreno                          */}
        {/* ------------------------------------------------------------- */}
        <h2 className="mt-14 text-xl font-semibold text-texto">Dónde están esas áreas</h2>
        <p className="mt-3 max-w-3xl text-sm leading-relaxed text-texto-suave">
          El gráfico dice cuánto sale de cada área; el mapa, dónde queda. Están marcadas las
          concesiones con YPF en el título —operadas por la compañía o con participación—, sobre la
          cuenca neuquina, que es de donde sale{' '}
          {fmt.porcentaje(
            produccion.rankings.cuenca?.find((fila) => fila.nombre === 'Neuquina')?.participacion ??
              null,
            0,
          )}{' '}
          de todo lo que produce.
        </p>
        <div className="marquesina mt-5 rounded-lg border border-borde bg-superficie p-5">
          <div className="grid items-start gap-8 lg:grid-cols-[26rem_minmax(0,1fr)]">
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
            <div>
              <LeyendaMapa
                capas={['areas_ypf', 'concesiones', 'ductos', 'gasoductos', 'rutas']}
                puntos={['pozos', 'refinerias']}
              />
              <ul className="mt-5 space-y-2 text-xs leading-relaxed text-texto-suave">
                <li>
                  La concesión que más produce es{' '}
                  <span className="text-texto">{mejorConcesion?.nombre}</span>, con{' '}
                  {fmt.entero(mejorConcesion?.actual_bd ?? 0)} boe/d de promedio en los últimos doce
                  meses: {fmt.porcentaje(mejorConcesion?.participacion ?? null, 0)} de todo lo que
                  produce la compañía.
                </li>
                <li>
                  Medido por pueblo más cercano, la producción se concentra alrededor de{' '}
                  <span className="text-texto">{mejorLocalidad?.nombre}</span>:{' '}
                  {fmt.porcentaje(mejorLocalidad?.participacion ?? null, 0)} del total. Es la escala
                  real del asunto —un pueblo de la meseta y las áreas que lo rodean— detrás de una
                  compañía que cotiza en Nueva York.
                </li>
                <li>
                  Fuera de la cuenca neuquina, YPF todavía produce en el Golfo San Jorge, en Cuyo y
                  en el Austral. Esas áreas no están en este mapa, que es de la cuenca, pero sí en
                  el gráfico: se ven eligiendo la dimensión cuenca o provincia.
                </li>
              </ul>
            </div>
          </div>
        </div>

        <div className="mt-10 grid gap-6 lg:grid-cols-2">
          <div className="marquesina rounded-lg border border-borde bg-superficie p-5">
            <h3 className="text-sm font-medium text-texto-suave">Sobre el tiempo</h3>
            <ul className="mt-4 space-y-2 text-xs leading-relaxed text-texto-suave">
              <li>
                La fuente es mensual. <span className="text-texto">No hay dato diario</span>: lo que
                el selector llama &ldquo;por día&rdquo; es el caudal promedio del período, que es el
                volumen dividido por los días que ese período tiene.
              </li>
              <li>
                Por eso el pipeline guarda volumen y no caudal. El volumen se suma para armar un
                trimestre o un año; promediar caudales de meses de distinta duración da un número
                que no es el de nadie.
              </li>
              <li>
                Un mes se mueve por cosas que no son la tendencia: una parada de planta, febrero,
                un pozo nuevo que entra el día 20. El trimestre es la unidad en la que la compañía
                reporta y el año es donde se ve si crece.
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
                acá, buscando el pueblo más cercano al centro de cada yacimiento. Es una referencia
                geográfica y no una jurisdicción; ninguna regalía se reparte así.
              </li>
              <li>
                Los yacimientos de fuera de la cuenca neuquina no tienen polígono en las capas del
                proyecto, así que quedan agrupados como tales en vez de mezclarse con los que sí
                están ubicados.
              </li>
            </ul>
          </div>
        </div>

        <p className="mt-8 text-xs leading-relaxed text-texto-tenue">
          Fuente: {produccion.fuente}. El mismo dato para todos los operadores —y el ranking del
          país— está en{' '}
          <a href="/ypf-project/operativo" className="text-azul-claro hover:underline">
            el módulo operativo
          </a>
          ; las series completas de este módulo, en{' '}
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
