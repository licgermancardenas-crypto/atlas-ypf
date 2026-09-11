// El mapa, dibujado con la geometría de verdad.
//
// El resto de las ilustraciones del sitio son esquemas: un balancín, un tanque,
// un buque. Este no. La silueta de la cuenca es la silueta de la cuenca, los
// ductos son los ductos, los yacimientos son los polígonos del padrón y el
// relieve es el DEM de Copernicus sombreado con el sol en el noroeste. Todo
// sale de las mismas capas que alimentan el mapa 3D del caso, simplificadas
// hasta donde el ojo no nota la diferencia a este tamaño —de un mega y medio a
// trescientos kilobytes— en pipeline/transform/map_svg.py.
//
// Por eso vive acá y no en piezas.tsx: las piezas son dibujo, esto es dato.
//
// Las convenciones son las de un mapa de papel y no las de una infografía: el
// relieve iluminado desde arriba a la izquierda, los límites políticos
// punteados, las rutas y los ductos con filete —una línea del color del fondo
// abajo y la del trazo encima, que es lo que los hace pasar por arriba de todo
// sin taparlo—, el agua en celeste y la barra de escala abajo. Lo dorado es
// siempre el hidrocarburo, como en el resto del sitio.
//
// No lleva estado ni eventos, así que es un componente de servidor: viaja como
// markup y no suma un byte de JavaScript. El único movimiento —la corriente
// adentro del ducto— es una animación de CSS, que el ajuste de "menos
// movimiento" del sistema apaga solo.

import { cargar } from '@/lib/server-data';

export type CapaMapa =
  | 'provincias'
  | 'arroyos'
  | 'rios'
  | 'cuenca'
  | 'yacimientos'
  | 'vaca_muerta'
  | 'concesiones'
  | 'areas_ypf'
  | 'rutas_provinciales'
  | 'rutas'
  | 'ferrocarril'
  | 'gasoductos'
  | 'ductos';

export type PuntosMapa = 'instalaciones' | 'pozos' | 'localidades' | 'terminales' | 'refinerias';

interface Punto {
  x: number;
  y: number;
  nombre?: string;
  /** Solo en localidades: por qué está rotulada. */
  rango?: 'capital' | 'actividad' | 'referencia';
  /** Solo en pozos: producción acumulada del racimo, de 0 a 1 y en raíz. */
  p?: number;
  /** Solo en pozos: si el racimo tiene pozos de Vaca Muerta. */
  vm?: number;
  /** Solo en localidades rotuladas: dónde poner el nombre para que no se
   *  pise con otro. Lo resuelve el pipeline, que es donde están todas las
   *  posiciones a la vez. */
  tx?: number;
  ty?: number;
  anc?: 'start' | 'middle' | 'end';
}

export interface MapaWeb {
  generado: string;
  lienzo: { ancho: number; alto: number };
  encuadre: [number, number, number, number];
  /** Kilómetros por unidad del lienzo, para la barra de escala. */
  escala_km: number;
  relieve: { archivo: string; x: number; y: number; ancho: number; alto: number } | null;
  capas: Record<CapaMapa, string[]>;
  puntos: Record<PuntosMapa, Punto[]>;
  nota: string;
}

interface Trazo {
  color: string;
  grosor: number;
  opacidad: number;
  /** Relleno, como opacidad del mismo color. Solo para las capas de área. */
  relleno?: number;
  /** El filete de abajo, como múltiplo del grosor. */
  filete?: number;
  punteado?: string;
}

