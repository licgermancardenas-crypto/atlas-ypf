"""Simulador de escenarios: EBITDA proyectado a partir de los drivers del modelo.

Entrada: data/processed/ebitda_sensitivity.json (transform/ebitda_sensitivity.py)
Salidas: data/processed/scenario_coefficients.json (coeficientes + caso base)
         web/lib/scenarioEngine.ts                 (gemelo TypeScript, generado)

La función es pura: mismos inputs, mismos outputs, sin I/O ni estado. El
simulador del frontend tiene que recalcular en cada movimiento de slider sin ir
al backend, así que la versión que corre en el browser es TypeScript con los
coeficientes embebidos en el bundle.

Cómo se mantienen sincronizadas las dos versiones: no se mantienen a mano. Los
coeficientes salen del modelo, este script escribe el .ts completo —función y
constantes— y `--check` falla si el archivo del repo no coincide con lo que
generaría hoy. Si alguien edita el TypeScript a mano, CI lo marca. La duplicación
existe porque el browser no puede leer el modelo, no porque haya dos fuentes de
verdad.

Drivers del simulador, en el orden en que los mueve un analista:

    brent                 US$/bbl, el precio internacional
    produccion_kboed      producción de hidrocarburos de la compañía
    lifting_cost_usd_boe  costo de extracción
    crudo_procesado_kbbld carga de las refinerías (el lado downstream)
    fx_var_real           atraso cambiario del trimestre (ver abajo)

Sobre el FX: se probó como quinto driver y no resulta significativo (p 0,49
sobre 11 trimestres). Se expone igual, con su coeficiente y la marca
`significativo: false`, porque la pregunta "¿cuánto le saca el atraso cambiario
al EBITDA?" es legítima y la respuesta honesta es "con estos datos, no se puede
distinguir de cero". El frontend debería mostrarlo con esa advertencia, no
esconderlo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    PROCESSED,
    ROOT,
    base_parser,
    human,
    log,
    record,
    rel,
    save_json,
)

SRC = PROCESSED / "ebitda_sensitivity.json"
OUT_COEF = PROCESSED / "scenario_coefficients.json"
OUT_TS = ROOT / "web" / "lib" / "scenarioEngine.ts"

DRIVERS = [
    "brent_usd",
    "produccion_kboed",
    "lifting_cost_usd_boe",
    "crudo_procesado_kbbld",
]

# Escenarios con los que se verifica que las dos implementaciones dan lo mismo.
CASOS = [
    {"nombre": "base", "brent_usd": None},  # se completa con el último trimestre
    {"nombre": "brent_60", "brent_usd": 60.0},
    {"nombre": "brent_120", "brent_usd": 120.0},
    {"nombre": "costo_alto", "lifting_cost_usd_boe": 16.0},
    {"nombre": "produccion_600", "produccion_kboed": 600.0},
    {"nombre": "downstream_parado", "crudo_procesado_kbbld": 250.0},
    {"nombre": "atraso_cambiario", "fx_var_real": -0.20},
]


# --------------------------------------------------------------------------- #
# El motor
# --------------------------------------------------------------------------- #
def proyectar(escenario: dict, coeficientes: dict) -> dict:
    """EBITDA e ingresos proyectados para un escenario. Función pura.

    `escenario` acepta cualquier subconjunto de los drivers; lo que no venga se
    toma del caso base (el último trimestre reportado).
    """
    base = coeficientes["caso_base"]
    ebitda_coef = coeficientes["ebitda"]
    ingresos_coef = coeficientes["ingresos"]

    valores = {driver: float(escenario.get(driver, base[driver])) for driver in DRIVERS}
    fx_var_real = float(escenario.get("fx_var_real", 0.0))

    ebitda = ebitda_coef["const"] + sum(ebitda_coef[d] * valores[d] for d in DRIVERS)
    ebitda += coeficientes["fx"]["coeficiente"] * fx_var_real

    ingresos = ingresos_coef["const"] + sum(
        ingresos_coef[d] * valores[d] for d in ingresos_coef if d != "const"
    )

    margen = ebitda / ingresos if ingresos > 0 else float("nan")
    banda = coeficientes["ebitda"]["error_estandar"] * 1.96

    return {
        "ebitda_proyectado_musd": round(ebitda, 1),
        "ingresos_proyectados_musd": round(ingresos, 1),
        "margen": round(margen, 4),
        "delta_vs_real_musd": round(ebitda - base["adj_ebitda_musd"], 1),
        "delta_vs_real_pct": round(ebitda / base["adj_ebitda_musd"] - 1, 4),
        "banda_95_musd": [round(ebitda - banda, 1), round(ebitda + banda, 1)],
    }


# --------------------------------------------------------------------------- #
# Coeficientes
# --------------------------------------------------------------------------- #
def _coeficientes_de(modelo: dict) -> dict:
    return {c["variable"].replace("const", "const"): c["coeficiente"] for c in modelo["coeficientes"]}


def construir_coeficientes(sensibilidad: dict) -> dict:
    ebitda = sensibilidad["modelo_operativo"]
    ingresos = sensibilidad["modelo_ingresos"]
    fx_modelo = sensibilidad["modelo_fx"]
    fx_coef = next(c for c in fx_modelo["coeficientes"] if c["variable"] == "fx_var_real")
    ultimo = sensibilidad["ultimo_trimestre"]

    faltan = [d for d in DRIVERS if d not in _coeficientes_de(ebitda)]
    if faltan:
        raise RuntimeError(f"el modelo de EBITDA no trae los drivers {faltan}")

    return {
        "generado_desde": rel(SRC),
        "modelo_ebitda": ebitda["nombre"],
        "modelo_ingresos": ingresos["nombre"],
        "observaciones": ebitda["observaciones"],
        "periodo": ebitda["periodo"],
        "r2_ebitda": ebitda["r2"],
        "r2_ingresos": ingresos["r2"],
        "advertencia": (
            "Coeficientes estimados sobre pocos trimestres: la banda del 95% es parte del "
            "resultado, no un adorno."
        ),
        "ebitda": {
            **_coeficientes_de(ebitda),
            "error_estandar": ebitda["error_estandar_residual_musd"],
        },
        "ingresos": _coeficientes_de(ingresos),
        "fx": {
            "coeficiente": fx_coef["coeficiente"],
            "p_valor": fx_coef["p_valor"],
            "significativo": fx_coef["p_valor"] < 0.05,
            "nota": (
                "Estimado en una especificacion alternativa con "
                f"{fx_modelo['observaciones']} trimestres. No se distingue de cero: "
                "mostrar el slider con la advertencia."
            ),
        },
        "caso_base": {
            "trimestre": ultimo["trimestre"],
            "adj_ebitda_musd": ultimo["adj_ebitda_musd"],
            "revenues_musd": ultimo["revenues_musd"],
            "brent_usd": ultimo["brent_usd"],
            "produccion_kboed": ultimo["produccion_kboed"],
            "lifting_cost_usd_boe": ultimo["lifting_cost_usd_boe"],
            "crudo_procesado_kbbld": ultimo["crudo_procesado_kbbld"],
        },
    }


def casos_de_prueba(coeficientes: dict) -> list[dict]:
    """Escenarios con su resultado, para que el TypeScript se compare contra esto."""
    salida = []
    for caso in CASOS:
        escenario = {k: v for k, v in caso.items() if k != "nombre" and v is not None}
        salida.append(
            {"nombre": caso["nombre"], "escenario": escenario, "esperado": proyectar(escenario, coeficientes)}
        )
    return salida


# --------------------------------------------------------------------------- #
# Gemelo TypeScript
# --------------------------------------------------------------------------- #
def generar_typescript(coeficientes: dict, casos: list[dict]) -> str:
    coef_json = json.dumps(coeficientes, ensure_ascii=False, indent=2)
    casos_json = json.dumps(casos, ensure_ascii=False, indent=2)
    drivers_ts = ", ".join(f"'{d}'" for d in DRIVERS)
    union_ts = " | ".join(f"'{d}'" for d in DRIVERS)

    return f'''// GENERADO por pipeline/transform/scenario_engine.py — no editar a mano.
// Para regenerarlo: python pipeline/transform/scenario_engine.py
// CI corre `--check` y falla si este archivo quedó desincronizado del modelo.
// Paridad con la versión Python: `verificarCasos()` devuelve los escenarios en
// los que las dos implementaciones no coinciden — vacío es lo esperado.
//
// Gemelo TypeScript del simulador de escenarios. Es una función pura y corre
// entera en el browser: el slider recalcula sin ir al backend.

export type Driver = {union_ts};

export interface Escenario {{
  brent_usd?: number;
  produccion_kboed?: number;
  lifting_cost_usd_boe?: number;
  crudo_procesado_kbbld?: number;
  /** Atraso cambiario del trimestre. Ver COEFICIENTES.fx: no es significativo. */
  fx_var_real?: number;
}}

export interface Proyeccion {{
  ebitda_proyectado_musd: number;
  ingresos_proyectados_musd: number;
  margen: number;
  delta_vs_real_musd: number;
  delta_vs_real_pct: number;
  banda_95_musd: [number, number];
}}

export const DRIVERS: Driver[] = [{drivers_ts}];

export const COEFICIENTES = {coef_json} as const;

const redondear = (valor: number, decimales: number): number => {{
  const factor = 10 ** decimales;
  return Math.round(valor * factor) / factor;
}};

/**
 * EBITDA e ingresos proyectados para un escenario.
 * Lo que no venga en `escenario` se toma del caso base (último trimestre real).
 */
export function proyectar(
  escenario: Escenario,
  coeficientes: typeof COEFICIENTES = COEFICIENTES,
): Proyeccion {{
  const base = coeficientes.caso_base;
  const coefEbitda = coeficientes.ebitda as Record<string, number>;
  const coefIngresos = coeficientes.ingresos as Record<string, number>;

  const valores: Record<string, number> = {{}};
  for (const driver of DRIVERS) {{
    const propuesto = escenario[driver];
    valores[driver] = propuesto === undefined ? (base as Record<string, number>)[driver] : propuesto;
  }}
  const fxVarReal = escenario.fx_var_real ?? 0;

  let ebitda = coefEbitda.const;
  for (const driver of DRIVERS) ebitda += coefEbitda[driver] * valores[driver];
  ebitda += coeficientes.fx.coeficiente * fxVarReal;

  let ingresos = coefIngresos.const;
  for (const [variable, coeficiente] of Object.entries(coefIngresos)) {{
    if (variable !== 'const') ingresos += coeficiente * valores[variable];
  }}

  const margen = ingresos > 0 ? ebitda / ingresos : Number.NaN;
  const banda = coefEbitda.error_estandar * 1.96;

  return {{
    ebitda_proyectado_musd: redondear(ebitda, 1),
    ingresos_proyectados_musd: redondear(ingresos, 1),
    margen: redondear(margen, 4),
    delta_vs_real_musd: redondear(ebitda - base.adj_ebitda_musd, 1),
    delta_vs_real_pct: redondear(ebitda / base.adj_ebitda_musd - 1, 4),
    banda_95_musd: [redondear(ebitda - banda, 1), redondear(ebitda + banda, 1)],
  }};
}}

/** Escenarios calculados en Python. Si el TypeScript no los reproduce, hay un bug. */
export const CASOS_DE_PRUEBA = {casos_json} as const;

/** Devuelve los casos en los que las dos implementaciones no coinciden. */
export function verificarCasos(): string[] {{
  const fallas: string[] = [];
  for (const caso of CASOS_DE_PRUEBA) {{
    const obtenido = proyectar(caso.escenario as Escenario);
    for (const [clave, esperado] of Object.entries(caso.esperado)) {{
      const valor = (obtenido as Record<string, unknown>)[clave];
      if (JSON.stringify(valor) !== JSON.stringify(esperado)) {{
        fallas.push(`${{caso.nombre}}.${{clave}}: ${{JSON.stringify(valor)}} != ${{JSON.stringify(esperado)}}`);
      }}
    }}
  }}
  return fallas;
}}
'''


def main() -> int:
    parser = base_parser("Genera el simulador de escenarios y su gemelo TypeScript")
    parser.add_argument(
        "--check",
        action="store_true",
        help="no escribe: falla si el TypeScript del repo no coincide con el modelo",
    )
    args = parser.parse_args()

    if not SRC.exists():
        log(f"falta {rel(SRC)}; correr antes pipeline/transform/ebitda_sensitivity.py")
        return 1

    sensibilidad = json.loads(SRC.read_text(encoding="utf-8"))
    coeficientes = construir_coeficientes(sensibilidad)
    casos = casos_de_prueba(coeficientes)
    typescript = generar_typescript(coeficientes, casos)

    if args.check:
        if not OUT_TS.exists():
            log(f"FALTA {rel(OUT_TS)}: correr sin --check para generarlo")
            return 1
        if OUT_TS.read_text(encoding="utf-8") != typescript:
            log(f"DESINCRONIZADO: {rel(OUT_TS)} no coincide con el modelo actual")
            log("correr: python pipeline/transform/scenario_engine.py")
            return 1
        log(f"{rel(OUT_TS)} esta sincronizado con el modelo")
        return 0

    base = coeficientes["caso_base"]
    control = proyectar({}, coeficientes)
    error = control["ebitda_proyectado_musd"] - base["adj_ebitda_musd"]
    log(
        f"  caso base {base['trimestre']}: real US$ {base['adj_ebitda_musd']:,.0f}M, "
        f"modelo US$ {control['ebitda_proyectado_musd']:,.0f}M (residual {error:+,.0f}M)"
    )
    for caso in casos[1:]:
        log(f"  {caso['nombre']:20s} -> US$ {caso['esperado']['ebitda_proyectado_musd']:>8,.0f}M")

    OUT_TS.parent.mkdir(parents=True, exist_ok=True)
    OUT_TS.write_text(typescript, encoding="utf-8")
    bytes_coef = save_json({**coeficientes, "casos_de_prueba": casos}, OUT_COEF, indent=2)

    log(f"escrito {rel(OUT_COEF)} - {human(bytes_coef)}")
    log(f"escrito {rel(OUT_TS)} - {human(OUT_TS.stat().st_size)}")

    record(
        "scenario_engine",
        source=rel(SRC),
        outputs=[rel(OUT_COEF), rel(OUT_TS)],
        drivers=DRIVERS,
        casos=len(casos),
        r2_ebitda=coeficientes["r2_ebitda"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
