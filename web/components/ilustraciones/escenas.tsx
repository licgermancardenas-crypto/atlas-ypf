// Las escenas: piezas combinadas para contar algo.
//
// Cada módulo del sitio tiene la suya y cada segmento la propia. La regla es
// que la escena diga de qué habla la página sin leer el título: si la de
// mercado se puede confundir con la de producción, está mal dibujada.
//
// Todas comparten lienzo (240 × 140) y línea de piso (y = 118), así que puestas
// una debajo de la otra en distintas páginas se sienten del mismo mundo. Las de
// intemperie llevan cielo y cerros; las de escritorio, no: un organigrama no
// pasa al aire libre.

import {
  ACENTO,
  AGUA,
  Agua,
  Balancin,
  Barril,
  BarrilTumbado,
  BocaDePozo,
  BombaFractura,
  Buque,
  Camion,
  Cerros,
  Cielo,
  DomoGNL,
  Ducto,
  Gota,
  LibroAbierto,
  Lienzo,
  Marquesina,
  Mechero,
  Meseta,
  Molino,
  Organigrama,
  PanelSolar,
  PilaBarriles,
  PiletaAgua,
  SUAVE,
  SiloArena,
  Sol,
  Surtidor,
  TRAZO,
  Tanque,
  TorreDestilacion,
  TorrePerforacion,
  TrenGNL,
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
/** Un pad de shale completo: se perfora, se fractura y después queda el
 *  balancín. Los tres momentos del mismo pozo, de izquierda a derecha. */
export function EscenaUpstream({
  className,
  quieto,
  etiqueta = 'Un yacimiento de shale: torre de perforación, equipo de fractura, balancín y barriles',
}: Escena) {
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <Cielo id="cielo-upstream" />
      <Cerros />
      <Meseta opacidad={0.35} />
      <TorrePerforacion x={42} y={118} escala={0.66} opacidad={0.5} />
      <PiletaAgua x={96} y={118} escala={0.55} opacidad={0.55} />
      <SiloArena x={74} y={116} escala={0.5} opacidad={0.6} />
      <BombaFractura x={120} y={116} escala={0.5} opacidad={0.65} />
      <Balancin x={162} y={118} escala={0.92} anima={!quieto} />
      <Barril x={214} y={118} escala={0.72} llenado={0.62} />
      <Gota x={214} y={96} escala={0.85} anima={!quieto} />
    </Lienzo>
  );
}

/** De la refinería al surtidor, que es el camino del barril hasta la calle. */
export function EscenaDownstream({
  className,
  quieto,
  etiqueta = 'Una refinería: torres de destilación, tanques, ducto y estación de servicio',
}: Escena) {
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <Cielo id="cielo-downstream" estrellas={false} />
      <Cerros opacidad={0.5} />
      <Meseta opacidad={0.3} />
      <TorreDestilacion x={28} y={118} alto={60} />
      <TorreDestilacion x={54} y={118} alto={42} opacidad={0.7} />
      <Mechero x={74} y={118} escala={0.5} anima={!quieto} opacidad={0.8} />
      <Tanque x={106} y={118} escala={0.8} llenado={0.55} />
      <Ducto x={126} y={106} largo={30} />
      <Marquesina x={196} y={118} escala={0.92} />
      <Surtidor x={196} y={118} escala={0.5} />
      <BarrilTumbado x={160} y={114} escala={0.38} opacidad={0.7} />
    </Lienzo>
  );
}

/** El gas: tren de licuefacción, tanques esféricos y el barco que se lo lleva. */
export function EscenaGas({
  className,
  quieto,
  etiqueta = 'Planta de licuefacción de GNL, tanques esféricos y buque metanero',
}: Escena) {
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <Cielo id="cielo-gas" />
      <Agua y={124} />
      <TrenGNL x={44} y={120} escala={0.68} />
      <DomoGNL x={94} y={120} escala={0.62} llenado={0.6} />
      <DomoGNL x={124} y={120} escala={0.52} llenado={0.4} opacidad={0.75} />
      {/* el muelle y el brazo de carga */}
      <path d="M140 120 h26 v-10" stroke={TRAZO} strokeWidth={1.3} opacity={0.7} fill="none" />
      <path d="M166 110 q10 -8 18 0" stroke={ACENTO} strokeWidth={1.4} fill="none" />
      <Buque x={186} y={122} escala={0.62} anima={!quieto} />
    </Lienzo>
  );
}

