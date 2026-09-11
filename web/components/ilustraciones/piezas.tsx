// Las piezas con las que se dibuja todo el sitio.
//
// La idea es la de un juego de bloques: un barril, un balancín, un mechero, un
// tanque, un buque. Cada pieza se dibuja una sola vez, en su propio sistema de
// coordenadas y con el origen abajo al centro, y las escenas las combinan con
// transform. Así una refinería y una estación de servicio comparten el mismo
// tanque, y si mañana el tanque mejora, mejoran las dos.
//
// Tres reglas para que todo se lea como una familia:
//   · el trazo lleva la estructura y el relleno solo aparece donde hay materia
//     —el crudo, la llama, el agua—, nunca en el metal;
//   · la profundidad se hace con opacidad, no con color: fondo 0,35, medio 0,6,
//     frente 1;
//   · el dorado es siempre el producto o la energía. Si algo brilla, es porque
//     vale plata.

export const TRAZO = 'var(--color-azul-claro)';
export const ACENTO = 'var(--color-oro)';
export const SUAVE = 'var(--color-neutro)';
export const AGUA = 'var(--color-celeste)';
export const VERDE = 'var(--color-alza)';

interface Pieza {
  x?: number;
  y?: number;
  escala?: number;
  opacidad?: number;
  className?: string;
}

/** Ubica una pieza: origen abajo al centro, escala uniforme. */
function Ubicar({
  x = 0,
  y = 0,
  escala = 1,
  opacidad = 1,
  children,
}: Pieza & { children: React.ReactNode }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${escala})`} opacity={opacidad}>
      {children}
    </g>
  );
}

// --------------------------------------------------------------------------- //
// El barril
// --------------------------------------------------------------------------- //
/** El tambor de 42 galones: la unidad en la que se cuenta este negocio.
 *
 *  `llenado` va de 0 a 1 y pinta el crudo adentro. Sirve de ilustración y de
 *  gráfico: una fila de barriles medio llenos dice una proporción sin ejes. */
export function Barril({
  llenado = 0,
  brillo = true,
  ...pieza
}: Pieza & { llenado?: number; brillo?: boolean }) {
  const alto = 34;
  const nivel = Math.max(0, Math.min(1, llenado));
  const idClip = `barril-${Math.round(nivel * 1000)}-${pieza.x ?? 0}-${pieza.y ?? 0}`;

  return (
    <Ubicar {...pieza}>
      <defs>
        <clipPath id={idClip}>
          <path d="M-11 -32 h22 v30 a11 4 0 0 1 -22 0 z" />
        </clipPath>
      </defs>

      {nivel > 0 ? (
        <g clipPath={`url(#${idClip})`}>
          <rect
            x={-12}
            y={-2 - alto * nivel}
            width={24}
            height={alto * nivel}
            fill={ACENTO}
            opacity={0.55}
          />
          <ellipse cx={0} cy={-2 - alto * nivel} rx={11} ry={3.4} fill={ACENTO} opacity={0.8} />
        </g>
      ) : null}

      {/* cuerpo */}
      <path d="M-11 -32 v30 a11 4 0 0 0 22 0 v-30" stroke={TRAZO} strokeWidth={1.5} fill="none" />
      <ellipse cx={0} cy={-32} rx={11} ry={4} stroke={TRAZO} strokeWidth={1.5} fill="none" />
      {/* los dos aros del tambor */}
      <path d="M-11 -24 a11 4 0 0 0 22 0" stroke={TRAZO} strokeWidth={1} opacity={0.7} fill="none" />
      <path d="M-11 -12 a11 4 0 0 0 22 0" stroke={TRAZO} strokeWidth={1} opacity={0.7} fill="none" />
      {brillo ? (
        <path d="M-6.5 -29 v24" stroke={TRAZO} strokeWidth={1} opacity={0.35} fill="none" />
      ) : null}
    </Ubicar>
  );
}

