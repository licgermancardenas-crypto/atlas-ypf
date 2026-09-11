import Link from 'next/link';

import { EscenaRed } from '@/components/ilustraciones/escenas';
import { Mapa } from '@/components/ilustraciones/mapa';
import { RedLazy } from '@/components/RedLazy';
import { Shell } from '@/components/Shell';
import { ProveedorEntidad } from '@/components/estado/entidad';
import { Dato, Franja } from '@/components/ui';
import { fmt, type Economia, type Financieros } from '@/lib/data';
import { cargar } from '@/lib/server-data';

// El módulo de relaciones.
//
// El resto del proyecto mira una dimensión por vez: producción por empresa,
// reservas por cuenca, NPV por yacimiento. Lo que ninguna contesta es con quién
// comparte cada quien, y en Vaca Muerta esa es una pregunta con consecuencias:
// las áreas se operan en bloques con socios, y esas participaciones cruzadas
// son la razón por la que la producción bruta operada y la neta consolidada no
// coinciden nunca.

export const metadata = {
  title: 'Relaciones — ATLAS-YPF',
  description:
    'Grafo de concesiones, yacimientos, empresas y pozos: quién opera qué, con quién y cuánto sale de cada nodo.',
};

interface ResumenGrafo {
  mes_referencia: string;
  advertencias: {
    pozos_sin_operadora_excluidos: number;
    concesiones_sin_titularidad: string[];
  };
  nodes: { type: string; props: Record<string, unknown> }[];
  edges: { type: string }[];
}

