// Tipos del módulo del libro y la matemática de la valuación.
//
// La valuación vive acá y no en el pipeline por la misma razón que el simulador
// de escenarios: son cuentas sobre supuestos que el lector mueve, y mandarlas al
// servidor en cada movimiento del slider las volvería lentas sin volverlas más
// ciertas. El pipeline entrega los agregados —EBITDA de los últimos doce meses,
// saldos del balance, la serie del múltiplo— y acá se combinan.
//
// Los números tienen que dar lo mismo que la hoja Valuación del Excel. Si algo
// cambia de un lado, cambia del otro: es el mismo método.

export interface LineaEstado {
  clave: string;
  etiqueta: string;
  original: string;
  orden: number;
  total: boolean;
  vigente: boolean;
  trimestral: (number | null)[];
  anual: (number | null)[];
  /** Una letra por trimestre: R reportado, D derivado por diferencia. */
  derivacion: string;
  /** Una letra por trimestre: U dólar como se publicó, A peso convertido. */
  moneda: string;
}

export interface Estados {
  generado: string;
  trimestres: string[];
  anios: string[];
  estados: Record<string, { titulo: string; lineas: LineaEstado[] }>;
}

export interface Segmentos {
  trimestres: string[];
  anios: string[];
  segmentos: string[];
  conceptos: Record<string, { titulo: string; filas: { segmento: string; trimestral: (number | null)[]; anual: (number | null)[] }[] }>;
}

export interface Comparables {
  anios: string[];
  emisores: {
    ticker: string;
    nombre: string;
    adrs: number | null;
    acciones_por_adr: number;
    precio: number | null;
    fecha_precio: string | null;
    ultimo_ejercicio: string | null;
    ejercicios: Record<string, Record<string, number>>;
  }[];
  nota: string;
}

export interface Deuda {
  presentado: string;
  presentacion: string;
  total: number;
  escalera: { anio: number; monto: number }[];
  instrumentos: {
    clase: string;
    emitido: string;
    moneda: string;
    valor_nominal: number | null;
    tasa: string;
    vencimiento: number;
    no_corriente: number | null;
    corriente: number | null;
    total: number | null;
  }[];
  nota: string;
}

export interface Mercado {
  trimestre: string;
  precio_adr: number;
  fecha_precio: string;
  adrs: number;
  acciones_por_adr: number;
  riesgo_pais_pb: number | null;
  reservas: { anio: number; mmboe: number } | null;
  valor_boe_pozo: number | null;
  udm: {
    ingresos: number | null;
    ebit: number | null;
    ebitda: number | null;
    resultado_neto: number | null;
    antes_impuesto: number | null;
    impuesto: number | null;
    costos_financieros: number | null;
    flujo_operativo: number | null;
    capex: number | null;
  };
  balance: {
    deuda_no_corriente: number | null;
    deuda_corriente: number | null;
    caja: number | null;
    inversiones_corrientes: number | null;
    patrimonio: number | null;
    activos: number | null;
  };
  multiplos: { periodo: string; ev_ebitda: number; precio: number }[];
}

export interface Supuestos {
  precio: number;
  tasaLibre: number;
  riesgoPais: number;
  beta: number;
  prima: number;
  impuesto: number;
  crecimiento: number;
  perpetuo: number;
  valorBoe: number;
  multiplo: number;
}

export interface Valuacion {
  capitalizacion: number;
  deudaBruta: number;
  deudaNeta: number;
  ev: number;
  evEbitda: number | null;
  ke: number;
  kd: number;
  pesoDeuda: number;
  wacc: number;
  fcff: number | null;
  proyeccion: number[];
  valorPresente: number[];
  valorTerminal: number;
  pesoTerminal: number;
  metodos: { nombre: string; porAdr: number | null; detalle: string }[];
}

const ANIOS_PROYECCION = 5;

/** Mediana de la serie de múltiplos a la que cotizó el papel. */
export function medianaMultiplo(mercado: Mercado): number {
  const valores = mercado.multiplos.map((punto) => punto.ev_ebitda).sort((a, b) => a - b);
  if (!valores.length) return 5;
  const mitad = Math.floor(valores.length / 2);
  return valores.length % 2 ? valores[mitad] : (valores[mitad - 1] + valores[mitad]) / 2;
}

export function supuestosIniciales(mercado: Mercado): Supuestos {
  return {
    precio: mercado.precio_adr,
    tasaLibre: 0.0425,
    riesgoPais: (mercado.riesgo_pais_pb ?? 700) / 10000,
    beta: 1.1,
    prima: 0.055,
    impuesto: 0.35,
    crecimiento: 0.04,
    perpetuo: 0.02,
    valorBoe: mercado.valor_boe_pozo ?? 6,
    multiplo: Number(medianaMultiplo(mercado).toFixed(2)),
  };
}