/** El mismo barril, acostado: sirve para pilas y para el pie de una escena. */
export function BarrilTumbado(pieza: Pieza) {
  return (
    <Ubicar {...pieza}>
      <path d="M-16 -11 h32 a4 11 0 0 1 0 22 h-32 a4 11 0 0 1 0 -22 z" stroke={TRAZO} strokeWidth={1.4} fill="none" />
      <ellipse cx={-16} cy={0} rx={4} ry={11} stroke={TRAZO} strokeWidth={1.4} fill="none" />
      <path d="M-8 -10.6 v21.2 M4 -10.6 v21.2" stroke={TRAZO} strokeWidth={1} opacity={0.6} />
    </Ubicar>
  );
}

/** La gota: cae sola si se le pasa `anima`. */
export function Gota({ anima = false, ...pieza }: Pieza & { anima?: boolean }) {
  return (
    <Ubicar {...pieza}>
      <g className={anima ? 'anima-goteo' : undefined} style={{ transformOrigin: 'center' }}>
        <path d="M0 -8 C 4.5 -2.5, 5.5 1, 0 1 C -5.5 1, -4.5 -2.5, 0 -8 Z" fill={ACENTO} opacity={0.9} />
      </g>
    </Ubicar>
  );
}

// --------------------------------------------------------------------------- //
// Upstream
// --------------------------------------------------------------------------- //
/** El balancín. La cabeza se mueve sola: es lo único que se mueve en un
 *  yacimiento y es lo que todo el mundo reconoce como "petróleo". */
export function Balancin({ anima = true, ...pieza }: Pieza & { anima?: boolean }) {
  return (
    <Ubicar {...pieza}>
      {/* base y torre */}
      <path d="M-16 0 H16" stroke={TRAZO} strokeWidth={1.6} />
      <path d="M-9 0 L0 -26 L9 0" stroke={TRAZO} strokeWidth={1.6} fill="none" />
      <path d="M-5 -13 H5" stroke={TRAZO} strokeWidth={1} opacity={0.7} />
      {/* motor */}
      <rect x={-24} y={-9} width={12} height={9} rx={1.5} stroke={TRAZO} strokeWidth={1.2} fill="none" />

      {/* el brazo, que oscila sobre el eje */}
      <g className={anima ? 'anima-balanceo' : undefined} style={{ transformOrigin: '0px -26px' }}>
        <path d="M-22 -26 H26" stroke={ACENTO} strokeWidth={2.6} strokeLinecap="round" />
        {/* contrapeso */}
        <circle cx={-24} cy={-26} r={5} fill={ACENTO} opacity={0.75} />
        {/* cabeza de caballo */}
        <path d="M26 -26 q6 0 6 6 q0 5 -5 6" stroke={ACENTO} strokeWidth={2.2} fill="none" />
        <path d="M27 -14 V -6" stroke={TRAZO} strokeWidth={1.2} />
      </g>

      <circle cx={0} cy={-26} r={3} fill="var(--color-superficie)" stroke={ACENTO} strokeWidth={1.5} />
      {/* la varilla que entra al pozo */}
      <path d="M27 -6 V 0" stroke={TRAZO} strokeWidth={1.2} />
      <path d="M22 0 H32" stroke={TRAZO} strokeWidth={1.4} />
    </Ubicar>
  );
}

/** La torre de perforación, con el pozo horizontal punteado: en shale, la
 *  diferencia no la hace la torre sino ese tramo de rama. */
export function TorrePerforacion({ rama = true, ...pieza }: Pieza & { rama?: boolean }) {
  return (
    <Ubicar {...pieza}>
      <path d="M-14 0 L0 -50 L14 0" stroke={TRAZO} strokeWidth={1.6} fill="none" />
      <path d="M-10.5 -12 H10.5 M-8 -24 H8 M-5.5 -36 H5.5" stroke={TRAZO} strokeWidth={1} opacity={0.7} />
      <path d="M-8 -12 L8 -24 M-8 -24 L8 -12 M-5.5 -36 L5.5 -24" stroke={TRAZO} strokeWidth={0.8} opacity={0.4} />
      <path d="M0 -50 V-56" stroke={TRAZO} strokeWidth={1.5} />
      <rect x={-4} y={-58} width={8} height={3} rx={1} stroke={ACENTO} strokeWidth={1.3} fill="none" />
      <path d="M-18 0 H18" stroke={TRAZO} strokeWidth={1.6} />
      {rama ? (
        <path d="M0 0 V14 q0 6 8 6 H34" stroke={ACENTO} strokeWidth={1.4} strokeDasharray="3 3" fill="none" opacity={0.9} />
      ) : null}
    </Ubicar>
  );
}

