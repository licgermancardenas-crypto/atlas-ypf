// El mapa, dibujado con la geometría de verdad.
//
// El resto de las ilustraciones del sitio son esquemas: un balancín, un tanque,
// un buque. Este no. La silueta de la cuenca es la silueta de la cuenca, los
// ductos son los ductos y las rutas son las rutas nacionales, sacados de las
// mismas capas del IGN y de la Secretaría de Energía que alimentan el mapa 3D
// del módulo de operaciones. Lo único que se les hizo es simplificarlas hasta
// donde el ojo no nota la diferencia a este tamaño —de un mega y medio a treinta
// kilobytes— en pipeline/transform/map_svg.py.
//
// Por eso vive acá y no en piezas.tsx: las piezas son dibujo, esto es dato.
//
// No lleva estado ni eventos, así que es un componente de servidor: viaja como
// markup y no suma un byte de JavaScript. El movimiento —la corriente adentro
// del ducto— es una animación de CSS, que el ajuste de "menos movimiento" del
// sistema apaga sola.

import { cargar } from '@/lib/server-data';

export type CapaMapa =
  | 'provincias'
  | 'rios'
  | 'cuenca'
  | 'concesiones'
  | 'rutas'
  | 'gasoductos'
  | 'ductos';

export type PuntosMapa = 'refinerias' | 'terminales' | 'localidades' | 'pozos';

export interface MapaWeb {
  generado: string;
  lienzo: { ancho: number; alto: number };
  encuadre: [number, number, number, number];
  capas: Record<CapaMapa, string[]>;
  puntos: Record<PuntosMapa, { x: number; y: number; nombre?: string }[]>;
  nota: string;
}

// Cómo se ve cada capa. El orden del objeto es el orden de dibujo: lo que va
// atrás primero, y el crudo último porque es lo que tiene que saltar.
const ESTILO: Record<CapaMapa, { color: string; grosor: number; opacidad: number; relleno?: number }> = {
  provincias: { color: 'var(--color-neutro)', grosor: 0.6, opacidad: 0.28 },
  rios: { color: 'var(--color-celeste)', grosor: 0.7, opacidad: 0.35 },
  cuenca: { color: 'var(--color-azul-claro)', grosor: 1.4, opacidad: 0.9, relleno: 0.07 },
  concesiones: { color: 'var(--color-azul-claro)', grosor: 0.8, opacidad: 0.5, relleno: 0.12 },
  rutas: { color: 'var(--color-neutro)', grosor: 0.7, opacidad: 0.45 },
  gasoductos: { color: 'var(--color-celeste)', grosor: 1, opacidad: 0.75 },
  ductos: { color: 'var(--color-oro)', grosor: 1.3, opacidad: 0.95 },
};

const ESTILO_PUNTO: Record<PuntosMapa, { color: string; radio: number; opacidad: number }> = {
  // Los pozos vienen agrupados: cada punto es un racimo, no un pozo suelto.
  pozos: { color: 'var(--color-oro)', radio: 1, opacidad: 0.5 },
  localidades: { color: 'var(--color-neutro)', radio: 0.8, opacidad: 0.4 },
  terminales: { color: 'var(--color-celeste)', radio: 2, opacidad: 0.9 },
  refinerias: { color: 'var(--color-baja)', radio: 2.4, opacidad: 1 },
};

const ORDEN_CAPAS: CapaMapa[] = [
  'provincias',
  'rios',
  'cuenca',
  'concesiones',
  'rutas',
  'gasoductos',
  'ductos',
];

const ORDEN_PUNTOS: PuntosMapa[] = ['localidades', 'pozos', 'terminales', 'refinerias'];

export interface OpcionesMapa {
  className?: string;
  etiqueta?: string;
  /** Qué capas entran. Sin esto entran todas menos las localidades. */
  capas?: CapaMapa[];
  puntos?: PuntosMapa[];
  /** La capa que manda: se dibuja más gruesa y el resto baja a fondo. */
  foco?: CapaMapa;
  /** El crudo corriendo por el caño. Se apaga solo con prefers-reduced-motion. */
  corriente?: boolean;
  quieto?: boolean;
  /** Rotula los puntos de estas capas —las que traen nombre en el JSON—. */
  rotulos?: PuntosMapa[];
}

