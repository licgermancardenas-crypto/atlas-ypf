// Los cálculos del módulo de producción, separados de la pantalla.
//
// Todo lo que la pantalla dice —la lectura de arriba, la variación de un KPI,
// una señal de la sección Intelligence— sale de acá y de los arrays que publica
// el pipeline. Nada se escribe a mano en el JSX: si un número no se puede
// calcular con los datos que hay, la función devuelve null y el componente
// muestra un guion, que es lo honesto.
//
// Dos reglas gobiernan este archivo:
//
//   · el pipeline entrega volumen mensual, no caudal. El volumen se suma para
//     armar un trimestre o un año; el caudal no, porque promediar caudales de
//     meses de distinta duración da un número que no es de nadie. El caudal se
//     calcula al final, dividiendo por los días del período.
//   · toda comparación declara contra qué compara. Un "+6%" sin período es un
//     número decorativo.

export type IdDimension = 'cuenca' | 'provincia' | 'concesion' | 'yacimiento' | 'localidad';
export type IdFluido = 'oil' | 'gas' | 'boe';
export type IdRecurso = 'todo' | 'convencional' | 'shale' | 'tight';
export type IdPeriodo = 'mes' | 'trimestre' | 'anio';
export type IdMetrica = 'caudal' | 'volumen';
export type IdVista =
  | 'produccion'
  | 'crecimiento'
  | 'participacion'
  | 'ranking'
  | 'cohortes'
  | 'curvas';

export interface MiembroYPF {
  nombre: string;
  oil_convencional?: number[];
  oil_shale?: number[];
  oil_tight?: number[];
  gas_convencional?: number[];
  gas_shale?: number[];
  gas_tight?: number[];
}

export interface FilaRankingYPF {
  nombre: string;
  actual_bd: number;
  previo_bd: number;
  delta_bd: number;
  crecimiento: number | null;
  participacion: number | null;
  oil_bd?: number;
  gas_bd?: number;
  shale_bd?: number;
  convencional_bd?: number;
  tight_bd?: number;
  shale_share?: number | null;
}

export interface Traspaso {
  dimension: IdDimension;
  nombre: string;
  /** Último mes en que el área declaró producción operada por YPF. */
  ultimo_mes: string;
  /** Caudal de los últimos tres meses en que declaró. */
  bd_previo: number;
  /** true si el archivo del país muestra el área todavía produciendo después
   *  de ese mes: entonces no dejó de producir, dejó de ser de YPF. */
  sigue_en_el_pais?: boolean;
  bd_pais?: number;
}

export interface FichaActivo {
  provincia?: string;
  cuenca?: string;
  concesion?: string;
  localidad?: string;
  yacimientos?: number;
  /** Cuando el activo cruza más de una: se guarda cuántas, no se elige en silencio. */
  provincias?: number;
  cuencas?: number;
  concesiones?: number;
}

export interface ProduccionYPF {
  empresa: string;
  fuente: string;
  nota: string;
  nota_localidad: string;
  generado?: string;
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
  rankings: Record<string, FilaRankingYPF[]>;
  meta: Record<string, Record<string, FichaActivo>>;
  /** Las áreas que dejaron de declarar producción operada por YPF. */
  traspasos?: Traspaso[];
  /** Los nombres de las cohortes, en orden, tal como los publica el pipeline. */
  cohortes?: string[];
  localidades: Record<string, { pueblo: string; km: number }>;
  dimensiones_en: string;
}

export const DIMENSIONES: { id: IdDimension; etiqueta: string; plural: string }[] = [
  { id: 'concesion', etiqueta: 'Concesión', plural: 'concesiones' },
  { id: 'yacimiento', etiqueta: 'Yacimiento', plural: 'yacimientos' },
  { id: 'cuenca', etiqueta: 'Cuenca', plural: 'cuencas' },
  { id: 'provincia', etiqueta: 'Provincia', plural: 'provincias' },
  { id: 'localidad', etiqueta: 'Localidad', plural: 'localidades' },
];

export const FLUIDOS: { id: IdFluido; etiqueta: string }[] = [
  { id: 'boe', etiqueta: 'Todo (boe)' },
  { id: 'oil', etiqueta: 'Petróleo' },
  { id: 'gas', etiqueta: 'Gas' },
];

export const RECURSOS: { id: IdRecurso; etiqueta: string; ayuda: string }[] = [
  { id: 'todo', etiqueta: 'Todo', ayuda: 'Convencional, shale y tight sumados.' },
  { id: 'shale', etiqueta: 'Shale', ayuda: 'Vaca Muerta, casi en su totalidad.' },
  {
    id: 'convencional',
    etiqueta: 'Convencional',
    ayuda: 'Los campos viejos: la parte que declina y que el shale tiene que compensar.',
  },
  { id: 'tight', etiqueta: 'Tight', ayuda: 'No convencional de roca compacta: Lajas, Mulichinco.' },
];

export const PERIODOS: { id: IdPeriodo; etiqueta: string; meses: number }[] = [
  { id: 'mes', etiqueta: 'Mes', meses: 1 },
  { id: 'trimestre', etiqueta: 'Trimestre', meses: 3 },
  { id: 'anio', etiqueta: 'Año', meses: 12 },
];

