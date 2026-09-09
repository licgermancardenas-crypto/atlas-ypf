// GENERADO por pipeline/transform/scenario_engine.py — no editar a mano.
// Para regenerarlo: python pipeline/transform/scenario_engine.py
// CI corre `--check` y falla si este archivo quedó desincronizado del modelo.
// Paridad con la versión Python: `verificarCasos()` devuelve los escenarios en
// los que las dos implementaciones no coinciden — vacío es lo esperado.
//
// Gemelo TypeScript del simulador de escenarios. Es una función pura y corre
// entera en el browser: el slider recalcula sin ir al backend.

export type Driver = 'brent_usd' | 'produccion_kboed' | 'lifting_cost_usd_boe' | 'crudo_procesado_kbbld';

export interface Escenario {
  brent_usd?: number;
  produccion_kboed?: number;
  lifting_cost_usd_boe?: number;
  crudo_procesado_kbbld?: number;
  /** Atraso cambiario del trimestre. Ver COEFICIENTES.fx: no es significativo. */
  fx_var_real?: number;
}

export interface Proyeccion {
  ebitda_proyectado_musd: number;
  ingresos_proyectados_musd: number;
  margen: number;
  delta_vs_real_musd: number;
  delta_vs_real_pct: number;
  banda_95_musd: [number, number];
}

export const DRIVERS: Driver[] = ['brent_usd', 'produccion_kboed', 'lifting_cost_usd_boe', 'crudo_procesado_kbbld'];

export const COEFICIENTES = {
  "generado_desde": "data/processed/ebitda_sensitivity.json",
  "modelo_ebitda": "adj_ebitda ~ brent + produccion + lifting_cost + crudo_procesado",
  "modelo_ingresos": "revenues ~ brent + produccion + crudo_procesado",
  "observaciones": 15,
  "periodo": [
    "2022Q4",
    "2026Q2"
  ],
  "r2_ebitda": 0.9116,
  "r2_ingresos": 0.739,
  "advertencia": "Coeficientes estimados sobre pocos trimestres: la banda del 95% es parte del resultado, no un adorno.",
  "ebitda": {
    "const": -7235.2023,
    "brent_usd": 24.6631,
    "produccion_kboed": 7.671,
    "lifting_cost_usd_boe": -57.1854,
    "crudo_procesado_kbbld": 10.6381,
    "error_estandar": 164.9
  },
  "ingresos": {
    "const": -9023.596,
    "brent_usd": 30.7172,
    "produccion_kboed": 11.9322,
    "crudo_procesado_kbbld": 16.3847
  },
  "fx": {
    "coeficiente": -295.8181,
    "p_valor": 0.4908,
    "significativo": false,
    "nota": "Estimado en una especificacion alternativa con 11 trimestres. No se distingue de cero: mostrar el slider con la advertencia."
  },
  "caso_base": {
    "trimestre": "2026Q2",
    "adj_ebitda_musd": 2804.0,
    "revenues_musd": 6574.0,
    "brent_usd": 96.94,
    "produccion_kboed": 544.4,
    "lifting_cost_usd_boe": 8.4,
    "crudo_procesado_kbbld": 350.8
  }
} as const;

const redondear = (valor: number, decimales: number): number => {
  const factor = 10 ** decimales;
  return Math.round(valor * factor) / factor;
};

/**
 * EBITDA e ingresos proyectados para un escenario.
 * Lo que no venga en `escenario` se toma del caso base (último trimestre real).
 */
export function proyectar(
  escenario: Escenario,
  coeficientes: typeof COEFICIENTES = COEFICIENTES,
): Proyeccion {
  const base = coeficientes.caso_base;
  const coefEbitda = coeficientes.ebitda as Record<string, number>;
  const coefIngresos = coeficientes.ingresos as Record<string, number>;

  const valores: Record<string, number> = {};
  for (const driver of DRIVERS) {
    const propuesto = escenario[driver];
    valores[driver] =
      propuesto === undefined ? (base as unknown as Record<string, number>)[driver] : propuesto;
  }
  const fxVarReal = escenario.fx_var_real ?? 0;

  let ebitda = coefEbitda.const;
  for (const driver of DRIVERS) ebitda += coefEbitda[driver] * valores[driver];
  ebitda += coeficientes.fx.coeficiente * fxVarReal;

  let ingresos = coefIngresos.const;
  for (const [variable, coeficiente] of Object.entries(coefIngresos)) {
    if (variable !== 'const') ingresos += coeficiente * valores[variable];
  }

  const margen = ingresos > 0 ? ebitda / ingresos : Number.NaN;
  const banda = coefEbitda.error_estandar * 1.96;

  return {
    ebitda_proyectado_musd: redondear(ebitda, 1),
    ingresos_proyectados_musd: redondear(ingresos, 1),
    margen: redondear(margen, 4),
    delta_vs_real_musd: redondear(ebitda - base.adj_ebitda_musd, 1),
    delta_vs_real_pct: redondear(ebitda / base.adj_ebitda_musd - 1, 4),
    banda_95_musd: [redondear(ebitda - banda, 1), redondear(ebitda + banda, 1)],
  };
}

