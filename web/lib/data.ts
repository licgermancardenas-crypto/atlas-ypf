// Tipos y formato de los datos del pipeline. Este módulo lo importan tanto los
// Server Components como los del cliente, así que no puede tocar el filesystem:
// la lectura de archivos vive en lib/server-data.ts. Si algo de acá importara
// node:fs, el bundle del browser se rompería al intentar resolverlo.

// --------------------------------------------------------------------------- //
// Financieros trimestrales
// --------------------------------------------------------------------------- //
export interface TrimestreFinanciero {
  trimestre: string;
  revenues_musd: number | null;
  adj_ebitda_musd: number | null;
  net_result_musd: number | null;
  capex_musd: number | null;
  fcf_musd: number | null;
  net_debt_musd: number | null;
  net_leverage_x: number | null;
  produccion_kboed: number | null;
  shale_oil_kbbld: number | null;
  precio_crudo_usd_bbl: number | null;
  lifting_cost_usd_boe: number | null;
}

export interface Financieros {
  generado: string;
  fuente: string;
  trimestres: number;
  serie: TrimestreFinanciero[];
}

// --------------------------------------------------------------------------- //
// Sensibilidad del EBITDA
// --------------------------------------------------------------------------- //
export interface Coeficiente {
  variable: string;
  coeficiente: number;
  error_estandar: number;
  p_valor: number;
  ic_95: [number, number];
}

export interface Modelo {
  nombre: string;
  observaciones: number;
  periodo: [string, string];
  r2: number;
  r2_ajustado: number;
  error_estandar_residual_musd: number;
  coeficientes: Coeficiente[];
}

export interface Descomposicion {
  desde: string;
  hasta: string;
  ebitda_previo_musd: number;
  ebitda_actual_musd: number;
  delta_musd: number;
  efecto_precio_musd: number;
  efecto_volumen_musd: number;
  efecto_costo_musd: number;
  efecto_downstream_musd: number;
  residual_musd: number;
  /** El residual del puente es la resta de estos dos: el error del modelo en
   *  cada trimestre, no una partida que falte en el medio. */
  residual_previo_musd: number;
  residual_actual_musd: number;
  error_estandar_residual_musd: number;
  brent_previo: number;
  brent_actual: number;
}

export interface PuntoSerieEbitda {
  trimestre: string;
  adj_ebitda_musd: number | null;
  ebitda_ajustado_musd: number | null;
  revenues_musd: number | null;
  brent_usd: number | null;
  precio_crudo_usd_bbl: number | null;
  diferencial_usd_bbl: number | null;
  produccion_kboed: number | null;
  shale_oil_kbbld: number | null;
  lifting_cost_usd_boe: number | null;
  margen_ebitda: number | null;
}

export interface Sensibilidad {
  advertencia: string;
  modelo_operativo: Modelo;
  modelo_largo: Modelo;
  modelo_fx: Modelo;
  ultimo_trimestre: {
    trimestre: string;
    adj_ebitda_musd: number;
    brent_usd: number;
    produccion_kboed: number;
    lifting_cost_usd_boe: number;
    crudo_procesado_kbbld: number;
    revenues_musd: number;
  };
  descomposicion_ultimo_trimestre: Descomposicion;
  grilla_costos: { lifting_cost_usd_boe: number; ebitda_musd: number }[];
  serie: PuntoSerieEbitda[];
}

// --------------------------------------------------------------------------- //
// Reacción del mercado
// --------------------------------------------------------------------------- //
export interface EventoBalance {
  trimestre: string;
  fecha_reporte: string;
  fecha_evento: string;
  retorno_dia: number;
  retorno_anormal_dia: number;
  t_estadistico: number;
  car_0_3: number;
  adj_ebitda_musd: number | null;
  adj_ebitda_musd_yoy: number | null;
}

export interface PuntoSemanal {
  fecha: string;
  ypf: number | null;
  vist: number | null;
  pam: number | null;
  brent: number | null;
  embi: number | null;
  precio_ypf: number | null;
}

export interface Mercado {
  metodo: string;
  resumen: {
    balances: number;
    con_reaccion_negativa: number;
    retorno_anormal_mediano: number;
    car_0_3_mediano: number;
    peor: string;
    mejor: string;
  };
  riesgo_pais: {
    nombre: string;
    observaciones: number;
    r2: number;
    beta_brent: number;
    efecto_100pb_riesgo_pais: number;
    efecto_100pb_p: number;
  };
  eventos: EventoBalance[];
  serie_semanal: PuntoSemanal[];
}

// --------------------------------------------------------------------------- //
// Producción
// --------------------------------------------------------------------------- //
export interface PuntoProduccion {
  fecha: string;
  operador?: string;
  petroleo_bd: number;
  gas_boed: number;
  boed: number;
  pozos: number;
}