export const METRICAS: { id: IdMetrica; etiqueta: string }[] = [
  { id: 'caudal', etiqueta: 'Por día' },
  { id: 'volumen', etiqueta: 'Total del período' },
];

/** Los colores tienen significado: el fluido y el tipo de roca mandan, no el
 *  orden de la serie. Cuando se apilan activos, la rampa arranca por el azul de
 *  marca —el activo principal— y sigue con tonos que se distinguen sobre fondo
 *  oscuro sin volverse un arcoíris. */
export const COLOR = {
  petroleo: 'var(--color-oro)',
  gas: 'var(--color-celeste)',
  shale: 'var(--color-shale)',
  convencional: 'var(--color-neutro)',
  tight: 'var(--color-azul-claro)',
  alza: 'var(--color-alza)',
  baja: 'var(--color-baja)',
};

export const RAMPA = [
  '#0054eb',
  '#f0a830',
  '#3fb98a',
  '#8e6fd8',
  '#75aadb',
  '#e2603f',
  '#4d90ff',
  '#c9a227',
  '#2f8f72',
  '#a86a4d',
  '#d46fa0',
  '#2bb3c0',
  '#7f9ad4',
  '#9a5ea8',
  '#b0713f',
  '#5f7099',
  '#41546f',
];

/** El color de "Otros" es siempre el mismo y siempre el más apagado: la barra
 *  de resto no compite con ningún activo. */
export const COLOR_OTROS = '#41546f';
export const NOMBRE_OTROS = 'Otros';

export type ClaveSerie = keyof Omit<MiembroYPF, 'nombre'>;

/** Las claves del JSON que entran según fluido y tipo de recurso elegidos. */
export function clavesDe(fluido: IdFluido, recurso: IdRecurso): ClaveSerie[] {
  const fluidos: ('oil' | 'gas')[] = fluido === 'boe' ? ['oil', 'gas'] : [fluido];
  const recursos: ('convencional' | 'shale' | 'tight')[] =
    recurso === 'todo' ? ['convencional', 'shale', 'tight'] : [recurso];
  return fluidos.flatMap((f) => recursos.map((r) => `${f}_${r}` as ClaveSerie));
}

export interface Grupos {
  etiquetas: string[];
  /** Días de cada período: el divisor que convierte volumen en caudal. */
  dias: number[];
  /** Si el período tiene todos sus meses. El último casi nunca los tiene. */
  completo: boolean[];
  /** A qué período cae cada mes del array original. */
  grupoDe: number[];
}

/** Cómo se llama el período al que cae cada mes, cuántos días tiene y si está
 *  completo.
 *
 *  Lo de "completo" no es un detalle: el último trimestre del archivo casi
 *  siempre tiene un mes, y mostrado como total del período parece un derrumbe
 *  que no ocurrió. */
export function agrupar(fechas: string[], dias: number[], periodo: IdPeriodo): Grupos {
  const esperados = PERIODOS.find((item) => item.id === periodo)!.meses;
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

  return {
    etiquetas,
    dias: diasPorGrupo,
    completo: mesesPorGrupo.map((meses) => meses >= esperados),
    grupoDe,
  };
}

/** Suma las claves pedidas de un miembro y las lleva a la grilla de períodos. */
export function volumenPorPeriodo(
  miembro: MiembroYPF | Record<string, number[]>,
  claves: ClaveSerie[],
  grupos: Grupos,
): number[] {
  const salida = new Array<number>(grupos.etiquetas.length).fill(0);
  for (const clave of claves) {
    const serie = (miembro as Record<string, number[] | undefined>)[clave];
    if (!serie) continue;
    for (let indice = 0; indice < serie.length; indice += 1) {
      const grupo = grupos.grupoDe[indice];
      if (grupo !== undefined) salida[grupo] += serie[indice];
    }
  }
  return salida;
}

export interface SerieMiembro {
  nombre: string;
  valores: number[];
  /** Volumen del último período con datos: manda el orden de apilado. */
  ultimo: number;
  total: number;
}

export interface SeriesArmadas {
  etiquetas: string[];
  /** Las series que se dibujan, ya recortadas al rango y al top elegido. */
  series: SerieMiembro[];
  /** El total por período, sin recortar: el denominador de la participación. */
  totales: number[];
  dias: number[];
  completo: boolean[];
  /** Cuántos miembros quedaron fuera del top y se juntaron en "Otros". */
  agrupados: number;
  /** Si ese "Otros" incluye además la cola que el pipeline ya venía agrupando. */
  incluyeResto: boolean;
  hayParciales: boolean;
}

interface OpcionesSeries {
  miembros: MiembroYPF[];
  claves: ClaveSerie[];
  grupos: Grupos;
  /** Cuántas series propias antes de juntar el resto en "Otros". 0 = todas. */
  top: number;
  desde: number;
  hasta: number;
}