/** El dibujo en sí, ya con los datos en la mano. */
export function Dibujo({
  mapa,
  className,
  etiqueta = 'Mapa de la cuenca neuquina: concesiones, oleoductos, gasoductos y rutas',
  capas = ORDEN_CAPAS,
  puntos = ['pozos', 'refinerias'],
  foco,
  corriente = true,
  quieto,
  rotulos = [],
}: OpcionesMapa & { mapa: MapaWeb }) {
  const { ancho, alto } = mapa.lienzo;
  const elegidas = ORDEN_CAPAS.filter((capa) => capas.includes(capa));

  return (
    <svg
      viewBox={`0 0 ${ancho} ${alto}`}
      className={className}
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
      role="img"
      aria-label={etiqueta}
    >
      {elegidas.map((capa) => {
        const base = ESTILO[capa];
        // El foco no cambia el color, cambia el peso: la capa protagonista
        // engorda un poco y las demás se corren al fondo. Así el mismo mapa
        // sirve para hablar de concesiones o de ductos sin redibujarse.
        const destacada = !foco || foco === capa;
        const grosor = destacada ? base.grosor * (foco ? 1.25 : 1) : base.grosor * 0.85;
        const opacidad = destacada ? base.opacidad : base.opacidad * 0.4;
        // La corriente va encima y no en el trazo mismo: si se puntea la línea,
        // el caño se corta. Así abajo queda el ducto entero y arriba pasa algo.
        const anima = corriente && !quieto && destacada && (capa === 'ductos' || capa === 'gasoductos');

        return (
          <g key={capa}>
            {(mapa.capas[capa] ?? []).map((traza, indice) => (
              <path
                key={indice}
                d={traza}
                stroke={base.color}
                strokeWidth={grosor}
                opacity={opacidad}
                fill={base.relleno ? base.color : 'none'}
                fillOpacity={base.relleno ? base.relleno * (destacada ? 1 : 0.5) : undefined}
              />
            ))}
            {anima ? (
              <g className="anima-corriente">
                {(mapa.capas[capa] ?? []).map((traza, indice) => (
                  <path
                    key={indice}
                    d={traza}
                    stroke="var(--color-texto)"
                    strokeWidth={grosor * 0.55}
                    opacity={0.5}
                    fill="none"
                  />
                ))}
              </g>
            ) : null}
          </g>
        );
      })}

      {ORDEN_PUNTOS.filter((capa) => puntos.includes(capa)).map((capa) => {
        const estilo = ESTILO_PUNTO[capa];
        return (
          <g key={capa}>
            {(mapa.puntos[capa] ?? []).map((punto, indice) => (
              <circle
                key={indice}
                cx={punto.x}
                cy={punto.y}
                r={estilo.radio}
                fill={estilo.color}
                opacity={estilo.opacidad}
              />
            ))}
            {rotulos.includes(capa)
              ? (mapa.puntos[capa] ?? [])
                  .filter((punto) => punto.nombre)
                  .map((punto, indice) => (
                    <text
                      key={`r${indice}`}
                      x={punto.x + 4}
                      y={punto.y + 2.5}
                      fill="var(--color-texto-suave)"
                      fontSize={6}
                      opacity={0.75}
                      style={{ fontFamily: 'var(--font-mono)' }}
                    >
                      {punto.nombre}
                    </text>
                  ))
              : null}
          </g>
        );
      })}
    </svg>
  );
}

/** La leyenda, para cuando el mapa es el contenido y no la decoración.
 *
 *  Toma los colores de la misma tabla que el dibujo, así que no hay forma de
 *  que la muestra diga una cosa y el trazo otra. */
export function LeyendaMapa({
  capas = ['concesiones', 'ductos', 'gasoductos', 'rutas'],
  puntos = ['pozos', 'refinerias'],
  className,
}: {
  capas?: CapaMapa[];
  puntos?: PuntosMapa[];
  className?: string;
}) {
  const nombres: Record<CapaMapa | PuntosMapa, string> = {
    provincias: 'Límites provinciales',
    rios: 'Ríos',
    cuenca: 'Cuenca neuquina',
    concesiones: 'Áreas concesionadas',
    rutas: 'Rutas nacionales',
    gasoductos: 'Gasoductos troncales',
    ductos: 'Oleoductos y poliductos',
    refinerias: 'Refinerías',
    terminales: 'Terminales',
    localidades: 'Localidades',
    pozos: 'Racimos de pozos',
  };

  return (
    <ul className={`space-y-2 text-xs text-texto-suave ${className ?? ''}`}>
      {capas.map((capa) => (
        <li key={capa} className="flex items-center gap-2.5">
          <svg width={18} height={8} aria-hidden className="shrink-0">
            <path
              d="M0 4 H18"
              stroke={ESTILO[capa].color}
              strokeWidth={Math.max(1.4, ESTILO[capa].grosor * 1.4)}
              opacity={ESTILO[capa].opacidad}
            />
          </svg>
          {nombres[capa]}
        </li>
      ))}
      {puntos.map((capa) => (
        <li key={capa} className="flex items-center gap-2.5">
          <svg width={18} height={8} aria-hidden className="shrink-0">
            <circle
              cx={9}
              cy={4}
              r={Math.max(1.8, ESTILO_PUNTO[capa].radio)}
              fill={ESTILO_PUNTO[capa].color}
              opacity={ESTILO_PUNTO[capa].opacidad}
            />
          </svg>
          {nombres[capa]}
        </li>
      ))}
    </ul>
  );
}

/** El mapa completo, cargando el JSON del pipeline. */
export async function Mapa(opciones: OpcionesMapa) {
  const mapa = await cargar<MapaWeb>('mapa_web.json');
  return <Dibujo mapa={mapa} {...opciones} />;
}

/** La silueta sola: cuenca y concesiones, sin infraestructura. Para cuando el
 *  mapa es un fondo y no el tema. */
export async function MapaSilueta({ className, etiqueta }: { className?: string; etiqueta?: string }) {
  return (
    <Mapa
      className={className}
      etiqueta={etiqueta ?? 'Silueta de la cuenca neuquina con las áreas concesionadas'}
      capas={['cuenca', 'concesiones']}
      puntos={['pozos']}
      corriente={false}
    />
  );
}

/** Por dónde sale el crudo: ductos y rutas al frente, el resto de contexto. */
export async function MapaDuctos({ className, etiqueta }: { className?: string; etiqueta?: string }) {
  return (
    <Mapa
      className={className}
      etiqueta={
        etiqueta ??
        'Mapa de la cuenca con la red de oleoductos, los gasoductos troncales, las rutas nacionales y las refinerías'
      }
      foco="ductos"
      puntos={['refinerias', 'terminales', 'pozos']}
    />
  );
}