/** El árbol de navidad: la boca del pozo cuando ya no hay torre. */
export function BocaDePozo(pieza: Pieza) {
  return (
    <Ubicar {...pieza}>
      <path d="M-8 0 H8" stroke={TRAZO} strokeWidth={1.5} />
      <path d="M0 0 V-14" stroke={TRAZO} strokeWidth={1.8} />
      <path d="M-6 -14 H6 V-20 H-6 Z" stroke={TRAZO} strokeWidth={1.3} fill="none" />
      <path d="M-9 -9 H9" stroke={TRAZO} strokeWidth={1.2} />
      <circle cx={0} cy={-23} r={2.4} stroke={ACENTO} strokeWidth={1.3} fill="none" />
    </Ubicar>
  );
}

/** El mechero: la llama titila sola. */
export function Mechero({ anima = true, ...pieza }: Pieza & { anima?: boolean }) {
  return (
    <Ubicar {...pieza}>
      <path d="M0 0 V-30" stroke={TRAZO} strokeWidth={1.5} />
      <path d="M-4 0 H4" stroke={TRAZO} strokeWidth={1.4} />
      <path d="M-3 -10 H3 M-3 -20 H3" stroke={TRAZO} strokeWidth={0.9} opacity={0.6} />
      <g className={anima ? 'anima-titileo' : undefined} style={{ transformOrigin: '0px -30px' }}>
        <path d="M0 -44 C 5 -37, 5 -30, 0 -30 C -5 -30, -5 -37, 0 -44 Z" fill={ACENTO} opacity={0.85} />
        <path d="M0 -38 C 2.5 -34.5, 2.5 -31, 0 -31 C -2.5 -31, -2.5 -34.5, 0 -38 Z" fill="var(--color-texto)" opacity={0.35} />
      </g>
    </Ubicar>
  );
}

// --------------------------------------------------------------------------- //
// Midstream y downstream
// --------------------------------------------------------------------------- //
/** La torre de destilación. */
export function TorreDestilacion({ alto = 54, ...pieza }: Pieza & { alto?: number }) {
  return (
    <Ubicar {...pieza}>
      <path d={`M-10 0 V-${alto} h20 V0`} stroke={TRAZO} strokeWidth={1.6} fill="none" />
      <path d={`M-10 -${alto * 0.32} h20 M-10 -${alto * 0.62} h20`} stroke={TRAZO} strokeWidth={1} opacity={0.6} />
      <path d={`M0 -${alto} V-${alto + 8}`} stroke={TRAZO} strokeWidth={1.3} />
      <path d={`M-10 -${alto} q10 -7 20 0`} stroke={TRAZO} strokeWidth={1.3} fill="none" />
      <path d={`M-14 -${alto * 0.5} H-10 M10 -${alto * 0.72} H14`} stroke={TRAZO} strokeWidth={1.1} opacity={0.75} />
    </Ubicar>
  );
}

