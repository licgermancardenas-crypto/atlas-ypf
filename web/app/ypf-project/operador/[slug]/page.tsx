import Link from 'next/link';
import { notFound } from 'next/navigation';

import { OperadorProduccion, type PuntoOperador } from '@/components/OperadorProduccion';
import { Dato, Franja, Tabla } from '@/components/ui';
import { fmt, type CurvasDeclive, type Economia } from '@/lib/data';
import { aSlug, desdeSlug } from '@/lib/operadores';
import { cargar } from '@/lib/server-data';
import type { Reservas } from '@/components/Reservas';
import type { DimensionProduccion, ProduccionPais } from '@/components/ExploradorProduccion';

// La ficha de un operador: el drill-through del caso.
//
// La página principal compara a todos contra todos; esta contesta la pregunta
// que viene después de mirar una fila de una tabla: "¿y esta compañía cómo
// está?". Todo sale de datos que el pipeline ya produce —producción por
// concepto, reservas, economía de pozo, áreas—; lo único nuevo es juntarlos
// alrededor de un nombre.
//
// Se prerenderiza una por operador en el build. Son trece: no hay motivo para
// resolverlas en cada visita.

interface Concesion {
  nombre: string;
  operador: string;
  pozos: number;
  boe_acum_mboe: number;
  boe_por_pozo_mboe: number | null;
  npv_musd_mediano: number | null;
}

async function cargarConcesiones(): Promise<Concesion[]> {
  const coleccion = await cargar<{
    features: { properties: Concesion }[];
  }>('geo/concessions.geojson');
  return coleccion.features.map((f) => f.properties).filter((p) => p.pozos > 0);
}

async function cargarTodo() {
  const [pais, dimensiones, reservas, economia, declive, concesiones] = await Promise.all([
    cargar<ProduccionPais>('country_production.json'),
    cargar<{ dimensiones: Record<string, DimensionProduccion> }>('country_dimensions.json'),
    cargar<Reservas>('reserves.json'),
    cargar<Economia>('well_economics.json'),
    cargar<CurvasDeclive>('decline_type_curves.json'),
    cargarConcesiones(),
  ]);
  return { pais, dimensiones, reservas, economia, declive, concesiones };
}

/** Los operadores con ficha propia: los que aparecen en la serie de producción
 *  por empresa, que es la fuente que cubre a todos y no solo a los de Vaca
 *  Muerta. Se excluye "Otros", que es un agregado y no una compañía. */