/** Arma las series del gráfico: agrupa por período, recorta al rango de años y
 *  junta la cola larga en "Otros".
 *
 *  Juntar la cola no es una simplificación estética. Diecisiete áreas apiladas
 *  son diecisiete colores que nadie distingue; cinco más el resto dejan ver qué
 *  mueve el total, que es la pregunta. El detalle sigue estando a un clic. */
export function armarSeries({
  miembros,
  claves,
  grupos,
  top,
  desde,
  hasta,
}: OpcionesSeries): SeriesArmadas {
  const dentro: number[] = [];
  grupos.etiquetas.forEach((etiqueta, indice) => {
    const anio = Number(etiqueta.slice(0, 4));
    if (anio >= desde && anio <= hasta) dentro.push(indice);
  });

  const recortar = (valores: number[]) => dentro.map((indice) => valores[indice] ?? 0);

  const crudas: SerieMiembro[] = [];
  for (const miembro of miembros) {
    const valores = recortar(volumenPorPeriodo(miembro, claves, grupos));
    const total = valores.reduce((suma, valor) => suma + valor, 0);
    if (total <= 0) continue;
    crudas.push({
      nombre: miembro.nombre,
      valores,
      ultimo: valores[valores.length - 1] ?? 0,
      total,
    });
  }

  // Orden: el que más produjo en el último período, primero. Es el que explica
  // el total de hoy, no el que explicaba el de 2012.
  crudas.sort((a, b) => b.ultimo - a.ultimo || b.total - a.total);

  const totales = crudas.length
    ? crudas[0].valores.map((_, indice) =>
        crudas.reduce((suma, serie) => suma + (serie.valores[indice] ?? 0), 0),
      )
    : dentro.map(() => 0);

  // El pipeline ya trae su propia cola agrupada bajo el mismo nombre: los
  // activos que no entraron en las dieciséis series que publica. Si acá se
  // agrega otro "Otros" sin mirar, quedan dos series con el mismo nombre, el
  // apilado suma dos veces la misma banda y el total deja de cerrar. Los dos
  // restos son lo mismo conceptualmente, así que se funden en uno.
  const propias = crudas.filter((serie) => serie.nombre !== NOMBRE_OTROS);
  const restoPrevio = crudas.find((serie) => serie.nombre === NOMBRE_OTROS) ?? null;

  const largo = dentro.length;
  const sumarSeries = (lista: SerieMiembro[]) => {
    const valores = new Array<number>(largo).fill(0);
    for (const serie of lista) {
      for (let indice = 0; indice < largo; indice += 1) valores[indice] += serie.valores[indice] ?? 0;
    }
    return valores;
  };

  let series = crudas;
  let agrupados = 0;
  let incluyeResto = false;

  if (top > 0 && (propias.length > top + 1 || (propias.length > top && restoPrevio))) {
    const principales = propias.slice(0, top);
    const resto = propias.slice(top);
    agrupados = resto.length;
    incluyeResto = Boolean(restoPrevio);
    const valores = sumarSeries(restoPrevio ? [...resto, restoPrevio] : resto);
    series = [
      ...principales,
      {
        nombre: NOMBRE_OTROS,
        valores,
        ultimo: valores[valores.length - 1] ?? 0,
        total: valores.reduce((suma, valor) => suma + valor, 0),
      },
    ];
  }

  return {
    etiquetas: dentro.map((indice) => grupos.etiquetas[indice]),
    series,
    totales,
    dias: dentro.map((indice) => grupos.dias[indice]),
    completo: dentro.map((indice) => grupos.completo[indice]),
    agrupados,
    incluyeResto,
    hayParciales: dentro.some((indice) => !grupos.completo[indice]),
  };
}

/** Volumen a lo que se muestra: caudal del período o volumen total. */
export function medir(volumen: number, dias: number, metrica: IdMetrica): number {
  return metrica === 'caudal' ? volumen / (dias || 1) : volumen;
}

export function unidadDe(fluido: IdFluido, metrica: IdMetrica): string {
  const base = fluido === 'oil' ? 'bbl' : 'boe';
  return metrica === 'caudal' ? `${base}/d` : base;
}

/** Variación contra el mismo período del año anterior.
 *
 *  El desfasaje depende de la escala: doce meses, cuatro trimestres o un año.
 *  Comparar contra el período anterior y no contra el mismo del año pasado
 *  mezclaría estacionalidad con tendencia. */
export function interanual(valores: number[], periodo: IdPeriodo): (number | null)[] {
  const paso = periodo === 'mes' ? 12 : periodo === 'trimestre' ? 4 : 1;
  return valores.map((valor, indice) => {
    const previo = valores[indice - paso];
    if (indice < paso || !previo) return null;
    return valor / previo - 1;
  });
}

export interface VentanaUDM {
  oil: number;
  gas: number;
  boe: number;
  shale: number;
  convencional: number;
  tight: number;
  shareShale: number | null;
  dias: number;
}

