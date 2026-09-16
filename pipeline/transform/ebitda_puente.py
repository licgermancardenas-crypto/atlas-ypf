"""El puente del EBITDA: cuánto del cambio fue precio, cuánto volumen y cuánto costo.

Por qué existe: el caso pregunta por qué el mercado castigó a la acción con un
balance récord, y la respuesta empieza por de dónde salió el récord. Un EBITDA
que sube porque el crudo subió no vale lo mismo que uno que sube porque la
compañía produce más o le cuesta menos: el primero se lo lleva el ciclo.

Cómo se arma, que es lo que hay que poder auditar:

  El EBITDA de Upstream es volumen por margen unitario, así que su variación se
  abre exacto en tres términos —el clásico precio/volumen/costo—:

      volumen  (Q1 − Q0) × (P0 − C0)      lo que aporta producir más, al margen viejo
      precio   (P1 − P0) × Q1             lo que aporta cobrar más, sobre el volumen nuevo
      costo    −(C1 − C0) × Q1            lo que se lleva el costo unitario

  donde Q es la producción del trimestre, P el ingreso por barril del segmento
  y C su costo unitario (ingresos menos EBITDA, sobre la producción). Sumados
  dan exactamente la variación del EBITDA de Upstream: no hay residuo.

  Los otros negocios entran por su variación, y al final queda un término de
  ajustes: la diferencia entre el EBITDA ajustado que publica la compañía y la
  suma de los segmentos, que son los ajustes de consolidación y las partidas
  que la compañía excluye. Así el puente cierra contra el número publicado.

Lo que el puente no distingue: dentro de "precio" conviven el precio del crudo,
el del gas y la mezcla de productos; el ingreso por barril es el promedio de
todo eso. Para separar el efecto del Brent está el modelo de
transform/ebitda_sensitivity.py.

Entradas: data/processed/segments_ypf_homologado.parquet  (transform/segments_ypf.py)
          data/processed/financials_ypf.parquet           (producción y EBITDA del release)
Salida:   data/processed/ebitda_puente.parquet + .json
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import PROCESSED, base_parser, human, log, record, rel, save_json, save_parquet  # noqa: E402

SEGMENTOS = PROCESSED / "segments_ypf_homologado.parquet"
RELEASE = PROCESSED / "financials_ypf.parquet"
SALIDA = PROCESSED / "ebitda_puente.parquet"
SALIDA_JSON = PROCESSED / "ebitda_puente.json"

DIAS = {1: 90.25, 2: 91.0, 3: 92.0, 4: 92.0}
# Las dos comparaciones del tablero: contra el año anterior y contra el trimestre.
DESFASES = {"Año anterior": 4, "Trimestre anterior": 1}
DOWNSTREAM = "Downstream y gas"
ADMINISTRACION = "Administración central y otros"
CONSOLIDACION = "Ajustes de consolidación"


def panel() -> pd.DataFrame:
    """Un renglón por trimestre con lo que necesita el puente."""
    segmentos = pd.read_parquet(SEGMENTOS)
    segmentos = segmentos[segmentos["tipo"] == "trimestre"]
    ancho = segmentos.pivot_table(index="periodo", columns=["segmento", "concepto"], values="valor_musd",
                                  aggfunc="first")

    def linea(segmento: str, concepto: str) -> pd.Series:
        clave = (segmento, concepto)
        return ancho[clave] if clave in ancho.columns else pd.Series(dtype=float)

    datos = pd.DataFrame(index=ancho.index)
    for segmento, prefijo in (("Upstream", "up"), (DOWNSTREAM, "dg"), (ADMINISTRACION, "ac"),
                              (CONSOLIDACION, "co")):
        operativo = linea(segmento, "resultado_operativo")
        depreciacion = linea(segmento, "depreciacion_ppe")
        datos[f"ebitda_{prefijo}"] = operativo.add(depreciacion, fill_value=0)
        datos[f"ingresos_{prefijo}"] = linea(segmento, "ingresos_totales")

    release = pd.read_parquet(RELEASE).set_index("trimestre")
    for campo in ("adj_ebitda_musd", "produccion_kboed", "precio_crudo_usd_bbl", "lifting_cost_usd_boe"):
        datos[campo] = release[campo] if campo in release.columns else pd.NA

    datos["trimestre_del_anio"] = [int(p[-1]) for p in datos.index]
    datos["dias"] = datos["trimestre_del_anio"].map(DIAS)
    # Producción del trimestre en millones de boe: kboe/d × días.
    datos["volumen_mmboe"] = datos["produccion_kboed"] * datos["dias"] / 1000
    datos["precio_por_boe"] = datos["ingresos_up"] / datos["volumen_mmboe"]
    datos["costo_por_boe"] = (datos["ingresos_up"] - datos["ebitda_up"]) / datos["volumen_mmboe"]
    return datos.sort_index()


def puente(datos: pd.DataFrame) -> pd.DataFrame:
    filas = []
    periodos = list(datos.index)
    for i, periodo in enumerate(periodos):
        for etiqueta, desfase in DESFASES.items():
            if i - desfase < 0:
                continue
            base, ahora = datos.loc[periodos[i - desfase]], datos.loc[periodo]
            if pd.isna(ahora["adj_ebitda_musd"]) or pd.isna(base["adj_ebitda_musd"]):
                continue
            q0, q1 = base["volumen_mmboe"], ahora["volumen_mmboe"]
            p0, p1 = base["precio_por_boe"], ahora["precio_por_boe"]
            c0, c1 = base["costo_por_boe"], ahora["costo_por_boe"]
            completo = not any(pd.isna(v) for v in (q0, q1, p0, p1, c0, c1))
            volumen = (q1 - q0) * (p0 - c0) if completo else float("nan")
            precio = (p1 - p0) * q1 if completo else float("nan")
            costo = -(c1 - c0) * q1 if completo else float("nan")
            otros = float(ahora["ebitda_dg"] - base["ebitda_dg"]) if not pd.isna(ahora["ebitda_dg"]) else float("nan")
            central = float(ahora["ebitda_ac"] - base["ebitda_ac"]) if not pd.isna(ahora["ebitda_ac"]) else float("nan")
            # Las eliminaciones entre segmentos se mueven cientos de millones de
            # un trimestre a otro: sin su propio término ensucian el residuo.
            consolidacion = (float(ahora["ebitda_co"] - base["ebitda_co"])
                             if not pd.isna(ahora["ebitda_co"]) else float("nan"))
            delta = float(ahora["adj_ebitda_musd"] - base["adj_ebitda_musd"])
            explicado = sum(v for v in (volumen, precio, costo, otros, central, consolidacion) if not pd.isna(v))
            filas.append({
                "periodo": periodo,
                "comparacion": etiqueta,
                "periodo_base": periodos[i - desfase],
                "ebitda_base_musd": float(base["adj_ebitda_musd"]),
                "ebitda_musd": float(ahora["adj_ebitda_musd"]),
                "delta_musd": delta,
                "volumen_musd": volumen,
                "precio_musd": precio,
                "costo_musd": costo,
                "otros_negocios_musd": otros,
                "administracion_musd": central,
                "consolidacion_musd": consolidacion,
                # Lo que queda: las partidas que la compañía excluye de su EBITDA
                # ajustado —deterioros, resultados no recurrentes—.
                "ajustes_musd": delta - explicado,
                "volumen_mmboe": float(q1) if not pd.isna(q1) else float("nan"),
                "precio_por_boe": float(p1) if not pd.isna(p1) else float("nan"),
                "costo_por_boe": float(c1) if not pd.isna(c1) else float("nan"),
            })
    return pd.DataFrame(filas)


def main() -> int:
    parser = base_parser(__doc__.splitlines()[0])
    parser.parse_args()
    if not SEGMENTOS.exists() or not RELEASE.exists():
        raise SystemExit("faltan segments_ypf_homologado.parquet o financials_ypf.parquet")

    datos = panel()
    tabla = puente(datos)
    if tabla.empty:
        raise SystemExit("no se pudo armar ningún puente: faltan producción o segmentos")

    bytes_parquet = save_parquet(tabla, SALIDA)
    ultimo = tabla[(tabla["periodo"] == tabla["periodo"].max()) & (tabla["comparacion"] == "Año anterior")]
    payload = {
        "generado": pd.Timestamp.now("UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metodo": ("Descomposición contable exacta del EBITDA de Upstream (volumen × margen unitario), más la "
                   "variación de los otros negocios y de las eliminaciones entre segmentos; el resto es lo que "
                   "la compañía ajusta para llegar a su EBITDA publicado."),
        "unidades": {"musd": "millones de dólares", "precio_por_boe": "US$ por boe de producción"},
        "advertencia": ("El precio por boe es el ingreso de Upstream sobre la producción: adentro conviven crudo, "
                        "gas y mezcla. Para aislar el Brent está ebitda_sensitivity.json."),
        "comparaciones": list(DESFASES),
        "trimestres": sorted(tabla["periodo"].unique()),
        "ultimo": ultimo.to_dict("records")[0] if len(ultimo) else None,
    }
    bytes_json = save_json(payload, SALIDA_JSON, indent=2)
    record(
        "transform/ebitda-puente",
        rows=int(len(tabla)),
        bytes=int(bytes_parquet + bytes_json),
        outputs=[rel(SALIDA), rel(SALIDA_JSON)],
        note="precio/volumen/costo de Upstream + otros negocios + ajustes, por trimestre",
    )
    log(f"{rel(SALIDA)} ({human(bytes_parquet)}) · {len(tabla)} puentes · "
        f"{tabla['periodo'].min()}–{tabla['periodo'].max()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