export async function generateStaticParams() {
  const { dimensiones } = await cargarTodo();
  return (dimensiones.dimensiones.empresa?.miembros ?? [])
    .map((miembro) => miembro.nombre)
    .filter((nombre) => nombre !== 'Otros')
    .map((nombre) => ({ slug: aSlug(nombre) }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const { dimensiones } = await cargarTodo();
  const nombres = (dimensiones.dimensiones.empresa?.miembros ?? []).map((m) => m.nombre);
  const operador = desdeSlug(slug, nombres);
  return {
    title: operador ? `${operador} — ATLAS-YPF` : 'Operador — ATLAS-YPF',
    description: operador
      ? `Producción, reservas y economía de pozo de ${operador} en la Argentina.`
      : undefined,
  };
}

export default async function FichaOperador({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const { pais, dimensiones, reservas, economia, declive, concesiones } = await cargarTodo();

  const bloque = dimensiones.dimensiones.empresa;
  const nombres = (bloque?.miembros ?? []).map((m) => m.nombre);
  const operador = desdeSlug(slug, nombres);
  if (!operador || !bloque) notFound();

  const miembro = bloque.miembros.find((m) => m.nombre === operador)!;

  // La serie de petróleo por concepto. Se recorta a los últimos diez años: antes
  // de 2015 el shale es una línea pegada a cero y solo achata el resto.
  const serie: PuntoOperador[] = bloque.fechas
    .map((fecha, indice) => ({
      fecha,
      convencional: miembro.oil_convencional[indice] ?? 0,
      shale: miembro.oil_shale[indice] ?? 0,
      tight: miembro.oil_tight[indice] ?? 0,
    }))
    .filter((punto) => Number(punto.fecha.slice(0, 4)) >= 2015);

  const ultimo = serie[serie.length - 1];
  const haceUnAnio = serie[serie.length - 13];
  const totalUltimo = ultimo ? ultimo.convencional + ultimo.shale + ultimo.tight : 0;
  const totalPrevio = haceUnAnio
    ? haceUnAnio.convencional + haceUnAnio.shale + haceUnAnio.tight
    : 0;

  const enRanking = (pais.rankings.empresa ?? []).find((fila) => fila.nombre === operador);
  const suReserva = reservas.ranking_ultimo.find((fila) => fila.operador === operador);
  const suEconomia = economia.por_operador.find((fila) => fila.operador === operador);
  const suCurva = declive.por_operador.find((fila) => fila.operador === operador);

  const susAreas = concesiones
    .filter((area) => area.operador?.toUpperCase().includes(operador.split(' ')[0].toUpperCase()))
    .sort((a, b) => b.boe_acum_mboe - a.boe_acum_mboe)
    .slice(0, 10);

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <Link
        href="/ypf-project"
        className="font-mono text-xs tracking-[0.2em] text-azul-claro transition hover:opacity-80"
      >
        ← VOLVER AL CASO
      </Link>

      <Franja className="mt-8 w-24" />
      <h1 className="mt-5 text-3xl font-bold sm:text-4xl">{operador}</h1>
      <p className="mt-3 max-w-2xl leading-relaxed text-texto-suave">
        Producción, reservas y economía de pozo, con los mismos datos y los mismos criterios que el
        resto del caso. La producción es bruta operada: incluye la parte de los socios, así que es
        mayor que la que la compañía consolida en su balance.
      </p>

      <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Dato
          etiqueta={`Petróleo · ${ultimo?.fecha ?? '—'}`}
          valor={`${fmt.entero(totalUltimo)} bbl/d`}
          delta={totalPrevio ? totalUltimo / totalPrevio - 1 : null}
          deltaReferencia=" i.a."
          detalle={
            enRanking?.participacion
              ? `${fmt.porcentaje(enRanking.participacion, 1)} de la producción del país`
              : undefined
          }
          tono="marca"
        />
        <Dato
          etiqueta="Shale sobre su producción"
          valor={fmt.porcentaje(totalUltimo ? (ultimo?.shale ?? 0) / totalUltimo : null, 0)}
          detalle={`${fmt.entero(ultimo?.shale)} bbl/d de shale`}
          tono="alza"
        />
        <Dato
          etiqueta="Reservas comprobadas"
          valor={suReserva ? `${fmt.entero(suReserva.comprobadas_mboe)} Mboe` : '—'}
          detalle={
            suReserva?.share_no_convencional !== null && suReserva?.share_no_convencional !== undefined
              ? `${fmt.porcentaje(suReserva.share_no_convencional, 0)} no convencional`
              : 'sin dato en el informe de reservas'
          }
        />
        <Dato
          etiqueta="Vida de reservas"
          valor={suReserva?.vida_reservas ? `${fmt.numero(suReserva.vida_reservas, 1)} años` : '—'}
          detalle="al ritmo de producción del último año"
          tono={suReserva?.vida_reservas && suReserva.vida_reservas < 10 ? 'baja' : 'neutro'}
        />
      </div>

      <section className="mt-10 rounded-lg border border-borde bg-superficie p-5">
        <h2 className="text-sm font-medium text-texto-suave">
          Producción de petróleo por tipo de recurso
        </h2>
        <div className="mt-4">
          <OperadorProduccion serie={serie} unidad="bbl/d" />
        </div>
        <p className="mt-3 text-xs leading-relaxed text-texto-tenue">
          El bloque gris es el convencional. Cuando se achica mientras el total se sostiene, la
          compañía no está creciendo: está reemplazando producción vieja por shale.
        </p>
      </section>

      {suEconomia || suCurva ? (
        <section className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Dato
            etiqueta="NPV mediano por pozo"
            valor={suEconomia ? `US$ ${fmt.numero(suEconomia.npv_musd_mediano, 1)}M` : '—'}
            detalle={suEconomia ? `sobre ${fmt.entero(suEconomia.pozos)} pozos ajustados` : undefined}
            tono={suEconomia && suEconomia.npv_musd_mediano >= 0 ? 'alza' : 'baja'}
          />
          <Dato
            etiqueta="Brent de breakeven"
            valor={suEconomia ? `US$ ${fmt.numero(suEconomia.breakeven_brent_mediano, 1)}` : '—'}
            detalle="por debajo, el pozo no repaga"
            tono="crudo"
          />
          <Dato
            etiqueta="EUR mediana"
            valor={suEconomia ? `${fmt.entero(suEconomia.eur_bbl_mediana / 1000)} Mbbl` : '—'}
            detalle="estimada sobre la curva ajustada"
          />
          <Dato
            etiqueta="Declive del primer año"
            valor={suCurva ? fmt.porcentaje(suCurva.declive_ef_anual_mediano, 0) : '—'}
            detalle="mediano de sus pozos de Vaca Muerta"
          />
        </section>
      ) : null}

      {susAreas.length ? (
        <section className="mt-6 rounded-lg border border-borde bg-superficie p-5">
          <h2 className="text-sm font-medium text-texto-suave">Sus áreas, por producción acumulada</h2>
          <div className="mt-4">
            <Tabla
              columnas={[
                { clave: 'nombre', titulo: 'Concesión' },
                { clave: 'pozos', titulo: 'Pozos', alineacion: 'der' },
                { clave: 'acumulada', titulo: 'Acumulada', alineacion: 'der' },
                { clave: 'porPozo', titulo: 'Por pozo', alineacion: 'der' },
                { clave: 'npv', titulo: 'NPV mediano', alineacion: 'der' },
              ]}
              filas={susAreas.map((area) => ({
                nombre: (
                  <Link
                    href={`/ypf-project?zona=${encodeURIComponent(area.nombre)}`}
                    className="text-azul-claro hover:underline"
                  >
                    {area.nombre}
                  </Link>
                ),
                pozos: fmt.entero(area.pozos),
                acumulada: `${fmt.entero(area.boe_acum_mboe)} Mboe`,
                porPozo: `${fmt.entero(area.boe_por_pozo_mboe)} Mboe`,
                npv:
                  area.npv_musd_mediano === null ? (
                    '—'
                  ) : (
                    <span className={area.npv_musd_mediano >= 0 ? 'text-alza' : 'text-baja'}>
                      US$ {fmt.numero(area.npv_musd_mediano, 1)}M
                    </span>
                  ),
              }))}
            />
          </div>
          <p className="mt-3 text-xs leading-relaxed text-texto-tenue">
            Clic en un área abre el caso con el mapa parado sobre ella. El NPV es el del pozo
            evaluado como si se perforara hoy: un área vieja con NPV negativo no dio pérdida, no
            repagaría el capex de hoy.
          </p>
        </section>
      ) : null}

      <p className="mt-8 text-xs text-texto-tenue">
        Fuentes: Secretaría de Energía (producción SESCO y capítulo IV, informe anual de reservas,
        concesiones). {economia.advertencia}
      </p>
    </main>
  );
}