/** El tanque de almacenamiento, con techo flotante y nivel de crudo. */
export function Tanque({ llenado = 0.6, ...pieza }: Pieza & { llenado?: number }) {
  const alto = 26;
  const nivel = Math.max(0, Math.min(1, llenado));
  return (
    <Ubicar {...pieza}>
      {nivel > 0 ? (
        <rect x={-17} y={-alto * nivel} width={34} height={alto * nivel} fill={ACENTO} opacity={0.18} />
      ) : null}
      <path d={`M-17 0 V-${alto}`} stroke={TRAZO} strokeWidth={1.5} />
      <path d={`M17 0 V-${alto}`} stroke={TRAZO} strokeWidth={1.5} />
      <ellipse cx={0} cy={-alto} rx={17} ry={5} stroke={TRAZO} strokeWidth={1.5} fill="none" />
      <ellipse cx={0} cy={0} rx={17} ry={5} stroke={TRAZO} strokeWidth={1.5} fill="none" />
      <ellipse cx={0} cy={-alto * nivel} rx={17} ry={5} stroke={ACENTO} strokeWidth={1.2} fill="none" opacity={0.8} />
      <path d="M-6 -31 h12" stroke={TRAZO} strokeWidth={1.1} opacity={0.7} />
    </Ubicar>
  );
}

/** Un tramo de ducto, con sus soportes. */
export function Ducto({ largo = 48, ...pieza }: Pieza & { largo?: number }) {
  const soportes = Array.from({ length: Math.max(2, Math.round(largo / 22)) });
  return (
    <Ubicar {...pieza}>
      <path d={`M0 0 H${largo}`} stroke={ACENTO} strokeWidth={2.2} />
      {soportes.map((_, indice) => {
        const x = (largo / (soportes.length - 1)) * indice;
        return <path key={indice} d={`M${x} 0 v7`} stroke={TRAZO} strokeWidth={1.1} opacity={0.7} />;
      })}
      <path d={`M${largo * 0.35} -4 v8 M${largo * 0.7} -4 v8`} stroke={ACENTO} strokeWidth={1} opacity={0.55} />
    </Ubicar>
  );
}

/** El surtidor: el único punto donde el negocio toca a una persona. */
export function Surtidor(pieza: Pieza) {
  return (
    <Ubicar {...pieza}>
      <path d="M-14 0 V-40 h28 V0" stroke={TRAZO} strokeWidth={1.6} fill="none" />
      <path d="M-14 0 H14" stroke={TRAZO} strokeWidth={1.6} />
      <rect x={-9} y={-34} width={18} height={13} rx={1.5} stroke={ACENTO} strokeWidth={1.3} fill="none" />
      <path d="M-8 -14 h16" stroke={TRAZO} strokeWidth={1} opacity={0.6} />
      <path d="M14 -34 h7 v22" stroke={TRAZO} strokeWidth={1.3} fill="none" />
      <path d="M21 -12 q-5 0 -5 -4" stroke={ACENTO} strokeWidth={1.5} fill="none" />
    </Ubicar>
  );
}

/** El camión cisterna. */
export function Camion(pieza: Pieza) {
  return (
    <Ubicar {...pieza}>
      <path d="M-30 -8 h34 a7 7 0 0 1 0 14 h-34 a7 7 0 0 1 0 -14 z" stroke={TRAZO} strokeWidth={1.4} fill="none" />
      <path d="M-18 -8 v14 M-6 -8 v14" stroke={TRAZO} strokeWidth={0.9} opacity={0.55} />
      <path d="M6 6 h6 v-9 h8 l5 9 h3" stroke={TRAZO} strokeWidth={1.4} fill="none" />
      <circle cx={-20} cy={8} r={4} stroke={TRAZO} strokeWidth={1.3} fill="none" />
      <circle cx={16} cy={8} r={4} stroke={TRAZO} strokeWidth={1.3} fill="none" />
    </Ubicar>
  );
}

// --------------------------------------------------------------------------- //
// Gas, agua y viento
// --------------------------------------------------------------------------- //
/** El buque metanero, con sus tanques esféricos. Se mece si se le pide. */
export function Buque({ anima = true, ...pieza }: Pieza & { anima?: boolean }) {
  return (
    <Ubicar {...pieza}>
      <g className={anima ? 'anima-oleaje' : undefined}>
        <path d="M-54 0 h108 l-11 13 H-43 Z" stroke={TRAZO} strokeWidth={1.6} fill="none" />
        <circle cx={-28} cy={-11} r={10} stroke={TRAZO} strokeWidth={1.4} fill="none" />
        <circle cx={0} cy={-11} r={10} stroke={TRAZO} strokeWidth={1.4} fill="none" />
        <circle cx={28} cy={-11} r={10} stroke={ACENTO} strokeWidth={1.4} fill="none" />
        <path d="M46 0 v-18 h10 V0" stroke={TRAZO} strokeWidth={1.4} fill="none" />
        <path d="M48 -18 v-6" stroke={TRAZO} strokeWidth={1.1} />
      </g>
    </Ubicar>
  );
}

