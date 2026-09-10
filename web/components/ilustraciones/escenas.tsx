// Las escenas: piezas combinadas para contar algo.
//
// Cada módulo del sitio tiene la suya y cada segmento la propia. La regla es
// que la escena diga de qué habla la página sin leer el título: si la de
// mercado se puede confundir con la de producción, está mal dibujada.
//
// Todas comparten lienzo (240 × 140) y línea de piso (y = 118), así que puestas
// una debajo de la otra en distintas páginas se sienten del mismo mundo.

import {
  ACENTO,
  AGUA,
  Agua,
  Balancin,
  Barril,
  BarrilTumbado,
  BocaDePozo,
  Buque,
  Camion,
  Ducto,
  Gota,
  Lienzo,
  Mechero,
  Meseta,
  Molino,
  PanelSolar,
  SUAVE,
  Sol,
  Surtidor,
  TRAZO,
  Tanque,
  TorreDestilacion,
  TorrePerforacion,
} from '@/components/ilustraciones/piezas';

interface Escena {
  className?: string;
  etiqueta?: string;
  /** El movimiento se puede apagar por escena, además del ajuste del sistema. */
  quieto?: boolean;
}

// --------------------------------------------------------------------------- //
// Los negocios
// --------------------------------------------------------------------------- //
export function EscenaUpstream({ className, quieto, etiqueta = 'Un yacimiento: torre de perforación, balancín y barriles' }: Escena) {
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <Meseta />
      <TorrePerforacion x={54} y={118} escala={0.72} opacidad={0.55} />
      <BocaDePozo x={98} y={118} escala={0.8} opacidad={0.5} />
      <Balancin x={150} y={118} escala={1} anima={!quieto} />
      <Barril x={206} y={118} escala={0.8} llenado={0.62} />
      <Gota x={206} y={92} escala={0.9} anima={!quieto} />
    </Lienzo>
  );
}

export function EscenaDownstream({ className, etiqueta = 'Una refinería: torres de destilación, tanque, ducto y surtidor' }: Escena) {
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <Meseta opacidad={0.3} />
      <TorreDestilacion x={30} y={118} alto={58} />
      <TorreDestilacion x={58} y={118} alto={40} opacidad={0.65} />
      <Tanque x={100} y={118} escala={0.85} llenado={0.55} />
      <Ducto x={124} y={104} largo={40} />
      <Surtidor x={196} y={118} escala={0.9} />
      <BarrilTumbado x={166} y={112} escala={0.42} opacidad={0.75} />
    </Lienzo>
  );
}

export function EscenaGas({ className, quieto, etiqueta = 'Planta de licuefacción y buque metanero' }: Escena) {
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <Agua y={126} />
      <TorreDestilacion x={26} y={120} alto={46} opacidad={0.85} />
      <Mechero x={54} y={120} escala={0.75} anima={!quieto} />
      <Ducto x={68} y={110} largo={26} opacidad={0.8} />
      <Buque x={158} y={120} escala={0.78} anima={!quieto} />
    </Lienzo>
  );
}

export function EscenaRenovables({ className, quieto, etiqueta = 'Molinos de viento y paneles solares' }: Escena) {
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <Meseta opacidad={0.3} />
      <Sol x={208} y={36} escala={0.75} />
      <Molino x={38} y={118} escala={0.5} opacidad={0.5} anima={!quieto} />
      <Molino x={74} y={118} escala={0.78} anima={!quieto} />
      <PanelSolar x={168} y={116} escala={1} />
    </Lienzo>
  );
}

export function EscenaCorporativa({ className, etiqueta = 'La casa matriz' }: Escena) {
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <Meseta opacidad={0.25} />
      <g opacity={0.9}>
        <path d="M92 118 V54 h56 v64" stroke={TRAZO} strokeWidth={1.6} />
        <path d="M92 54 L120 36 L148 54" stroke={ACENTO} strokeWidth={1.6} />
        {[68, 82, 96].map((y) => (
          <path key={y} d={`M100 ${y} h40`} stroke={TRAZO} strokeWidth={1} opacity={0.55} />
        ))}
        <path d="M112 118 V104 h16 v14" stroke={ACENTO} strokeWidth={1.4} />
      </g>
      <BarrilTumbado x={186} y={112} escala={0.4} opacidad={0.5} />
      <Barril x={62} y={118} escala={0.5} llenado={0.3} opacidad={0.6} />
    </Lienzo>
  );
}