export function EscenaRenovables({
  className,
  quieto,
  etiqueta = 'Molinos de viento y paneles solares',
}: Escena) {
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <Cielo id="cielo-renovables" estrellas={false} />
      <Cerros opacidad={0.55} />
      <Meseta opacidad={0.25} />
      <Sol x={206} y={34} escala={0.7} />
      <Molino x={36} y={118} escala={0.44} opacidad={0.45} anima={!quieto} />
      <Molino x={72} y={118} escala={0.72} anima={!quieto} />
      <Molino x={118} y={118} escala={0.34} opacidad={0.35} anima={!quieto} />
      <PanelSolar x={172} y={116} escala={0.95} />
    </Lienzo>
  );
}

/** Administración central: lo que no es un negocio es una estructura. */
export function EscenaCorporativa({ className, etiqueta = 'La estructura corporativa' }: Escena) {
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <Cielo id="cielo-corporativa" estrellas={false} />
      {/* el edificio, al fondo y apagado: el organigrama es lo que manda */}
      <g opacity={0.28}>
        <path d="M26 118 V44 h40 v74" stroke={TRAZO} strokeWidth={1.4} />
        {[56, 68, 80, 92, 104].map((y) => (
          <path key={y} d={`M32 ${y} h28`} stroke={TRAZO} strokeWidth={0.9} />
        ))}
        <path d="M186 118 V62 h32 v56" stroke={TRAZO} strokeWidth={1.3} />
        {[74, 86, 98].map((y) => (
          <path key={y} d={`M192 ${y} h20`} stroke={TRAZO} strokeWidth={0.9} />
        ))}
      </g>
      <Organigrama x={126} y={110} escala={1.05} />
      <path d="M0 118 H240" stroke={SUAVE} strokeWidth={1} opacity={0.4} />
    </Lienzo>
  );
}

// --------------------------------------------------------------------------- //
// Los módulos
// --------------------------------------------------------------------------- //
/** El caso: el trimestre récord y la acción que lo vendió, en un solo dibujo.
 *
 *  Es la tesis entera: barriles que suben, precio que baja, y el cruce en el
 *  medio. Ninguna otra escena del sitio usa dos series a la vez, así que no se
 *  puede confundir con la de finanzas. */
export function EscenaBalance({
  className,
  etiqueta = 'Producción que sube y precio de la acción que baja, cruzándose',
}: Escena) {
  const barras = [
    { x: 34, alto: 20 },
    { x: 60, alto: 30 },
    { x: 86, alto: 38 },
    { x: 112, alto: 52 },
    { x: 138, alto: 60 },
    { x: 164, alto: 78 },
  ];
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <Cielo id="cielo-caso" estrellas={false} />
      <path d="M20 118 H224" stroke={SUAVE} strokeWidth={1.1} opacity={0.6} />

      {/* lo que la compañía produjo: sube */}
      {barras.map((barra, indice) => (
        <path
          key={barra.x}
          d={`M${barra.x} 118 V${118 - barra.alto} h16 v${barra.alto} z`}
          stroke={ACENTO}
          strokeWidth={1.2}
          fill={ACENTO}
          fillOpacity={0.12 + indice * 0.05}
        />
      ))}

      {/* lo que el mercado hizo: baja, y cruza */}
      <path
        d="M28 34 C 74 42, 96 56, 120 76 C 146 98, 176 104, 214 108"
        stroke="var(--color-baja)"
        strokeWidth={2.4}
        fill="none"
      />
      <circle cx={214} cy={108} r={3.6} fill="var(--color-baja)" />
      <path d="M200 96 L214 108 L212 94" stroke="var(--color-baja)" strokeWidth={1.6} fill="none" />

      <Barril x={200} y={118} escala={0.58} llenado={0.85} />
    </Lienzo>
  );
}

/** Finanzas: una planilla, y nada más que una planilla. Lo que la distingue del
 *  caso es que acá no hay serie: hay celdas. */
export function EscenaFinanzas({ className, etiqueta = 'Una planilla de conceptos por trimestre' }: Escena) {
  const columnas = [64, 96, 128, 160, 192];
  const filas = [46, 60, 74, 88, 102];
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <path
        d="M22 116 V32 h196 v84 z"
        stroke={TRAZO}
        strokeWidth={1.5}
        fill="var(--color-superficie-alta)"
        fillOpacity={0.3}
      />
      {/* encabezado de períodos */}
      <path d="M22 32 h196 v14 h-196 z" fill={TRAZO} fillOpacity={0.18} stroke={TRAZO} strokeWidth={1.2} />
      {columnas.map((x) => (
        <path key={x} d={`M${x} 32 V116`} stroke={TRAZO} strokeWidth={0.85} opacity={0.35} />
      ))}
      {filas.map((y) => (
        <path key={y} d={`M22 ${y} h196`} stroke={TRAZO} strokeWidth={0.85} opacity={0.3} />
      ))}
      {/* la primera columna, fija, con los conceptos */}
      <path d="M22 46 h42 v70 h-42 z" fill={TRAZO} fillOpacity={0.1} />
      {[53, 67, 81, 95, 109].map((y) => (
        <path key={y} d={`M28 ${y} h28`} stroke={TRAZO} strokeWidth={0.9} opacity={0.45} />
      ))}
      {/* tres celdas marcadas: la fila que se está siguiendo */}
      {columnas.slice(0, 4).map((x, indice) => (
        <path
          key={x}
          d={`M${x} 74 h32 v14 h-32 z`}
          fill={ACENTO}
          fillOpacity={0.12 + indice * 0.06}
          stroke={ACENTO}
          strokeWidth={1}
        />
      ))}
      <path d="M22 88 h196" stroke={ACENTO} strokeWidth={1.3} opacity={0.8} />
    </Lienzo>
  );
}