/** El molino, girando. */
export function Molino({ anima = true, ...pieza }: Pieza & { anima?: boolean }) {
  return (
    <Ubicar {...pieza}>
      <path d="M-5 0 L-1.6 -46 h3.2 L5 0 Z" stroke={TRAZO} strokeWidth={1.4} fill="none" />
      <g className={anima ? 'anima-giro' : undefined} style={{ transformOrigin: '0px -46px' }}>
        <path d="M0 -46 V-76" stroke={ACENTO} strokeWidth={2} strokeLinecap="round" />
        <path d="M0 -46 L26 -31" stroke={ACENTO} strokeWidth={2} strokeLinecap="round" />
        <path d="M0 -46 L-26 -31" stroke={ACENTO} strokeWidth={2} strokeLinecap="round" />
      </g>
      <circle cx={0} cy={-46} r={2.8} fill="var(--color-superficie)" stroke={ACENTO} strokeWidth={1.4} />
    </Ubicar>
  );
}

/** Paneles solares en perspectiva. */
export function PanelSolar(pieza: Pieza) {
  return (
    <Ubicar {...pieza}>
      <path d="M-26 0 L-8 -24 H34 L14 0 Z" stroke={TRAZO} strokeWidth={1.5} fill={AGUA} fillOpacity={0.08} />
      <path d="M-17 -12 H24 M-8 -24 L-16 0 M8 -24 L1 0 M22 -24 L15 0" stroke={TRAZO} strokeWidth={0.9} opacity={0.55} />
      <path d="M-14 0 v7 M10 0 v7" stroke={TRAZO} strokeWidth={1.3} />
    </Ubicar>
  );
}

/** El sol, para las escenas de renovables. */
export function Sol(pieza: Pieza) {
  return (
    <Ubicar {...pieza}>
      <circle cx={0} cy={0} r={9} stroke={ACENTO} strokeWidth={1.5} fill="none" />
      <path d="M0 -16 V-22 M0 16 V22 M-16 0 H-22 M16 0 H22 M-11 -11 L-15 -15 M11 11 L15 15 M11 -11 L15 -15 M-11 11 L-15 15"
        stroke={ACENTO} strokeWidth={1.2} opacity={0.8} />
    </Ubicar>
  );
}

// --------------------------------------------------------------------------- //
// Terreno y fondo
// --------------------------------------------------------------------------- //
/** La meseta patagónica: dos siluetas y una línea de horizonte. */
export function Meseta({ opacidad = 0.45 }: { opacidad?: number }) {
  return (
    <g opacity={opacidad}>
      <path d="M0 118 C 34 104, 62 108, 88 118" stroke={SUAVE} strokeWidth={1.2} fill="none" />
      <path d="M108 118 C 142 98, 184 104, 240 116" stroke={SUAVE} strokeWidth={1.2} fill="none" opacity={0.7} />
      <path d="M0 118 H240" stroke={SUAVE} strokeWidth={1} />
    </g>
  );
}

/** El agua, para las escenas de puerto. */
export function Agua({ y = 124 }: { y?: number }) {
  return (
    <g opacity={0.4}>
      <path d={`M0 ${y} H240`} stroke={AGUA} strokeWidth={1} />
      <path d={`M10 ${y + 7} q9 -4 18 0 t18 0 t18 0 t18 0`} stroke={AGUA} strokeWidth={1} fill="none" />
      <path d={`M130 ${y + 13} q9 -4 18 0 t18 0 t18 0 t18 0`} stroke={AGUA} strokeWidth={1} fill="none" opacity={0.7} />
    </g>
  );
}