// El orden de las claves es el orden de dibujo: primero el terreno, después el
// agua, después lo que el hombre le puso encima, y el hidrocarburo al final
// porque es lo que tiene que saltar.
const ESTILO: Record<CapaMapa, Trazo> = {
  provincias: { color: 'var(--color-neutro)', grosor: 0.6, opacidad: 0.5, punteado: '3 3' },
  arroyos: { color: 'var(--color-celeste)', grosor: 0.4, opacidad: 0.28 },
  rios: { color: 'var(--color-celeste)', grosor: 0.9, opacidad: 0.6 },
  cuenca: { color: 'var(--color-azul-claro)', grosor: 1.3, opacidad: 0.85, relleno: 0.06 },
  yacimientos: { color: 'var(--color-azul-claro)', grosor: 0.35, opacidad: 0.35, relleno: 0.05 },
  vaca_muerta: { color: 'var(--color-oro)', grosor: 0.4, opacidad: 0.38, relleno: 0.12 },
  concesiones: { color: 'var(--color-azul-claro)', grosor: 0.7, opacidad: 0.45 },
  areas_ypf: { color: 'var(--color-azul)', grosor: 1, opacidad: 0.95, relleno: 0.22 },
  rutas_provinciales: { color: 'var(--color-neutro)', grosor: 0.4, opacidad: 0.5 },
  rutas: { color: 'var(--color-texto-suave)', grosor: 0.8, opacidad: 0.8, filete: 2 },
  ferrocarril: { color: 'var(--color-neutro)', grosor: 0.6, opacidad: 0.7, punteado: '1 2.5' },
  gasoductos: { color: 'var(--color-celeste)', grosor: 0.9, opacidad: 0.8, filete: 2.4 },
  ductos: { color: 'var(--color-oro)', grosor: 1, opacidad: 0.95, filete: 2.6 },
};

const ESTILO_PUNTO: Record<PuntosMapa, { color: string; radio: number; opacidad: number }> = {
  instalaciones: { color: 'var(--color-neutro)', radio: 0.5, opacidad: 0.5 },
  // Los pozos vienen agrupados por yacimiento: cada punto es un racimo. El
  // radio de acá es el máximo; cada racimo lo escala por su acumulada.
  pozos: { color: 'var(--color-oro)', radio: 3.4, opacidad: 0.55 },
  localidades: { color: 'var(--color-texto-suave)', radio: 0.9, opacidad: 0.5 },
  terminales: { color: 'var(--color-celeste)', radio: 1.6, opacidad: 0.9 },
  refinerias: { color: 'var(--color-baja)', radio: 2.1, opacidad: 1 },
};

const ORDEN_CAPAS: CapaMapa[] = [
  'provincias',
  'arroyos',
  'rios',
  'cuenca',
  'yacimientos',
  'vaca_muerta',
  'concesiones',
  'areas_ypf',
  'rutas_provinciales',
  'rutas',
  'ferrocarril',
  'gasoductos',
  'ductos',
];

const ORDEN_PUNTOS: PuntosMapa[] = ['instalaciones', 'pozos', 'localidades', 'terminales', 'refinerias'];

const NOMBRES: Record<CapaMapa | PuntosMapa, string> = {
  provincias: 'Límites provinciales',
  arroyos: 'Arroyos',
  rios: 'Ríos',
  cuenca: 'Cuenca neuquina',
  yacimientos: 'Yacimientos',
  vaca_muerta: 'Yacimientos de Vaca Muerta',
  concesiones: 'Áreas concesionadas',
  areas_ypf: 'Áreas con YPF en el título',
  rutas_provinciales: 'Rutas provinciales',
  rutas: 'Rutas nacionales',
  ferrocarril: 'Ferrocarril',
  gasoductos: 'Gasoductos troncales',
  ductos: 'Oleoductos y poliductos',
  instalaciones: 'Instalaciones',
  pozos: 'Racimos de pozos',
  localidades: 'Localidades',
  terminales: 'Terminales',
  refinerias: 'Refinerías',
};

export interface OpcionesMapa {
  className?: string;
  etiqueta?: string;
  /** Qué capas entran. Sin esto entran todas. */
  capas?: CapaMapa[];
  /** Qué puntos entran. Las instalaciones no entran salvo que se las pida. */
  puntos?: PuntosMapa[];
  /** La capa que manda: se dibuja más gruesa y el resto baja a fondo. */
  foco?: CapaMapa;
  /** El crudo corriendo por el caño. Se apaga solo con prefers-reduced-motion. */
  corriente?: boolean;
  quieto?: boolean;
  /** Los nombres de las localidades que el pipeline marcó como clave. */
  rotulos?: boolean;
  /** La barra de escala y el norte, abajo. */
  escala?: boolean;
  relieve?: boolean;
  /** El filete del borde, que es lo que hace que se lea como una lámina. */
  marco?: boolean;
}