/** El libro: el mayor abierto, que es lo que un libro contable es. */
export function EscenaLibro({ className, etiqueta = 'Un libro mayor abierto, con un barril al lado' }: Escena) {
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <Cielo id="cielo-libro" estrellas={false} />
      <LibroAbierto x={112} y={104} escala={1.08} />
      <Barril x={202} y={116} escala={0.6} llenado={0.55} />
      <BarrilTumbado x={30} y={110} escala={0.34} opacidad={0.5} />
      <path d="M14 118 H226" stroke={SUAVE} strokeWidth={1} opacity={0.35} />
    </Lienzo>
  );
}

/** Operativo: la cuenca vista desde arriba, con los pozos como puntos. */
export function EscenaCuenca({
  className,
  quieto,
  etiqueta = 'La cuenca vista desde arriba, con sus concesiones y sus pozos',
}: Escena) {
  const pozos = [
    [66, 74], [80, 66], [94, 78], [108, 70], [122, 82], [136, 72],
    [78, 92], [96, 96], [116, 92], [134, 100], [150, 88], [58, 86],
    [148, 62], [164, 76],
  ];
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <Cielo id="cielo-cuenca" estrellas={false} />
      <path
        d="M40 96 C 44 58, 92 34, 138 42 C 186 50, 206 84, 190 104 C 172 126, 78 128, 40 96 Z"
        stroke={TRAZO}
        strokeWidth={1.6}
        fill={TRAZO}
        fillOpacity={0.07}
      />
      <path d="M70 44 V120 M104 38 V124 M138 40 V122 M44 70 H196 M46 94 H194" stroke={TRAZO} strokeWidth={0.8} opacity={0.3} />
      {/* los pozos horizontales: el punto es la boca y la línea, la rama */}
      {pozos.map(([x, y], indice) => (
        <g key={indice} opacity={indice % 3 === 0 ? 0.95 : 0.6}>
          <circle cx={x} cy={y} r={2.1} fill={ACENTO} />
          <path d={`M${x} ${y} h${indice % 2 ? 9 : -9}`} stroke={ACENTO} strokeWidth={0.9} opacity={0.6} />
        </g>
      ))}
      <Balancin x={200} y={124} escala={0.38} anima={!quieto} opacidad={0.85} />
      <path d="M16 118 H240" stroke={SUAVE} strokeWidth={1} opacity={0.2} />
    </Lienzo>
  );
}

/** Economía de pozo: la curva de declino, que es la física del negocio. */
export function EscenaPozo({ className, etiqueta = 'La curva de declino de un pozo' }: Escena) {
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <path d="M40 116 H212" stroke={SUAVE} strokeWidth={1.2} />
      <path d="M40 116 V28" stroke={SUAVE} strokeWidth={1.2} />
      <path d="M40 40 C 78 96, 120 106, 212 110 L212 116 L40 116 Z" fill={ACENTO} fillOpacity={0.16} />
      <path d="M40 40 C 78 96, 120 106, 212 110" stroke={ACENTO} strokeWidth={2} fill="none" />
      <path d="M40 40 h-6 M40 72 h-6 M40 104 h-6" stroke={SUAVE} strokeWidth={1} opacity={0.6} />
      <BocaDePozo x={40} y={116} escala={0.55} opacidad={0.85} />
      <Barril x={92} y={116} escala={0.5} llenado={0.85} opacidad={0.9} />
      <Barril x={186} y={116} escala={0.5} llenado={0.25} opacidad={0.85} />
    </Lienzo>
  );
}

