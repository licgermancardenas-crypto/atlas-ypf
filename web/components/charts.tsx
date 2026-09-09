'use client';

// Los gráficos de Recharts de la página. Comparten ejes, tooltip y paleta, así
// que viven juntos: si el tooltip cambia, cambia una vez para todos.

import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type {
  CurvasDeclive,
  Descomposicion,
  EventoBalance,
  PuntoProduccion,
  PuntoSerieEbitda,
  PuntoSemanal,
} from '@/lib/data';
import { fmt } from '@/lib/data';

const COLORES = {
  crudo: 'oklch(0.76 0.15 62)',
  crudoSuave: 'oklch(0.62 0.13 62)',
  shale: 'oklch(0.72 0.13 195)',
  alza: 'oklch(0.74 0.15 155)',
  baja: 'oklch(0.66 0.18 20)',
  neutro: 'oklch(0.62 0.02 250)',
  grilla: 'oklch(0.33 0.018 250)',
  texto: 'oklch(0.72 0.012 250)',
};

const ejeComun = {
  stroke: COLORES.texto,
  tick: { fill: COLORES.texto, fontSize: 11 },
  tickLine: false,
  axisLine: { stroke: COLORES.grilla },
};

const tooltipComun = {
  contentStyle: {
    background: 'oklch(0.22 0.014 250)',
    border: '1px solid oklch(0.33 0.018 250)',
    borderRadius: '0.5rem',
    fontSize: '0.8rem',
  },
  labelStyle: { color: 'oklch(0.95 0.005 250)', marginBottom: '0.25rem' },
};

function Marco({ children, alto = 320 }: { children: React.ReactElement; alto?: number }) {
  return (
    <ResponsiveContainer width="100%" height={alto}>
      {children}
    </ResponsiveContainer>
  );
}

// --------------------------------------------------------------------------- //
// EBITDA contra Brent
// --------------------------------------------------------------------------- //
export function EbitdaBrent({ serie }: { serie: PuntoSerieEbitda[] }) {
  const datos = serie
    .filter((punto) => punto.adj_ebitda_musd !== null)
    .map((punto) => ({ ...punto, etiqueta: fmt.trimestre(punto.trimestre) }));

  return (
    <Marco alto={340}>
      <ComposedChart data={datos} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={COLORES.grilla} strokeDasharray="2 4" vertical={false} />
        <XAxis dataKey="etiqueta" {...ejeComun} interval={3} />
        <YAxis yAxisId="ebitda" {...ejeComun} width={52} />
        <YAxis yAxisId="brent" orientation="right" {...ejeComun} width={44} />
        <Tooltip
          {...tooltipComun}
          formatter={(valor, nombre) =>
            String(nombre) === 'Brent'
              ? [`US$ ${fmt.decimal(Number(valor))}/bbl`, String(nombre)]
              : [fmt.musd(Number(valor)), String(nombre)]
          }
        />
        <Legend wrapperStyle={{ fontSize: '0.75rem', color: COLORES.texto }} />
        <Bar
          yAxisId="ebitda"
          dataKey="adj_ebitda_musd"
          name="EBITDA ajustado"
          fill={COLORES.crudoSuave}
          radius={[3, 3, 0, 0]}
        />
        <Line
          yAxisId="brent"
          type="monotone"
          dataKey="brent_usd"
          name="Brent"
          stroke={COLORES.shale}
          strokeWidth={2}
          dot={false}
        />
      </ComposedChart>
    </Marco>
  );
}