/** Caudal promedio de una ventana de meses del total de la compañía. */
export function ventana(datos: ProduccionYPF, desde: number, hasta: number): VentanaUDM | null {
  const dias = datos.dias.slice(desde, hasta).reduce((suma, valor) => suma + valor, 0);
  if (!dias) return null;

  const sumar = (claves: ClaveSerie[]) =>
    claves.reduce((suma, clave) => {
      const serie = datos.total[clave];
      if (!serie) return suma;
      return suma + serie.slice(desde, hasta).reduce((parcial, valor) => parcial + valor, 0);
    }, 0);

  const oil = sumar(clavesDe('oil', 'todo')) / dias;
  const gas = sumar(clavesDe('gas', 'todo')) / dias;
  const shale = sumar(clavesDe('boe', 'shale')) / dias;
  const convencional = sumar(clavesDe('boe', 'convencional')) / dias;
  const tight = sumar(clavesDe('boe', 'tight')) / dias;
  const boe = oil + gas;

  return { oil, gas, boe, shale, convencional, tight, shareShale: boe ? shale / boe : null, dias };
}

export interface ComparacionUDM {
  actual: VentanaUDM;
  previa: VentanaUDM | null;
  /** Variaciones relativas contra los doce meses previos. */
  varOil: number | null;
  varGas: number | null;
  varBoe: number | null;
  /** Cambio de la participación shale, en puntos porcentuales. */
  deltaShale: number | null;
  /** Cuánto sumó o restó cada tipo de roca, en caudal. */
  aporteShale: number | null;
  aporteConvencional: number | null;
  aporteTight: number | null;
  desdeActual: string;
  hastaActual: string;
  desdePrevia: string | null;
  hastaPrevia: string | null;
}

/** Los últimos doce meses contra los doce previos, que es la comparación que
 *  usa todo el módulo: neutraliza la estacionalidad y no depende de que el
 *  último mes publicado esté completo. */
export function compararUDM(datos: ProduccionYPF): ComparacionUDM | null {
  const n = datos.fechas.length;
  const actual = ventana(datos, Math.max(0, n - 12), n);
  if (!actual) return null;
  const previa = n >= 24 ? ventana(datos, n - 24, n - 12) : null;

  const variacion = (ahora: number, antes: number | undefined) =>
    antes && antes > 0 ? ahora / antes - 1 : null;

  return {
    actual,
    previa,
    varOil: variacion(actual.oil, previa?.oil),
    varGas: variacion(actual.gas, previa?.gas),
    varBoe: variacion(actual.boe, previa?.boe),
    deltaShale:
      previa && actual.shareShale !== null && previa.shareShale !== null
        ? actual.shareShale - previa.shareShale
        : null,
    aporteShale: previa ? actual.shale - previa.shale : null,
    aporteConvencional: previa ? actual.convencional - previa.convencional : null,
    aporteTight: previa ? actual.tight - previa.tight : null,
    desdeActual: datos.fechas[Math.max(0, n - 12)],
    hastaActual: datos.fechas[n - 1],
    desdePrevia: n >= 24 ? datos.fechas[n - 24] : null,
    hastaPrevia: n >= 24 ? datos.fechas[n - 13] : null,
  };
}

/** La serie mensual de caudal para los sparkline de los KPI. */
export function chispa(
  datos: ProduccionYPF,
  claves: ClaveSerie[],
  meses = 36,
): { valores: number[]; desde: string; hasta: string } {
  const n = datos.fechas.length;
  const inicio = Math.max(0, n - meses);
  const valores: number[] = [];
  for (let indice = inicio; indice < n; indice += 1) {
    const dias = datos.dias[indice] || 30;
    const volumen = claves.reduce((suma, clave) => suma + (datos.total[clave]?.[indice] ?? 0), 0);
    valores.push(volumen / dias);
  }
  return { valores, desde: datos.fechas[inicio], hasta: datos.fechas[n - 1] };
}

export interface Senal {
  id: string;
  tipo: 'alza' | 'baja' | 'neutro' | 'atencion';
  titulo: string;
  cuerpo: string;
  /** Contra qué se compara. Una señal sin período es una opinión. */
  periodo: string;
}

function porcentaje(valor: number, decimales = 1): string {
  return `${valor >= 0 ? '+' : '−'}${Math.abs(valor * 100)
    .toFixed(decimales)
    .replace('.', ',')}%`;
}

function miles(valor: number): string {
  const absoluto = Math.abs(valor);
  const texto =
    absoluto >= 1000
      ? `${(absoluto / 1000).toFixed(1).replace('.', ',')}k`
      : absoluto.toFixed(0);
  return `${valor < 0 ? '−' : ''}${texto}`;
}

function puntos(valor: number): string {
  return `${valor >= 0 ? '+' : '−'}${Math.abs(valor * 100)
    .toFixed(1)
    .replace('.', ',')} p.p.`;
}

/** Las señales de la sección Intelligence.
 *
 *  Cada una sale de una cuenta sobre los arrays publicados y dice contra qué
 *  período compara. Las que no se pueden calcular con los datos disponibles no
 *  se muestran: preferimos cuatro señales verdaderas a seis con una inventada.
 */
