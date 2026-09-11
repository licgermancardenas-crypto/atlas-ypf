'use client';

// Lo que produce YPF, abierto por dónde y por cuándo.
//
// El explorador del módulo operativo mira el país y contesta quién produce. Este
// mira una sola compañía y contesta las dos preguntas que vienen después: de
// dónde sale lo que produce y cómo cambia según la lupa con la que se lo mire.
//
// Las cinco dimensiones son las que usa cualquiera que siga el sector —cuenca,
// provincia, concesión, yacimiento y el pueblo más cercano—, y las tres escalas
// de tiempo importan más de lo que parece: en el mes se ve el ruido operativo
// (una parada de planta, un mes de 28 días), en el trimestre se ve lo que la
// compañía reporta y en el año se ve la tendencia. El mismo dato cuenta tres
// historias distintas.
//
// Dos decisiones que gobiernan todo el componente:
//
//   · el pipeline entrega volumen mensual y no caudal. El volumen se suma para
//     armar un trimestre o un año; el caudal no, porque promediar caudales de
//     meses de distinta duración da un número que no es el de nadie. El caudal
//     se calcula acá, al final, dividiendo por los días del período elegido.
//   · "por día" no es un corte de la fuente, que es mensual: es el caudal
//     promedio. Lo dice el selector y lo repite la nota, porque la diferencia
//     entre "el día que más produjo" y "el promedio diario del mes" es la
//     diferencia entre un dato que existe y uno que no.