const PUNTOS_POR_DEFECTO: PuntosMapa[] = ['pozos', 'localidades', 'terminales', 'refinerias'];

// La capa de YPF queda afuera del mapa general: es una lectura de una sola
// compañía y solo tiene sentido en el módulo que habla de ella.
const CAPAS_POR_DEFECTO: CapaMapa[] = ORDEN_CAPAS.filter((capa) => capa !== 'areas_ypf');

/** El dibujo en sí, ya con los datos en la mano. */
export function Dibujo({
  mapa,
  className,
  etiqueta = 'Mapa de la cuenca neuquina: relieve, yacimientos, concesiones, oleoductos, gasoductos y rutas',
  capas = CAPAS_POR_DEFECTO,
  puntos = PUNTOS_POR_DEFECTO,
  foco,
  corriente = true,
  quieto,
  rotulos = true,
  escala = true,
  relieve = true,
  marco = true,
}: OpcionesMapa & { mapa: MapaWeb }) {
  const { ancho, alto } = mapa.lienzo;
  const elegidas = ORDEN_CAPAS.filter((capa) => capas.includes(capa));
  const sufijo = `${ancho}x${alto}`;
  // El área dibujada: el rectángulo que ocupa el marco geográfico adentro del
  // lienzo. Todo se recorta ahí, y ahí va el filete: así la ilustración se lee
  // como una lámina y no como un dibujo que se deshilacha en los bordes.
  const area = mapa.relieve ?? { x: 0, y: 0, ancho, alto };

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
      <defs>
        {/* El relieve se difumina contra los bordes: cortado en seco parecería
            una foto pegada encima del dibujo. */}
        <radialGradient id={`desvanecer-${sufijo}`} cx="50%" cy="48%" r="78%">
          <stop offset="62%" stopColor="#fff" stopOpacity={1} />
          <stop offset="100%" stopColor="#fff" stopOpacity={0} />
        </radialGradient>
        <mask id={`mascara-relieve-${sufijo}`}>
          <rect x={0} y={0} width={ancho} height={alto} fill={`url(#desvanecer-${sufijo})`} />
        </mask>
        <clipPath id={`lamina-${sufijo}`}>
          <rect x={area.x} y={area.y} width={area.ancho} height={area.alto} />
        </clipPath>
      </defs>

      <g clipPath={`url(#lamina-${sufijo})`}>

      {relieve && mapa.relieve ? (
        <image
          href={`/data/${mapa.relieve.archivo}`}
          x={mapa.relieve.x}
          y={mapa.relieve.y}
          width={mapa.relieve.ancho}
          height={mapa.relieve.alto}
          opacity={0.55}
          mask={`url(#mascara-relieve-${sufijo})`}
          preserveAspectRatio="none"
        />
      ) : null}

      {elegidas.map((capa) => {
        const base = ESTILO[capa];
        // El foco no cambia el color, cambia el peso: la capa protagonista
        // engorda un poco y las demás se corren al fondo. Así el mismo mapa
        // sirve para hablar de concesiones o de ductos sin redibujarse.
        const destacada = !foco || foco === capa;
        const grosor = destacada ? base.grosor * (foco ? 1.2 : 1) : base.grosor * 0.85;
        const opacidad = destacada ? base.opacidad : base.opacidad * 0.4;
        const trazos = mapa.capas[capa] ?? [];
        // La corriente va encima y no en el trazo mismo: si se puntea la línea,
        // el caño se corta. Así abajo queda el ducto entero y arriba pasa algo.
        const anima =
          corriente && !quieto && destacada && (capa === 'ductos' || capa === 'gasoductos');

        return (
          <g key={capa}>
            {base.filete ? (
              <g opacity={0.55}>
                {trazos.map((traza, indice) => (
                  <path
                    key={indice}
                    d={traza}
                    stroke="var(--color-fondo)"
                    strokeWidth={grosor * (base.filete ?? 1)}
                    fill="none"
                  />
                ))}
              </g>
            ) : null}
            {trazos.map((traza, indice) => (
              <path
                key={indice}
                d={traza}
                stroke={base.color}
                strokeWidth={grosor}
                strokeDasharray={base.punteado}
                opacity={opacidad}
                fill={base.relleno ? base.color : 'none'}
                fillOpacity={base.relleno ? base.relleno * (destacada ? 1 : 0.5) : undefined}
              />
            ))}
            {anima ? (
              <g className="anima-corriente">
                {trazos.map((traza, indice) => (
                  <path
                    key={indice}
                    d={traza}
                    stroke="var(--color-texto)"
                    strokeWidth={grosor * 0.5}
                    opacity={0.45}
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
        const lista = mapa.puntos[capa] ?? [];

        if (capa === 'pozos') {
          return (
            <g key={capa}>
              {lista.map((punto, indice) => (
                <circle
                  key={indice}
                  cx={punto.x}
                  cy={punto.y}
                  // Un piso de medio punto: un racimo chico tiene que verse,
                  // porque que exista ya es la información.
                  r={0.5 + (punto.p ?? 0) * estilo.radio}
                  fill={estilo.color}
                  opacity={punto.vm ? 0.6 : 0.32}
                />
              ))}
            </g>
          );
        }

        if (capa === 'localidades') {
          return (
            <g key={capa}>
              {lista.map((punto, indice) => (
                <circle
                  key={indice}
                  cx={punto.x}
                  cy={punto.y}
                  r={punto.rango ? 1.5 : estilo.radio}
                  fill={punto.rango ? 'var(--color-texto)' : estilo.color}
                  opacity={punto.rango ? 0.9 : estilo.opacidad}
                />
              ))}
            </g>
          );
        }

        return (
          <g key={capa}>
            {lista.map((punto, indice) => (
              <g key={indice}>
                {capa === 'refinerias' ? (
                  <circle
                    cx={punto.x}
                    cy={punto.y}
                    r={estilo.radio + 1.6}
                    fill={estilo.color}
                    opacity={0.18}
                  />
                ) : null}
                <circle
                  cx={punto.x}
                  cy={punto.y}
                  r={estilo.radio}
                  fill={estilo.color}
                  opacity={estilo.opacidad}
                  stroke="var(--color-fondo)"
                  strokeWidth={capa === 'refinerias' ? 0.6 : 0}
                />
              </g>
            ))}
          </g>
        );
      })}

      {rotulos && puntos.includes('localidades')
        ? (mapa.puntos.localidades ?? [])
            .filter((punto) => punto.rango)
            .map((punto, indice) => (
              <text
                key={indice}
                x={punto.x + (punto.tx ?? 2.6)}
                y={punto.y + (punto.ty ?? 1.8)}
                textAnchor={punto.anc ?? 'start'}
                fill="var(--color-texto)"
                fontSize={punto.rango === 'capital' ? 6.2 : 5.2}
                opacity={punto.rango === 'referencia' ? 0.6 : 0.85}
                stroke="var(--color-fondo)"
                strokeWidth={1.4}
                paintOrder="stroke"
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {punto.nombre}
              </text>
            ))
        : null}

      </g>

      {marco ? (
        <rect
          x={area.x}
          y={area.y}
          width={area.ancho}
          height={area.alto}
          stroke="var(--color-borde-vivo)"
          strokeWidth={1}
          fill="none"
        />
      ) : null}

      {escala ? <Escala mapa={mapa} area={area} /> : null}
    </svg>
  );
}

/** La barra de escala y el norte. Un mapa sin escala es un dibujo. */
function Escala({
  mapa,
  area,
}: {
  mapa: MapaWeb;
  area: { x: number; y: number; ancho: number; alto: number };
}) {
  const kilometros = 100;
  const largo = kilometros / mapa.escala_km;
  const x = area.x + 8;
  const y = area.y + area.alto - 10;

  return (
    <g opacity={0.75}>
      <path d={`M${x} ${y} h${largo}`} stroke="var(--color-texto-suave)" strokeWidth={1} />
      <path
        d={`M${x} ${y - 2.5} v5 M${x + largo / 2} ${y - 1.8} v3.6 M${x + largo} ${y - 2.5} v5`}
        stroke="var(--color-texto-suave)"
        strokeWidth={1}
      />
      <text
        x={x}
        y={y - 5}
        fill="var(--color-texto-suave)"
        fontSize={5.4}
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        {kilometros} km
      </text>
      <g transform={`translate(${area.x + area.ancho - 12} ${y - 4})`}>
        <path
          d="M0 4 V-8 M-2.6 -4.6 L0 -8 L2.6 -4.6"
          stroke="var(--color-texto-suave)"
          strokeWidth={1}
        />
        <text
          x={0}
          y={11}
          fill="var(--color-texto-suave)"
          fontSize={5.4}
          textAnchor="middle"
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          N
        </text>
      </g>
    </g>
  );
}

/** La leyenda, para cuando el mapa es el contenido y no la decoración.
 *
 *  Toma los colores de la misma tabla que el dibujo, así que no hay forma de
 *  que la muestra diga una cosa y el trazo otra. */
export function LeyendaMapa({
  capas = ['vaca_muerta', 'concesiones', 'ductos', 'gasoductos', 'rutas'],
  puntos = ['pozos', 'refinerias'],
  className,
}: {
  capas?: CapaMapa[];
  puntos?: PuntosMapa[];
  className?: string;
}) {
  return (
    <ul className={`space-y-2 text-xs text-texto-suave ${className ?? ''}`}>
      {capas.map((capa) => (
        <li key={capa} className="flex items-center gap-2.5">
          <svg width={18} height={8} aria-hidden className="shrink-0">
            {ESTILO[capa].relleno ? (
              <rect
                x={1}
                y={1}
                width={16}
                height={6}
                fill={ESTILO[capa].color}
                fillOpacity={Math.min(0.35, (ESTILO[capa].relleno ?? 0) * 3)}
                stroke={ESTILO[capa].color}
                strokeWidth={1}
                opacity={ESTILO[capa].opacidad + 0.2}
              />
            ) : (
              <path
                d="M0 4 H18"
                stroke={ESTILO[capa].color}
                strokeWidth={Math.max(1.4, ESTILO[capa].grosor * 1.6)}
                strokeDasharray={ESTILO[capa].punteado}
                opacity={ESTILO[capa].opacidad}
              />
            )}
          </svg>
          {NOMBRES[capa]}
        </li>
      ))}
      {puntos.map((capa) => (
        <li key={capa} className="flex items-center gap-2.5">
          <svg width={18} height={8} aria-hidden className="shrink-0">
            <circle
              cx={9}
              cy={4}
              r={capa === 'pozos' ? 2.6 : Math.max(1.8, ESTILO_PUNTO[capa].radio)}
              fill={ESTILO_PUNTO[capa].color}
              opacity={ESTILO_PUNTO[capa].opacidad}
            />
          </svg>
          {NOMBRES[capa]}
          {capa === 'pozos' ? <span className="text-texto-tenue"> · área por acumulada</span> : null}
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

/** La silueta sola: relieve, cuenca y concesiones, sin infraestructura. Para
 *  cuando el mapa es un fondo y no el tema. */
export async function MapaSilueta({
  className,
  etiqueta,
}: {
  className?: string;
  etiqueta?: string;
}) {
  return (
    <Mapa
      className={className}
      etiqueta={etiqueta ?? 'Silueta de la cuenca neuquina con las áreas concesionadas'}
      capas={['cuenca', 'concesiones', 'vaca_muerta']}
      puntos={['pozos']}
      corriente={false}
      rotulos={false}
      escala={false}
      marco={false}
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
      puntos={['pozos', 'localidades', 'terminales', 'refinerias']}
    />
  );
}