export function senales(datos: ProduccionYPF, dimension: IdDimension): Senal[] {
  const salida: Senal[] = [];
  const comparacion = compararUDM(datos);
  if (!comparacion) return salida;

  const ventanaTexto = comparacion.desdePrevia
    ? `${comparacion.desdeActual} – ${comparacion.hastaActual} contra ${comparacion.desdePrevia} – ${comparacion.hastaPrevia}`
    : `${comparacion.desdeActual} – ${comparacion.hastaActual}`;

  if (comparacion.varBoe !== null) {
    salida.push({
      id: 'total',
      tipo: comparacion.varBoe >= 0 ? 'alza' : 'baja',
      titulo: 'Producción total',
      cuerpo:
        `El caudal operado promedió ${miles(comparacion.actual.boe)} boe/d, ` +
        `${porcentaje(comparacion.varBoe)} contra los doce meses previos ` +
        `(petróleo ${comparacion.varOil !== null ? porcentaje(comparacion.varOil) : '—'}, ` +
        `gas ${comparacion.varGas !== null ? porcentaje(comparacion.varGas) : '—'}).`,
      periodo: ventanaTexto,
    });
  }

  if (comparacion.deltaShale !== null && comparacion.actual.shareShale !== null) {
    salida.push({
      id: 'shale',
      tipo: comparacion.deltaShale >= 0 ? 'alza' : 'baja',
      titulo: 'Peso del shale',
      cuerpo:
        `El shale es el ${(comparacion.actual.shareShale * 100).toFixed(0)}% de la producción, ` +
        `${puntos(comparacion.deltaShale)} contra el año previo. ` +
        `Aportó ${miles(comparacion.aporteShale ?? 0)} boe/d mientras el convencional ` +
        `${(comparacion.aporteConvencional ?? 0) >= 0 ? 'sumó' : 'restó'} ` +
        `${miles(Math.abs(comparacion.aporteConvencional ?? 0))} boe/d.`,
      periodo: ventanaTexto,
    });
  }

  // Solo las que producen: el ranking trae además las áreas que produjeron en la
  // ventana previa y ya no, para que los agregados cierren, y contarlas acá
  // diría "sobre 73 concesiones en producción" cuando son 52.
  const concesiones = (datos.rankings.concesion ?? []).filter((fila) => fila.actual_bd > 0);
  if (concesiones.length >= 5) {
    const cinco = concesiones.slice(0, 5).reduce((suma, fila) => suma + (fila.participacion ?? 0), 0);
    salida.push({
      id: 'concentracion',
      tipo: 'neutro',
      titulo: 'Concentración',
      cuerpo:
        `Las cinco concesiones más grandes explican el ${(cinco * 100).toFixed(0)}% de lo que ` +
        `produce la compañía, sobre ${concesiones.length} concesiones en producción.`,
      periodo: `${comparacion.desdeActual} – ${comparacion.hastaActual}`,
    });
  }

  const provincias = datos.rankings.provincia ?? [];
  if (provincias.length) {
    const primera = provincias[0];
    salida.push({
      id: 'territorio',
      tipo: 'neutro',
      titulo: 'Territorio',
      cuerpo:
        `${primera.nombre} concentra el ${((primera.participacion ?? 0) * 100).toFixed(0)}% de la ` +
        `producción operada, repartida en ${provincias.length} provincias.`,
      periodo: `${comparacion.desdeActual} – ${comparacion.hastaActual}`,
    });
  }

  // Las áreas que cambiaron de operador. Es la señal que más se parece a una
  // noticia, y la única de este bloque que sale de un cruce contra otra fuente
  // —el archivo del país— en vez de una cuenta sobre las series propias.
  const movidas = (datos.traspasos ?? []).filter((fila) => fila.dimension === 'concesion');
  if (movidas.length) {
    const total = movidas.reduce((suma, fila) => suma + fila.bd_previo, 0);
    const mes = movidas[0].ultimo_mes;
    const confirmadas = movidas.filter((fila) => fila.sigue_en_el_pais);
    salida.push({
      id: 'traspaso',
      tipo: 'atencion',
      titulo: movidas.length === 1 ? 'Un área dejó de declarar' : 'Áreas que dejaron de declarar',
      cuerpo:
        `${movidas.length === 1 ? '1 concesión' : `${movidas.length} concesiones`} con ` +
        `${miles(total)} boe/d no declaran producción operada por YPF después de ${mes}` +
        (confirmadas.length
          ? `, y ${confirmadas.length === 1 ? 'la que se puede verificar sigue' : 'las que se pueden verificar siguen'} ` +
            `produciendo en el archivo del país: es un cambio de operador y no una caída.`
          : '. La fuente no dice por qué; el archivo del país no publica esas áreas por separado.'),
      periodo: `hasta ${mes}`,
    });
  }

  const delDimension = datos.rankings[dimension] ?? [];
  if (delDimension.length) {
    const ordenadas = [...delDimension].sort((a, b) => b.delta_bd - a.delta_bd);
    const sube = ordenadas[0];
    const baja = ordenadas[ordenadas.length - 1];
    const etiqueta = DIMENSIONES.find((item) => item.id === dimension)!.etiqueta.toLowerCase();
    if (sube && baja && sube.nombre !== baja.nombre) {
      salida.push({
        id: 'movimiento',
        tipo: baja.delta_bd < 0 ? 'atencion' : 'alza',
        titulo: 'Mayor movimiento',
        cuerpo:
          `Por ${etiqueta}, ${sube.nombre} es la que más sumó (${miles(sube.delta_bd)} boe/d) y ` +
          `${baja.nombre} la que más restó (${miles(baja.delta_bd)} boe/d).`,
        periodo: ventanaTexto,
      });
    }
  }

  return salida;
}