// --------------------------------------------------------------------------- //
// Producción de shale contra costo de extracción
// --------------------------------------------------------------------------- //
export function ShaleYCostos({ serie }: { serie: PuntoSerieEbitda[] }) {
  const datos = serie
    .filter((punto) => punto.shale_oil_kbbld !== null)
    .map((punto) => ({ ...punto, etiqueta: fmt.trimestre(punto.trimestre) }));

  return (
    <Marco alto={300}>
      <ComposedChart data={datos} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={COLORES.grilla} strokeDasharray="2 4" vertical={false} />
        <XAxis dataKey="etiqueta" {...ejeComun} />
        <YAxis yAxisId="shale" {...ejeComun} width={48} />
        <YAxis yAxisId="costo" orientation="right" domain={[0, 20]} {...ejeComun} width={40} />
        <Tooltip
          {...tooltipComun}
          formatter={(valor, nombre) =>
            String(nombre).startsWith('Lifting')
              ? [`US$ ${fmt.decimal(Number(valor))}/boe`, String(nombre)]
              : [`${fmt.decimal(Number(valor))} Kbbl/d`, String(nombre)]
          }
        />
        <Legend wrapperStyle={{ fontSize: '0.75rem', color: COLORES.texto }} />
        <Area
          yAxisId="shale"
          type="monotone"
          dataKey="shale_oil_kbbld"
          name="Shale oil"
          stroke={COLORES.shale}
          fill={COLORES.shale}
          fillOpacity={0.15}
          strokeWidth={2}
        />
        <Line
          yAxisId="costo"
          type="monotone"
          dataKey="lifting_cost_usd_boe"
          name="Lifting cost"
          stroke={COLORES.crudo}
          strokeWidth={2}
          dot={false}
        />
      </ComposedChart>
    </Marco>
  );
}

// --------------------------------------------------------------------------- //
// Event study: reacción anormal a cada balance
// --------------------------------------------------------------------------- //
export function ReaccionBalances({ eventos }: { eventos: EventoBalance[] }) {
  const datos = eventos.map((evento) => ({
    etiqueta: fmt.trimestre(evento.trimestre),
    anormal: evento.retorno_anormal_dia * 100,
    esUltimo: evento.trimestre === eventos[eventos.length - 1]?.trimestre,
  }));

  return (
    <Marco alto={300}>
      <BarChart data={datos} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={COLORES.grilla} strokeDasharray="2 4" vertical={false} />
        <XAxis dataKey="etiqueta" {...ejeComun} angle={-45} textAnchor="end" height={56} />
        <YAxis {...ejeComun} width={44} unit="%" />
        <Tooltip
          {...tooltipComun}
          formatter={(valor) => [`${fmt.numero(Number(valor))}%`, 'Retorno anormal']}
        />
        <ReferenceLine y={0} stroke={COLORES.texto} strokeWidth={1} />
        <Bar dataKey="anormal" radius={[3, 3, 0, 0]}>
          {datos.map((punto, indice) => (
            <Cell
              key={indice}
              fill={punto.anormal >= 0 ? COLORES.alza : COLORES.baja}
              fillOpacity={punto.esUltimo ? 1 : 0.65}
              stroke={punto.esUltimo ? COLORES.crudo : undefined}
              strokeWidth={punto.esUltimo ? 2 : 0}
            />
          ))}
        </Bar>
      </BarChart>
    </Marco>
  );
}

