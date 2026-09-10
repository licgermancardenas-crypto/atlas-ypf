import { Shell } from '@/components/Shell';
import { IlustracionSegmento } from '@/components/segmentos/Ilustraciones';
import { ModuloSegmentos } from '@/components/segmentos/ModuloSegmentos';
import { QUE_HACE } from '@/components/segmentos/negocios';
import { Dato, Franja } from '@/components/ui';
import { fmt, type Economia, type Financieros } from '@/lib/data';
import type { Segmentos } from '@/lib/libro';
import { cargar } from '@/lib/server-data';

// El módulo de segmentos.
//
// Tiene página propia y no una pestaña adentro del libro por una razón: es el
// único lugar del proyecto donde la compañía se ve como lo que es —tres
// negocios distintos con un mismo dueño— y esa lectura no se hace con una
// tabla, se hace con la cadena. El libro sigue teniendo la grilla para el que
// quiera los números crudos.

export const metadata = {
  title: 'Segmentos — ATLAS-YPF',
  description:
    'La cadena de valor de YPF con los números adentro: qué produce Upstream, cuánto le vende a la propia compañía, qué factura Downstream al mercado y qué margen deja cada negocio.',
};

const ORDEN_FICHAS = [
  'Upstream',
  'Midstream y Downstream',
  'GNL y gas integrado',
  'Nuevas energías',
];