/** Escenarios calculados en Python. Si el TypeScript no los reproduce, hay un bug. */
export const CASOS_DE_PRUEBA = [
  {
    "nombre": "base",
    "escenario": {},
    "esperado": {
      "ebitda_proyectado_musd": 2583.2,
      "ingresos_proyectados_musd": 6197.8,
      "margen": 0.4168,
      "delta_vs_real_musd": -220.8,
      "delta_vs_real_pct": -0.0787,
      "banda_95_musd": [
        2260.0,
        2906.4
      ]
    }
  },
  {
    "nombre": "brent_60",
    "escenario": {
      "brent_usd": 60.0
    },
    "esperado": {
      "ebitda_proyectado_musd": 1672.2,
      "ingresos_proyectados_musd": 5063.1,
      "margen": 0.3303,
      "delta_vs_real_musd": -1131.8,
      "delta_vs_real_pct": -0.4037,
      "banda_95_musd": [
        1349.0,
        1995.4
      ]
    }
  },
  {
    "nombre": "brent_120",
    "escenario": {
      "brent_usd": 120.0
    },
    "esperado": {
      "ebitda_proyectado_musd": 3152.0,
      "ingresos_proyectados_musd": 6906.1,
      "margen": 0.4564,
      "delta_vs_real_musd": 348.0,
      "delta_vs_real_pct": 0.1241,
      "banda_95_musd": [
        2828.7,
        3475.2
      ]
    }
  },
  {
    "nombre": "costo_alto",
    "escenario": {
      "lifting_cost_usd_boe": 16.0
    },
    "esperado": {
      "ebitda_proyectado_musd": 2148.6,
      "ingresos_proyectados_musd": 6197.8,
      "margen": 0.3467,
      "delta_vs_real_musd": -655.4,
      "delta_vs_real_pct": -0.2337,
      "banda_95_musd": [
        1825.4,
        2471.8
      ]
    }
  },
  {
    "nombre": "produccion_600",
    "escenario": {
      "produccion_kboed": 600.0
    },
    "esperado": {
      "ebitda_proyectado_musd": 3009.7,
      "ingresos_proyectados_musd": 6861.2,
      "margen": 0.4387,
      "delta_vs_real_musd": 205.7,
      "delta_vs_real_pct": 0.0734,
      "banda_95_musd": [
        2686.5,
        3332.9
      ]
    }
  },
  {
    "nombre": "downstream_parado",
    "escenario": {
      "crudo_procesado_kbbld": 250.0
    },
    "esperado": {
      "ebitda_proyectado_musd": 1510.9,
      "ingresos_proyectados_musd": 4546.2,
      "margen": 0.3323,
      "delta_vs_real_musd": -1293.1,
      "delta_vs_real_pct": -0.4612,
      "banda_95_musd": [
        1187.7,
        1834.1
      ]
    }
  },
  {
    "nombre": "atraso_cambiario",
    "escenario": {
      "fx_var_real": -0.2
    },
    "esperado": {
      "ebitda_proyectado_musd": 2642.4,
      "ingresos_proyectados_musd": 6197.8,
      "margen": 0.4263,
      "delta_vs_real_musd": -161.6,
      "delta_vs_real_pct": -0.0576,
      "banda_95_musd": [
        2319.2,
        2965.6
      ]
    }
  }
] as const;

/** Devuelve los casos en los que las dos implementaciones no coinciden. */
export function verificarCasos(): string[] {
  const fallas: string[] = [];
  for (const caso of CASOS_DE_PRUEBA) {
    const obtenido = proyectar(caso.escenario as Escenario);
    for (const [clave, esperado] of Object.entries(caso.esperado)) {
      const valor = (obtenido as unknown as Record<string, unknown>)[clave];
      if (JSON.stringify(valor) !== JSON.stringify(esperado)) {
        fallas.push(`${caso.nombre}.${clave}: ${JSON.stringify(valor)} != ${JSON.stringify(esperado)}`);
      }
    }
  }
  return fallas;
}
