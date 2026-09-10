import Link from 'next/link';

import { EscenaCuenca } from '@/components/ilustraciones/escenas';
import { Panel } from '@/components/Panel';
import { Shell } from '@/components/Shell';
import { TablaExcel, type FilaExcel } from '@/components/TablaExcel';
import { Dato, Franja } from '@/components/ui';
import type { ProduccionPais } from '@/components/ExploradorProduccion';
import type { Reservas } from '@/components/Reservas';
import { fmt, type CurvasDeclive, type Economia, type Financieros, type Produccion } from '@/lib/data';
import { aSlug } from '@/lib/operadores';
import { cargar } from '@/lib/server-data';

// El módulo operativo: el activo, no el balance.
//
// La pregunta que organiza esta pantalla es distinta a la de finanzas. Allá es
// cuánto entró; acá es de dónde sale, quién lo opera, cuánto queda y cuánto
// cuesta sacarlo. Por eso la tabla principal cruza a los operadores contra las
// cuatro dimensiones que importan a la vez —producción, reservas, vida y
// economía de pozo—, que es un cruce que en el caso está repartido en tres
// secciones distintas.

export const metadata = {
  title: 'Operativo — ATLAS-YPF',
  description:
    'Producción por operador y área, reservas, vida de reservas y economía de pozo en Vaca Muerta.',
};

