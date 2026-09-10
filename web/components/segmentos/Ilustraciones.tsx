// Las ilustraciones de cada segmento, dibujadas acá.
//
// Por qué SVG propio y no fotos: una foto de una refinería es de alguien, pesa
// cien veces más y no se adapta al tema oscuro del sitio. Estas son de línea,
// usan la misma paleta que los gráficos, pesan menos que un párrafo y escalan
// a cualquier tamaño. Además son honestas: son esquemas de lo que hace cada
// negocio, no una postal de una planta que quizá ni sea de YPF.
//
// Todas comparten el mismo lienzo (240 × 140) y el mismo grosor de trazo, para
// que puestas una al lado de la otra se lean como una familia.

const TRAZO = 'var(--color-azul-claro)';
const ACENTO = 'var(--color-oro)';
const SUAVE = 'var(--color-neutro)';

interface Props {
  className?: string;
}

function Lienzo({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <svg
      viewBox="0 0 240 140"
      className={className}
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

/** Upstream: el balancín, la torre de perforación y la meseta. */
export function Upstream({ className }: Props) {
  return (
    <Lienzo className={className}>
      {/* la meseta */}
      <path d="M0 118 H240" stroke={SUAVE} strokeWidth="1" opacity="0.5" />
      <path d="M8 118 C 40 104, 70 108, 96 118" stroke={SUAVE} strokeWidth="1.2" opacity="0.55" />
      <path d="M120 118 C 150 100, 186 106, 232 118" stroke={SUAVE} strokeWidth="1.2" opacity="0.45" />

      {/* torre de perforación */}
      <path d="M44 118 L60 44 L76 118" stroke={TRAZO} strokeWidth="1.6" />
      <path d="M50 92 H70 M53 76 H67 M56 60 H64" stroke={TRAZO} strokeWidth="1.1" opacity="0.75" />
      <path d="M60 44 V32" stroke={TRAZO} strokeWidth="1.6" />
      <circle cx="60" cy="29" r="3" stroke={ACENTO} strokeWidth="1.6" />

      {/* balancín */}
      <path d="M150 118 V88" stroke={TRAZO} strokeWidth="1.6" />
      <path d="M140 118 L150 88 L160 118" stroke={TRAZO} strokeWidth="1.6" />
      <path d="M124 78 L182 96" stroke={ACENTO} strokeWidth="2.4" />
      <circle cx="150" cy="88" r="3.4" fill="var(--color-superficie)" stroke={ACENTO} strokeWidth="1.6" />
      <path d="M182 96 V112" stroke={TRAZO} strokeWidth="1.4" />
      <path d="M176 112 H188" stroke={TRAZO} strokeWidth="1.4" />
      <path d="M124 78 L120 86 L128 86 Z" fill={ACENTO} opacity="0.85" />

      {/* el pozo horizontal, que es lo que cambia todo en shale */}
      <path
        d="M182 118 V130 H206"
        stroke={ACENTO}
        strokeWidth="1.4"
        strokeDasharray="3 3"
        opacity="0.9"
      />
    </Lienzo>
  );
}

/** Midstream y Downstream: la refinería, el ducto y el surtidor. */
export function MidstreamDownstream({ className }: Props) {
  return (
    <Lienzo className={className}>
      <path d="M0 118 H240" stroke={SUAVE} strokeWidth="1" opacity="0.5" />

      {/* torres de destilación */}
      <path d="M28 118 V56 H48 V118" stroke={TRAZO} strokeWidth="1.6" />
      <path d="M28 74 H48 M28 92 H48" stroke={TRAZO} strokeWidth="1" opacity="0.6" />
      <path d="M38 56 V44" stroke={TRAZO} strokeWidth="1.4" />
      <path d="M34 44 Q38 34 42 44" stroke={ACENTO} strokeWidth="1.6" />

      <path d="M58 118 V72 H72 V118" stroke={TRAZO} strokeWidth="1.6" />
      <path d="M58 90 H72" stroke={TRAZO} strokeWidth="1" opacity="0.6" />

      {/* tanque */}
      <ellipse cx="98" cy="86" rx="16" ry="5" stroke={TRAZO} strokeWidth="1.4" />
      <path d="M82 86 V112" stroke={TRAZO} strokeWidth="1.4" />
      <path d="M114 86 V112" stroke={TRAZO} strokeWidth="1.4" />
      <ellipse cx="98" cy="112" rx="16" ry="5" stroke={TRAZO} strokeWidth="1.4" />

      {/* el ducto que cruza al surtidor */}
      <path d="M120 104 H164" stroke={ACENTO} strokeWidth="2" />
      <path d="M132 100 V108 M148 100 V108" stroke={ACENTO} strokeWidth="1.2" opacity="0.7" />

      {/* surtidor */}
      <path d="M176 118 V70 H204 V118" stroke={TRAZO} strokeWidth="1.6" />
      <rect x="182" y="78" width="16" height="12" rx="1.5" stroke={ACENTO} strokeWidth="1.4" />
      <path d="M204 82 H214 V104" stroke={TRAZO} strokeWidth="1.4" />
      <path d="M214 104 h-6" stroke={ACENTO} strokeWidth="1.6" />
      <path d="M176 118 H204" stroke={TRAZO} strokeWidth="1.6" />
    </Lienzo>
  );
}

/** GNL y gas integrado: la planta de licuefacción y el buque. */
export function GasIntegrado({ className }: Props) {
  return (
    <Lienzo className={className}>
      {/* el agua */}
      <path d="M0 120 H240" stroke={SUAVE} strokeWidth="1" opacity="0.5" />
      <path d="M12 128 q10 -5 20 0 t20 0 t20 0 t20 0" stroke={SUAVE} strokeWidth="1" opacity="0.4" />
      <path d="M132 134 q10 -5 20 0 t20 0 t20 0 t20 0" stroke={SUAVE} strokeWidth="1" opacity="0.3" />

      {/* planta de licuefacción */}
      <path d="M18 120 V64 H54 V120" stroke={TRAZO} strokeWidth="1.6" />
      <path d="M26 64 V50 M40 64 V44" stroke={TRAZO} strokeWidth="1.4" />
      <path d="M36 44 Q40 34 44 44" stroke={ACENTO} strokeWidth="1.6" />
      <path d="M18 88 H54" stroke={TRAZO} strokeWidth="1" opacity="0.6" />

      {/* ducto hacia el muelle */}
      <path d="M54 108 H92" stroke={ACENTO} strokeWidth="2" />

      {/* buque metanero: casco y tanques esféricos */}
      <path d="M96 120 h108 l-10 12 H106 Z" stroke={TRAZO} strokeWidth="1.6" />
      <circle cx="122" cy="108" r="10" stroke={TRAZO} strokeWidth="1.4" />
      <circle cx="150" cy="108" r="10" stroke={TRAZO} strokeWidth="1.4" />
      <circle cx="178" cy="108" r="10" stroke={ACENTO} strokeWidth="1.4" />
      <path d="M196 120 V102 h10 v18" stroke={TRAZO} strokeWidth="1.4" />
    </Lienzo>
  );
}

/** Nuevas energías: el molino y los paneles. */
export function NuevasEnergias({ className }: Props) {
  return (
    <Lienzo className={className}>
      <path d="M0 118 H240" stroke={SUAVE} strokeWidth="1" opacity="0.5" />

      {/* molino */}
      <path d="M64 118 L70 52" stroke={TRAZO} strokeWidth="1.8" />
      <circle cx="70" cy="50" r="3" fill="var(--color-superficie)" stroke={ACENTO} strokeWidth="1.6" />
      <path d="M70 50 L70 18" stroke={ACENTO} strokeWidth="1.8" />
      <path d="M70 50 L98 64" stroke={ACENTO} strokeWidth="1.8" />
      <path d="M70 50 L42 64" stroke={ACENTO} strokeWidth="1.8" />
      <path d="M56 118 H78" stroke={TRAZO} strokeWidth="1.4" />

      {/* molino chico, atrás */}
      <path d="M32 118 L36 78" stroke={TRAZO} strokeWidth="1.2" opacity="0.55" />
      <path d="M36 77 L36 60 M36 77 L50 85 M36 77 L22 85" stroke={TRAZO} strokeWidth="1.2" opacity="0.55" />

      {/* paneles solares */}
      <path d="M140 112 L164 78 H208 L188 112 Z" stroke={TRAZO} strokeWidth="1.5" />
      <path d="M152 95 H192 M164 78 L150 112 M180 78 L168 112" stroke={TRAZO} strokeWidth="1" opacity="0.6" />
      <path d="M150 112 V120 M186 112 V120" stroke={TRAZO} strokeWidth="1.3" />

      {/* el sol */}
      <circle cx="206" cy="40" r="9" stroke={ACENTO} strokeWidth="1.5" />
      <path d="M206 24 V18 M206 62 V56 M190 40 h-6 M228 40 h-6" stroke={ACENTO} strokeWidth="1.3" />
    </Lienzo>
  );
}

/** Administración central: la casa matriz y lo que no es un negocio. */
export function Central({ className }: Props) {
  return (
    <Lienzo className={className}>
      <path d="M0 118 H240" stroke={SUAVE} strokeWidth="1" opacity="0.5" />
      <path d="M84 118 V46 h72 v72" stroke={TRAZO} strokeWidth="1.6" />
      <path d="M84 46 L120 26 L156 46" stroke={ACENTO} strokeWidth="1.6" />
      {[62, 78, 94].map((y) => (
        <path key={y} d={`M94 ${y} h52`} stroke={TRAZO} strokeWidth="1" opacity="0.55" />
      ))}
      <path d="M112 118 V102 h16 v16" stroke={ACENTO} strokeWidth="1.4" />
    </Lienzo>
  );
}

/** El segmento que ya no se publica: se dibuja apagado, como lo que fue. */
export function Historico({ className }: Props) {
  return (
    <Lienzo className={className}>
      <path d="M0 118 H240" stroke={SUAVE} strokeWidth="1" opacity="0.4" />
      <path d="M70 118 V66 h40 v52" stroke={SUAVE} strokeWidth="1.4" opacity="0.7" />
      <path d="M130 118 V84 h40 v34" stroke={SUAVE} strokeWidth="1.4" opacity="0.55" />
      <path d="M70 66 L90 52 L110 66" stroke={SUAVE} strokeWidth="1.3" opacity="0.7" />
    </Lienzo>
  );
}

export const ILUSTRACIONES: Record<string, (props: Props) => React.ReactElement> = {
  Upstream,
  'Midstream y Downstream': MidstreamDownstream,
  Downstream: MidstreamDownstream,
  Industrialización: MidstreamDownstream,
  Comercialización: MidstreamDownstream,
  'GNL y gas integrado': GasIntegrado,
  'Gas y energía': GasIntegrado,
  'Nuevas energías': NuevasEnergias,
  'Administración central y otros': Central,
  'Ajustes de consolidación': Historico,
};

export function IlustracionSegmento({ segmento, className }: { segmento: string; className?: string }) {
  const Dibujo = ILUSTRACIONES[segmento] ?? Historico;
  return <Dibujo className={className} />;
}
