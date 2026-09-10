import { EscenaLibro } from '@/components/ilustraciones/escenas';
import { Shell } from '@/components/Shell';
import { Libro } from '@/components/libro/Libro';
import { Dato, Franja } from '@/components/ui';
import { fmt, type Economia, type Financieros } from '@/lib/data';
import { medianaMultiplo, type Mercado } from '@/lib/libro';
import { cargar } from '@/lib/server-data';

// El libro: los estados contables completos, adentro del sitio.
//
// El proyecto ya publicaba un Excel con los tres estados, los segmentos, la
// valuación y los comparables. Un Excel se descarga, se abre en otra ventana y
// queda congelado en los supuestos con los que se generó. Acá está lo mismo,
// pero la valuación se recalcula mientras se mueven los supuestos, que es la
// única parte del libro donde el lector tiene algo para decir.
//
// El Excel sigue estando y se descarga desde acá: para copiar un rango y
// pegarlo en otro modelo, sigue siendo la herramienta.

export const metadata = {
  title: 'El libro — ATLAS-YPF',
  description:
    'Estados contables trimestrales de YPF, segmentos, comparables, perfil de deuda y una valuación por cuatro métodos que se recalcula con los supuestos a mano.',
};

export default async function ModuloLibro() {
  const [mercado, financieros, economia] = await Promise.all([
    cargar<Mercado>('mercado_web.json'),
    cargar<Financieros>('financials_ypf.json'),
    cargar<Economia>('well_economics.json'),
  ]);

  const { udm, balance } = mercado;
  const adrsEnMillones = mercado.adrs / 1_000_000;
  const capitalizacion = mercado.precio_adr * adrsEnMillones;
  const deudaNeta =
    (balance.deuda_no_corriente ?? 0) +
    (balance.deuda_corriente ?? 0) -
    (balance.caja ?? 0) -
    (balance.inversiones_corrientes ?? 0);
  const ev = capitalizacion + deudaNeta;

  // La columna de YPF en la tabla de comparables: los últimos doce meses, que
  // es lo que cotiza hoy, contra el último ejercicio publicado de los otros dos.
  const ypfComparable = {
    titulo: `YPF UDM ${mercado.trimestre}`,
    valores: {
      ingresos: udm.ingresos,
      ebitda: udm.ebitda,
      margen: udm.ebitda && udm.ingresos ? udm.ebitda / udm.ingresos : null,
      resultado_neto: udm.resultado_neto,
      capex: udm.capex === null ? null : -udm.capex,
      deuda_neta: deudaNeta,
      apalancamiento: udm.ebitda ? deudaNeta / udm.ebitda : null,
      ev_ebitda: udm.ebitda ? ev / udm.ebitda : null,
      precio_libro: balance.patrimonio ? capitalizacion / balance.patrimonio : null,
    },
  };

  return (
    <Shell
      actualizado={financieros.generado.slice(0, 10)}
      operadores={economia.por_operador.map((fila) => fila.operador!).filter(Boolean)}
      modulo="libro"
    >
      <main className="mx-auto max-w-6xl px-6 py-12">
        <div className="flex items-start justify-between gap-10">
          <div>
            <Franja className="w-24" />
            <h1 className="mt-5 text-3xl font-bold sm:text-4xl">El libro</h1>
            <p className="mt-3 max-w-3xl leading-relaxed text-texto-suave">
          Los estados contables de YPF armados desde los 6-K y los 20-F de la SEC, trimestre por
          trimestre desde 2020: resultados, balance, flujo de efectivo, la apertura por segmento, el
          perfil de deuda y los comparables. Y una valuación por cuatro métodos que se recalcula
          mientras movés los supuestos, que es lo que un archivo no puede hacer.
            </p>
          </div>
          <EscenaLibro className="hidden h-32 w-56 shrink-0 lg:block" />
        </div>

        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Dato
            etiqueta={`EBITDA UDM al ${fmt.trimestre(mercado.trimestre)}`}
            valor={fmt.musd(udm.ebitda)}
            detalle={`margen ${fmt.porcentaje(udm.ebitda && udm.ingresos ? udm.ebitda / udm.ingresos : null)}`}
            tono="marca"
          />
          <Dato
            etiqueta="Deuda neta / EBITDA"
            valor={udm.ebitda ? `${(deudaNeta / udm.ebitda).toFixed(2)}x` : '—'}
            detalle={`deuda neta ${fmt.musd(deudaNeta)}`}
          />
          <Dato
            etiqueta="EV / EBITDA"
            valor={udm.ebitda ? `${(ev / udm.ebitda).toFixed(2)}x` : '—'}
            detalle={`mediana desde 2020: ${medianaMultiplo(mercado).toFixed(2)}x`}
            tono="crudo"
          />
          <Dato
            etiqueta="Precio del ADR"
            valor={`US$ ${mercado.precio_adr.toFixed(2)}`}
            detalle={`al ${mercado.fecha_precio}`}
            tono="alza"
          />
        </div>

        <div className="mt-8">
          <Libro mercado={mercado} ypfComparable={ypfComparable} />
        </div>

        <div className="mt-10 grid gap-6 lg:grid-cols-2">
          <div className="marquesina rounded-lg border border-borde bg-superficie p-5">
            <h3 className="text-sm font-medium text-texto-suave">De dónde sale cada número</h3>
            <ul className="mt-4 space-y-2 text-xs leading-relaxed text-texto-suave">
              <li>
                Los estados salen de las tablas del Item 1 de cada 6-K y de los 20-F. El cuarto
                trimestre no lo publica nadie: sale del ejercicio menos los nueve meses.
              </li>
              <li>
                Hasta 2022 la compañía presentaba en pesos. Su moneda funcional es el dólar, así que
                esa presentación es una traducción y acá se deshace con el mismo tipo de cambio: el
                activo de diciembre de 2022 vuelve a dar los 25.912 millones que publicó, con un
                décimo de punto de diferencia.
              </li>
              <li>
                Los comparables salen del XBRL de los 20-F de Vista y Pampa, que la SEC publica
                estructurado. Su último ejercicio disponible es 2024.
              </li>
            </ul>
          </div>

          <div className="marquesina rounded-lg border border-borde bg-superficie p-5">
            <h3 className="text-sm font-medium text-texto-suave">El mismo libro, en Excel</h3>
            <p className="mt-4 text-xs leading-relaxed text-texto-suave">
              Trece hojas con los tres estados, análisis, segmentos, operativo, valuación,
              comparables, deuda y una hoja de chequeos donde las identidades contables tienen que
              dar cero. Las fórmulas están vivas: cada ratio apunta a la línea que lo origina, así
              que se puede auditar celda por celda o usarlo de base para otro modelo.
            </p>
            <a
              href="/YPF_estados_financieros.xlsx"
              className="mt-4 inline-block rounded-md border border-borde px-3 py-1.5 text-xs text-texto-suave transition-colors hover:border-azul-claro hover:text-azul-claro"
              download
            >
              Descargar el Excel
            </a>
          </div>
        </div>

        <p className="mt-8 text-xs leading-relaxed text-texto-tenue">
          Los estados completos, línea por línea y con la presentación de la que salió cada número,
          están en{' '}
          <a href="/data/estados_web.json" className="text-azul-claro hover:underline">
            estados_web.json
          </a>
          . El pipeline que los arma corre solo todas las semanas.
        </p>
      </main>
    </Shell>
  );
}
