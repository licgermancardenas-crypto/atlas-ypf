// El sparkline de un KPI: la forma de la serie, sin ejes.
//
// No reemplaza al gráfico grande ni pretende que se lea un valor: contesta una
// sola pregunta —¿esto venía subiendo o bajando?— en el espacio de una línea de
// texto. Por eso no lleva escala, no lleva grilla y no responde al mouse.
//
// Es SVG a mano y no Recharts: un ResponsiveContainer por tarjeta son cuatro
// observers de resize para dibujar cuarenta puntos.

export function Chispa({
  valores,
  color = 'var(--color-azul-claro)',
  alto = 28,
  ancho = 120,
  etiqueta,
}: {
  valores: number[];
  color?: string;
  alto?: number;
  ancho?: number;
  /** Qué dice la serie, para quien no la ve. */
  etiqueta?: string;
}) {
  if (valores.length < 2) return null;

  const maximo = Math.max(...valores);
  const minimo = Math.min(...valores);
  const rango = maximo - minimo || 1;
  const paso = ancho / (valores.length - 1);
  // Un colchón arriba y abajo para que el trazo no se pegue al borde de la caja.
  const y = (valor: number) => alto - 3 - ((valor - minimo) / rango) * (alto - 6);

  const puntos = valores.map((valor, indice) => `${indice * paso},${y(valor)}`);
  const linea = `M${puntos.join(' L')}`;
  const area = `${linea} L${ancho},${alto} L0,${alto} Z`;
  const ultimo = valores[valores.length - 1];
  const id = `chispa-${Math.round(maximo)}-${valores.length}`;

  return (
    <svg
      viewBox={`0 0 ${ancho} ${alto}`}
      width="100%"
      height={alto}
      preserveAspectRatio="none"
      role={etiqueta ? 'img' : undefined}
      aria-label={etiqueta}
      aria-hidden={etiqueta ? undefined : true}
      className="overflow-visible"
    >
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.28} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${id})`} />
      <path d={linea} fill="none" stroke={color} strokeWidth={1.4} vectorEffect="non-scaling-stroke" />
      <circle cx={ancho} cy={y(ultimo)} r={2} fill={color} />
    </svg>
  );
}

/** Una barra de composición: tres partes que suman uno.
 *
 *  Sirve donde un porcentaje solo no alcanza: "76% shale" no dice qué es el
 *  otro 24%, y acá se ve que es casi todo convencional. */
export function Composicion({
  partes,
  etiqueta,
}: {
  partes: { nombre: string; valor: number; color: string }[];
  etiqueta?: string;
}) {
  const total = partes.reduce((suma, parte) => suma + Math.max(parte.valor, 0), 0);
  if (!total) return null;

  return (
    <div
      className="flex h-1.5 w-full overflow-hidden rounded-full bg-superficie-alta"
      role={etiqueta ? 'img' : undefined}
      aria-label={etiqueta}
      aria-hidden={etiqueta ? undefined : true}
    >
      {partes.map((parte) => (
        <span
          key={parte.nombre}
          className="h-full"
          style={{
            width: `${(Math.max(parte.valor, 0) / total) * 100}%`,
            background: parte.color,
          }}
          title={parte.nombre}
        />
      ))}
    </div>
  );
}