// --------------------------------------------------------------------------- //
// Los módulos
// --------------------------------------------------------------------------- //
/** El caso: el balance del trimestre, con la lupa encima. */
export function EscenaBalance({ className, etiqueta = 'Un balance bajo la lupa, con barriles al lado' }: Escena) {
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <Meseta opacidad={0.2} />
      {/* la hoja */}
      <g>
        <path d="M62 116 V38 h74 v78 z" stroke={TRAZO} strokeWidth={1.5} fill="var(--color-superficie-alta)" fillOpacity={0.35} />
        <path d="M72 52 h54 M72 64 h54 M72 76 h34" stroke={TRAZO} strokeWidth={1} opacity={0.55} />
        {/* dos barras que suben, que es de lo que habla el caso */}
        <path d="M76 106 V92 h8 v14 z" stroke={ACENTO} strokeWidth={1.2} fill={ACENTO} fillOpacity={0.25} />
        <path d="M92 106 V84 h8 v22 z" stroke={ACENTO} strokeWidth={1.2} fill={ACENTO} fillOpacity={0.35} />
        <path d="M108 106 V72 h8 v34 z" stroke={ACENTO} strokeWidth={1.2} fill={ACENTO} fillOpacity={0.5} />
      </g>
      {/* la lupa: el caso es una pregunta, no un anuncio */}
      <g>
        <circle cx={152} cy={68} r={20} stroke={ACENTO} strokeWidth={1.8} />
        <path d="M167 83 L182 98" stroke={ACENTO} strokeWidth={2.2} />
        <path d="M140 74 q8 -12 22 -6" stroke={ACENTO} strokeWidth={1} opacity={0.5} />
      </g>
      <Barril x={38} y={118} escala={0.62} llenado={0.75} />
      <Barril x={206} y={118} escala={0.5} llenado={0.4} opacidad={0.7} />
    </Lienzo>
  );
}

/** Finanzas: la serie trimestral como una planilla con velas encima. */
export function EscenaFinanzas({ className, etiqueta = 'Una planilla trimestral y una serie de barras' }: Escena) {
  const barras = [
    { x: 132, alto: 26 },
    { x: 148, alto: 38 },
    { x: 164, alto: 32 },
    { x: 180, alto: 52 },
    { x: 196, alto: 46 },
    { x: 212, alto: 68 },
  ];
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <path d="M18 116 V34 h96 v82 z" stroke={TRAZO} strokeWidth={1.5} fill="var(--color-superficie-alta)" fillOpacity={0.3} />
      <path d="M18 48 h96 M18 62 h96 M18 76 h96 M18 90 h96 M18 104 h96" stroke={TRAZO} strokeWidth={0.8} opacity={0.35} />
      <path d="M42 34 V116 M66 34 V116 M90 34 V116" stroke={TRAZO} strokeWidth={0.8} opacity={0.35} />
      <path d="M18 34 h96 v14 h-96 z" fill={TRAZO} fillOpacity={0.18} stroke={TRAZO} strokeWidth={1.2} />
      <path d="M118 116 H228" stroke={SUAVE} strokeWidth={1} opacity={0.6} />
      {barras.map((barra) => (
        <path
          key={barra.x}
          d={`M${barra.x} 116 V${116 - barra.alto} h10 v${barra.alto} z`}
          stroke={ACENTO}
          strokeWidth={1.2}
          fill={ACENTO}
          fillOpacity={0.3}
        />
      ))}
    </Lienzo>
  );
}

/** El libro: los estados apilados, con el barril como unidad de todo. */
export function EscenaLibro({ className, etiqueta = 'Los tres estados contables apilados' }: Escena) {
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      {[0, 1, 2].map((indice) => (
        <g key={indice} opacity={1 - indice * 0.22}>
          <path
            d={`M${52 + indice * 14} ${112 - indice * 16} V${44 - indice * 16} h72 v${68} z`}
            stroke={TRAZO}
            strokeWidth={1.4}
            fill="var(--color-superficie-alta)"
            fillOpacity={0.4}
          />
        </g>
      ))}
      <path d="M90 44 h50 M90 56 h50 M90 68 h32 M90 80 h44" stroke={TRAZO} strokeWidth={1} opacity={0.5} />
      <path d="M90 92 h50" stroke={ACENTO} strokeWidth={1.4} />
      <Barril x={196} y={118} escala={0.72} llenado={0.55} />
      <BarrilTumbado x={36} y={112} escala={0.42} opacidad={0.6} />
    </Lienzo>
  );
}