// --------------------------------------------------------------------------- //
// Fondo: lo que da profundidad
// --------------------------------------------------------------------------- //
/** El cielo de la cuenca: un degradado tenue y algunas estrellas.
 *
 *  El sitio es oscuro y las escenas quedaban flotando sobre el fondo plano de
 *  la tarjeta. Un cielo apenas más claro arriba ancla el dibujo sin competir
 *  con nada: es el mismo truco de una acuarela, el papel se ve igual pero el
 *  objeto deja de estar en el aire.
 */
export function Cielo({ id = 'cielo', estrellas = true }: { id?: string; estrellas?: boolean }) {
  return (
    <g>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={TRAZO} stopOpacity={0.1} />
          <stop offset="70%" stopColor={TRAZO} stopOpacity={0.02} />
          <stop offset="100%" stopColor={TRAZO} stopOpacity={0} />
        </linearGradient>
      </defs>
      <rect x={0} y={0} width={240} height={122} fill={`url(#${id})`} />
      {estrellas ? (
        <g opacity={0.5}>
          {[
            [26, 22], [58, 14], [104, 26], [152, 16], [196, 28], [224, 18], [80, 34], [178, 40],
          ].map(([x, y], indice) => (
            <circle key={indice} cx={x} cy={y} r={indice % 3 === 0 ? 1.2 : 0.8} fill={TRAZO} />
          ))}
        </g>
      ) : null}
    </g>
  );
}

/** Los cerros del fondo: dos capas, la de atrás más apagada que la de adelante. */
export function Cerros({ opacidad = 1 }: { opacidad?: number }) {
  return (
    <g opacity={opacidad}>
      <path
        d="M-4 108 L28 84 L52 98 L76 78 L104 100 L128 88 L160 104 L188 86 L216 102 L244 92 V122 H-4 Z"
        fill={SUAVE}
        fillOpacity={0.1}
        stroke={SUAVE}
        strokeWidth={0.9}
        strokeOpacity={0.35}
      />
      <path
        d="M-4 116 L36 100 L62 110 L96 96 L124 110 L158 98 L196 112 L244 104 V124 H-4 Z"
        fill={SUAVE}
        fillOpacity={0.16}
        stroke={SUAVE}
        strokeWidth={1}
        strokeOpacity={0.45}
      />
    </g>
  );
}

// --------------------------------------------------------------------------- //
// Más cosas del yacimiento
// --------------------------------------------------------------------------- //
/** Una pila de barriles: tres abajo, dos arriba. Es la imagen del stock. */
export function PilaBarriles({ llenado = 0.7, ...pieza }: Pieza & { llenado?: number }) {
  return (
    <Ubicar {...pieza}>
      <Barril x={-24} y={0} escala={0.78} llenado={llenado} />
      <Barril x={0} y={0} escala={0.78} llenado={Math.max(0, llenado - 0.15)} />
      <Barril x={24} y={0} escala={0.78} llenado={Math.max(0, llenado - 0.3)} />
      <Barril x={-12} y={-27} escala={0.78} llenado={Math.min(1, llenado + 0.2)} opacidad={0.95} />
      <Barril x={12} y={-27} escala={0.78} llenado={llenado} opacidad={0.95} />
    </Ubicar>
  );
}

/** El silo de arena: sin arena no hay fractura, y la arena viaja en estos. */
export function SiloArena(pieza: Pieza) {
  return (
    <Ubicar {...pieza}>
      <path d="M-11 0 V-30 h22 V0" stroke={TRAZO} strokeWidth={1.5} fill="none" />
      <path d="M-11 -30 L0 -38 L11 -30" stroke={TRAZO} strokeWidth={1.3} fill="none" />
      <path d="M-11 0 L-5 10 h10 L11 0" stroke={TRAZO} strokeWidth={1.3} fill="none" />
      <path d="M-11 -18 h22" stroke={TRAZO} strokeWidth={0.9} opacity={0.55} />
      <path d="M-4 10 v5 h8 v-5" stroke={ACENTO} strokeWidth={1.2} fill="none" />
    </Ubicar>
  );
}