export default async function ModuloRed() {
  const [grafo, financieros, economia] = await Promise.all([
    cargar<ResumenGrafo>('graph/entities_agregado.json'),
    cargar<Financieros>('financials_ypf.json'),
    cargar<Economia>('well_economics.json'),
  ]);

  const cuenta = (tipo: string) => grafo.nodes.filter((nodo) => nodo.type === tipo).length;
  const titularidades = grafo.edges.filter((arista) => arista.type === 'titularidad').length;

  // Con cuántos socios opera cada área: es el número que justifica la vista.
  const socios = grafo.nodes
    .filter((nodo) => nodo.type === 'concesion')
    .map((nodo) => (nodo.props.empresas as string[] | undefined)?.length ?? 0);
  const compartidas = socios.filter((cantidad) => cantidad > 1).length;
  const conTitularidad = socios.filter((cantidad) => cantidad > 0).length;

  return (
    <Shell
      actualizado={financieros.generado.slice(0, 10)}
      operadores={economia.por_operador.map((fila) => fila.operador!).filter(Boolean)}
      modulo="red"
    >
      <ProveedorEntidad>
        <main className="mx-auto max-w-6xl px-6 py-12">
          <div className="flex items-start justify-between gap-10">
            <div>
              <Franja className="w-24" />
              <h1 className="mt-5 text-3xl font-bold sm:text-4xl">Relaciones</h1>
              <p className="mt-3 max-w-3xl leading-relaxed text-texto-suave">
            Quién opera qué, con quién y cuánto sale de cada nodo. Clic en cualquier círculo abre
            su ficha con las entidades conectadas; cada una de esas es a su vez un clic. El link de
            la barra de direcciones se actualiza solo, así que una selección se puede compartir.
              </p>
            </div>
            <EscenaRed className="hidden h-32 w-56 shrink-0 lg:block" />
          </div>

          <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Dato
              etiqueta="Concesiones"
              valor={fmt.entero(cuenta('concesion'))}
              detalle={`${fmt.entero(conTitularidad)} con titularidad cargada`}
              tono="marca"
            />
            <Dato
              etiqueta="Áreas con socios"
              valor={fmt.entero(compartidas)}
              detalle="más de una empresa en el título"
              tono="crudo"
            />
            <Dato
              etiqueta="Empresas"
              valor={fmt.entero(cuenta('empresa'))}
              detalle={`${fmt.entero(titularidades)} participaciones declaradas`}
            />
            <Dato
              etiqueta="Yacimientos"
              valor={fmt.entero(cuenta('yacimiento'))}
              detalle={`sobre ${fmt.entero(cuenta('concesion'))} concesiones`}
              tono="alza"
            />
          </div>

          <div className="mt-8">
            <RedLazy />
          </div>

          <div className="mt-8 grid gap-6 lg:grid-cols-2">
            <div className="marquesina rounded-lg border border-borde bg-superficie p-5">
              <h3 className="text-sm font-medium text-texto-suave">Cómo leer el grafo</h3>
              <ul className="mt-4 space-y-2 text-xs leading-relaxed text-texto-suave">
                <li>
                  Las aristas <span className="text-texto">titularidad</span> llevan el porcentaje
                  del padrón: son las que muestran a dos competidores adentro de la misma área.
                </li>
                <li>
                  El tamaño del círculo va por la raíz de la métrica elegida, así que lo
                  proporcional es el área y no el radio. Con escala lineal, Loma Campana taparía
                  el resto de la cuenca.
                </li>
                <li>
                  Los pozos no están al abrir. Son el 95% de los nodos y a esta escala no se
                  distingue uno de otro: se piden de a una concesión desde el botón de la ficha.
                </li>
              </ul>
            </div>

            <div className="marquesina rounded-lg border border-borde bg-superficie p-5">
              <h3 className="text-sm font-medium text-texto-suave">Lo que este grafo no sabe</h3>
              <ul className="mt-4 space-y-2 text-xs leading-relaxed text-texto-suave">
                <li>
                  {grafo.advertencias.concesiones_sin_titularidad.length} concesiones con
                  producción no figuran con ese nombre en el padrón y quedan sin socios. No se les
                  asigna la titularidad de un área parecida: valen el 0,5% de la producción del
                  mes y un match aproximado sería inventar de quién es cada cosa.
                </li>
                <li>
                  La producción es <span className="text-texto">bruta operada</span> del mes{' '}
                  {grafo.mes_referencia}: el total de un operador incluye la parte de sus socios.
                  El porcentaje de la arista dice cuánto le toca en el título, no cuánto consolida.
                </li>
                <li>
                  Las participaciones son las vigentes en el padrón, sin historia: una cesión de
                  hace dos años no se ve.
                </li>
              </ul>
            </div>
          </div>

          <div className="marquesina mt-6 rounded-lg border border-borde bg-superficie p-5">
            <div className="grid items-center gap-6 lg:grid-cols-[16rem_minmax(0,1fr)]">
              <Mapa
                className="w-full"
                capas={['provincias', 'rios', 'cuenca', 'concesiones']}
                puntos={['pozos']}
                foco="concesiones"
                corriente={false}
                etiqueta="Las áreas concesionadas de la cuenca neuquina sobre el mapa"
              />
              <div>
                <h3 className="text-sm font-medium text-texto-suave">El grafo no tiene geografía</h3>
                <p className="mt-4 text-xs leading-relaxed text-texto-suave">
                  Los nodos de arriba se acomodan por fuerzas, no por ubicación: dos áreas linderas
                  pueden terminar en puntas opuestas de la pantalla, y eso es lo que hace legible la
                  titularidad. El costo es que se pierde de vista dónde queda cada cosa. Éste es el
                  mismo padrón —las {fmt.entero(cuenta('concesion'))} concesiones— puesto sobre el
                  terreno: la mancha azul es todo lo concesionado y los puntos dorados son los
                  racimos de pozos, que se apilan en una fracción chica de esa superficie.
                </p>
                <p className="mt-3 text-xs leading-relaxed text-texto-tenue">
                  Los polígonos salen del mismo archivo que el mapa navegable del caso, simplificados
                  para que el dibujo pese treinta kilobytes en vez de un mega.
                </p>
              </div>
            </div>
          </div>

          <p className="mt-8 text-xs leading-relaxed text-texto-tenue">
            Fuente de la titularidad: padrón de Concesiones de Explotación de la Secretaría de
            Energía, el mismo del que salen los polígonos{' '}
            <Link href="/ypf-project#activo" className="text-azul-claro hover:underline">
              del mapa
            </Link>
            . El grafo completo, con los {fmt.entero(5062)} pozos adentro, está en{' '}
            <a href="/data/graph/entities.json" className="text-azul-claro hover:underline">
              entities.json
            </a>
            .
          </p>
        </main>
      </ProveedorEntidad>
    </Shell>
  );
}