export default async function ModuloOperativo() {
  const [pais, reservas, economia, declive, produccion, financieros] = await Promise.all([
    cargar<ProduccionPais>('country_production.json'),
    cargar<Reservas>('reserves.json'),
    cargar<Economia>('well_economics.json'),
    cargar<CurvasDeclive>('decline_type_curves.json'),
    cargar<Produccion>('production_summary.json'),
    cargar<Financieros>('financials_ypf.json'),
  ]);

  const meses = pais.pais.filter((mes) => mes.oil_total !== null);
  const ultimo = meses[meses.length - 1];
  const haceUnAnio = meses[meses.length - 13] ?? meses[0];
  const variacion = (actual: number | null, anterior: number | null) =>
    actual !== null && anterior !== null && anterior !== 0 ? actual / anterior - 1 : null;

  // El cruce que no existe en ninguna otra pantalla: cada operador con sus
  // cuatro dimensiones al lado.
  const operadores = (pais.rankings.empresa ?? [])
    .filter((fila) => fila.nombre !== 'Otros' && fila.actual_bd > 0)
    .slice(0, 12);

  const buscarReserva = (nombre: string) =>
    reservas.ranking_ultimo.find((fila) => fila.operador === nombre);
  const buscarEconomia = (nombre: string) =>
    economia.por_operador.find((fila) => fila.operador === nombre);
  const buscarCurva = (nombre: string) =>
    declive.por_operador.find((fila) => fila.operador === nombre);

  const nombres = operadores.map((fila) => fila.nombre);
  const filasOperadores: FilaExcel[] = [
    {
      concepto: 'Producción, bbl/d',
      formato: 'entero',
      mapaCalor: true,
      valores: operadores.map((fila) => fila.actual_bd),
    },
    {
      concepto: 'Variación interanual',
      nivel: 1,
      formato: 'signo',
      mapaCalor: true,
      valores: operadores.map((fila) => fila.crecimiento),
    },
    {
      concepto: 'Participación del país',
      nivel: 1,
      formato: 'porcentaje',
      valores: operadores.map((fila) => fila.participacion),
    },
    {
      concepto: 'Reservas comprobadas, Mboe',
      formato: 'entero',
      subtotal: true,
      valores: nombres.map((nombre) => buscarReserva(nombre)?.comprobadas_mboe ?? null),
    },
    {
      concepto: 'No convencional',
      nivel: 1,
      formato: 'porcentaje0',
      valores: nombres.map((nombre) => buscarReserva(nombre)?.share_no_convencional ?? null),
    },
    {
      concepto: 'Vida de reservas, años',
      nivel: 1,
      formato: 'decimal',
      mapaCalor: true,
      valores: nombres.map((nombre) => buscarReserva(nombre)?.vida_reservas ?? null),
      ayuda: 'Reservas comprobadas sobre la producción del año',
    },
    {
      concepto: 'NPV mediano por pozo, US$ M',
      formato: 'decimal',
      subtotal: true,
      mapaCalor: true,
      valores: nombres.map((nombre) => buscarEconomia(nombre)?.npv_musd_mediano ?? null),
    },
    {
      concepto: 'Brent de breakeven',
      nivel: 1,
      formato: 'decimal',
      valores: nombres.map((nombre) => buscarEconomia(nombre)?.breakeven_brent_mediano ?? null),
    },
    {
      concepto: 'EUR mediana, Mbbl',
      nivel: 1,
      formato: 'entero',
      valores: nombres.map((nombre) => {
        const fila = buscarEconomia(nombre);
        return fila ? fila.eur_bbl_mediana / 1000 : null;
      }),
    },
    {
      concepto: 'Declive del primer año',
      nivel: 1,
      formato: 'porcentaje0',
      valores: nombres.map((nombre) => buscarCurva(nombre)?.declive_ef_anual_mediano ?? null),
    },
    {
      concepto: 'Pozos ajustados',
      nivel: 1,
      formato: 'entero',
      valores: nombres.map((nombre) => buscarEconomia(nombre)?.pozos ?? null),
    },
  ];

  const areas = (pais.rankings.concesion ?? []).slice(0, 15);
  const filasAreas: FilaExcel[] = [
    {
      concepto: 'Producción actual, bbl/d',
      formato: 'entero',
      mapaCalor: true,
      valores: areas.map((fila) => fila.actual_bd),
    },
    {
      concepto: 'Hace un año',
      nivel: 1,
      formato: 'entero',
      valores: areas.map((fila) => fila.previo_bd),
    },
    {
      concepto: 'Variación, bbl/d',
      nivel: 1,
      formato: 'entero',
      mapaCalor: true,
      subtotal: true,
      valores: areas.map((fila) => fila.delta_bd),
    },
    {
      concepto: 'Variación relativa',
      nivel: 1,
      formato: 'signo',
      valores: areas.map((fila) => fila.crecimiento),
    },
  ];

  return (
    <Shell
      actualizado={financieros.generado.slice(0, 10)}
      operadores={economia.por_operador.map((fila) => fila.operador!).filter(Boolean)}
      modulo="operativo"
    >
      <main className="mx-auto max-w-6xl px-6 py-12">
        <div className="flex items-start justify-between gap-10">
          <div>
            <Franja className="w-24" />
            <h1 className="mt-5 text-3xl font-bold sm:text-4xl">Operativo</h1>
            <p className="mt-3 max-w-3xl leading-relaxed text-texto-suave">
          De dónde sale el crudo, quién lo opera, cuánto queda y cuánto cuesta sacarlo. La
          producción es bruta operada: incluye la parte de los socios, así que para cada compañía es
          mayor que la que consolida en su balance.
            </p>
          </div>
          <EscenaCuenca className="hidden h-32 w-56 shrink-0 lg:block" />
        </div>

        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Dato
            etiqueta={`Petróleo del país · ${ultimo.fecha}`}
            valor={`${fmt.entero(ultimo.oil_total)} bbl/d`}
            delta={variacion(ultimo.oil_total, haceUnAnio.oil_total)}
            deltaReferencia=" i.a."
            tono="marca"
          />
          <Dato
            etiqueta="Shale"
            valor={`${fmt.entero(ultimo.oil_shale)} bbl/d`}
            delta={variacion(ultimo.oil_shale, haceUnAnio.oil_shale)}
            deltaReferencia=" i.a."
            tono="alza"
          />
          <Dato
            etiqueta="Convencional"
            valor={`${fmt.entero(ultimo.oil_convencional)} bbl/d`}
            delta={variacion(ultimo.oil_convencional, haceUnAnio.oil_convencional)}
            deltaReferencia=" i.a."
            tono="baja"
          />
          <Dato
            etiqueta="Shale sobre el total"
            valor={fmt.porcentaje(
              ultimo.oil_shale && ultimo.oil_total ? ultimo.oil_shale / ultimo.oil_total : null,
              0,
            )}
            detalle="hace cinco años era menos de un cuarto"
            tono="crudo"
          />
          <Dato
            etiqueta="Pozos de Vaca Muerta"
            valor={fmt.entero(produccion.cobertura.pozos_vaca_muerta)}
            detalle={`de ${fmt.entero(produccion.cobertura.pozos)} no convencionales`}
          />
          <Dato
            etiqueta="Pozos con curva ajustada"
            valor={fmt.entero(declive.pozos_ajustados)}
            detalle="Arps desde el mes pico"
          />
          <Dato
            etiqueta="NPV mediano por pozo"
            valor={`US$ ${fmt.numero(economia.resumen.npv_musd_mediano, 1)}M`}
            detalle={`breakeven US$ ${fmt.numero(economia.resumen.breakeven_brent_mediano, 0)}/bbl`}
            tono="alza"
          />
          <Dato
            etiqueta="Reservas del ranking"
            valor={`${fmt.entero(
              reservas.ranking_ultimo.reduce((suma, fila) => suma + fila.comprobadas_mboe, 0),
            )} Mboe`}
            detalle={`comprobadas al cierre de ${reservas.ultimo_anio}`}
          />
        </div>

        <div className="mt-8 space-y-6">
          <Panel
            titulo="Los operadores, en las cuatro dimensiones que importan"
            archivo="atlas-ypf-operadores"
            columnas={[
              { clave: 'nombre', titulo: 'Operador' },
              { clave: 'actual_bd', titulo: 'Producción bbl/d', alineacion: 'der' },
              { clave: 'crecimiento', titulo: 'Variación i.a.', alineacion: 'der', formato: 'porcentaje0' as const },
              { clave: 'participacion', titulo: 'Del país', alineacion: 'der', formato: 'porcentaje0' as const },
            ]}
            datos={operadores as unknown as Record<string, unknown>[]}
            nota={
              <>
                Producción, reservas y economía de pozo en la misma grilla. La lectura incómoda está
                en la fila de vida de reservas: YPF produce más que nadie y es la que menos años de
                inventario tiene. Cada operador tiene{' '}
                <span className="text-azul-claro">ficha propia</span> con su serie completa.
              </>
            }
          >
            <TablaExcel columnas={nombres} filas={filasOperadores} etiquetaPrimera="Indicador" />
          </Panel>

          <div className="flex flex-wrap gap-2">
            {nombres.slice(0, 8).map((nombre) => (
              <Link
                key={nombre}
                href={`/ypf-project/operador/${aSlug(nombre)}`}
                className="rounded-md border border-borde px-3 py-1.5 text-xs text-texto-suave transition hover:border-azul-claro hover:text-azul-claro"
              >
                {nombre} →
              </Link>
            ))}
          </div>

          <Panel
            titulo="Las áreas que más se movieron en el último año"
            archivo="atlas-ypf-areas"
            columnas={[
              { clave: 'nombre', titulo: 'Concesión' },
              { clave: 'actual_bd', titulo: 'Actual bbl/d', alineacion: 'der' },
              { clave: 'previo_bd', titulo: 'Hace un año', alineacion: 'der' },
              { clave: 'delta_bd', titulo: 'Variación', alineacion: 'der' },
              { clave: 'crecimiento', titulo: 'Relativa', alineacion: 'der', formato: 'porcentaje0' as const },
            ]}
            datos={areas as unknown as Record<string, unknown>[]}
            nota="Ordenadas por variación absoluta y no porcentual: un área que arrancó de cero encabezaría cualquier ranking relativo sin mover la aguja de nadie."
          >
            <TablaExcel
              columnas={areas.map((fila) => fila.nombre)}
              filas={filasAreas}
              etiquetaPrimera="Indicador"
            />
          </Panel>
        </div>

        <p className="mt-8 text-xs leading-relaxed text-texto-tenue">
          El mapa con las {fmt.entero(produccion.cobertura.pozos)} ubicaciones, los ductos y las
          concesiones está en{' '}
          <Link href="/ypf-project#activo" className="text-azul-claro hover:underline">
            la sección 04 del caso
          </Link>
          . Fuentes: Secretaría de Energía (producción SESCO y capítulo IV, reservas, concesiones).
        </p>
      </main>
    </Shell>
  );
}