/** La lectura principal: dos frases armadas con los mismos números.
 *
 *  No es un resumen editorial escrito a mano: si el próximo refresco del
 *  pipeline da otra cosa, esta frase dice otra cosa. */
export function lectura(datos: ProduccionYPF): { titulo: string; cuerpo: string } | null {
  const comparacion = compararUDM(datos);
  if (!comparacion) return null;

  const { actual, varBoe, deltaShale, aporteShale, aporteConvencional } = comparacion;
  const direccion =
    varBoe === null ? 'se mantiene' : varBoe > 0.01 ? 'crece' : varBoe < -0.01 ? 'cae' : 'se mantiene';

  const concesiones = datos.rankings.concesion ?? [];
  const motor = [...concesiones].sort((a, b) => b.delta_bd - a.delta_bd)[0];

  const titulo =
    `La producción operada ${direccion}` +
    (varBoe !== null ? ` ${porcentaje(varBoe)} interanual` : '') +
    `, con ${miles(actual.boe)} boe/d en los últimos doce meses.`;

  const partes: string[] = [];
  if (actual.shareShale !== null) {
    partes.push(
      `El shale explica el ${(actual.shareShale * 100).toFixed(0)}% del total` +
        (deltaShale !== null ? ` (${puntos(deltaShale)} contra el año previo)` : ''),
    );
  }
  if (aporteShale !== null && aporteConvencional !== null) {
    partes.push(
      `aportó ${miles(aporteShale)} boe/d mientras el convencional ` +
        `${aporteConvencional >= 0 ? 'sumó' : 'restó'} ${miles(Math.abs(aporteConvencional))} boe/d`,
    );
  }
  if (motor && motor.delta_bd > 0) {
    partes.push(`${motor.nombre} es el activo que más suma (${miles(motor.delta_bd)} boe/d)`);
  }

  return { titulo, cuerpo: partes.length ? `${partes.join('; ')}.` : '' };
}

export interface FilaRankingCalculada {
  nombre: string;
  valor: number;
  delta: number | null;
}

/** El ranking del último año calculado desde las series mensuales.
 *
 *  Hace falta cuando se cruzan producto y tipo de roca —petróleo shale, por
 *  ejemplo—, porque esa combinación no viene precalculada en el ranking del
 *  pipeline. Solo alcanza a los activos con serie propia, y la pantalla lo
 *  aclara: un ranking parcial presentado como completo es peor que ninguno. */
export function rankingDeSeries(
  miembros: MiembroYPF[],
  claves: ClaveSerie[],
  dias: number[],
): FilaRankingCalculada[] {
  const n = dias.length;
  const desdeActual = Math.max(0, n - 12);
  const diasActual = dias.slice(desdeActual, n).reduce((suma, valor) => suma + valor, 0) || 1;
  const hayPrevia = n >= 24;
  const diasPrevia = hayPrevia
    ? dias.slice(n - 24, n - 12).reduce((suma, valor) => suma + valor, 0) || 1
    : 1;

  const sumar = (miembro: MiembroYPF, desde: number, hasta: number) =>
    claves.reduce((suma, clave) => {
      const serie = miembro[clave];
      if (!serie) return suma;
      return suma + serie.slice(desde, hasta).reduce((parcial, valor) => parcial + valor, 0);
    }, 0);

  return miembros
    .map((miembro) => {
      const actual = sumar(miembro, desdeActual, n) / diasActual;
      const previa = hayPrevia ? sumar(miembro, n - 24, n - 12) / diasPrevia : null;
      return {
        nombre: miembro.nombre,
        valor: actual,
        delta: previa === null ? null : actual - previa,
      };
    })
    .filter((fila) => fila.valor > 0)
    .sort((a, b) => b.valor - a.valor);
}

/** La serie mensual de caudal de un miembro, para el sparkline de su ficha. */
export function serieMensualDe(
  miembro: MiembroYPF,
  claves: ClaveSerie[],
  dias: number[],
  meses = 36,
): number[] {
  const n = dias.length;
  const inicio = Math.max(0, n - meses);
  const salida: number[] = [];
  for (let indice = inicio; indice < n; indice += 1) {
    const volumen = claves.reduce((suma, clave) => suma + (miembro[clave]?.[indice] ?? 0), 0);
    salida.push(volumen / (dias[indice] || 30));
  }
  return salida;
}

/** Con qué columna del ranking se puede medir la combinación elegida.
 *
 *  El ranking del pipeline trae el último año abierto por fluido y por tipo de
 *  roca, pero no el cruce de los dos. Cuando se piden las dos cosas a la vez
 *  —petróleo shale, por ejemplo— hay que calcularlo de las series, y esas solo
 *  existen para los principales activos. La función lo dice en `alcance` para
 *  que la pantalla pueda avisarlo en vez de mostrar un ranking incompleto como
 *  si fuera todo. */