/** Operativo: la cuenca, con los pozos como puntos y las concesiones como grilla. */
export function EscenaCuenca({ className, quieto, etiqueta = 'La cuenca vista desde arriba, con sus pozos' }: Escena) {
  const pozos = [
    [66, 74], [80, 66], [94, 78], [108, 70], [122, 82], [136, 72],
    [78, 92], [96, 96], [116, 92], [134, 100], [150, 88], [58, 86],
  ];
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      {/* el contorno de la cuenca */}
      <path
        d="M40 96 C 44 58, 92 34, 138 42 C 186 50, 206 84, 190 104 C 172 126, 78 128, 40 96 Z"
        stroke={TRAZO}
        strokeWidth={1.6}
        fill={TRAZO}
        fillOpacity={0.07}
      />
      {/* las concesiones */}
      <path d="M70 44 V120 M104 38 V124 M138 40 V122 M44 70 H196 M46 94 H194" stroke={TRAZO} strokeWidth={0.8} opacity={0.3} />
      {pozos.map(([x, y], indice) => (
        <circle key={indice} cx={x} cy={y} r={2.2} fill={ACENTO} opacity={indice % 3 === 0 ? 0.95 : 0.6} />
      ))}
      <Balancin x={196} y={124} escala={0.42} anima={!quieto} opacidad={0.9} />
      <path d="M20 118 H240" stroke={SUAVE} strokeWidth={1} opacity={0.25} />
    </Lienzo>
  );
}

/** Economía de pozo: la curva de declino, que es la física del negocio. */
export function EscenaPozo({ className, etiqueta = 'La curva de declino de un pozo' }: Escena) {
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <path d="M40 116 H212" stroke={SUAVE} strokeWidth={1.2} />
      <path d="M40 116 V28" stroke={SUAVE} strokeWidth={1.2} />
      {/* el área bajo la curva es lo que se recupera */}
      <path d="M40 40 C 78 96, 120 106, 212 110 L212 116 L40 116 Z" fill={ACENTO} fillOpacity={0.16} />
      <path d="M40 40 C 78 96, 120 106, 212 110" stroke={ACENTO} strokeWidth={2} fill="none" />
      <path d="M40 40 h-6 M40 72 h-6 M40 104 h-6" stroke={SUAVE} strokeWidth={1} opacity={0.6} />
      <BocaDePozo x={40} y={116} escala={0.55} opacidad={0.85} />
      <Barril x={186} y={116} escala={0.52} llenado={0.35} opacidad={0.85} />
      <Barril x={92} y={116} escala={0.52} llenado={0.85} opacidad={0.9} />
    </Lienzo>
  );
}

/** Simulador: las perillas que mueven el resultado. */
export function EscenaSimulador({ className, etiqueta = 'Perillas y palancas: los drivers del resultado' }: Escena) {
  const perillas = [
    { x: 70, valor: -35 },
    { x: 120, valor: 25 },
    { x: 170, valor: 65 },
  ];
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      {perillas.map((perilla) => (
        <g key={perilla.x}>
          <circle cx={perilla.x} cy={62} r={22} stroke={TRAZO} strokeWidth={1.5} />
          <circle cx={perilla.x} cy={62} r={30} stroke={TRAZO} strokeWidth={0.9} strokeDasharray="2 5" opacity={0.45} />
          <path
            d={`M${perilla.x} 62 L${perilla.x + 16 * Math.sin((perilla.valor * Math.PI) / 100)} ${
              62 - 16 * Math.cos((perilla.valor * Math.PI) / 100)
            }`}
            stroke={ACENTO}
            strokeWidth={2.2}
          />
          <circle cx={perilla.x} cy={62} r={3} fill={ACENTO} />
        </g>
      ))}
      <path d="M44 108 H196" stroke={SUAVE} strokeWidth={1.2} opacity={0.6} />
      <path d="M44 108 H150" stroke={ACENTO} strokeWidth={2.4} />
      <circle cx={150} cy={108} r={4.5} fill="var(--color-superficie)" stroke={ACENTO} strokeWidth={1.8} />
    </Lienzo>
  );
}

/** Datos y método: de las fuentes al dato, pasando por el embudo. */
export function EscenaDatos({ className, quieto, etiqueta = 'De las fuentes al dato: el pipeline' }: Escena) {
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      {/* las fuentes */}
      {[46, 76, 106].map((x, indice) => (
        <g key={x} opacity={0.9 - indice * 0.1}>
          <path d={`M${x - 12} 30 h24 v18 h-24 z`} stroke={TRAZO} strokeWidth={1.3} fill="var(--color-superficie-alta)" fillOpacity={0.35} />
          <path d={`M${x - 7} 36 h14 M${x - 7} 42 h9`} stroke={TRAZO} strokeWidth={0.9} opacity={0.55} />
          <path d={`M${x} 48 V64`} stroke={TRAZO} strokeWidth={1} opacity={0.5} />
        </g>
      ))}
      {/* el embudo */}
      <path d="M30 64 H122 L86 96 V116 H66 V96 Z" stroke={ACENTO} strokeWidth={1.6} fill={ACENTO} fillOpacity={0.1} />
      <Gota x={76} y={122} escala={0.8} anima={!quieto} />
      {/* la base de datos */}
      <g>
        <ellipse cx={176} cy={52} rx={30} ry={9} stroke={TRAZO} strokeWidth={1.4} />
        <path d="M146 52 V96 a30 9 0 0 0 60 0 V52" stroke={TRAZO} strokeWidth={1.4} fill="none" />
        <path d="M146 68 a30 9 0 0 0 60 0 M146 84 a30 9 0 0 0 60 0" stroke={TRAZO} strokeWidth={1} opacity={0.55} />
        <path d="M122 78 H146" stroke={ACENTO} strokeWidth={1.6} strokeDasharray="4 3" />
      </g>
    </Lienzo>
  );
}

