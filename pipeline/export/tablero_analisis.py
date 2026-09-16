"""Las tarjetas de análisis del tablero: puente, simulador, deuda, comparables y territorio.

Viven acá y no en export/tablero.py porque son otra cosa: el tablero de arriba
cuenta qué pasó en el trimestre, y estas cinco tarjetas contestan por qué. Se
dibujan sobre la misma hoja y con los mismos ayudantes, que llegan en un
contexto —las funciones que ya saben escribir una fila del bloque de datos,
insertar un gráfico o poner un ícono—.

  Puente        de dónde salió la variación del EBITDA: precio, volumen, costo,
                los otros negocios y lo que la compañía ajusta;
  Simulador     el EBITDA que sale del modelo estimado, moviendo Brent,
                producción, lifting cost y crudo procesado;
  Deuda         cuánto vence cada año y a qué cupón;
  Comparables   YPF contra Vista y Pampa, con la misma cuenta para los tres;
  Territorio    la producción por cuenca, provincia, concesión, yacimiento o
                localidad, según lo que se elija.

Todo sale de data/processed/: ebitda_puente, scenario_coefficients,
deuda_perfil, tablero_comparables y tablero_territorio. Acá no se calcula nada
que no esté en un transform; lo que hay son fórmulas que eligen y muestran.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

CIAN = "#22d3ee"
AZUL_PROFUNDO = "#1d4ed8"
AMBAR = "#fbbf24"
APAGADO = "#27405f"
TEXTO = "#eaf2ff"
TEXTO_SUAVE = "#8ea3c4"
TEXTO_TENUE = "#5d7295"
GRILLA = "#1a2e4a"
INDIGO = "#818cf8"

# El puente, en el orden en que se lee: de dónde salía el EBITDA, qué lo movió
# y dónde terminó.
COMPONENTES = [
    ("volumen_musd", "Volumen"),
    ("precio_musd", "Precio"),
    ("costo_musd", "Costo"),
    ("otros_negocios_musd", "Otros negocios"),
    ("administracion_musd", "Administración"),
    ("consolidacion_musd", "Consolidación"),
    ("ajustes_musd", "Ajustes de la compañía"),
]

# El simulador: qué puede mover el lector y entre qué valores.
PALANCAS = [
    ("brent", "Brent", "US$/bbl", "brent_usd", [40, 50, 60, 70, 80, 90, 100, 110, 120, 130]),
    ("produccion", "Producción", "kboe/d", "produccion_kboed", [440, 470, 500, 520, 540, 560, 580, 600, 640]),
    ("lifting", "Lifting cost", "US$/boe", "lifting_cost_usd_boe", [6, 7, 8, 9, 10, 12, 14, 16]),
    ("refino", "Crudo procesado", "kbbl/d", "crudo_procesado_kbbld", [280, 300, 320, 340, 360, 380, 400]),
]

COMPARADAS = [
    ("margen_ebitda", "Margen EBITDA", "porcentaje"),
    ("deuda_neta_ebitda", "Deuda neta / EBITDA", "multiplo"),
    ("capex_sobre_ebitda", "Capex / EBITDA", "porcentaje"),
]

TERRITORIO_TOPE = 10


def cargar(procesados: Path) -> dict:
    """Lo que necesitan estas tarjetas; lo que falte deja su tarjeta en blanco."""
    def leer_json(nombre: str):
        ruta = procesados / nombre
        return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None

    def leer_parquet(nombre: str):
        ruta = procesados / nombre
        return pd.read_parquet(ruta) if ruta.exists() else None

    return {
        "puente": leer_parquet("ebitda_puente.parquet"),
        "coeficientes": leer_json("scenario_coefficients.json"),
        "deuda": leer_parquet("deuda_perfil.parquet"),
        "deuda_meta": leer_json("deuda_perfil.json"),
        "comparables": leer_parquet("tablero_comparables.parquet"),
        "comparables_meta": leer_json("tablero_comparables.json"),
        "territorio": leer_parquet("tablero_territorio.parquet"),
        "territorio_meta": leer_json("tablero_territorio.json"),
    }


def escribir(c, procesados: Path) -> None:
    """Dibuja las cinco tarjetas. `c` es el contexto que arma export/tablero.py."""
    datos = cargar(procesados)
    puente(c, datos)
    simulador(c, datos)
    deuda(c, datos)
    comparables(c, datos)
    territorio(c, datos)


# --------------------------------------------------------------------------- #
# Puente del EBITDA
# --------------------------------------------------------------------------- #
def puente(c, datos: dict) -> None:
    tabla = datos["puente"]
    x, y, w, h = c.titulo_tarjeta("puente", "Puente del EBITDA", "puente_sub", icono="flujo")
    if tabla is None or tabla.empty:
        return

    fmt = c.fmt
    columnas = [clave for clave, _ in COMPONENTES]
    c.bloque("Puente del EBITDA (transform/ebitda_puente.py)",
             ["Base", "Total", *[etiqueta for _, etiqueta in COMPONENTES]])
    crudo_inicio = c.fila()
    for fila_datos in tabla.itertuples():
        # El libro guarda dólares y muestra millones: el transform da millones.
        c.renglon(f"{c.etiqueta_trimestre(fila_datos.periodo)}|{fila_datos.comparacion}", [
            (float(fila_datos.ebitda_base_musd) * 1e6, fmt["millones"]),
            (float(fila_datos.ebitda_musd) * 1e6, fmt["millones"]),
            *[(None if pd.isna(getattr(fila_datos, col)) else float(getattr(fila_datos, col)) * 1e6, fmt["millones"])
              for col in columnas],
        ])
    crudo_fin = c.fila() - 1
    c.saltar()

    etiquetas = f"{c.local(crudo_inicio, None)}:{c.local(crudo_fin, None)}"
    clave = f"{c.SEL}&\"|\"&{c.COMP}"

    def del_puente(indice: int) -> str:
        columna = c.letra(c.columna_valor(indice))
        return (f"IFERROR(INDEX(${columna}${crudo_inicio + 1}:${columna}${crudo_fin + 1},"
                f"MATCH({clave},{etiquetas},0)),\"\")")

    # Las barras: cada escalón se apoya en lo acumulado hasta ahí. "Oculto" es
    # la parte transparente de la columna apilada, y sube/baja la parte pintada.
    c.bloque("Puente: barras del trimestre elegido", ["Valor", "Oculto", "Sube", "Baja", "Acumulado"])
    barras_inicio = c.fila()
    base = c.renglon(f"={c.CMP}", [
        (f"=N({del_puente(0)})", fmt["millones"]),
        (0, fmt["millones"]),
        (f"={c.local(c.fila(), 0)}", fmt["millones"]),
        (0, fmt["millones"]),
        (f"={c.local(c.fila(), 0)}", fmt["millones"]),
    ])
    previo = base
    for i, (_, etiqueta) in enumerate(COMPONENTES):
        fila_actual = c.fila()
        valor = c.local(fila_actual, 0)
        acumulado_previo = c.local(previo, 4)
        c.renglon(etiqueta, [
            (f"=N({del_puente(i + 2)})", fmt["millones"]),
            (f"=MIN({acumulado_previo},{acumulado_previo}+{valor})", fmt["millones"]),
            (f"=MAX({valor},0)", fmt["millones"]),
            (f"=MAX(-{valor},0)", fmt["millones"]),
            (f"={acumulado_previo}+{valor}", fmt["millones"]),
        ])
        previo = fila_actual
    total = c.renglon(f"={c.SEL}", [
        (f"=N({del_puente(1)})", fmt["millones"]),
        (0, fmt["millones"]),
        (f"={c.local(c.fila(), 0)}", fmt["millones"]),
        (0, fmt["millones"]),
        (f"={c.local(c.fila(), 0)}", fmt["millones"]),
    ])
    barras_fin = total
    c.saltar()

    cascada = c.libro.add_chart({"type": "column", "subtype": "stacked"})
    cascada.add_series({
        "categories": c.categorias(barras_inicio, barras_fin),
        "values": c.serie(barras_inicio, barras_fin, 1),
        "fill": {"none": True}, "border": {"none": True}, "gap": 40,
    })
    puntos_extremos = [{"fill": {"color": AZUL_PROFUNDO}, "border": {"none": True}}]
    cascada.add_series({
        "categories": c.categorias(barras_inicio, barras_fin),
        "values": c.serie(barras_inicio, barras_fin, 2),
        "fill": {"color": CIAN}, "border": {"none": True},
        # El primero y el último son el EBITDA de cada punta, no un escalón.
        "points": puntos_extremos + [None] * len(COMPONENTES) + puntos_extremos,
        "data_labels": {"value": True, "position": "outside_end", "num_format": '#,##0,,"M"',
                        "font": {"name": c.FUENTE, "size": 8, "bold": True, "color": TEXTO}},
    })
    cascada.add_series({
        "categories": c.categorias(barras_inicio, barras_fin),
        "values": c.serie(barras_inicio, barras_fin, 3),
        "fill": {"color": AMBAR}, "border": {"none": True},
        "data_labels": {"value": True, "position": "inside_base", "num_format": '#,##0,,"M"',
                        "font": {"name": c.FUENTE, "size": 8, "bold": True, "color": "#2b1a05"}},
    })
    c.ejes_limpios(cascada)
    cascada.set_plotarea({"fill": {"none": True}, "border": {"none": True},
                          "layout": {"x": 0.05, "y": 0.06, "width": 0.93, "height": 0.82}})
    c.insertar(cascada, x + 6, y + 64, w - 12, h - 96)
    c.texto(x + 12, y + h - 30, w - 24, 22,
            "Volumen, precio y costo salen de Upstream (volumen × margen unitario); el resto son los otros "
            "negocios, las eliminaciones entre segmentos y lo que la compañía ajusta.", 7, TEXTO_TENUE)


# --------------------------------------------------------------------------- #
# Simulador
# --------------------------------------------------------------------------- #
def simulador(c, datos: dict) -> None:
    coeficientes = datos["coeficientes"]
    x, y, w, h = c.titulo_tarjeta("simulador", "Simulador de EBITDA", "simulador_sub", icono="rayo", ancho=250)
    if not coeficientes:
        return

    fmt = c.fmt
    ebitda = coeficientes["ebitda"]
    base = coeficientes["caso_base"]

    c.bloque("Simulador: coeficientes del modelo (transform/ebitda_sensitivity.py)", ["Coeficiente", "Caso base"])
    filas = {}
    constante = c.renglon("Constante", [(float(ebitda["const"]), fmt["numero"]), (None, fmt["texto"])])
    for clave, etiqueta, unidad, campo, _ in PALANCAS:
        filas[clave] = c.renglon(f"{etiqueta} ({unidad})", [
            (float(ebitda[campo]), fmt["numero"]),
            (float(base[campo]), fmt["decimal"]),
        ])
    error = c.renglon("Error estándar (MUSD)", [(float(ebitda["error_estandar"]), fmt["numero"]), (None, fmt["texto"])])
    ebitda_base = c.renglon("EBITDA del caso base", [(float(base["adj_ebitda_musd"]) * 1e6, fmt["millones"]),
                                                    (None, fmt["texto"])])
    c.saltar()

    # Las palancas: celdas desbloqueadas con lista, como los otros controles.
    controles = {}
    for clave, etiqueta, unidad, _, opciones in PALANCAS:
        celda = c.control(clave, str(opciones[len(opciones) // 2]))
        c.validar(celda, [str(o) for o in opciones], etiqueta)
        controles[clave] = celda

    estimado = " + ".join([c.local(constante, 0)] + [
        f"{c.local(filas[clave], 0)}*{controles[clave]}" for clave, _, _, _, _ in PALANCAS
    ])
    c.bloque("Simulador: resultado", ["Valor"])
    fila_estimado = c.renglon("EBITDA estimado del trimestre", [(f"=({estimado})*1000000", fmt["millones"])])
    piso = c.renglon("Piso del rango (95%)",
                     [(f"={c.local(fila_estimado, 0)}-1.96*{c.local(error, 0)}*1000000", fmt["millones"])])
    techo = c.renglon("Techo del rango (95%)",
                      [(f"={c.local(fila_estimado, 0)}+1.96*{c.local(error, 0)}*1000000", fmt["millones"])])
    contra = c.renglon("Contra el caso base", [
        (f"=IFERROR(({c.local(fila_estimado, 0)}-{c.local(ebitda_base, 0)})/ABS({c.local(ebitda_base, 0)}),\"\")",
         fmt["variacion"]),
    ])
    c.saltar()

    # Los cuatro renglones de palancas, alineados con sus celdas.
    for i, (clave, etiqueta, unidad, _, _) in enumerate(PALANCAS):
        cx, cy, _, _ = c.CONTROLES[clave]
        c.texto(x + 12, cy - 4, 136, 22, f"{etiqueta} · {unidad}", 8, TEXTO_SUAVE)
        c.texto(cx - 92, cy - 4, 84, 22, "", 8, TEXTO_TENUE, alinear="right",
                enlace=c.vinculo(filas[clave], 1))

    y_salida = y + 238
    c.texto(x + 12, y_salida, 220, 20, "EBITDA estimado", 8, TEXTO_TENUE)
    c.texto(x + 12, y_salida + 18, w - 24, 40, "", 22, TEXTO, negrita=True, enlace=c.vinculo(fila_estimado))
    c.texto(x + 12, y_salida + 60, 120, 20, "Rango 95%", 8, TEXTO_TENUE)
    c.texto(x + 110, y_salida + 60, 110, 20, "", 9, TEXTO_SUAVE, alinear="right", enlace=c.vinculo(piso))
    c.texto(x + 220, y_salida + 60, 20, 20, "a", 8, TEXTO_TENUE, alinear="center")
    c.texto(x + 240, y_salida + 60, 110, 20, "", 9, TEXTO_SUAVE, alinear="right", enlace=c.vinculo(techo))
    c.texto(x + 12, y_salida + 84, 200, 20, "Contra el caso base", 8, TEXTO_TENUE)
    c.texto(x + w - 140, y_salida + 84, 128, 20, "", 11, CIAN, negrita=True, alinear="right",
            enlace=c.vinculo(contra))
    c.texto(x + 12, y + h - 40, w - 24, 34,
            "Regresión sobre quince trimestres: el rango importa más que el punto, y no es una proyección de "
            "la compañía. El tipo de cambio no entra porque no se distingue de cero.", 7, TEXTO_TENUE)


# --------------------------------------------------------------------------- #
# Deuda
# --------------------------------------------------------------------------- #
def deuda(c, datos: dict) -> None:
    perfil, meta = datos["deuda"], datos["deuda_meta"]
    x, y, w, h = c.titulo_tarjeta("deuda", "Deuda: cuándo vence y a qué cupón", "deuda_sub", icono="balanza")
    if perfil is None or perfil.empty:
        return

    fmt = c.fmt
    c.bloque("Deuda: perfil de vencimientos (transform/deuda_perfil.py)", ["Monto", "Cupón", "Instrumentos"])
    inicio = c.fila()
    for fila_datos in perfil.itertuples():
        c.renglon(str(int(fila_datos.anio)), [
            (float(fila_datos.monto_musd) * 1e6, fmt["millones"]),
            (None if pd.isna(fila_datos.tasa_promedio_pct) else float(fila_datos.tasa_promedio_pct) / 100,
             fmt["porcentaje_decimal"]),
            (int(fila_datos.instrumentos), fmt["entero"]),
        ])
    fin = c.fila() - 1
    resumen = {}
    for clave, etiqueta, valor, formato in [
        ("total", "Deuda total", float(meta["total_musd"]) * 1e6, fmt["millones"]),
        ("cupon", "Cupón promedio ponderado", float(meta["tasa_promedio_pct"]) / 100, fmt["porcentaje_decimal"]),
        ("vida", "Vida promedio (años)", float(meta["vida_promedio_anios"]), fmt["decimal"]),
    ]:
        resumen[clave] = c.renglon(etiqueta, [(valor, formato)])
    mayor = c.renglon("Año con más vencimientos", [
        (f"=INDEX({c.local(inicio, None)}:{c.local(fin, None)},"
         f"MATCH(MAX({c.local(inicio, 0)}:{c.local(fin, 0)}),{c.local(inicio, 0)}:{c.local(fin, 0)},0))", fmt["texto"]),
    ])
    monto_mayor = c.renglon("Monto de ese año", [(f"=MAX({c.local(inicio, 0)}:{c.local(fin, 0)})", fmt["millones"])])
    c.saltar()

    fichas = [("Deuda total", c.vinculo(resumen["total"]), TEXTO),
              ("Cupón promedio", c.vinculo(resumen["cupon"]), CIAN),
              ("Vida promedio", c.vinculo(resumen["vida"]), TEXTO_SUAVE)]
    ancho = (w - 24 - 2 * 12) / 3
    for i, (rotulo, enlace, tinte) in enumerate(fichas):
        fx = x + 12 + i * (ancho + 12)
        c.texto(fx, y + 62, ancho, 18, rotulo, 8, TEXTO_TENUE)
        c.texto(fx, y + 78, ancho, 30, "", 17, tinte, negrita=True, enlace=enlace)

    escalera = c.libro.add_chart({"type": "column"})
    escalera.add_series({
        "categories": c.categorias(inicio, fin),
        "values": c.serie(inicio, fin, 0),
        "gradient": {"colors": [CIAN, AZUL_PROFUNDO], "angle": 90}, "border": {"none": True}, "gap": 45,
        "data_labels": {"value": True, "position": "outside_end", "num_format": '#,##0,,"M"',
                        "font": {"name": c.FUENTE, "size": 8, "bold": True, "color": TEXTO}},
    })
    c.ejes_limpios(escalera)
    escalera.set_plotarea({"fill": {"none": True}, "border": {"none": True},
                           "layout": {"x": 0.06, "y": 0.08, "width": 0.92, "height": 0.76}})
    c.insertar(escalera, x + 6, y + 118, w - 12, h - 152)
    c.texto(x + 12, y + h - 32, w - 24, 24,
            "El año es el del vencimiento del capital: los bonos que amortizan en cuotas figuran enteros contra "
            "su último pago, así que la escalera es un techo por año.", 7, TEXTO_TENUE)


# --------------------------------------------------------------------------- #
# Comparables
# --------------------------------------------------------------------------- #
def comparables(c, datos: dict) -> None:
    tabla, meta = datos["comparables"], datos["comparables_meta"]
    x, y, w, h = c.titulo_tarjeta("comparables", "YPF contra Vista y Pampa", "comparables_sub", icono="velas")
    if tabla is None or tabla.empty or not meta:
        return

    fmt = c.fmt
    anios = meta["anios_comparables"]
    tickers = ["YPF", "VIST", "PAM"]
    presentes = [t for t in tickers if t in set(tabla["ticker"])]
    indexada = tabla.set_index(["ticker", "anio"])

    c.bloque("Comparables: margen EBITDA por ejercicio", presentes)
    margen_inicio = c.fila()
    for anio in anios:
        c.renglon(f"FY{anio[-2:]}", [
            (float(indexada.loc[(t, anio), "margen_ebitda"]) if (t, anio) in indexada.index else None,
             fmt["porcentaje_decimal"]) for t in presentes
        ])
    margen_fin = c.fila() - 1
    c.saltar()

    c.bloque("Comparables: el último ejercicio comparable", presentes)
    filas_metricas = {}
    for clave, etiqueta, formato in COMPARADAS:
        filas_metricas[clave] = c.renglon(etiqueta, [
            (float(indexada.loc[(t, meta["ultimo_ejercicio_comun"]), clave])
             if (t, meta["ultimo_ejercicio_comun"]) in indexada.index else None, fmt[formato])
            for t in presentes
        ])
    multiplos = {m["ticker"]: m for m in meta.get("multiplos", [])}
    fila_ev = c.renglon("EV / EBITDA (precio de hoy)", [
        (multiplos.get(t, {}).get("ev_ebitda"), fmt["multiplo"]) for t in presentes
    ])
    fila_pvl = c.renglon("Precio / valor libro", [
        (multiplos.get(t, {}).get("precio_valor_libro"), fmt["multiplo"]) for t in presentes
    ])
    c.saltar()

    grafico = c.libro.add_chart({"type": "column"})
    colores = {"YPF": CIAN, "VIST": INDIGO, "PAM": APAGADO}
    for i, ticker in enumerate(presentes):
        grafico.add_series({
            "name": ticker,
            "categories": c.categorias(margen_inicio, margen_fin),
            "values": c.serie(margen_inicio, margen_fin, i),
            "fill": {"color": colores.get(ticker, APAGADO)}, "border": {"none": True},
            "gap": 60, "overlap": -10,
            "data_labels": {"value": True, "position": "outside_end", "num_format": "0%",
                            "font": {"name": c.FUENTE, "size": 7, "color": TEXTO_SUAVE}},
        })
    c.ejes_limpios(grafico, formato_y="0%")
    grafico.set_plotarea({"fill": {"none": True}, "border": {"none": True},
                          "layout": {"x": 0.09, "y": 0.1, "width": 0.88, "height": 0.74}})
    ancho_grafico = 330
    c.insertar(grafico, x + 6, y + 88, ancho_grafico, h - 124)
    c.texto(x + 12, y + 64, ancho_grafico, 20, "Margen EBITDA por ejercicio", 8, TEXTO_TENUE)
    for i, ticker in enumerate(presentes):
        c.texto(x + 12 + i * 92, y + h - 46, 90, 18, f"■ {ticker}", 8, colores.get(ticker, APAGADO), negrita=True)

    # La tabla: una columna por compañía.
    tx = x + ancho_grafico + 24
    ancho_etiqueta = 150
    ancho_columna = (w - 24 - (tx - x) - ancho_etiqueta) / len(presentes)
    c.texto(tx, y + 64, 200, 20, f"Ejercicio {meta['ultimo_ejercicio_comun']}", 8, TEXTO_TENUE)
    for i, ticker in enumerate(presentes):
        c.texto(tx + ancho_etiqueta + i * ancho_columna, y + 64, ancho_columna, 20, ticker, 9,
                colores.get(ticker, APAGADO), negrita=True, alinear="right")
    renglones = [*[(etiqueta, filas_metricas[clave]) for clave, etiqueta, _ in COMPARADAS],
                 ("EV / EBITDA", fila_ev), ("Precio / valor libro", fila_pvl)]
    for j, (etiqueta, fila_dato) in enumerate(renglones):
        yy = y + 92 + j * 34
        c.texto(tx, yy, 170, 22, etiqueta, 9, TEXTO_SUAVE)
        for i in range(len(presentes)):
            c.texto(tx + ancho_etiqueta + i * ancho_columna, yy, ancho_columna, 22, "", 10, TEXTO, negrita=True,
                    alinear="right", enlace=c.vinculo(fila_dato, i))
    c.texto(tx, y + h - 46, w - 24 - (tx - x), 34,
            "Mismo cálculo para los tres: EBITDA como resultado operativo más depreciaciones y deuda neta "
            "sobre EBITDA. El múltiplo usa el precio de hoy contra el último ejercicio cerrado.", 7, TEXTO_TENUE)


# --------------------------------------------------------------------------- #
# Territorio
# --------------------------------------------------------------------------- #
def territorio(c, datos: dict) -> None:
    tabla, meta = datos["territorio"], datos["territorio_meta"]
    x, y, w, h = c.titulo_tarjeta("territorio", "Producción por territorio", "territorio_sub", icono="pin",
                                  ancho=210)
    if tabla is None or tabla.empty or not meta:
        return

    fmt = c.fmt
    dimensiones = meta["dimensiones"]
    periodos = meta["trimestres"]
    ancho_tabla = tabla.pivot_table(index=["dimension", "miembro"], columns="periodo", values="boed", aggfunc="first")
    ancho_tabla = ancho_tabla.reindex(columns=periodos)
    shale = tabla.pivot_table(index=["dimension", "miembro"], columns="periodo", values="shale_boed", aggfunc="first")
    shale = shale.reindex(columns=periodos)

    # La celda del control ya existe (la crea export/tablero.py con el resto);
    # acá se le cuelga la lista.
    celda_dimension = c.DIMENSION
    c.validar(celda_dimension, dimensiones, "Dimensión")

    c.bloque("Territorio: boe/d por trimestre (transform/tablero_territorio.py)",
             [c.etiqueta_trimestre(p) for p in periodos])
    crudo_inicio = c.fila()
    for (dimension, miembro), fila_datos in ancho_tabla.iterrows():
        c.renglon(f"{dimension}|{miembro}", [
            (None if pd.isna(v) else float(v), fmt["entero"]) for v in fila_datos
        ])
    crudo_fin = c.fila() - 1
    c.saltar()

    c.bloque("Territorio: shale por trimestre", [c.etiqueta_trimestre(p) for p in periodos])
    shale_inicio = c.fila()
    for (dimension, miembro), fila_datos in shale.iterrows():
        c.renglon(f"{dimension}|{miembro}", [
            (None if pd.isna(v) else float(v), fmt["entero"]) for v in fila_datos
        ])
    shale_fin = c.fila() - 1
    c.saltar()

    encabezados_periodos = [c.etiqueta_trimestre(p) for p in periodos]

    def columna_de(celda_trimestre: str) -> str:
        """La columna del trimestre elegido dentro de los bloques de arriba."""
        lista = ",".join(f'"{e}"' for e in encabezados_periodos)
        return f"MATCH({celda_trimestre},{{{lista}}},0)"

    def valor(bloque_inicio: int, bloque_fin: int, celda_trimestre: str, fila_miembro: int) -> str:
        primera, ultima = c.columna_valor(0), c.columna_valor(len(periodos) - 1)
        rango = (f"${c.letra(primera)}${bloque_inicio + 1}:${c.letra(ultima)}${bloque_fin + 1}")
        # Cada valor ocupa seis columnas combinadas: la enésima empieza en (n−1)*6+1.
        return f"IFERROR(INDEX({rango},{fila_miembro},({columna_de(celda_trimestre)}-1)*6+1),0)"

    c.bloque("Territorio: trimestre elegido", ["boe/d", "Comparación", "Variación", "Shale", "Parte shale", "Orden"])
    elegido_inicio = c.fila()
    total_miembros = len(ancho_tabla)
    for i, (dimension, miembro) in enumerate(ancho_tabla.index):
        fila_actual = c.fila()
        propio = c.local(fila_actual, 0)
        base = c.local(fila_actual, 1)
        de_la_dimension = f'{celda_dimension}="{dimension}"'
        c.renglon(f"{dimension}|{miembro}", [
            (f"=IF({de_la_dimension},{valor(crudo_inicio, crudo_fin, c.SEL, i + 1)},\"\")", fmt["entero"]),
            (f"=IF({de_la_dimension},{valor(crudo_inicio, crudo_fin, c.CMP, i + 1)},\"\")", fmt["entero"]),
            (f'=IFERROR(IF(N({base})=0,"",({propio}-{base})/ABS({base})),"")', fmt["variacion_corta"]),
            (f"=IF({de_la_dimension},{valor(shale_inicio, shale_fin, c.SEL, i + 1)},\"\")", fmt["entero"]),
            (f'=IFERROR(IF(N({propio})=0,"",{c.local(fila_actual, 3)}/{propio}),"")', fmt["porcentaje"]),
            (f'=IF({de_la_dimension},N({propio})+{total_miembros - i}/10000,"")', fmt["numero"]),
        ])
    elegido_fin = c.fila() - 1
    c.saltar()

    orden = f"{c.local(elegido_inicio, 5)}:{c.local(elegido_fin, 5)}"
    nombres = f"{c.local(elegido_inicio, None)}:{c.local(elegido_fin, None)}"
    c.bloque("Territorio: ranking del trimestre",
             ["boe/d", "Variación", "Parte shale", "Participación", "Mostrado"])
    ranking_inicio = c.fila()
    for k in range(1, TERRITORIO_TOPE + 1):
        posicion = f"MATCH(LARGE({orden},{k}),{orden},0)"
        fila_actual = c.fila()
        c.renglon(f'=IFERROR(MID(INDEX({nombres},{posicion}),FIND("|",INDEX({nombres},{posicion}))+1,200),"")', [
            # NA() y no vacío: con menos miembros que puestos, la barra no se dibuja.
            (f"=IFERROR(INDEX({c.local(elegido_inicio, 0)}:{c.local(elegido_fin, 0)},{posicion}),NA())", fmt["entero"]),
            (f"=IFERROR(INDEX({c.local(elegido_inicio, 2)}:{c.local(elegido_fin, 2)},{posicion}),\"\")",
             fmt["variacion_corta"]),
            (f"=IFERROR(INDEX({c.local(elegido_inicio, 4)}:{c.local(elegido_fin, 4)},{posicion}),\"\")",
             fmt["porcentaje"]),
            (f"=IFERROR({c.local(fila_actual, 0)}/SUM({c.local(elegido_inicio, 0)}:{c.local(elegido_fin, 0)}),\"\")",
             fmt["porcentaje"]),
            # Lo mismo que la columna del gráfico, pero sin el #N/D que deja el
            # puesto vacío: la tabla se lee, el gráfico necesita el hueco.
            # IFNA es de Excel 2013 y xlsxwriter la escribiría como función futura:
            # con ISNA alcanza y funciona en cualquier versión.
            (f'=IF(ISNA({c.local(fila_actual, 0)}),"",{c.local(fila_actual, 0)})', fmt["entero"]),
        ])
    ranking_fin = c.fila() - 1
    total_territorio = c.renglon("Total de la dimensión", [
        (f"=SUM({c.local(elegido_inicio, 0)}:{c.local(elegido_fin, 0)})", fmt["entero"]),
        (None, fmt["texto"]), (None, fmt["texto"]), (None, fmt["texto"]), (None, fmt["texto"]),
    ])
    c.saltar()

    barras = c.libro.add_chart({"type": "bar"})
    barras.add_series({
        "categories": c.categorias(ranking_inicio, ranking_fin),
        "values": c.serie(ranking_inicio, ranking_fin, 0),
        "gradient": {"colors": [AZUL_PROFUNDO, CIAN], "angle": 0}, "border": {"none": True}, "gap": 50,
        "data_labels": {"value": True, "position": "outside_end", "num_format": '#,##0,"k"',
                        "font": {"name": c.FUENTE, "size": 8, "bold": True, "color": TEXTO}},
    })
    barras.set_plotarea({"fill": {"none": True}, "border": {"none": True},
                         "layout": {"x": 0.28, "y": 0.02, "width": 0.66, "height": 0.96}})
    barras.set_x_axis(c.eje_oculto())
    barras.set_y_axis({"num_font": {"name": c.FUENTE, "size": 8, "color": TEXTO_SUAVE}, "reverse": True,
                       "line": {"none": True}, "major_tick_mark": "none",
                       "major_gridlines": {"visible": False}})
    c.insertar(barras, x + 6, y + 62, 780, h - 76)

    # La tabla de la derecha: los mismos diez, con el detalle.
    tx = x + 812
    columnas = [("boe/d", 4, 96), ("Contra", 1, 84), ("Shale", 2, 70), ("Parte", 3, 70)]
    c.texto(tx, y + 62, 200, 18, "Los diez primeros", 8, TEXTO_TENUE)
    x_columna = tx + 180
    for etiqueta, _, ancho_columna in columnas:
        c.texto(x_columna, y + 62, ancho_columna, 18, etiqueta, 8, TEXTO_TENUE, alinear="right")
        x_columna += ancho_columna
    for i in range(TERRITORIO_TOPE):
        fila_dato = ranking_inicio + i
        yy = y + 84 + i * 26
        c.texto(tx, yy, 180, 20, "", 9, TEXTO_SUAVE, enlace=c.vinculo(fila_dato, None))
        x_columna = tx + 180
        for _, indice, ancho_columna in columnas:
            c.texto(x_columna, yy, ancho_columna, 20, "", 9, TEXTO if indice == 4 else TEXTO_SUAVE,
                    negrita=indice == 4, alinear="right", enlace=c.vinculo(fila_dato, indice))
            x_columna += ancho_columna
    c.texto(tx, y + h - 34, 180, 20, "Total de la dimensión", 8, TEXTO_TENUE)
    c.texto(tx + 180, y + h - 34, 96, 20, "", 9, CIAN, negrita=True, alinear="right",
            enlace=c.vinculo(total_territorio, 0))
    c.texto(tx + 290, y + h - 34, w - 24 - (tx + 290 - x), 20,
            "Bruta operada, con la parte de los socios.", 7, TEXTO_TENUE)