export interface Produccion {
  fuente: string;
  cobertura: {
    desde: string;
    hasta: string;
    pozos: number;
    pozos_vaca_muerta: number;
    operadores: number;
  };
  vaca_muerta_total: PuntoProduccion[];
  vaca_muerta_por_operador: PuntoProduccion[];
  ypf_vaca_muerta: PuntoProduccion[];
}

// --------------------------------------------------------------------------- //
// Producción nacional (SESCO + capítulo IV)
// --------------------------------------------------------------------------- //
export interface PuntoPais {
  fecha: string;
  oil_convencional: number | null;
  oil_shale: number | null;
  oil_tight: number | null;
  oil_total: number | null;
  gas_total: number | null;
  boed_total: number | null;
}

// --------------------------------------------------------------------------- //
// Economía de pozo y curvas de declive
// --------------------------------------------------------------------------- //
export interface AgregadoEconomico {
  operador?: string;
  vintage?: string;
  yacimiento?: string;
  pozos: number;
  npv_musd_mediano: number;
  irr_mediana: number;
  payback_meses_mediano: number;
  breakeven_brent_mediano: number;
  eur_bbl_mediana: number;
  /** Qué proporción de los pozos del grupo da NPV positivo. */
  pozos_con_npv_positivo?: number;
  /** Sobre cuántos pozos se calculó la mediana del breakeven. Cuando es menos
   *  que el total, a los que faltan no les cierra a ningún precio y la mediana
   *  es la de los que sí cierran: hay que decirlo donde se muestre. */
  pozos_con_breakeven?: number;
}

export interface Economia {
  supuestos: Record<string, number | string>;
  advertencia: string;
  resumen: {
    pozos: number;
    npv_musd_mediano: number;
    irr_mediana: number;
    payback_meses_mediano: number;
    breakeven_brent_mediano: number;
    pozos_con_npv_positivo: number;
    prima_riesgo_pais_musd_mediana: number;
  };
  por_operador: AgregadoEconomico[];
  por_vintage: AgregadoEconomico[];
  /** Solo los yacimientos con al menos diez pozos ajustados: el núcleo no
   *  convencional, que es donde hay curvas de las que colgar una economía. */
  por_yacimiento: AgregadoEconomico[];
  sensibilidad_brent_capex: {
    brent: number;
    capex_musd: number;
    npv_musd_mediano: number;
    pozos_con_npv_positivo: number;
  }[];
}

export interface CurvasDeclive {
  metodo: string;
  advertencia: string;
  pozos_ajustados: number;
  por_operador: {
    operador: string;
    pozos: number;
    pico_bd_mediano: number;
    declive_ef_anual_mediano: number;
    eur_bbl_mediano: number;
  }[];
  por_vintage: {
    vintage: number;
    pozos: number;
    pico_bd_mediano: number;
    declive_ef_anual_mediano: number;
    eur_bbl_mediano: number;
  }[];
  curva_tipo_por_vintage: {
    vintage: string;
    mes_prod: number;
    caudal_bd: number;
    pozos: number;
  }[];
}

// --------------------------------------------------------------------------- //
// Formato (una sola definición para toda la página)
// --------------------------------------------------------------------------- //
const NUMERO = new Intl.NumberFormat('es-AR');
const DECIMAL = new Intl.NumberFormat('es-AR', { maximumFractionDigits: 1 });

// Todo pasa por Intl en es-AR: coma decimal y punto de miles. Un "3.6%" al lado
// de un "US$ 2.804M" en la misma pantalla se lee como error de la página, no
// como una convención distinta.
const conDecimales = (decimales: number) =>
  new Intl.NumberFormat('es-AR', {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales,
  });

export const fmt = {
  entero: (valor: number | null | undefined) =>
    valor === null || valor === undefined ? '—' : NUMERO.format(Math.round(valor)),
  decimal: (valor: number | null | undefined) =>
    valor === null || valor === undefined ? '—' : DECIMAL.format(valor),
  numero: (valor: number | null | undefined, decimales = 2) =>
    valor === null || valor === undefined ? '—' : conDecimales(decimales).format(valor),
  musd: (valor: number | null | undefined) =>
    valor === null || valor === undefined ? '—' : `US$ ${NUMERO.format(Math.round(valor))}M`,
  porcentaje: (valor: number | null | undefined, decimales = 1) =>
    valor === null || valor === undefined
      ? '—'
      : `${conDecimales(decimales).format(valor * 100)}%`,
  porcentajeConSigno: (valor: number | null | undefined, decimales = 1) =>
    valor === null || valor === undefined
      ? '—'
      : `${valor >= 0 ? '+' : ''}${conDecimales(decimales).format(valor * 100)}%`,
  // Un p-valor que redondea a cero no es cero: mostrarlo como "0,000" invita a
  // leerlo como un dato exacto en vez de como "más chico que el umbral".
  pValor: (valor: number | null | undefined) =>
    valor === null || valor === undefined
      ? '—'
      : valor < 0.001
        ? '< 0,001'
        : conDecimales(3).format(valor),
  trimestre: (valor: string) => valor.replace(/(\d{4})Q(\d)/, '$2T$1'),
};
