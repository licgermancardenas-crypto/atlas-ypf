import { EscenaFinanzas } from '@/components/ilustraciones/escenas';
import { Panel } from '@/components/Panel';
import { Shell } from '@/components/Shell';
import { TablaExcel, type FilaExcel } from '@/components/TablaExcel';
import { Dato, Franja } from '@/components/ui';
import { fmt, type Economia, type Financieros, type Sensibilidad } from '@/lib/data';
import { cargar } from '@/lib/server-data';

// El módulo financiero.
//
// El caso cuenta una historia; esto es la planilla que hay abajo. Un analista no
// quiere el gráfico: quiere los conceptos en las filas, los trimestres en las
// columnas y poder recorrer con el dedo. Por eso la tabla maestra está
// transpuesta respecto de cómo viene el dato —una fila por concepto, no por
// trimestre—, que es como se arma un modelo financiero.

export const metadata = {
  title: 'Finanzas — ATLAS-YPF',
  description:
    'Serie trimestral de YPF, ratios derivados y sensibilidad del valor del pozo a Brent y capex.',
};

export default async function ModuloFinanzas() {
  const [financieros, sensibilidad, economia] = await Promise.all([
    cargar<Financieros>('financials_ypf.json'),
    cargar<Sensibilidad>('ebitda_sensitivity.json'),
    cargar<Economia>('well_economics.json'),
  ]);

  const serie = sensibilidad.serie;
  const trimestres = serie.map((punto) => fmt.trimestre(punto.trimestre));
  const ultimo = financieros.serie[financieros.serie.length - 1];
  const previo = financieros.serie[financieros.serie.length - 5];

  const variacion = (actual: number | null, anterior: number | null) =>
    actual !== null && anterior !== null && anterior !== 0 ? actual / anterior - 1 : null;

  const columna = <K extends keyof (typeof serie)[number]>(clave: K) =>
    serie.map((punto) => punto[clave] as number | null);

  // Ratios que no vienen del pipeline: se derivan acá porque son combinaciones
  // de líneas que ya están, y calcularlas en el transform sería guardar en disco
  // algo que es una división.
  const derivar = (
    numerador: (number | null)[],
    denominador: (number | null)[],
  ): (number | null)[] =>
    numerador.map((valor, indice) => {
      const abajo = denominador[indice];
      return valor !== null && abajo !== null && abajo !== 0 ? valor / abajo : null;
    });

  const ingresos = columna('revenues_musd');
  const ebitda = columna('adj_ebitda_musd');
  const produccion = columna('produccion_kboed');
  // Los boe del trimestre: la producción viene por día, y 91,25 es el trimestre
  // promedio del año. Sirve de denominador para las dos líneas unitarias.
  const boeDelTrimestre = produccion.map((valor) =>
    valor !== null ? valor * 1000 * 91.25 : null,
  );
  const aDolares = (musd: (number | null)[]) =>
    musd.map((valor) => (valor !== null ? valor * 1_000_000 : null));

  const filasResultado: FilaExcel[] = [
    { concepto: 'Ingresos', formato: 'entero', valores: ingresos, ayuda: 'Ventas totales del trimestre, US$ millones' },
    { concepto: 'EBITDA ajustado', formato: 'entero', subtotal: true, valores: ebitda },
    {
      concepto: 'Margen EBITDA',
      nivel: 1,
      formato: 'porcentaje',
      mapaCalor: true,
      valores: columna('margen_ebitda'),
      ayuda: 'EBITDA ajustado sobre ingresos',
    },
    {
      concepto: 'Brent promedio',
      nivel: 1,
      formato: 'decimal',
      valores: columna('brent_usd'),
      ayuda: 'Promedio del trimestre, US$/bbl',
    },
    {
      concepto: 'Crudo realizado',
      nivel: 1,
      formato: 'decimal',
      valores: columna('precio_crudo_usd_bbl'),
      ayuda: 'Precio que efectivamente cobró la compañía, US$/bbl',
    },
    {
      concepto: 'Diferencial vs. Brent',
      nivel: 2,
      formato: 'decimal',
      mapaCalor: true,
      valores: columna('diferencial_usd_bbl'),
      ayuda: 'Cuánto se pierde entre el precio internacional y el local',
    },
  ];

  const filasOperativas: FilaExcel[] = [
    { concepto: 'Producción total', formato: 'decimal', valores: produccion, ayuda: 'Kboe/d' },
    { concepto: 'Shale oil', nivel: 1, formato: 'decimal', valores: columna('shale_oil_kbbld'), ayuda: 'Kbbl/d' },
    {
      concepto: 'Lifting cost',
      nivel: 1,
      formato: 'decimal',
      mapaCalor: true,
      valores: columna('lifting_cost_usd_boe'),
      ayuda: 'Costo de extracción, US$/boe',
    },
    {
      concepto: 'EBITDA por boe',
      nivel: 1,
      formato: 'decimal',
      subtotal: true,
      valores: derivar(aDolares(ebitda), boeDelTrimestre),
      ayuda: 'Lo que deja cada barril equivalente producido, US$/boe',
    },
    {
      concepto: 'Ingresos por boe',
      nivel: 2,
      formato: 'decimal',
      valores: derivar(aDolares(ingresos), boeDelTrimestre),
      ayuda: 'Ingresos del trimestre sobre los boe producidos, US$/boe',
    },
  ];

  // La grilla de sensibilidad es una tabla de doble entrada como la que arma
  // cualquiera en Excel: capex en las filas, Brent en las columnas.
  const brents = [...new Set(economia.sensibilidad_brent_capex.map((f) => f.brent))].sort(
    (a, b) => a - b,
  );
  const capexes = [...new Set(economia.sensibilidad_brent_capex.map((f) => f.capex_musd))].sort(
    (a, b) => a - b,
  );
  const filasSensibilidad: FilaExcel[] = capexes.map((capex) => ({
    concepto: `Capex US$ ${fmt.numero(capex, 0)}M`,
    formato: 'decimal',
    mapaCalor: true,
    valores: brents.map(
      (brent) =>
        economia.sensibilidad_brent_capex.find(
          (fila) => fila.brent === brent && fila.capex_musd === capex,
        )?.npv_musd_mediano ?? null,
    ),
  }));

  return (
    <Shell actualizado={financieros.generado.slice(0, 10)} operadores={[]} modulo="finanzas">
      <main className="mx-auto max-w-6xl px-6 py-12">
        <div className="flex items-start justify-between gap-10">
          <div>
            <Franja className="w-24" />
            <h1 className="mt-5 text-3xl font-bold sm:text-4xl">Finanzas</h1>
            <p className="mt-3 max-w-3xl leading-relaxed text-texto-suave">
          {financieros.trimestres} trimestres reconstruidos desde los earnings releases que YPF
          adjunta a cada 6-K, cruzados con Brent y con la producción. Los conceptos van en las filas
          y los períodos en las columnas, que es como se lee un modelo financiero y no como viene el
          dato.
            </p>
          </div>
          <EscenaFinanzas className="hidden h-32 w-56 shrink-0 lg:block" />
        </div>

        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Dato
            etiqueta={`Ingresos · ${fmt.trimestre(ultimo.trimestre)}`}
            valor={fmt.musd(ultimo.revenues_musd)}
            delta={variacion(ultimo.revenues_musd, previo.revenues_musd)}
            deltaReferencia=" i.a."
            tono="marca"
          />
          <Dato
            etiqueta="EBITDA ajustado"
            valor={fmt.musd(ultimo.adj_ebitda_musd)}
            delta={variacion(ultimo.adj_ebitda_musd, previo.adj_ebitda_musd)}
            deltaReferencia=" i.a."
            tono="alza"
          />
          <Dato
            etiqueta="Resultado neto"
            valor={fmt.musd(ultimo.net_result_musd)}
            delta={variacion(ultimo.net_result_musd, previo.net_result_musd)}
            deltaReferencia=" i.a."
          />
          <Dato
            etiqueta="Flujo libre"
            valor={fmt.musd(ultimo.fcf_musd)}
            detalle="después de capex e intereses"
            tono={ultimo.fcf_musd && ultimo.fcf_musd >= 0 ? 'alza' : 'baja'}
          />
          <Dato
            etiqueta="CAPEX"
            valor={fmt.musd(ultimo.capex_musd)}
            delta={variacion(ultimo.capex_musd, previo.capex_musd)}
            deltaReferencia=" i.a."
          />
          <Dato
            etiqueta="Deuda neta"
            valor={fmt.musd(ultimo.net_debt_musd)}
            delta={variacion(ultimo.net_debt_musd, previo.net_debt_musd)}
            deltaReferencia=" i.a."
          />
          <Dato
            etiqueta="Deuda neta / EBITDA"
            valor={`${fmt.numero(ultimo.net_leverage_x, 2)}x`}
            detalle="mínimo de la serie reconstruida"
            tono="alza"
          />
          <Dato
            etiqueta="Margen EBITDA"
            valor={fmt.porcentaje(
              ultimo.adj_ebitda_musd && ultimo.revenues_musd
                ? ultimo.adj_ebitda_musd / ultimo.revenues_musd
                : null,
            )}
            delta={variacion(
              ultimo.adj_ebitda_musd && ultimo.revenues_musd
                ? ultimo.adj_ebitda_musd / ultimo.revenues_musd
                : null,
              previo.adj_ebitda_musd && previo.revenues_musd
                ? previo.adj_ebitda_musd / previo.revenues_musd
                : null,
            )}
            deltaReferencia=" i.a."
            tono="crudo"
          />
        </div>

        <div className="mt-8 space-y-6">
          <Panel
            titulo="Resultado y precios, por trimestre"
            archivo="atlas-ypf-finanzas-resultado"
            columnas={[
              { clave: 'trimestre', titulo: 'Trimestre' },
              { clave: 'revenues_musd', titulo: 'Ingresos', alineacion: 'der' },
              { clave: 'adj_ebitda_musd', titulo: 'EBITDA aj.', alineacion: 'der' },
              { clave: 'margen_ebitda', titulo: 'Margen', alineacion: 'der', formato: 'porcentaje' as const },
              { clave: 'brent_usd', titulo: 'Brent', alineacion: 'der', formato: 'decimal' as const },
              {
                clave: 'precio_crudo_usd_bbl',
                titulo: 'Crudo realizado',
                alineacion: 'der',
                formato: 'decimal' as const,
              },
            ]}
            datos={serie as unknown as Record<string, unknown>[]}
            nota="Las celdas con fondo comparan dentro de su propia fila: en una tabla que mezcla márgenes y dólares por barril, una escala común no diría nada."
          >
            <TablaExcel columnas={trimestres} filas={filasResultado} etiquetaPrimera="US$ millones" />
          </Panel>

          <Panel
            titulo="Operativo y costos, por trimestre"
            archivo="atlas-ypf-finanzas-operativo"
            columnas={[
              { clave: 'trimestre', titulo: 'Trimestre' },
              { clave: 'produccion_kboed', titulo: 'Producción Kboe/d', alineacion: 'der', formato: 'decimal' as const },
              { clave: 'shale_oil_kbbld', titulo: 'Shale Kbbl/d', alineacion: 'der', formato: 'decimal' as const },
              {
                clave: 'lifting_cost_usd_boe',
                titulo: 'Lifting US$/boe',
                alineacion: 'der',
                formato: 'decimal' as const,
              },
              { clave: 'ebitda_por_boe', titulo: 'EBITDA/boe', alineacion: 'der', formato: 'decimal' as const },
            ]}
            datos={serie as unknown as Record<string, unknown>[]}
            nota="El EBITDA por boe es la línea que junta las dos mitades del caso: cuánto deja cada barril después de sacarlo."
          >
            <TablaExcel columnas={trimestres} filas={filasOperativas} etiquetaPrimera="Por trimestre" />
          </Panel>

          <Panel
            titulo="Sensibilidad del pozo tipo: NPV mediano según Brent y capex"
            archivo="atlas-ypf-sensibilidad"
            columnas={[
              { clave: 'brent', titulo: 'Brent US$/bbl', alineacion: 'der' },
              { clave: 'capex_musd', titulo: 'Capex US$ M', alineacion: 'der', formato: 'decimal' as const },
              { clave: 'npv_musd_mediano', titulo: 'NPV mediano US$ M', alineacion: 'der', formato: 'decimal' as const },
              {
                clave: 'pozos_con_npv_positivo',
                titulo: '% pozos con NPV > 0',
                alineacion: 'der',
                formato: 'porcentaje0' as const,
              },
            ]}
            datos={economia.sensibilidad_brent_capex as unknown as Record<string, unknown>[]}
            nota={
              <>
                Tabla de doble entrada sobre {fmt.entero(economia.resumen.pozos)} pozos ajustados. A
                Brent 50 y capex US$ 14M el pozo mediano destruye valor; hace falta un Brent de{' '}
                {fmt.numero(economia.resumen.breakeven_brent_mediano, 0)} para que repague.{' '}
                {economia.advertencia}
              </>
            }
          >
            <TablaExcel
              columnas={brents.map((brent) => `US$ ${brent}`)}
              filas={filasSensibilidad}
              etiquetaPrimera="NPV mediano, US$ M"
              anchoPrimera="11rem"
            />
          </Panel>
        </div>

        <p className="mt-8 text-xs leading-relaxed text-texto-tenue">
          Cada trimestre se toma del release donde es el trimestre titular, no de las columnas
          comparativas de reportes posteriores: lo que se explica es la reacción del mercado al dato
          de ese momento. Fuente: SEC EDGAR, más Brent de Yahoo Finance.
        </p>
      </main>
    </Shell>
  );
}