// --------------------------------------------------------------------------- //
// Puente del último trimestre
// --------------------------------------------------------------------------- //
export function Puente({ descomposicion }: { descomposicion: Descomposicion }) {
  const pasos = [
    { nombre: fmt.trimestre(descomposicion.desde), valor: descomposicion.ebitda_previo_musd, tipo: 'total' },
    { nombre: 'Precio', valor: descomposicion.efecto_precio_musd, tipo: 'paso' },
    { nombre: 'Volumen', valor: descomposicion.efecto_volumen_musd, tipo: 'paso' },
    { nombre: 'Costo', valor: descomposicion.efecto_costo_musd, tipo: 'paso' },
    { nombre: 'Downstream', valor: descomposicion.efecto_downstream_musd, tipo: 'paso' },
    { nombre: 'Sin explicar', valor: descomposicion.residual_musd, tipo: 'residual' },
    { nombre: fmt.trimestre(descomposicion.hasta), valor: descomposicion.ebitda_actual_musd, tipo: 'total' },
  ] as const;

  // Cada barra intermedia flota sobre el acumulado anterior: es lo que hace que
  // un waterfall se lea como una suma y no como siete barras sueltas.
  let acumulado = 0;
  const datos = pasos.map((paso) => {
    if (paso.tipo === 'total') {
      acumulado = paso.valor;
      return { ...paso, base: 0, alto: paso.valor };
    }
    const base = acumulado;
    acumulado += paso.valor;
    return { ...paso, base: Math.min(base, acumulado), alto: Math.abs(paso.valor) };
  });

  const color = (tipo: string, valor: number) =>
    tipo === 'total' ? COLORES.neutro : tipo === 'residual' ? COLORES.crudo : valor >= 0 ? COLORES.alza : COLORES.baja;

  return (
    <Marco alto={300}>
      <BarChart data={datos} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} stackOffset="sign">
        <CartesianGrid stroke={COLORES.grilla} strokeDasharray="2 4" vertical={false} />
        <XAxis dataKey="nombre" {...ejeComun} />
        <YAxis {...ejeComun} width={56} />
        <Tooltip
          {...tooltipComun}
          formatter={(_valor, _nombre, item) => [
            fmt.musd((item?.payload as { valor?: number } | undefined)?.valor ?? 0),
            'Efecto',
          ]}
        />
        <Bar dataKey="base" stackId="puente" fill="transparent" />
        <Bar dataKey="alto" stackId="puente" radius={[3, 3, 0, 0]}>
          {datos.map((punto, indice) => (
            <Cell key={indice} fill={color(punto.tipo, punto.valor)} />
          ))}
        </Bar>
      </BarChart>
    </Marco>
  );
}

// --------------------------------------------------------------------------- //
// Producción de Vaca Muerta por operador
// --------------------------------------------------------------------------- //
export function ProduccionPorOperador({ puntos }: { puntos: PuntoProduccion[] }) {
  const operadores = Array.from(new Set(puntos.map((punto) => punto.operador!))).slice(0, 6);
  const porFecha = new Map<string, Record<string, number | string>>();

  for (const punto of puntos) {
    if (!operadores.includes(punto.operador!)) continue;
    const fila = porFecha.get(punto.fecha) ?? { fecha: punto.fecha };
    fila[punto.operador!] = punto.boed / 1000; // Mboe/d: el eje no necesita seis dígitos
    porFecha.set(punto.fecha, fila);
  }

  const datos = Array.from(porFecha.values()).sort((a, b) =>
    String(a.fecha).localeCompare(String(b.fecha)),
  );
  const paleta = [
    COLORES.crudo,
    COLORES.shale,
    COLORES.alza,
    COLORES.baja,
    COLORES.crudoSuave,
    COLORES.neutro,
  ];

  return (
    <Marco alto={320}>
      <LineChart data={datos} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={COLORES.grilla} strokeDasharray="2 4" vertical={false} />
        <XAxis dataKey="fecha" {...ejeComun} minTickGap={40} />
        <YAxis {...ejeComun} width={44} unit="k" />
        <Tooltip
          {...tooltipComun}
          formatter={(valor, nombre) => [`${fmt.decimal(Number(valor))} Mboe/d`, String(nombre)]}
        />
        <Legend wrapperStyle={{ fontSize: '0.75rem', color: COLORES.texto }} />
        {operadores.map((operador, indice) => (
          <Line
            key={operador}
            type="monotone"
            dataKey={operador}
            stroke={paleta[indice % paleta.length]}
            strokeWidth={operador === 'YPF' ? 2.5 : 1.5}
            dot={false}
          />
        ))}
      </LineChart>
    </Marco>
  );
}