/** La bomba de fractura: el camión que mete el agua a presión. */
export function BombaFractura(pieza: Pieza) {
  return (
    <Ubicar {...pieza}>
      <path d="M-26 0 h30 v-14 h-30 z" stroke={TRAZO} strokeWidth={1.4} fill="none" />
      <path d="M-20 -14 v-6 h8 v6" stroke={TRAZO} strokeWidth={1.1} fill="none" />
      <path d="M4 0 h8 v-10 h6 l4 10 h2" stroke={TRAZO} strokeWidth={1.3} fill="none" />
      <path d="M-26 -7 h30" stroke={TRAZO} strokeWidth={0.8} opacity={0.5} />
      <circle cx={-16} cy={3} r={3.4} stroke={TRAZO} strokeWidth={1.2} fill="none" />
      <circle cx={14} cy={3} r={3.4} stroke={TRAZO} strokeWidth={1.2} fill="none" />
      <path d="M-30 -4 h-8" stroke={ACENTO} strokeWidth={1.6} />
    </Ubicar>
  );
}

/** La pileta de agua: el otro insumo de la fractura, y el que se discute. */
export function PiletaAgua(pieza: Pieza) {
  return (
    <Ubicar {...pieza}>
      <path d="M-26 0 L-20 -12 H20 L26 0 Z" stroke={TRAZO} strokeWidth={1.3} fill={AGUA} fillOpacity={0.14} />
      <path d="M-19 -6 q8 -3 16 0 t16 0" stroke={AGUA} strokeWidth={1} opacity={0.7} fill="none" />
    </Ubicar>
  );
}

// --------------------------------------------------------------------------- //
// Gas
// --------------------------------------------------------------------------- //
/** El tanque esférico de GNL, con su estructura de patas. */
export function DomoGNL({ llenado = 0.55, ...pieza }: Pieza & { llenado?: number }) {
  const radio = 16;
  const id = `domo-${pieza.x ?? 0}-${pieza.y ?? 0}`;
  return (
    <Ubicar {...pieza}>
      <defs>
        <clipPath id={id}>
          <circle cx={0} cy={-radio - 6} r={radio} />
        </clipPath>
      </defs>
      <g clipPath={`url(#${id})`}>
        <rect
          x={-radio}
          y={-6 - 2 * radio * llenado}
          width={radio * 2}
          height={2 * radio * llenado}
          fill={AGUA}
          opacity={0.22}
        />
      </g>
      <circle cx={0} cy={-radio - 6} r={radio} stroke={TRAZO} strokeWidth={1.5} fill="none" />
      <path d={`M-11 -6 L-13 0 M11 -6 L13 0 M0 -6 V0`} stroke={TRAZO} strokeWidth={1.2} />
      <path d="M-15 0 H15" stroke={TRAZO} strokeWidth={1.3} />
      <path d={`M0 -${radio * 2 + 6} v-6`} stroke={ACENTO} strokeWidth={1.2} />
    </Ubicar>
  );
}

/** El tren de licuefacción: módulos, cañería y torre de proceso. */
export function TrenGNL(pieza: Pieza) {
  return (
    <Ubicar {...pieza}>
      <path d="M-34 0 V-22 h68 V0" stroke={TRAZO} strokeWidth={1.5} fill="none" />
      <path d="M-34 -22 h68" stroke={TRAZO} strokeWidth={1} opacity={0.5} />
      {[-24, -8, 8, 24].map((x) => (
        <path key={x} d={`M${x} -22 V-34`} stroke={TRAZO} strokeWidth={1.1} opacity={0.8} />
      ))}
      <path d="M-28 -34 h56" stroke={TRAZO} strokeWidth={1.2} />
      <path d="M-18 -34 V-46 M6 -34 V-52" stroke={TRAZO} strokeWidth={1.3} />
      <path d="M-24 -46 h12 M0 -52 h12" stroke={TRAZO} strokeWidth={1.1} opacity={0.7} />
      <path d="M-34 -10 h-10 M34 -10 h10" stroke={ACENTO} strokeWidth={1.6} />
      <path d="M-14 0 v8 h28 v-8" stroke={TRAZO} strokeWidth={1.1} opacity={0.6} fill="none" />
    </Ubicar>
  );
}