export default async function ModuloSegmentosPagina() {
  const [segmentos, financieros, economia] = await Promise.all([
    cargar<Segmentos>('segmentos_web.json'),
    cargar<Financieros>('financials_ypf.json'),
    cargar<Economia>('well_economics.json'),
  ]);

  const ultimo = segmentos.trimestres.length - 1;
  const valor = (concepto: string, segmento: string): number | null =>
    segmentos.conceptos[concepto]?.filas.find((fila) => fila.segmento === segmento)?.trimestral[
      ultimo
    ] ?? null;

  const ingresosUpstream = valor('ingresos_totales', 'Upstream');
  const interUpstream = valor('ingresos_intersegmento', 'Upstream');
  const capexUpstream = valor('capex_ppe', 'Upstream');
  const capexTotal = valor('capex_ppe', 'Total');
  const operativoTotal = valor('resultado_operativo', 'Total');
  const operativoUpstream = valor('resultado_operativo', 'Upstream');
  const externosDownstream = valor('ingresos_externos', 'Midstream y Downstream');
  const totalIngresos = valor('ingresos_totales', 'Total');

  return (
    <Shell
      actualizado={financieros.generado.slice(0, 10)}
      operadores={economia.por_operador.map((fila) => fila.operador!).filter(Boolean)}
      modulo="segmentos"
    >
      <main className="mx-auto max-w-6xl px-6 py-12">
        <Franja className="w-24" />
        <h1 className="mt-5 text-3xl font-bold sm:text-4xl">Segmentos</h1>
        <p className="mt-3 max-w-3xl leading-relaxed text-texto-suave">
          YPF no es una empresa: son tres. Una saca petróleo y gas de la roca, otra lo refina y lo
          vende en la esquina, y una tercera está construyendo un negocio de gas que todavía casi no
          factura. El consolidado los promedia hasta que no se distingue ninguno, y por eso un
          trimestre récord no dice, por sí solo, de dónde vino.
        </p>

        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Dato
            etiqueta="Upstream le vende a la propia YPF"
            valor={
              ingresosUpstream && interUpstream
                ? fmt.porcentaje(interUpstream / ingresosUpstream, 0)
                : '—'
            }
            detalle={`de sus ${fmt.musd(ingresosUpstream)} de ingresos`}
            tono="marca"
          />
          <Dato
            etiqueta="Downstream factura al mercado"
            valor={
              externosDownstream && totalIngresos
                ? fmt.porcentaje(externosDownstream / totalIngresos, 0)
                : '—'
            }
            detalle="de todo lo que cobra la compañía"
            tono="crudo"
          />
          <Dato
            etiqueta="Capex que se lleva Upstream"
            valor={capexUpstream && capexTotal ? fmt.porcentaje(capexUpstream / capexTotal, 0) : '—'}
            detalle={`${fmt.musd(capexUpstream)} en el trimestre`}
          />
          <Dato
            etiqueta="Resultado operativo de Upstream"
            valor={
              operativoUpstream && operativoTotal
                ? fmt.porcentaje(operativoUpstream / operativoTotal, 0)
                : '—'
            }
            detalle="del resultado operativo consolidado"
            tono="alza"
          />
        </div>

        <div className="mt-10">
          <ModuloSegmentos segmentos={segmentos} />
        </div>

        {/* ------------------------------------------------------------- */}
        {/* Los negocios, para leer sin tocar nada                          */}
        {/* ------------------------------------------------------------- */}
        <h2 className="mt-14 text-xl font-semibold text-texto">Qué hace cada negocio</h2>
        <div className="mt-5 grid gap-5 md:grid-cols-2">
          {ORDEN_FICHAS.filter((segmento) => QUE_HACE[segmento]).map((segmento) => {
            const ficha = QUE_HACE[segmento];
            return (
              <div
                key={segmento}
                className="marquesina rounded-lg border border-borde bg-superficie p-5"
              >
                <IlustracionSegmento segmento={segmento} className="h-28 w-full" />
                <h3 className="mt-3 text-sm font-medium text-texto">{segmento}</h3>
                <p className="text-xs text-texto-suave">{ficha.titulo}</p>
                <p className="mt-3 text-xs leading-relaxed text-texto-suave">{ficha.texto}</p>
                {ficha.datos.length ? (
                  <ul className="mt-3 space-y-1.5 border-t border-borde/60 pt-3 text-[0.7rem] leading-relaxed text-texto-tenue">
                    {ficha.datos.map((dato) => (
                      <li key={dato}>· {dato}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            );
          })}
        </div>

        <div className="mt-10 grid gap-6 lg:grid-cols-2">
          <div className="marquesina rounded-lg border border-borde bg-superficie p-5">
            <h3 className="text-sm font-medium text-texto-suave">Cómo leer estos números</h3>
            <ul className="mt-4 space-y-2 text-xs leading-relaxed text-texto-suave">
              <li>
                Los ingresos de un segmento incluyen lo que le vende a los otros. Por eso la suma de
                los segmentos es mayor que el ingreso consolidado, y la diferencia —los ajustes de
                consolidación— es exactamente lo que la compañía se vende a sí misma.
              </li>
              <li>
                El precio al que Upstream le vende el crudo a Downstream lo fija la propia compañía.
                Mueve el margen de un segmento contra el otro sin cambiar el consolidado: mirar el
                margen de un solo negocio, aislado, dice menos de lo que parece.
              </li>
              <li>
                La apertura cambió dos veces desde 2020. Cada trimestre se muestra con la que la
                compañía usó para ese período. El 4T22 no tiene apertura publicada comparable: es el
                trimestre en el que cambió.
              </li>
            </ul>
          </div>

          <div className="marquesina rounded-lg border border-borde bg-superficie p-5">
            <h3 className="text-sm font-medium text-texto-suave">De dónde sale</h3>
            <p className="mt-4 text-xs leading-relaxed text-texto-suave">
              De la nota de segmentos de cada 6-K y de cada 20-F: la misma que audita el estado de
              resultados. El total de la nota da los ingresos del estado, y las partes dan el total
              en los treinta trimestres publicados; los dos controles corren en cada actualización
              del pipeline.
            </p>
            <p className="mt-3 text-xs leading-relaxed text-texto-suave">
              La compañía la publica acumulada desde enero, así que el trimestre sale por
              diferencia. Las ilustraciones son esquemas propios: no hay fotos de plantas ajenas.
            </p>
            <a
              href="/ypf-project/libro?vista=segmentos"
              className="mt-4 inline-block rounded-md border border-borde px-3 py-1.5 text-xs text-texto-suave transition-colors hover:border-azul-claro hover:text-azul-claro"
            >
              Ver la grilla con todos los números
            </a>
          </div>
        </div>
      </main>
    </Shell>
  );
}