/** Simulador: las perillas que mueven el resultado. */
export function EscenaSimulador({ className, etiqueta = 'Perillas y una palanca: los drivers del resultado' }: Escena) {
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
      {[46, 76, 106].map((x, indice) => (
        <g key={x} opacity={0.9 - indice * 0.1}>
          <path d={`M${x - 12} 30 h24 v18 h-24 z`} stroke={TRAZO} strokeWidth={1.3} fill="var(--color-superficie-alta)" fillOpacity={0.35} />
          <path d={`M${x - 7} 36 h14 M${x - 7} 42 h9`} stroke={TRAZO} strokeWidth={0.9} opacity={0.55} />
          <path d={`M${x} 48 V64`} stroke={TRAZO} strokeWidth={1} opacity={0.5} />
        </g>
      ))}
      <path d="M30 64 H122 L86 96 V116 H66 V96 Z" stroke={ACENTO} strokeWidth={1.6} fill={ACENTO} fillOpacity={0.1} />
      <Gota x={76} y={122} escala={0.8} anima={!quieto} />
      <g>
        <ellipse cx={176} cy={52} rx={30} ry={9} stroke={TRAZO} strokeWidth={1.4} />
        <path d="M146 52 V96 a30 9 0 0 0 60 0 V52" stroke={TRAZO} strokeWidth={1.4} fill="none" />
        <path d="M146 68 a30 9 0 0 0 60 0 M146 84 a30 9 0 0 0 60 0" stroke={TRAZO} strokeWidth={1} opacity={0.55} />
        <path d="M122 78 H146" stroke={ACENTO} strokeWidth={1.6} strokeDasharray="4 3" />
      </g>
    </Lienzo>
  );
}

/** Relaciones: el grafo tiene forma, porque la titularidad tiene forma.
 *
 *  Arriba las empresas, en el medio las áreas y abajo los pozos. Un área con
 *  dos empresas encima es un bloque compartido, que es de lo que habla el
 *  módulo. */
export function EscenaRed({ className, etiqueta = 'Empresas, áreas compartidas y pozos: el grafo de titularidad' }: Escena) {
  const empresas = [
    { x: 62, r: 8 },
    { x: 122, r: 6 },
    { x: 182, r: 6.5 },
  ];
  const areas = [
    { x: 86, padres: [0, 1] },
    { x: 152, padres: [1, 2] },
    { x: 40, padres: [0] },
  ];
  const pozos = [30, 46, 62, 78, 96, 112, 130, 146, 164, 182, 198];
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      {/* de empresa a área: la participación */}
      {areas.map((area) =>
        area.padres.map((padre) => (
          <path
            key={`${area.x}-${padre}`}
            d={`M${empresas[padre].x} 42 L${area.x} 78`}
            stroke={ACENTO}
            strokeWidth={1}
            opacity={0.45}
          />
        )),
      )}
      {/* de área a pozo */}
      {pozos.map((x, indice) => {
        const area = areas[indice % areas.length];
        return (
          <path
            key={x}
            d={`M${area.x} 78 L${x} 112`}
            stroke={TRAZO}
            strokeWidth={0.7}
            opacity={0.28}
          />
        );
      })}

      {empresas.map((empresa) => (
        <circle
          key={empresa.x}
          cx={empresa.x}
          cy={42}
          r={empresa.r}
          fill={ACENTO}
          fillOpacity={0.22}
          stroke={ACENTO}
          strokeWidth={1.5}
        />
      ))}
      {areas.map((area) => (
        <rect
          key={area.x}
          x={area.x - 9}
          y={72}
          width={18}
          height={12}
          rx={2}
          fill={TRAZO}
          fillOpacity={0.2}
          stroke={TRAZO}
          strokeWidth={1.4}
        />
      ))}
      {pozos.map((x) => (
        <circle key={x} cx={x} cy={112} r={2.2} fill={AGUA} opacity={0.75} />
      ))}
    </Lienzo>
  );
}

/** Reservas: lo que todavía está abajo. */
export function EscenaReservas({ className, etiqueta = 'Las reservas: barriles todavía bajo tierra' }: Escena) {
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <Cielo id="cielo-reservas" estrellas={false} />
      <path d="M0 56 H240" stroke={SUAVE} strokeWidth={1.2} opacity={0.7} />
      <BocaDePozo x={56} y={56} escala={0.8} />
      <path d="M56 56 V88 q0 8 10 8 H140" stroke={ACENTO} strokeWidth={1.4} strokeDasharray="3 3" />
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
      <PilaBarriles x={184} y={118} escala={0.78} llenado={0.85} />
    </Lienzo>
  );
}

/** El transporte: el eslabón que la compañía no controla del todo. */
export function EscenaLogistica({ className, etiqueta = 'Ducto, tanque y camión cisterna' }: Escena) {
  return (
    <Lienzo className={className} etiqueta={etiqueta}>
      <Cielo id="cielo-logistica" estrellas={false} />
      <Cerros opacidad={0.45} />
      <Meseta opacidad={0.25} />
      <Ducto x={12} y={62} largo={124} />
      <Tanque x={184} y={100} escala={0.68} llenado={0.5} opacidad={0.85} />
      <Camion x={86} y={104} escala={0.92} />
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