// --------------------------------------------------------------------------- //
// Papel y oficina
// --------------------------------------------------------------------------- //
/** El libro mayor, abierto: dos páginas, el lomo y las columnas. */
export function LibroAbierto({ ...pieza }: Pieza) {
  return (
    <Ubicar {...pieza}>
      {/* las dos hojas, con la curva del papel */}
      <path
        d="M-52 0 C -34 -10, -14 -10, 0 -4 C 14 -10, 34 -10, 52 0 L52 -44 C 34 -54, 14 -54, 0 -48 C -14 -54, -34 -54, -52 -44 Z"
        stroke={TRAZO}
        strokeWidth={1.5}
        fill="var(--color-superficie-alta)"
        fillOpacity={0.45}
      />
      <path d="M0 -48 V-4" stroke={TRAZO} strokeWidth={1.3} opacity={0.8} />
      {/* renglones: a la izquierda el texto, a la derecha los números */}
      {[-38, -30, -22, -14].map((y) => (
        <path key={y} d={`M-44 ${y} h34`} stroke={TRAZO} strokeWidth={0.85} opacity={0.45} />
      ))}
      {[-38, -30, -22].map((y) => (
        <path key={y} d={`M10 ${y} h24`} stroke={TRAZO} strokeWidth={0.85} opacity={0.45} />
      ))}
      <path d="M10 -14 h34" stroke={ACENTO} strokeWidth={1.3} />
      <path d="M38 -38 h8 M38 -30 h8 M38 -22 h8" stroke={ACENTO} strokeWidth={0.85} opacity={0.7} />
    </Ubicar>
  );
}

/** Un organigrama: tres cajas y sus líneas. Dice "corporativo" mejor que un
 *  edificio, que podría ser cualquier cosa. */
export function Organigrama(pieza: Pieza) {
  return (
    <Ubicar {...pieza}>
      <path d="M-14 -46 h28 v14 h-28 z" stroke={ACENTO} strokeWidth={1.4} fill={ACENTO} fillOpacity={0.12} />
      <path d="M0 -32 V-22 M-30 -22 H30 M-30 -22 V-14 M0 -22 V-14 M30 -22 V-14" stroke={TRAZO} strokeWidth={1.1} />
      {[-30, 0, 30].map((x) => (
        <path
          key={x}
          d={`M${x - 12} -14 h24 v12 h-24 z`}
          stroke={TRAZO}
          strokeWidth={1.3}
          fill="var(--color-superficie-alta)"
          fillOpacity={0.4}
        />
      ))}
    </Ubicar>
  );
}

/** La marquesina de la estación: la única pieza de marca que se ve desde la
 *  calle, y la que le da nombre al efecto de los paneles del sitio. */
export function Marquesina(pieza: Pieza) {
  return (
    <Ubicar {...pieza}>
      <path d="M-34 -26 h68 v10 h-68 z" stroke={TRAZO} strokeWidth={1.5} fill={TRAZO} fillOpacity={0.14} />
      <path d="M-28 -16 V0 M28 -16 V0" stroke={TRAZO} strokeWidth={1.4} />
      <path d="M-22 -23 h16" stroke={ACENTO} strokeWidth={2.2} />
      <path d="M-22 -19.5 h10" stroke={AGUA} strokeWidth={1.6} opacity={0.9} />
    </Ubicar>
  );
}

/** El lienzo común: todas las escenas viven en 240 × 140. */
export function Lienzo({
  children,
  className,
  etiqueta,
}: {
  children: React.ReactNode;
  className?: string;
  etiqueta?: string;
}) {
  return (
    <svg
      viewBox="0 0 240 140"
      className={className}
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={etiqueta ? 'img' : undefined}
      aria-label={etiqueta}
      aria-hidden={etiqueta ? undefined : true}
    >
      {children}
    </svg>
  );
}