// --------------------------------------------------------------------------- //
// Curvas tipo por cohorte de pozos
// --------------------------------------------------------------------------- //
export function CurvasTipo({ curvas }: { curvas: CurvasDeclive['curva_tipo_por_vintage'] }) {
  const cohortes = ['2019.0', '2021.0', '2023.0', '2024.0', '2025.0'];
  const porMes = new Map<number, Record<string, number>>();

  for (const punto of curvas) {
    if (!cohortes.includes(punto.vintage) || punto.mes_prod > 36) continue;
    const fila = porMes.get(punto.mes_prod) ?? { mes_prod: punto.mes_prod };
    fila[punto.vintage] = punto.caudal_bd;
    porMes.set(punto.mes_prod, fila);
  }

  const datos = Array.from(porMes.values()).sort((a, b) => a.mes_prod - b.mes_prod);
  const paleta = [COLORES.neutro, COLORES.crudoSuave, COLORES.shale, COLORES.alza, COLORES.crudo];

  return (
    <Marco alto={320}>
      <LineChart data={datos} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={COLORES.grilla} strokeDasharray="2 4" vertical={false} />
        <XAxis
          dataKey="mes_prod"
          {...ejeComun}
          label={{ value: 'mes de producción', fill: COLORES.texto, fontSize: 11, dy: 12 }}
        />
        <YAxis {...ejeComun} width={52} />
        <Tooltip
          {...tooltipComun}
          labelFormatter={(valor) => `Mes ${valor}`}
          formatter={(valor, nombre) => [
            `${fmt.entero(Number(valor))} bbl/d`,
            `Pozos ${String(nombre).replace('.0', '')}`,
          ]}
        />
        <Legend
          wrapperStyle={{ fontSize: '0.75rem', color: COLORES.texto }}
          formatter={(valor: string) => valor.replace('.0', '')}
        />
        {cohortes.map((cohorte, indice) => (
          <Line
            key={cohorte}
            type="monotone"
            dataKey={cohorte}
            stroke={paleta[indice]}
            strokeWidth={indice === cohortes.length - 1 ? 2.5 : 1.5}
            dot={false}
          />
        ))}
      </LineChart>
    </Marco>
  );
}

// --------------------------------------------------------------------------- //
// La acción contra sus comparables y el riesgo país
// --------------------------------------------------------------------------- //
export function AccionYRiesgoPais({ serie }: { serie: PuntoSemanal[] }) {
  return (
    <Marco alto={320}>
      <ComposedChart data={serie} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={COLORES.grilla} strokeDasharray="2 4" vertical={false} />
        <XAxis dataKey="fecha" {...ejeComun} minTickGap={60} />
        <YAxis yAxisId="base100" {...ejeComun} width={48} />
        <YAxis yAxisId="embi" orientation="right" {...ejeComun} width={52} />
        <Tooltip
          {...tooltipComun}
          formatter={(valor, nombre) =>
            String(nombre) === 'Riesgo país'
              ? [`${fmt.entero(Number(valor))} pb`, String(nombre)]
              : [fmt.decimal(Number(valor)), String(nombre)]
          }
        />
        <Legend wrapperStyle={{ fontSize: '0.75rem', color: COLORES.texto }} />
        <Area
          yAxisId="embi"
          type="monotone"
          dataKey="embi"
          name="Riesgo país"
          stroke="transparent"
          fill={COLORES.baja}
          fillOpacity={0.12}
        />
        <Line
          yAxisId="base100"
          type="monotone"
          dataKey="ypf"
          name="YPF"
          stroke={COLORES.crudo}
          strokeWidth={2.5}
          dot={false}
        />
        <Line
          yAxisId="base100"
          type="monotone"
          dataKey="vist"
          name="Vista"
          stroke={COLORES.shale}
          strokeWidth={1.5}
          dot={false}
        />
        <Line
          yAxisId="base100"
          type="monotone"
          dataKey="brent"
          name="Brent"
          stroke={COLORES.neutro}
          strokeWidth={1.5}
          strokeDasharray="4 3"
          dot={false}
        />
      </ComposedChart>
    </Marco>
  );
}