/** Relaciones: el grafo de quién opera con quién. */
export function EscenaRed({ className, etiqueta = 'Un grafo de empresas, áreas y pozos' }: Escena) {
  const nodos = [
    { x: 62, y: 46, r: 7, color: ACENTO },
    { x: 120, y: 34, r: 5, color: TRAZO },
    { x: 172, y: 56, r: 9, color: ACENTO },
    { x: 96, y: 84, r: 6, color: TRAZO },
    { x: 150, y: 100, r: 5, color: TRAZO },
    { x: 46, y: 96, r: 4, color: AGUA },
    { x: 206, y: 96, r: 4, color: AGUA },
  ];
  const aristas = [
    [0, 1], [1, 2], [0, 3], [3, 4], [2, 4], [3, 5], [2, 6], [0, 5],
  ];
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      {aristas.map(([desde, hasta], indice) => (
        <path
          key={indice}
          d={`M${nodos[desde].x} ${nodos[desde].y} L${nodos[hasta].x} ${nodos[hasta].y}`}
          stroke={TRAZO}
          strokeWidth={1}
          opacity={0.45}
        />
      ))}
      {nodos.map((nodo, indice) => (
        <circle
          key={indice}
          cx={nodo.x}
          cy={nodo.y}
          r={nodo.r}
          fill={nodo.color}
          fillOpacity={0.25}
          stroke={nodo.color}
          strokeWidth={1.4}
        />
      ))}
      <path d="M20 122 H220" stroke={SUAVE} strokeWidth={1} opacity={0.25} />
    </Lienzo>
  );
}

/** Reservas: lo que todavía está abajo. */
export function EscenaReservas({ className, etiqueta = 'Las reservas: barriles todavía bajo tierra' }: Escena) {
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <path d="M0 56 H240" stroke={SUAVE} strokeWidth={1.2} opacity={0.7} />
      <BocaDePozo x={60} y={56} escala={0.8} />
      <path d="M60 56 V88 q0 8 10 8 H150" stroke={ACENTO} strokeWidth={1.4} strokeDasharray="3 3" />
      {/* los estratos */}
      {[74, 96, 118].map((y, indice) => (
        <path
          key={y}
          d={`M0 ${y} q60 ${indice % 2 ? 8 : -8} 120 0 t120 0`}
          stroke={SUAVE}
          strokeWidth={1}
          opacity={0.35}
          fill="none"
        />
      ))}
      <g opacity={0.9}>
        <Barril x={166} y={112} escala={0.55} llenado={0.9} />
        <Barril x={192} y={112} escala={0.55} llenado={0.7} />
        <Barril x={218} y={112} escala={0.55} llenado={0.45} />
        <Barril x={179} y={84} escala={0.5} llenado={0.8} opacidad={0.8} />
        <Barril x={205} y={84} escala={0.5} llenado={0.6} opacidad={0.8} />
      </g>
    </Lienzo>
  );
}

/** El transporte: el eslabón que la compañía no controla del todo. */
export function EscenaLogistica({ className, etiqueta = 'Ducto y camión cisterna' }: Escena) {
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <Meseta opacidad={0.3} />
      <Ducto x={16} y={64} largo={126} />
      <Tanque x={182} y={100} escala={0.7} llenado={0.5} opacidad={0.85} />
      <Camion x={90} y={104} escala={0.95} />
    </Lienzo>
  );
}

export const ESCENAS_SEGMENTO: Record<string, (props: Escena) => React.ReactElement> = {
  Upstream: EscenaUpstream,
  'Midstream y Downstream': EscenaDownstream,
  Downstream: EscenaDownstream,
  Industrialización: EscenaDownstream,
  Comercialización: EscenaLogistica,
  'GNL y gas integrado': EscenaGas,
  'Gas y energía': EscenaGas,
  'Nuevas energías': EscenaRenovables,
  'Administración central y otros': EscenaCorporativa,
  'Ajustes de consolidación': EscenaLogistica,
};

export function IlustracionSegmento({
  segmento,
  className,
  quieto,
}: {
  segmento: string;
  className?: string;
  quieto?: boolean;
}) {
  const Escena = ESCENAS_SEGMENTO[segmento] ?? EscenaCorporativa;
  return <Escena className={className} quieto={quieto} />;
}