export function medidaDelRanking(
  fluido: IdFluido,
  recurso: IdRecurso,
): { clave: keyof FilaRankingYPF | null; alcance: 'completo' | 'principales' } {
  if (fluido === 'boe' && recurso === 'todo') return { clave: 'actual_bd', alcance: 'completo' };
  if (fluido !== 'boe' && recurso === 'todo') {
    return { clave: fluido === 'oil' ? 'oil_bd' : 'gas_bd', alcance: 'completo' };
  }
  if (fluido === 'boe' && recurso !== 'todo') {
    const claves = {
      shale: 'shale_bd',
      convencional: 'convencional_bd',
      tight: 'tight_bd',
    } as const;
    return { clave: claves[recurso], alcance: 'completo' };
  }
  return { clave: null, alcance: 'principales' };
}

// ---------------------------------------------------------------------------
// Economía de pozo
//
// El módulo de producción contestaba cuánto sale de cada activo y no si eso
// conviene. El pipeline ya calcula lo segundo —NPV, TIR, payback y Brent de
// breakeven pozo por pozo, sobre las curvas de Arps ajustadas— pero por
// yacimiento y solo donde hay al menos diez pozos ajustados, que es el núcleo
// no convencional. Son 25 yacimientos contra los 111 que producen: pocos en
// número y la mayor parte del volumen.
//
// Nada de esto se recalcula acá. Lo único que hace el frontend es cruzar los
// nombres y mostrar lo que el pipeline publicó, con sus supuestos al lado: un
// breakeven sin el capex y el diferencial que lo produjeron es un número que no
// se puede discutir, y un número que no se puede discutir no sirve.
// ---------------------------------------------------------------------------

/** Los nombres del padrón de pozos y los de las series de producción no siempre
 *  coinciden en tildes ni en mayúsculas. Se comparan normalizados, que es el
 *  mismo criterio con el que la página cruza el grafo de entidades. */
export function normalizarNombre(texto: string): string {
  return texto
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toUpperCase();
}

// ---------------------------------------------------------------------------
// Cohortes: de qué época es la producción de hoy
//
// La tesis del caso es que el shale compensa el declino del convencional. Eso
// hoy se afirma en texto y se deduce de un porcentaje; acá se ve. Cada activo
// entra en la cohorte del año en que empezó a producir, y el apilado muestra
// qué parte del caudal de hoy viene de algo que arrancó hace quince años y qué
// parte de algo que arrancó anteayer.
//
// La serie empieza en 2009, así que de lo que ya producía en el primer mes no
// sabemos cuándo arrancó: están censurados por la izquierda y se los nombra por
// lo que se sabe —"ya producía en 2009"— y no por una fecha inventada.
// ---------------------------------------------------------------------------

/** La serie de una clave, o undefined si el miembro no la tiene. Existe para no
 *  castear el miembro a un Record en cada recorrido: la clave ya es un keyof. */
function serieDe(miembro: MiembroYPF, clave: ClaveSerie): number[] | undefined {
  return miembro[clave];
}

/** El primer mes con producción de un miembro, en índice de la grilla. Devuelve
 *  -1 si no produjo nunca con las claves pedidas. */
export function debutDe(miembro: MiembroYPF, claves: ClaveSerie[]): number {
  let primero = -1;
  for (const clave of claves) {
    const serie = serieDe(miembro, clave);
    if (!serie) continue;
    for (let indice = 0; indice < serie.length; indice += 1) {
      if (serie[indice] > 0) {
        if (primero < 0 || indice < primero) primero = indice;
        break;
      }
    }
  }
  return primero;
}

/** El color de cada cohorte: de lo viejo apagado a lo nuevo encendido. Acá el
 *  color es la lectura del gráfico y no una forma de distinguir series, así que
 *  no usa la rampa de activos. */
export const COLOR_COHORTE: Record<string, string> = {
  'Ya producía en 2009': '#41546f',
  '2010-2014': '#5f7099',
  '2015-2018': '#75aadb',
  '2019-2021': '#0054eb',
  '2022 en adelante': '#4d90ff',
};

// ---------------------------------------------------------------------------
// Curvas comparadas: cada activo desde su propio mes uno
// ---------------------------------------------------------------------------

export interface CurvaActivo {
  nombre: string;
  /** Caudal mensual desde el arranque efectivo del activo. */
  valores: number[];
  /** Con qué mes del calendario empieza la curva, para poder decirlo. */
  desde: string | null;
  /** El primer mes con producción, que puede ser bastante anterior. */
  primerMes: string | null;
  pico: number;
}

/** Desde dónde vale la pena mirar una curva: el primer mes en que el activo
 *  llegó a la décima parte de su propio pico. */
const UMBRAL_ARRANQUE = 0.1;