/** Todo en millones de dólares; el valor por ADR sale de dividir por los ADR. */
export function valuar(mercado: Mercado, supuestos: Supuestos): Valuacion {
  const { udm, balance } = mercado;
  const adrsEnMillones = mercado.adrs / 1_000_000;

  const capitalizacion = supuestos.precio * adrsEnMillones;
  const deudaBruta = (balance.deuda_no_corriente ?? 0) + (balance.deuda_corriente ?? 0);
  const deudaNeta =
    deudaBruta - (balance.caja ?? 0) - (balance.inversiones_corrientes ?? 0);
  const ev = capitalizacion + deudaNeta;

  const ke = supuestos.tasaLibre + supuestos.riesgoPais + supuestos.beta * supuestos.prima;
  const kd = deudaBruta > 0 ? -(udm.costos_financieros ?? 0) / deudaBruta : 0;
  const pesoDeuda = deudaNeta + capitalizacion > 0 ? deudaNeta / (deudaNeta + capitalizacion) : 0;
  const wacc = ke * (1 - pesoDeuda) + kd * (1 - supuestos.impuesto) * pesoDeuda;

  // Flujo libre para la firma: operativo, más los intereses después de
  // impuestos que ya se pagaron, menos el capex. El capex viene negativo.
  const fcff =
    udm.flujo_operativo !== null && udm.capex !== null
      ? udm.flujo_operativo + -(udm.costos_financieros ?? 0) * (1 - supuestos.impuesto) + udm.capex
      : null;

  const proyeccion: number[] = [];
  const valorPresente: number[] = [];
  let corriente = fcff ?? 0;
  for (let anio = 1; anio <= ANIOS_PROYECCION; anio += 1) {
    corriente = corriente * (1 + supuestos.crecimiento);
    proyeccion.push(corriente);
    valorPresente.push(corriente / (1 + wacc) ** anio);
  }
  const brecha = wacc - supuestos.perpetuo;
  const valorTerminal =
    brecha > 0.001 ? (corriente * (1 + supuestos.perpetuo)) / brecha / (1 + wacc) ** ANIOS_PROYECCION : 0;
  const evDescontado = valorPresente.reduce((suma, valor) => suma + valor, 0) + valorTerminal;

  const porAdr = (equity: number | null) =>
    equity === null || !Number.isFinite(equity) ? null : equity / adrsEnMillones;

  const evMultiplo = udm.ebitda !== null ? supuestos.multiplo * udm.ebitda : null;
  const reservas = mercado.reservas;
  const valorReservas = reservas ? reservas.mmboe * supuestos.valorBoe : null;

  return {
    capitalizacion,
    deudaBruta,
    deudaNeta,
    ev,
    evEbitda: udm.ebitda ? ev / udm.ebitda : null,
    ke,
    kd,
    pesoDeuda,
    wacc,
    fcff,
    proyeccion,
    valorPresente,
    valorTerminal,
    pesoTerminal: evDescontado > 0 ? valorTerminal / evDescontado : 0,
    metodos: [
      {
        nombre: 'Flujo de fondos descontado',
        porAdr: fcff === null ? null : porAdr(evDescontado - deudaNeta),
        detalle: `WACC ${(wacc * 100).toFixed(1)}%, crecimiento perpetuo ${(supuestos.perpetuo * 100).toFixed(1)}%`,
      },
      {
        nombre: 'Múltiplo histórico',
        porAdr: evMultiplo === null ? null : porAdr(evMultiplo - deudaNeta),
        detalle: `${supuestos.multiplo.toFixed(2)}x EBITDA de los últimos doce meses`,
      },
      {
        nombre: 'Valor de reservas',
        porAdr: valorReservas === null ? null : porAdr(valorReservas - deudaNeta),
        detalle: reservas
          ? `${reservas.mmboe.toFixed(0)} MMboe probadas (${reservas.anio}) a ${supuestos.valorBoe.toFixed(2)} USD/boe`
          : 'sin dato de reservas',
      },
      {
        nombre: 'Valor libro',
        porAdr: porAdr(balance.patrimonio),
        detalle: 'Patrimonio neto del último balance',
      },
    ],
  };
}

/** El valor por ADR del descontado para una combinación de WACC y crecimiento:
 *  es la grilla de sensibilidad, y se recalcula sin volver a proyectar. */
export function sensibilidad(
  mercado: Mercado,
  supuestos: Supuestos,
  wacc: number,
  perpetuo: number,
): number | null {
  const base = valuar(mercado, supuestos);
  if (base.fcff === null) return null;
  const brecha = wacc - perpetuo;
  if (brecha <= 0.001) return null;

  let valor = 0;
  base.proyeccion.forEach((flujo, indice) => {
    valor += flujo / (1 + wacc) ** (indice + 1);
  });
  const ultimo = base.proyeccion[base.proyeccion.length - 1];
  valor += (ultimo * (1 + perpetuo)) / brecha / (1 + wacc) ** base.proyeccion.length;
  return (valor - base.deudaNeta) / (mercado.adrs / 1_000_000);
}