import { useEffect, useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { fmt } from '@/lib/data';
import { useFiltros } from './estado/filtros';
import { Esqueleto, Panel } from './Panel';
import type { FilaRanking } from './RankingCrecimiento';

export interface MiembroYPF {
  nombre: string;
  oil_convencional?: number[];
  oil_shale?: number[];
  oil_tight?: number[];
  gas_convencional?: number[];
  gas_shale?: number[];
  gas_tight?: number[];
}

export interface ProduccionYPF {
  empresa: string;
  fuente: string;
  nota: string;
  nota_localidad: string;
  cobertura: { desde: string; hasta: string; meses: number };
  fechas: string[];
  dias: number[];
  total: Record<string, number[]>;
  resumen: {
    petroleo_bd: number;
    gas_boed: number;
    shale_bd: number;
    convencional_bd: number;
    tight_bd: number;
    concesiones: number;
    yacimientos: number;
    cuencas: number;
    provincias: number;
  };
  rankings: Record<string, FilaRanking[]>;
  localidades: Record<string, { pueblo: string; km: number }>;
  dimensiones_en: string;
}

type IdDimension = 'cuenca' | 'provincia' | 'concesion' | 'yacimiento' | 'localidad';
type IdFluido = 'oil' | 'gas' | 'boe';
type IdRecurso = 'todo' | 'convencional' | 'shale' | 'tight';
type IdPeriodo = 'mes' | 'trimestre' | 'anio';
type IdMetrica = 'caudal' | 'volumen';

const DIMENSIONES: { id: IdDimension; etiqueta: string }[] = [
  { id: 'cuenca', etiqueta: 'Cuenca' },
  { id: 'provincia', etiqueta: 'Provincia' },
  { id: 'concesion', etiqueta: 'Concesión' },
  { id: 'yacimiento', etiqueta: 'Yacimiento' },
  { id: 'localidad', etiqueta: 'Localidad' },
];

const FLUIDOS: { id: IdFluido; etiqueta: string }[] = [
  { id: 'oil', etiqueta: 'Petróleo' },
  { id: 'gas', etiqueta: 'Gas' },
  { id: 'boe', etiqueta: 'Todo, en boe' },
];

const RECURSOS: { id: IdRecurso; etiqueta: string; ayuda: string }[] = [
  { id: 'todo', etiqueta: 'Todo', ayuda: 'Convencional, shale y tight sumados.' },
  {
    id: 'convencional',
    etiqueta: 'Convencional',
    ayuda: 'Los campos viejos: la parte que declina y que el shale tiene que compensar.',
  },
  { id: 'shale', etiqueta: 'Shale', ayuda: 'Vaca Muerta, casi en su totalidad.' },
  { id: 'tight', etiqueta: 'Tight', ayuda: 'No convencional de roca compacta: Lajas, Mulichinco.' },
];

const PERIODOS: { id: IdPeriodo; etiqueta: string }[] = [
  { id: 'mes', etiqueta: 'Mes' },
  { id: 'trimestre', etiqueta: 'Trimestre' },
  { id: 'anio', etiqueta: 'Año' },
];

const METRICAS: { id: IdMetrica; etiqueta: string }[] = [
  { id: 'caudal', etiqueta: 'Por día' },
  { id: 'volumen', etiqueta: 'Total del período' },
];

const COLUMNAS_RANKING = [
  { clave: 'nombre', titulo: 'Nombre' },
  { clave: 'actual_bd', titulo: 'Últimos 12m (bd)', alineacion: 'der' as const },
  { clave: 'previo_bd', titulo: '12m previos (bd)', alineacion: 'der' as const },
  { clave: 'delta_bd', titulo: 'Variación (bd)', alineacion: 'der' as const },
  {
    clave: 'crecimiento',
    titulo: 'Relativa',
    alineacion: 'der' as const,
    formato: 'porcentaje0' as const,
  },
  {
    clave: 'participacion',
    titulo: 'De YPF',
    alineacion: 'der' as const,
    formato: 'porcentaje0' as const,
  },
];

// Diecisiete colores, uno por miembro con serie propia más "Otros". El azul de
// marca al frente: el primero del ranking es el protagonista.
const COLORES = [
  '#0054eb',
  '#f0a830',
  '#3fb98a',
  '#75aadb',
  '#e2603f',
  '#8e6fd8',
  '#4d90ff',
  '#c9a227',
  '#2f8f72',
  '#a86a4d',
  '#d46fa0',
  '#5f7099',
  '#2bb3c0',
  '#b0713f',
  '#7f9ad4',
  '#9a5ea8',
  '#41546f',
];

/** Las claves del JSON que entran según el fluido y el recurso elegidos. */
function clavesDe(fluido: IdFluido, recurso: IdRecurso): (keyof MiembroYPF)[] {
  const fluidos = fluido === 'boe' ? (['oil', 'gas'] as const) : ([fluido] as const);
  const recursos =
    recurso === 'todo' ? (['convencional', 'shale', 'tight'] as const) : ([recurso] as const);
  return fluidos.flatMap((f) => recursos.map((r) => `${f}_${r}` as keyof MiembroYPF));
}

/** Cómo se llama el período al que cae cada mes, cuántos días tiene y si está
 *  completo.
 *
 *  Lo de "completo" importa: el último trimestre del archivo casi siempre tiene
 *  uno o dos meses, y mostrado como total del período parece un derrumbe que no
 *  ocurrió. Va marcado con asterisco. */
function agrupar(fechas: string[], dias: number[], periodo: IdPeriodo) {
  const mesesEsperados = periodo === 'mes' ? 1 : periodo === 'trimestre' ? 3 : 12;
  const etiquetas: string[] = [];
  const diasPorGrupo: number[] = [];
  const mesesPorGrupo: number[] = [];
  const grupoDe: number[] = [];

  fechas.forEach((fecha, indice) => {
    const anio = fecha.slice(0, 4);
    const mes = Number(fecha.slice(5, 7));
    const etiqueta =
      periodo === 'mes' ? fecha : periodo === 'anio' ? anio : `${anio} T${Math.ceil(mes / 3)}`;

    if (etiquetas[etiquetas.length - 1] !== etiqueta) {
      etiquetas.push(etiqueta);
      diasPorGrupo.push(0);
      mesesPorGrupo.push(0);
    }
    grupoDe[indice] = etiquetas.length - 1;
    diasPorGrupo[etiquetas.length - 1] += dias[indice] ?? 30;
    mesesPorGrupo[etiquetas.length - 1] += 1;
  });

  const completo = mesesPorGrupo.map((meses) => meses >= mesesEsperados);
  return { etiquetas, diasPorGrupo, grupoDe, completo };
}

export function ExploradorYPF({ datos }: { datos: ProduccionYPF }) {
  const [dimension, setDimension] = useState<IdDimension>('concesion');
  const [fluido, setFluido] = useState<IdFluido>('boe');
  const [recurso, setRecurso] = useState<IdRecurso>('todo');
  const [periodo, setPeriodo] = useState<IdPeriodo>('trimestre');
  const [metrica, setMetrica] = useState<IdMetrica>('caudal');
  const [participacion, setParticipacion] = useState(false);
  const { filtros } = useFiltros();
  const [dimensiones, setDimensiones] = useState<Record<string, { miembros: MiembroYPF[] }> | null>(
    null,
  );

  // Las series mensuales son 250 KB y no hacen falta para leer los números de
  // arriba: se bajan cuando el panel se monta, no con la página.
  useEffect(() => {
    let vigente = true;
    fetch('/data/ypf_dimensiones.json')
      .then((respuesta) => respuesta.json())
      .then((payload: { dimensiones: Record<string, { miembros: MiembroYPF[] }> }) => {
        if (vigente) setDimensiones(payload.dimensiones);
      })
      .catch(() => {
        if (vigente) setDimensiones({});
      });
    return () => {
      vigente = false;
    };
  }, []);

  const unidad = metrica === 'caudal' ? (fluido === 'oil' ? 'bbl/d' : 'boe/d') : fluido === 'oil' ? 'bbl' : 'boe';
  const miembrosCrudos = dimensiones?.[dimension]?.miembros;

  const { filas, nombres, hayParciales } = useMemo(() => {
    if (!miembrosCrudos) {
      return { filas: [] as Record<string, string | number>[], nombres: [], hayParciales: false };
    }

    const claves = clavesDe(fluido, recurso);
    const { etiquetas, diasPorGrupo, grupoDe, completo } = agrupar(datos.fechas, datos.dias, periodo);

    // Un acumulador por miembro y por período: se recorre el mes una sola vez.
    const acumulado = new Map<string, number[]>();
    for (const miembro of miembrosCrudos) {
      const suma = new Array(etiquetas.length).fill(0);
      for (const clave of claves) {
        const serie = miembro[clave] as number[] | undefined;
        if (!serie) continue;
        for (let indice = 0; indice < serie.length; indice += 1) {
          suma[grupoDe[indice]] += serie[indice];
        }
      }
      if (suma.some((valor) => valor > 0)) acumulado.set(miembro.nombre, suma);
    }

    // Orden de apilado: el que más produjo en el último período, abajo.
    const visibles = [...acumulado.entries()].sort(
      (a, b) => (b[1][etiquetas.length - 1] ?? 0) - (a[1][etiquetas.length - 1] ?? 0),
    );

    let parciales = false;
    const armadas = etiquetas.map((etiqueta, indice) => {
      const incompleto = !completo[indice];
      if (incompleto) parciales = true;
      const fila: Record<string, string | number> = {
        periodo: incompleto ? `${etiqueta}*` : etiqueta,
      };
      let total = 0;
      for (const [nombre, serie] of visibles) {
        const volumen = serie[indice] ?? 0;
        const valor = metrica === 'caudal' ? volumen / (diasPorGrupo[indice] || 1) : volumen;
        fila[nombre] = Math.round(valor);
        total += valor;
      }
      if (participacion && total > 0) {
        for (const [nombre] of visibles) {
          fila[nombre] = Number((((fila[nombre] as number) / total) * 100).toFixed(1));
        }
      }
      return fila;
    });

    // El rango de años lo manda la barra de filtros, que es global al sitio: si
    // alguien eligió 2019-2026 arriba, este gráfico no puede arrancar en 2009.
    const dentro = armadas.filter((fila) => {
      const anio = Number(String(fila.periodo).slice(0, 4));
      return anio >= filtros.desde && anio <= filtros.hasta;
    });

    return {
      filas: dentro,
      nombres: visibles.map(([nombre]) => nombre),
      hayParciales: parciales && dentro.some((fila) => String(fila.periodo).endsWith('*')),
    };
  }, [
    miembrosCrudos,
    datos.fechas,
    datos.dias,
    fluido,
    recurso,
    periodo,
    metrica,
    participacion,
    filtros.desde,
    filtros.hasta,
  ]);

  const ranking = datos.rankings[dimension] ?? [];
  const ayuda = RECURSOS.find((item) => item.id === recurso)!.ayuda;
  const ultima = filas[filas.length - 1];
  const totalUltimo = nombres.reduce((suma, nombre) => suma + ((ultima?.[nombre] as number) ?? 0), 0);

  const compacto = (valor: number) =>
    Math.abs(valor) >= 1_000_000
      ? `${fmt.numero(valor / 1_000_000, 1)}M`
      : Math.abs(valor) >= 1_000
        ? `${fmt.numero(valor / 1_000, 0)}k`
        : fmt.entero(valor);

  return (
    <Panel
      titulo={`Producción de ${datos.empresa} por ${DIMENSIONES.find((d) => d.id === dimension)!.etiqueta.toLowerCase()}`}
      archivo={`atlas-ypf-produccion-${dimension}`}
      columnas={COLUMNAS_RANKING}
      datos={ranking as unknown as Record<string, unknown>[]}
      etiquetaVista="Gráfico"
      nota={
        <>
          {ayuda} {datos.nota}
          {dimension === 'localidad' ? ` ${datos.nota_localidad}` : ''}
          {hayParciales
            ? ' El período marcado con asterisco está incompleto: la fuente todavía no publicó todos sus meses.'
            : ''}{' '}
          La tabla trae el ranking
          completo de la dimensión elegida —{ranking.length}{' '}
          {dimension === 'localidad' ? 'localidades' : `${dimension}s`}— y se descarga en CSV.
        </>
      }
    >
      <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2">
        <Segmentado
          opciones={DIMENSIONES}
          valor={dimension}
          alCambiar={(id) => setDimension(id as IdDimension)}
        />
        <Segmentado opciones={FLUIDOS} valor={fluido} alCambiar={(id) => setFluido(id as IdFluido)} />
        <Segmentado
          opciones={RECURSOS}
          valor={recurso}
          alCambiar={(id) => setRecurso(id as IdRecurso)}
        />
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2">
        <Segmentado
          opciones={PERIODOS}
          valor={periodo}
          alCambiar={(id) => setPeriodo(id as IdPeriodo)}
        />
        <Segmentado
          opciones={METRICAS}
          valor={metrica}
          alCambiar={(id) => setMetrica(id as IdMetrica)}
        />
        <label className="flex items-center gap-2 text-xs text-texto-suave">
          <input
            type="checkbox"
            checked={participacion}
            onChange={(evento) => setParticipacion(evento.target.checked)}
            className="accent-[#0054eb]"
          />
          Ver participación
        </label>
        {ultima ? (
          <span className="tabular ml-auto text-xs text-texto-tenue">
            {String(ultima.periodo)}:{' '}
            <span className="text-texto">
              {participacion ? '100%' : `${fmt.entero(totalUltimo)} ${unidad}`}
            </span>
          </span>
        ) : null}
      </div>

      {!dimensiones ? (
        <>
          <p className="mb-3 font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-tenue">
            Bajando las series por dimensión…
          </p>
          <Esqueleto alto={360} />
        </>
      ) : (
        <ResponsiveContainer width="100%" height={380}>
          <AreaChart data={filas} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--color-borde)" strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="periodo"
              stroke="var(--color-texto-suave)"
              tick={{ fill: 'var(--color-texto-suave)', fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: 'var(--color-borde)' }}
              minTickGap={40}
            />
            <YAxis
              stroke="var(--color-texto-suave)"
              tick={{ fill: 'var(--color-texto-suave)', fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: 'var(--color-borde)' }}
              width={58}
              tickFormatter={(valor: number) =>
                participacion ? `${valor}%` : compacto(Number(valor))
              }
            />
            <Tooltip
              contentStyle={{
                background: 'var(--color-superficie-alta)',
                border: '1px solid var(--color-borde)',
                borderRadius: '0.5rem',
                fontSize: '0.75rem',
                fontFamily: 'var(--font-mono)',
                maxHeight: 280,
                overflow: 'auto',
              }}
              labelStyle={{ color: 'var(--color-texto)', marginBottom: '0.25rem' }}
              formatter={(valor, nombre) => [
                participacion
                  ? `${fmt.numero(Number(valor), 1)}%`
                  : `${fmt.entero(Number(valor))} ${unidad}`,
                String(nombre),
              ]}
            />
            <Legend wrapperStyle={{ fontSize: '0.7rem', color: 'var(--color-texto-suave)' }} />
            {nombres.map((nombre, indice) => (
              <Area
                key={nombre}
                type="monotone"
                dataKey={nombre}
                stackId="produccion"
                stroke={COLORES[indice % COLORES.length]}
                fill={COLORES[indice % COLORES.length]}
                fillOpacity={0.72}
                strokeWidth={0.5}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      )}
    </Panel>
  );
}

function Segmentado({
  opciones,
  valor,
  alCambiar,
}: {
  opciones: { id: string; etiqueta: string }[];
  valor: string;
  alCambiar: (id: string) => void;
}) {
  return (
    <div className="flex rounded-md border border-borde p-0.5">
      {opciones.map((opcion) => (
        <button
          key={opcion.id}
          type="button"
          onClick={() => alCambiar(opcion.id)}
          className={`rounded px-2.5 py-1 text-xs transition ${
            valor === opcion.id
              ? 'bg-superficie-alta text-azul-claro'
              : 'text-texto-tenue hover:text-texto-suave'
          }`}
        >
          {opcion.etiqueta}
        </button>
      ))}
    </div>
  );
}