/** La curva de un activo alineada a su arranque.
 *
 *  Comparar dos activos en el eje del calendario contesta cuál produce más hoy,
 *  que ya contesta el ranking. Alineados al arranque contestan otra cosa: si el
 *  que empezó después empieza más arriba y cae más rápido, que es la pregunta de
 *  fondo de un no convencional.
 *
 *  El arranque no es el primer barril. La Amarga Chica registra 39 boe/d en
 *  2011 —un pozo exploratorio— y recién despega en 2019: alineada por el primer
 *  barril, la curva son siete años de nada y después el tramo que importa queda
 *  fuera del gráfico. Por eso la curva empieza en el primer mes que alcanza el
 *  10% de su propio pico, y el mes del primer barril se muestra igual, al lado,
 *  porque el recorte es una decisión y no un dato de la fuente. */
export function curvaDesdeDebut(
  miembro: MiembroYPF,
  claves: ClaveSerie[],
  dias: number[],
  fechas: string[],
): CurvaActivo {
  const debut = debutDe(miembro, claves);
  const caudales: number[] = [];
  if (debut >= 0) {
    for (let indice = debut; indice < dias.length; indice += 1) {
      let volumen = 0;
      for (const clave of claves) {
        volumen += serieDe(miembro, clave)?.[indice] ?? 0;
      }
      caudales.push(volumen / (dias[indice] || 30));
    }
  }

  const pico = caudales.length ? Math.max(...caudales) : 0;
  const corte = caudales.findIndex((valor) => valor >= pico * UMBRAL_ARRANQUE);
  const desdeIndice = corte > 0 ? debut + corte : debut;

  return {
    nombre: miembro.nombre,
    valores: corte > 0 ? caudales.slice(corte) : caudales,
    desde: desdeIndice >= 0 ? (fechas[desdeIndice] ?? null) : null,
    primerMes: debut >= 0 ? (fechas[debut] ?? null) : null,
    pico,
  };
}

// ---------------------------------------------------------------------------
// Quiebres: qué se movió de golpe
// ---------------------------------------------------------------------------

/** El activo con el mayor salto o caída reciente.
 *
 *  El delta de doce meses contra doce meses que usan los KPI promedia y tapa lo
 *  que pasó de un mes para el otro: un activo que se cayó a la mitad en marzo
 *  puede seguir mostrando un interanual positivo. Esta cuenta compara el
 *  promedio de los últimos tres meses contra los tres anteriores, que es lo más
 *  corto que se puede mirar sin que el ruido mensual mande.
 *
 *  Pide un piso de tamaño porque un pozo chico que duplica no es una noticia, y
 *  un piso de variación porque si lo más grande que pasó fue un 6%, entonces no
 *  pasó nada y la señal no se muestra. */
export function quiebreReciente(
  miembros: MiembroYPF[],
  fechas: string[],
  dias: number[],
  claves: ClaveSerie[],
  etiquetaDimension: string,
  /** Las áreas que cambiaron de operador. Su serie cae a cero y sin excluirlas
   *  esta función anunciaría una caída del 100% que no ocurrió: el área sigue
   *  produciendo, pero ya no la opera YPF. Eso lo cuenta otra señal. */
  excluidos: Set<string> = new Set(),
): Senal | null {
  const meses = fechas.length;
  if (meses < 6 || !miembros.length) return null;

  const caudal = (miembro: MiembroYPF, desde: number, hasta: number) => {
    let volumen = 0;
    let diasDelTramo = 0;
    for (let indice = desde; indice < hasta; indice += 1) {
      for (const clave of claves) {
        volumen += serieDe(miembro, clave)?.[indice] ?? 0;
      }
      diasDelTramo += dias[indice] ?? 30;
    }
    return diasDelTramo > 0 ? volumen / diasDelTramo : 0;
  };

  let mayor: { nombre: string; antes: number; ahora: number; cambio: number } | null = null;
  for (const miembro of miembros) {
    if (excluidos.has(miembro.nombre)) continue;
    const antes = caudal(miembro, meses - 6, meses - 3);
    const ahora = caudal(miembro, meses - 3, meses);
    if (antes < 1500) continue;
    const cambio = ahora / antes - 1;
    if (Math.abs(cambio) < 0.2) continue;
    if (!mayor || Math.abs(cambio) > Math.abs(mayor.cambio)) {
      mayor = { nombre: miembro.nombre, antes, ahora, cambio };
    }
  }
  if (!mayor) return null;

  return {
    id: 'quiebre',
    tipo: mayor.cambio >= 0 ? 'alza' : 'atencion',
    titulo: mayor.cambio >= 0 ? 'Salto reciente' : 'Caída reciente',
    cuerpo:
      'Por ' +
      etiquetaDimension +
      ', ' +
      mayor.nombre +
      ' pasó de ' +
      miles(mayor.antes) +
      ' a ' +
      miles(mayor.ahora) +
      ' boe/d entre los dos últimos trimestres móviles (' +
      porcentaje(mayor.cambio) +
      '). Es el movimiento más brusco del período y no se ve en la variación ' +
      'interanual, que lo promedia con los meses previos.',
    periodo:
      fechas[meses - 3] +
      ' – ' +
      fechas[meses - 1] +
      ' contra ' +
      fechas[meses - 6] +
      ' – ' +
      fechas[meses - 4],
  };
}
