"""La hoja Tablero del Excel de estados: el trimestre en una pantalla.

Es la misma lectura que la hoja Resumen, armada como un tablero oscuro de
tarjetas: el trimestre, la serie, los márgenes contra otro período, el
acumulado del año, adónde va cada dólar de ingresos, en qué segmento se
invierte y los ejercicios.

Es interactivo sin macros. Cuatro listas desplegables gobiernan todo:

  Trimestre   cualquiera con doce trimestres de historia detrás;
  Segmento    consolidado o un negocio: las tarjetas que tienen apertura por
              segmento se filtran, las que no la tienen lo avisan;
  Métrica     qué muestra la serie de barras;
  Contra      si las comparaciones son contra un año antes o contra el
              trimestre anterior.

Cómo está construida, porque Excel no tiene tarjetas:

  - el fondo y las tarjetas redondeadas son una imagen generada acá, cortada
    en pedazos para dejar descubiertas las celdas de las listas (una imagen
    encima de una celda no deja hacer clic en ella);
  - los gráficos son gráficos nativos de Excel con fondo transparente;
  - los textos son cuadros de texto, y los que cambian están vinculados a una
    celda.

Ningún número está escrito: todo sale del bloque "Datos del tablero" al pie de
la hoja, que son fórmulas INDEX contra Resultados, Flujo de efectivo, Análisis,
Segmentos y Valuación, desplazadas según la columna del trimestre elegido.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import numpy as np
import xlsxwriter
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import iconos
import tablero_analisis

NOMBRE = "Tablero"
# Dónde están los datos cuando el exportador no lo dice (correr el módulo suelto).
PROCESADOS_POR_DEFECTO = Path(__file__).resolve().parents[2] / "data" / "processed"

# --------------------------------------------------------------------------- #
# Paleta
# --------------------------------------------------------------------------- #
PAGINA = "#050b16"
TEXTO = "#eaf2ff"
TEXTO_SUAVE = "#8ea3c4"
TEXTO_TENUE = "#5d7295"
CIAN = "#22d3ee"
AZUL_PROFUNDO = "#1d4ed8"
BARRA_APAGADA = "#27405f"
GRILLA = "#1a2e4a"
AMBAR = "#fbbf24"
CONTROL = "#132a4b"
CONTROL_BORDE = "#2f5b8f"

# Colores de las porciones de las dos tortas, de la más grande a la más chica.
PORCIONES = ["#22d3ee", "#3b82f6", "#1e3a8a", "#67e8f9", "#94a3b8", "#475569"]

FUENTE = "Segoe UI"

# Grilla de la hoja: celdas de 20 x 20 píxeles, así una posición en píxeles se
# traduce directo a fila, columna y desplazamiento.
CELDA = 20

# --------------------------------------------------------------------------- #
# Geometría, en píxeles desde la esquina de la hoja
# --------------------------------------------------------------------------- #
PANEL_X, PANEL_Y = 20, 20
PANEL_W, PANEL_H = 1560, 2960

IZQ_X, CEN_X, DER_X = 44, 440, 1144
IZQ_W, CEN_W, DER_W = 372, 680, 412

CABECERA = (PANEL_X + 24, 40, PANEL_W - 48, 60)
FILA_A_Y, FILA_A_H = 120, 286
FILA_B_Y, FILA_B_H = 430, 244
FILA_C_Y, FILA_C_H = 698, 228
FILA_D_Y, FILA_D_H = 950, 480
FILA_E_Y, FILA_E_H = 1454, 296
FILA_F_Y, FILA_F_H = 1780, 380
FILA_G_Y, FILA_G_H = 2184, 380
FILA_H_Y, FILA_H_H = 2588, 372

# El mapa: el recuadro donde se dibuja, relativo a la tarjeta. Su proporción
# es la de la ventana que arma transform/tablero_mapa.py.
MAPA_ANCHO_TARJETA = 700
MAPA_RECUADRO = (16, 64, 370, 400)

# Siluetas tenues en el fondo de algunas tarjetas: (ícono, lado, corrimiento x, y
# desde la esquina inferior derecha). Van donde no hay un gráfico encima.
MARCAS_DE_AGUA = {
    "capex": ("casco", 130, -14, -40),
    "mapa": ("cigueña", 150, -12, 4),
}

TARJETAS = {
    "heroe": (IZQ_X, FILA_A_Y, IZQ_W, FILA_A_H),
    "ingresos": (CEN_X, FILA_A_Y, CEN_W, FILA_A_H),
    "margenes": (DER_X, FILA_A_Y, DER_W, FILA_A_H),
    "semestre": (IZQ_X, FILA_B_Y, IZQ_W, FILA_B_H),
    "destino": (CEN_X, FILA_B_Y, CEN_W, FILA_B_H),
    "capex": (DER_X, FILA_B_Y, DER_W, FILA_B_H + 24 + FILA_C_H),
    "caja": (IZQ_X, FILA_C_Y, 660, FILA_C_H),
    "ejercicios": (IZQ_X + 660 + 24, FILA_C_Y, CEN_X + CEN_W - (IZQ_X + 660 + 24), FILA_C_H),
    "mapa": (IZQ_X, FILA_D_Y, MAPA_ANCHO_TARJETA, FILA_D_H),
    "operativo": (IZQ_X + MAPA_ANCHO_TARJETA + 24, FILA_D_Y,
                  DER_X + DER_W - (IZQ_X + MAPA_ANCHO_TARJETA + 24), FILA_D_H),
    "mercado": (IZQ_X, FILA_E_Y, DER_X - 24 - IZQ_X, FILA_E_H),
    "sensibilidad": (DER_X, FILA_E_Y, DER_W, FILA_E_H),
    "puente": (IZQ_X, FILA_F_Y, DER_X - 24 - IZQ_X, FILA_F_H),
    "simulador": (DER_X, FILA_F_Y, DER_W, FILA_F_H),
    "deuda": (IZQ_X, FILA_G_Y, 700, FILA_G_H),
    "comparables": (IZQ_X + 724, FILA_G_Y, DER_X + DER_W - (IZQ_X + 724), FILA_G_H),
    "territorio": (IZQ_X, FILA_H_Y, DER_X + DER_W - IZQ_X, FILA_H_H),
}

# Las celdas de las listas desplegables, en píxeles y alineadas a la grilla:
# (x, y, ancho, alto). La imagen de fondo no las cubre.
CONTROLES = {
    "trimestre": (920, 60, 80, 20),
    "segmento": (1120, 60, 180, 20),
    "metrica": (640, 140, 160, 20),
    "comparar": (1380, 140, 140, 20),
    # El simulador: cuatro celdas que el lector cambia a mano.
    "brent": (1400, 1860, 80, 20),
    "produccion": (1400, 1900, 80, 20),
    "lifting": (1400, 1940, 80, 20),
    "refino": (1400, 1980, 80, 20),
    # La dimensión del territorio.
    "dimension": (240, 2600, 160, 20),
}
# Lo que el marco de la pastilla sobresale de la celda: a la derecha deja lugar
# para la flecha.
MARCO_IZQ, MARCO_DER, MARCO_VERT = 8, 22, 5

# Ancho de la columna de caja, a la derecha de la tarjeta de destino.
RECUADRO_W = 196

# Donde arranca el bloque de datos, debajo del panel.
DATOS_FILA = (PANEL_Y + PANEL_H) // CELDA + 3

# Columnas del bloque de datos: una etiqueta ancha y ocho valores. Cada una es
# un rango combinado; las fórmulas y las series de los gráficos van a la
# primera celda del rango, que en vertical queda contigua.
DATOS_ETIQUETA = (1, 12)
DATOS_VALORES = [(13 + 6 * i, 18 + 6 * i) for i in range(40)]
ULTIMA_COLUMNA = DATOS_VALORES[-1][1] + 1

# El filtro usa la apertura homologada (transform/segments_ypf.py): la
# reportada cambió dos veces y un filtro por "Downstream" mostraba trimestres
# sueltos. Si el libro no la trae, cae a los negocios reportados.
APERTURA_HOMOLOGADA = "homologada"
SEGMENTOS_FILTRO_HOMOLOGADOS = ["Upstream", "Downstream y gas"]
# Todos los negocios que la compañía abrió alguna vez: la torta de capex muestra
# los que existían en el trimestre elegido, con su nombre de época.
SEGMENTOS_REPORTADOS = ["Upstream", "Midstream y Downstream", "Downstream", "Industrialización", "Comercialización",
                        "Gas y energía", "GNL y gas integrado", "Nuevas energías"]
SEGMENTOS_CAPEX = [*SEGMENTOS_REPORTADOS, "Administración central y otros"]
PORCIONES_CAPEX = 5  # la torta muestra los cinco mayores y agrupa el resto
# El EBITDA consolidado del tablero es el ajustado que publica la compañía: es
# el que lee el mercado. El de los estados (resultado operativo más
# depreciaciones) incluye los deterioros y se muestra al lado, con su nombre.
EBITDA = "EBITDA ajustado"
METRICAS = ["Ingresos", EBITDA, "Resultado operativo", "Capex", "Flujo operativo",
            "Flujo de caja libre", "Resultado neto"]
COMPARACIONES = ["Año anterior", "Trimestre anterior"]

# La serie de barras necesita doce trimestres hacia atrás del elegido.
HISTORIA = 12
TOPE = 2  # la barra llena del acumulado es el doble del año anterior

# Mapa: cuántas concesiones llevan rótulo, las que se listan al costado, y los
# tamaños de burbuja. Excel no tiene burbujas con tamaño por fórmula, así que
# cada tamaño es una serie y cada concesión cae en la que le toca.
MAPA_ROTULOS = 10
MAPA_LISTA = 10
TAMANIOS_BURBUJA = [7, 12, 18, 25, 33]
MAPA_COLORES = [CIAN, AMBAR]  # creció o se mantuvo / cayó contra la comparación


# --------------------------------------------------------------------------- #
# Imagen de fondo
# --------------------------------------------------------------------------- #
ESCALA_IMAGEN = 2


def _rgba(color: str, alfa: int = 255) -> tuple[int, int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16), alfa


def _degradado(ancho: int, alto: int, arriba: str, abajo: str, diagonal: bool = False) -> Image.Image:
    """Un degradado de dos colores, vertical o en diagonal."""
    a, b = np.array(_rgba(arriba), dtype=float), np.array(_rgba(abajo), dtype=float)
    ys = np.linspace(0, 1, alto)[:, None]
    xs = np.linspace(0, 1, ancho)[None, :]
    t = (xs + ys) / 2 if diagonal else np.broadcast_to(ys, (alto, ancho))
    matriz = a + (b - a) * t[..., None]
    return Image.fromarray(matriz.astype(np.uint8), "RGBA")


def _fuente(tamanio: int, negrita: bool = False) -> ImageFont.ImageFont:
    candidatos = (
        ["C:/Windows/Fonts/seguisb.ttf", "C:/Windows/Fonts/segoeuib.ttf"] if negrita else ["C:/Windows/Fonts/segoeui.ttf"]
    ) + [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if negrita else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf" if negrita else "DejaVuSans.ttf",
    ]
    for ruta in candidatos:
        try:
            return ImageFont.truetype(ruta, tamanio)
        except OSError:
            continue
    return ImageFont.load_default(size=tamanio)


def _tarjeta(lienzo: Image.Image, x: int, y: int, w: int, h: int, radio: int = 20,
             relleno: Image.Image | None = None, sombra: bool = True) -> None:
    """Pega una tarjeta redondeada con sombra, borde y brillo en el canto."""
    s = ESCALA_IMAGEN
    x, y, w, h, radio = x * s, y * s, w * s, h * s, radio * s

    if sombra:
        capa = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
        ImageDraw.Draw(capa).rounded_rectangle((x, y + 10 * s, x + w, y + h + 10 * s), radio, fill=(0, 0, 0, 120))
        lienzo.alpha_composite(capa.filter(ImageFilter.GaussianBlur(14 * s)))

    mascara = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, w - 1, h - 1), radio, fill=255)
    cuerpo = relleno if relleno is not None else _degradado(w, h, "#10223d", "#0b182c")
    cuerpo = cuerpo.resize((w, h)) if cuerpo.size != (w, h) else cuerpo
    lienzo.paste(cuerpo, (x, y), mascara)

    trazo = ImageDraw.Draw(lienzo)
    trazo.rounded_rectangle((x, y, x + w - 1, y + h - 1), radio, outline=_rgba("#27466f", 200), width=s)
    # El canto superior un poco más claro: es lo que hace que parezca vidrio.
    brillo = Image.new("RGBA", (w, min(radio * 2, h)), (0, 0, 0, 0))
    ImageDraw.Draw(brillo).rounded_rectangle(
        (s, s, w - 1 - s, h - 1 - s), radio, outline=(150, 200, 255, 60), width=s
    )
    lienzo.alpha_composite(brillo, (x, y))


def _subtrazos(trazo: str) -> list[list[tuple[float, float]]]:
    """Un path SVG de M, L y Z (lo que escribe transform/map_svg.py) en listas de puntos."""
    partes: list[list[tuple[float, float]]] = []
    for comando, x, y in re.findall(r"([MLZ])\s*(-?[\d.]+)?[ ,]?(-?[\d.]+)?", trazo):
        if comando == "M":
            partes.append([(float(x), float(y))])
        elif comando == "L" and partes:
            partes[-1].append((float(x), float(y)))
    return partes


def recuadro_del_mapa(mapa: dict) -> tuple[int, int, int, int]:
    """El rectángulo del mapa en la hoja, con la proporción de la ventana de datos."""
    tx, ty, _, _ = TARJETAS["mapa"]
    dx, dy, _, alto = MAPA_RECUADRO
    ventana = mapa["ventana"]
    ancho = round(alto * ventana["ancho"] / ventana["alto"])
    return tx + dx, ty + dy, ancho, alto


def dibujar_mapa(lienzo: Image.Image, mapa: dict, web: dict, relieve: Path) -> None:
    """El núcleo de Vaca Muerta: relieve, áreas de YPF, yacimientos, ríos y rutas.

    Es la misma cartografía que el mapa del sitio (mapa_web.json), recortada a
    la ventana donde están las concesiones y teñida para el fondo oscuro. Las
    burbujas no van acá: son un gráfico de Excel encima, porque cambian.
    """
    s = ESCALA_IMAGEN
    x, y, w, h = recuadro_del_mapa(mapa)
    ventana = mapa["ventana"]
    escala = w * s / ventana["ancho"]

    def a_px(px: float, py: float) -> tuple[float, float]:
        return (px - ventana["x"]) * escala, (py - ventana["y"]) * escala

    capa = Image.new("RGBA", (w * s, h * s), _rgba("#081629"))

    # El relieve: el sombreado viene en gris con alfa; lo oscuro son laderas en
    # sombra, que acá oscurecen el azul del fondo.
    info = web.get("relieve")
    if info and relieve.exists():
        sombreado = Image.open(relieve).convert("LA")
        fx, fy = sombreado.width / info["ancho"], sombreado.height / info["alto"]
        caja = (
            (ventana["x"] - info["x"]) * fx, (ventana["y"] - info["y"]) * fy,
            (ventana["x"] + ventana["ancho"] - info["x"]) * fx, (ventana["y"] + ventana["alto"] - info["y"]) * fy,
        )
        recorte = sombreado.crop(tuple(round(v) for v in caja)).resize((w * s, h * s), Image.BICUBIC)
        gris, alfa = (np.asarray(banda, dtype=float) for banda in recorte.split())
        sombra = ((255 - gris) * alfa / 255 * 0.75).clip(0, 255).astype(np.uint8)
        luz = (gris * alfa / 255 * 0.10).clip(0, 255).astype(np.uint8)
        capa.alpha_composite(Image.merge("RGBA", [Image.new("L", capa.size, 0)] * 3 + [Image.fromarray(sombra)]))
        claro = Image.new("RGBA", capa.size, _rgba("#7fb3ff"))
        claro.putalpha(Image.fromarray(luz))
        capa.alpha_composite(claro)

    capas = web.get("capas", {})

    # Sobre una imagen RGBA, Pillow no mezcla: el color con alfa pisa el píxel.
    # Cada capa se dibuja en una hoja transparente y se compone encima.
    def en_capa(dibujar) -> None:
        hoja_transparente = Image.new("RGBA", capa.size, (0, 0, 0, 0))
        dibujar(ImageDraw.Draw(hoja_transparente))
        capa.alpha_composite(hoja_transparente)

    def poligonos(clave: str, relleno, borde, ancho: int = 1) -> None:
        def dibujar(d):
            for trazo in capas.get(clave, []):
                for parte in _subtrazos(trazo):
                    if len(parte) >= 3:
                        d.polygon([a_px(*p) for p in parte], fill=relleno, outline=borde, width=ancho * s)
        en_capa(dibujar)

    def lineas(clave: str, color, ancho: float = 1) -> None:
        def dibujar(d):
            for trazo in capas.get(clave, []):
                for parte in _subtrazos(trazo):
                    if len(parte) >= 2:
                        d.line([a_px(*p) for p in parte], fill=color, width=max(1, round(ancho * s)))
        en_capa(dibujar)

    poligonos("concesiones", None, (120, 150, 200, 45))
    poligonos("areas_ypf", (37, 99, 235, 38), (96, 165, 250, 110))
    poligonos("vaca_muerta", (125, 211, 252, 22), None)
    lineas("rutas_provinciales", (148, 163, 184, 38), 0.6)
    lineas("rutas", (148, 163, 184, 90), 1)
    lineas("rios", (56, 130, 210, 170), 1.4)
    poligonos("provincias", None, (180, 200, 230, 50))

    dibujo = ImageDraw.Draw(capa)
    fuente = _fuente(9 * s)
    for punto in web.get("puntos", {}).get("localidades", []):
        if punto.get("rango") not in ("capital", "actividad"):
            continue
        px, py = a_px(punto["x"], punto["y"])
        if not (0 <= px <= w * s and 0 <= py <= h * s):
            continue
        dibujo.ellipse((px - 2 * s, py - 2 * s, px + 2 * s, py + 2 * s), fill=(226, 232, 240, 220))
        dibujo.text((px + 5 * s, py - 6 * s), punto["nombre"], font=fuente, fill=(203, 213, 225, 200))

    # Barra de escala: veinte kilómetros.
    km = web.get("escala_km")
    if km:
        largo = 20 / km * escala
        bx, by = 12 * s, h * s - 16 * s
        dibujo.line([(bx, by), (bx + largo, by)], fill=(203, 213, 225, 200), width=2 * s)
        for extremo in (bx, bx + largo):
            dibujo.line([(extremo, by - 4 * s), (extremo, by + 4 * s)], fill=(203, 213, 225, 200), width=s)
        dibujo.text((bx, by - 16 * s), "20 km", font=_fuente(8 * s), fill=(203, 213, 225, 200))

    mascara = Image.new("L", capa.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, w * s - 1, h * s - 1), 14 * s, fill=255)
    lienzo.paste(capa, (x * s, y * s), mascara)
    ImageDraw.Draw(lienzo).rounded_rectangle(
        (x * s, y * s, (x + w) * s - 1, (y + h) * s - 1), 14 * s, outline=_rgba("#27466f", 220), width=s
    )


def imagen_de_fondo(mapa: dict | None = None, web: dict | None = None, relieve: Path | None = None) -> Image.Image:
    s = ESCALA_IMAGEN
    ancho, alto = (PANEL_X + PANEL_W + 20) * s, (PANEL_Y + PANEL_H + 20) * s
    lienzo = Image.new("RGBA", (ancho, alto), _rgba(PAGINA))

    # Resplandor detrás del panel.
    halo = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(halo)
    dibujo.ellipse((200 * s, 80 * s, 900 * s, 600 * s), fill=_rgba("#1d4ed8", 70))
    dibujo.ellipse((1000 * s, 450 * s, 1600 * s, 950 * s), fill=_rgba("#0e7490", 55))
    lienzo.alpha_composite(halo.filter(ImageFilter.GaussianBlur(120 * s)))

    # El panel: la "tablet" que contiene todo.
    panel = _degradado(PANEL_W * s, PANEL_H * s, "#0b1830", "#070f1f")
    _tarjeta(lienzo, PANEL_X, PANEL_Y, PANEL_W, PANEL_H, radio=30, relleno=panel)

    # Cabecera.
    cx, cy, cw, ch = CABECERA
    _tarjeta(lienzo, cx, cy, cw, ch, radio=16, relleno=_degradado(cw * s, ch * s, "#0f213c", "#0c1a31"))

    for clave, (x, y, w, h) in TARJETAS.items():
        if clave == "heroe":
            relleno = _degradado(w * s, h * s, "#2563eb", "#071a45", diagonal=True)
            # Las curvas van en una hoja transparente: dibujadas directo sobre
            # el degradado, el alfa pisa el píxel y salen blancas.
            hoja_curvas = Image.new("RGBA", relleno.size, (0, 0, 0, 0))
            curvas = ImageDraw.Draw(hoja_curvas)
            for i in range(4):
                curvas.arc(
                    (-w * s * 0.5 + i * 40 * s, h * s * 0.55 + i * 14 * s, w * s * 1.4 + i * 40 * s, h * s * 2.0),
                    200, 320, fill=(190, 225, 255, 40 - i * 8), width=s,
                )
            relleno.alpha_composite(hoja_curvas)
            # Una gota enorme y casi invisible detrás del número: la firma de la tarjeta.
            lado_gota = 150 * s
            relleno.alpha_composite(iconos.marca_de_agua("gota", lado_gota, alfa=26),
                                    (w * s - lado_gota - 70 * s, h * s - lado_gota + 10 * s))
            _tarjeta(lienzo, x, y, w, h, radio=22, relleno=relleno)
        else:
            _tarjeta(lienzo, x, y, w, h)
        marca = MARCAS_DE_AGUA.get(clave)
        if marca:
            nombre_marca, lado_marca, dx, dy = marca
            lienzo.alpha_composite(iconos.marca_de_agua(nombre_marca, lado_marca * s, alfa=18),
                                   ((x + w - lado_marca + dx) * s, (y + h - lado_marca + dy) * s))

    if mapa and web and relieve is not None:
        dibujar_mapa(lienzo, mapa, web, relieve)

    # Recuadro del flujo libre, en la tarjeta de destino.
    dx, dy, dw, dh = TARJETAS["destino"]
    _tarjeta(lienzo, dx + dw - RECUADRO_W - 20, dy + dh - 96, RECUADRO_W, 76, radio=14,
             relleno=_degradado(RECUADRO_W * s, 76 * s, "#16325a", "#10264a"))
    # Pista de la torta del margen, en la tarjeta héroe.
    hx, hy, hw, _ = TARJETAS["heroe"]
    ImageDraw.Draw(lienzo).ellipse(((hx + hw - 104) * s, (hy + 18) * s, (hx + hw - 20) * s, (hy + 102) * s),
                                   outline=(255, 255, 255, 30), width=s)

    # Las pastillas de las listas: el marco va en la imagen y el centro queda
    # hueco para la celda, que se pinta del mismo color.
    for x, y, w, h in CONTROLES.values():
        dibujo = ImageDraw.Draw(lienzo)
        dibujo.rounded_rectangle(
            ((x - MARCO_IZQ) * s, (y - MARCO_VERT) * s, (x + w + MARCO_DER) * s, (y + h + MARCO_VERT) * s),
            (h / 2 + MARCO_VERT) * s, fill=_rgba(CONTROL), outline=_rgba(CONTROL_BORDE), width=s,
        )
        # La flecha: un triángulo dibujado, para no depender de una fuente.
        fx, fy = x + w + MARCO_DER / 2 - 1, y + h / 2
        dibujo.polygon([((fx - 4) * s, (fy - 2) * s), ((fx + 4) * s, (fy - 2) * s), (fx * s, (fy + 3) * s)],
                       fill=_rgba(CIAN))

    return lienzo.convert("RGB")


def _png(imagen: Image.Image) -> io.BytesIO:
    salida = io.BytesIO()
    imagen.save(salida, format="PNG", dpi=(96, 96))
    salida.seek(0)
    return salida


def pedazos_de_fondo(lienzo: Image.Image) -> list[tuple[int, int, Image.Image]]:
    """Corta el fondo en rectángulos que cubren todo menos las celdas de control.

    Se corta en franjas horizontales en los bordes de cada hueco; dentro de
    cada franja, en tramos entre huecos. Cada pedazo se estira un píxel sobre
    el siguiente para que el zoom de Excel no deje ver una costura.
    """
    s = ESCALA_IMAGEN
    ancho, alto = lienzo.width // s, lienzo.height // s
    huecos = sorted(CONTROLES.values())
    cortes_y = sorted({0, alto, *(y for _, y, _, _ in huecos), *(y + h for _, y, _, h in huecos)})
    pedazos = []
    for y0, y1 in zip(cortes_y, cortes_y[1:]):
        en_franja = [(x, w) for x, y, w, h in huecos if y <= y0 and y + h >= y1]
        tramos, cursor = [], 0
        for x, w in sorted(en_franja):
            if x > cursor:
                tramos.append((cursor, x))
            cursor = x + w
        if cursor < ancho:
            tramos.append((cursor, ancho))
        for x0, x1 in tramos:
            caja = (x0 * s, y0 * s, min(x1 + 1, ancho) * s, min(y1 + 1, alto) * s)
            pedazos.append((x0, y0, lienzo.crop(caja)))
    return pedazos


def imagen_de_pastilla(texto: str) -> io.BytesIO:
    """Un botón de navegación: la imagen lleva el vínculo a la hoja."""
    s = ESCALA_IMAGEN
    ancho, alto = 96 * s, 32 * s
    lienzo = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(lienzo)
    dibujo.rounded_rectangle((s, s, ancho - 1 - s, alto - 1 - s), alto // 2,
                             fill=_rgba("#0b1a30"), outline=_rgba("#2b4a74"), width=s)
    fuente = _fuente(12 * s)
    caja = dibujo.textbbox((0, 0), texto, font=fuente)
    dibujo.text(((ancho - (caja[2] - caja[0])) / 2 - caja[0], (alto - (caja[3] - caja[1])) / 2 - caja[1]),
                texto, font=fuente, fill=_rgba("#b9c9e3"))
    return _png(lienzo)


# --------------------------------------------------------------------------- #
# La hoja
# --------------------------------------------------------------------------- #
def fecha_corta(iso: str) -> str:
    """2026-08-11 → 11/08/2026."""
    anio, mes, dia = iso[:10].split("-")
    return f"{dia}/{mes}/{anio}"


def etiqueta_trimestre(periodo: str) -> str:
    """2026Q2 → 2T26, la manera en que se escribe un trimestre en castellano."""
    return f"{periodo[-1]}T{periodo[2:4]}"


def cargar_mercado(procesados: Path) -> dict | None:
    """El estudio de evento de transform/market_reaction.py; None si no está."""
    ruta = procesados / "market_reaction.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def cargar_mapa(procesados: Path) -> tuple[dict | None, dict | None, Path]:
    """Los datos del mapa y la cartografía del sitio; None si falta alguno."""
    datos, web = procesados / "tablero_mapa.json", procesados / "mapa_web.json"
    if not datos.exists() or not web.exists():
        return None, None, procesados / "mapa_relieve.png"
    return (json.loads(datos.read_text(encoding="utf-8")), json.loads(web.read_text(encoding="utf-8")),
            procesados / "mapa_relieve.png")


def escribir_tablero(libro: xlsxwriter.Workbook, hoja, hojas: dict, mapas: dict, analisis: dict,
                     valuacion: dict, segmentos: dict, operativo: dict, trimestres: list[str],
                     anios: list[str], procesados: Path | None = None) -> None:
    ultimo = trimestres[-1]
    nombre = hoja.get_name()
    letra = xlsxwriter.utility.xl_col_to_name
    homologada = [s for s in SEGMENTOS_FILTRO_HOMOLOGADOS
                  if ("ingresos_totales", s, APERTURA_HOMOLOGADA) in segmentos]

    def clave_segmento(concepto: str, segmento: str) -> tuple:
        return (concepto, segmento, APERTURA_HOMOLOGADA) if homologada else (concepto, segmento)

    segmentos_filtro = homologada or [s for s in SEGMENTOS_REPORTADOS if ("ingresos_totales", s) in segmentos]
    datos_mapa, web_mapa, relieve = cargar_mapa(procesados) if procesados else (None, None, Path())
    mercado = cargar_mercado(procesados) if procesados else None

    # --- la hoja como lienzo ------------------------------------------------
    fondo = libro.add_format({"bg_color": PAGINA})
    hoja.set_column_pixels(0, ULTIMA_COLUMNA, CELDA, fondo)
    hoja.set_default_row(15)
    hoja.hide_gridlines(2)
    hoja.hide_row_col_headers()
    hoja.set_tab_color(CIAN)
    hoja.set_zoom(90)
    # Impreso o exportado a PDF, el tablero entra en una página apaisada.
    hoja.set_landscape()
    hoja.set_paper(9)
    hoja.set_margins(0.2, 0.2, 0.2, 0.2)
    hoja.print_area(0, 0, (PANEL_Y + PANEL_H + 20) // CELDA, (PANEL_X + PANEL_W + 20) // CELDA)
    hoja.fit_to_pages(1, 1)

    def lugar(x: float, y: float) -> dict:
        return {"x_offset": int(x), "y_offset": int(y), "object_position": 3}

    for i, (x, y, pedazo) in enumerate(pedazos_de_fondo(imagen_de_fondo(datos_mapa, web_mapa, relieve))):
        hoja.insert_image(0, 0, f"fondo_{i}.png", {
            "image_data": _png(pedazo), "x_scale": 1 / ESCALA_IMAGEN, "y_scale": 1 / ESCALA_IMAGEN,
            **lugar(x, y), "decorative": True,
        })

    # --- formatos del bloque de datos ---------------------------------------
    base = {"font_name": FUENTE, "font_size": 9, "bg_color": PAGINA, "valign": "vcenter"}
    f_titulo = libro.add_format({**base, "font_size": 14, "bold": True, "font_color": TEXTO})
    f_nota = libro.add_format({**base, "font_color": TEXTO_TENUE})
    f_seccion = libro.add_format({**base, "bold": True, "font_color": CIAN, "bottom": 1, "bottom_color": GRILLA})
    f_encabezado = libro.add_format({**base, "bold": True, "font_color": TEXTO_SUAVE, "align": "right",
                                     "bottom": 1, "bottom_color": GRILLA})
    f_etiqueta = libro.add_format({**base, "font_color": TEXTO_SUAVE, "indent": 1})
    f_millones = libro.add_format({**base, "font_color": TEXTO, "align": "right",
                                   "num_format": '"US$ "#,##0,,"M";"−US$ "#,##0,,"M";"–"'})
    f_millones_vacio = libro.add_format({**base, "font_color": TEXTO, "align": "right",
                                         "num_format": '"US$ "#,##0,,"M";"−US$ "#,##0,,"M";""'})
    f_porcentaje = libro.add_format({**base, "font_color": TEXTO, "align": "right", "num_format": '0%;−0%;"0%"'})
    f_porcentaje_decimal = libro.add_format({**base, "font_color": TEXTO, "align": "right",
                                             "num_format": '0.0%;−0.0%;"–"'})
    f_variacion = libro.add_format({**base, "font_color": TEXTO, "align": "right",
                                    "num_format": '"▲ "0.0%;"▼ "0.0%;"–"'})
    # Una concesión que arranca de casi cero crece 3.000%: el número no dice
    # nada y rompe la columna.
    f_variacion_corta = libro.add_format({**base, "font_color": TEXTO, "align": "right",
                                          "num_format": '[>=10]"▲ >999%";[<0]"▼ "0.0%;"▲ "0.0%'})
    f_multiplo = libro.add_format({**base, "font_color": TEXTO, "align": "right", "num_format": '0.0"x";−0.0"x";"–"'})
    f_numero = libro.add_format({**base, "font_color": TEXTO, "align": "right", "num_format": "0.00"})
    # Una porción de 0,4% no es "0%": es chica, y se dice.
    f_porcentaje_chico = libro.add_format({**base, "font_color": TEXTO, "align": "right",
                                           "num_format": '[<0.005]"<1%";0%'})
    f_entero = libro.add_format({**base, "font_color": TEXTO, "align": "right", "num_format": '#,##0;−#,##0;"–"'})
    f_decimal = libro.add_format({**base, "font_color": TEXTO, "align": "right", "num_format": '#,##0.0;−#,##0.0;""'})
    f_miles = libro.add_format({**base, "font_color": TEXTO, "align": "right", "num_format": '#,##0.0,"k";;"–"'})
    f_texto = libro.add_format({**base, "font_color": TEXTO, "align": "right"})
    f_texto_izq = libro.add_format({**base, "font_color": TEXTO})
    f_control = libro.add_format({
        "font_name": FUENTE, "font_size": 9, "bold": True, "font_color": CIAN, "bg_color": CONTROL,
        "align": "center", "valign": "vcenter", "locked": False,
    })

    fila = DATOS_FILA
    hoja.write(fila, 1, "Datos del tablero", f_titulo)
    fila += 1
    hoja.write(
        fila, 1,
        "Todo lo que muestra el tablero sale de estas celdas. Son fórmulas INDEX contra las hojas de estados, "
        "Análisis, Segmentos y Valuación, desplazadas según el trimestre elegido arriba. No hay números escritos a mano.",
        f_nota,
    )
    fila += 2

    def rango(fila_celda: int, columna: tuple[int, int], valor, formato) -> None:
        primera, ultima = columna
        es_formula = isinstance(valor, str) and valor.startswith("=")
        hoja.merge_range(fila_celda, primera, fila_celda, ultima, "" if es_formula else valor, formato)
        if es_formula:
            hoja.write_formula(fila_celda, primera, valor, formato, "")

    def bloque(titulo: str, encabezados: list[str]) -> None:
        nonlocal fila
        rango(fila, (DATOS_ETIQUETA[0], DATOS_VALORES[max(len(encabezados), 1) - 1][1]), titulo, f_seccion)
        fila += 1
        rango(fila, DATOS_ETIQUETA, "", f_encabezado)
        for i, encabezado in enumerate(encabezados):
            rango(fila, DATOS_VALORES[i], encabezado, f_encabezado)
        fila += 1

    def renglon(etiqueta: str, valores: list[tuple[str | None, object]]) -> int:
        """Una fila del bloque. La etiqueta puede ser una fórmula."""
        nonlocal fila
        rango(fila, DATOS_ETIQUETA, etiqueta, f_etiqueta)
        for i, (valor, formato) in enumerate(valores):
            rango(fila, DATOS_VALORES[i], "" if valor is None else valor, formato)
        fila += 1
        return fila - 1

    def local(fila_celda: int, indice_valor: int | None = None) -> str:
        """Referencia absoluta a una celda del bloque; None es la columna de etiqueta."""
        columna = DATOS_ETIQUETA[0] if indice_valor is None else DATOS_VALORES[indice_valor][0]
        return f"${letra(columna)}${fila_celda + 1}"

    def vinculo(fila_celda: int, indice_valor: int | None = 0) -> str:
        return f"='{nombre}'!{local(fila_celda, indice_valor)}"

    def serie(primera_fila: int, ultima_fila: int, indice_valor: int) -> list:
        columna = DATOS_VALORES[indice_valor][0]
        return [nombre, primera_fila, columna, ultima_fila, columna]

    def categorias(primera_fila: int, ultima_fila: int) -> list:
        return [nombre, primera_fila, DATOS_ETIQUETA[0], ultima_fila, DATOS_ETIQUETA[0]]

    # --- celdas de control --------------------------------------------------
    def control(clave: str, valor: str) -> str:
        x, y, w, _ = CONTROLES[clave]
        fila_c, columna = y // CELDA, x // CELDA
        ultima = columna + w // CELDA - 1
        hoja.merge_range(fila_c, columna, fila_c, ultima, valor, f_control)
        return f"${letra(columna)}${fila_c + 1}"

    SEL = control("trimestre", etiqueta_trimestre(ultimo))
    SEG = control("segmento", "Consolidado")
    MET = control("metrica", METRICAS[0])
    COMP = control("comparar", COMPARACIONES[0])
    # La dimensión del territorio: su tarjeta está más abajo, pero el texto que
    # la nombra se arma acá, con el resto.
    DIMENSION = control("dimension", "Cuenca")

    # --- 1. listas ----------------------------------------------------------
    # Con la misma etiqueta que la celda de control: la selección se busca por
    # "2T26", y una lista que ofreciera "2026Q2" dejaría todo en #N/D.
    disponibles = [etiqueta_trimestre(p) for p in reversed(trimestres[HISTORIA - 1:])]
    opciones_segmento = ["Consolidado", *segmentos_filtro]
    alto_listas = max(len(trimestres), len(METRICAS))
    bloque("Listas", ["Período", "Trimestres a elegir", "Métricas", "Segmentos", "Comparación"])
    listas_inicio = fila
    for i in range(alto_listas):
        def item(lista: list[str]):
            return (lista[i] if i < len(lista) else None, f_texto)
        renglon(etiqueta_trimestre(trimestres[i]) if i < len(trimestres) else "", [
            item(trimestres), item(disponibles), item(METRICAS), item(opciones_segmento), item(COMPARACIONES),
        ])
    fila += 1

    def lista(indice_valor: int | None, largo: int) -> str:
        columna = letra(DATOS_ETIQUETA[0] if indice_valor is None else DATOS_VALORES[indice_valor][0])
        return f"${columna}${listas_inicio + 1}:${columna}${listas_inicio + largo}"

    L_ETIQUETAS, L_CODIGOS = lista(None, len(trimestres)), lista(0, len(trimestres))
    L_METRICAS, L_SEGMENTOS = lista(2, len(METRICAS)), lista(3, len(opciones_segmento))

    for celda_control, fuente, titulo in [
        (SEL, lista(1, len(disponibles)), "Trimestre"),
        (SEG, L_SEGMENTOS, "Segmento"),
        (MET, L_METRICAS, "Métrica"),
        (COMP, lista(4, len(COMPARACIONES)), "Comparar contra"),
    ]:
        hoja.data_validation(celda_control.replace("$", ""), {
            "validate": "list", "source": f"={fuente}",
            "input_title": titulo, "input_message": "Elegí de la lista",
            "error_title": titulo, "error_message": "El valor tiene que salir de la lista.",
        })

    # --- 2. selección -------------------------------------------------------
    bloque("Selección", ["Valor"])
    sel = {}

    def derivado(clave: str, etiqueta: str, formula: str, formato=f_texto) -> str:
        sel[clave] = local(renglon(etiqueta, [(formula, formato)]), 0)
        return sel[clave]

    POS = derivado("pos", "Posición del trimestre elegido", f"=MATCH({SEL},{L_ETIQUETAS},0)")
    CODIGO = derivado("codigo", "Código", f"=INDEX({L_CODIGOS},{POS})")
    # La columna del trimestre en las hojas de estados: todas comparten columnas.
    K = derivado("k", "Columna en las hojas de estados",
                 f"=MATCH({CODIGO},'{hojas['resultados']}'!$4:$4,0)")
    D = derivado("d", "Trimestres hacia atrás de la comparación", f'=IF({COMP}="{COMPARACIONES[1]}",1,4)')
    CMP = derivado("cmp", "Trimestre de comparación", f"=INDEX({L_ETIQUETAS},{POS}-{D})")
    N_TRIM = derivado("n", "Trimestre del año", f"=VALUE(RIGHT({CODIGO},1))")
    ANIO = derivado("anio", "Año", f"=VALUE(LEFT({CODIGO},4))")
    SEGI = derivado("segi", "Segmento (1 = consolidado)", f"=MATCH({SEG},{L_SEGMENTOS},0)")
    METI = derivado("meti", "Métrica", f"=MATCH({MET},{L_METRICAS},0)")
    TRAMO = derivado("tramo", "Acumulado del año",
                     f'=CHOOSE({N_TRIM},"1T","1S","9M","FY")&RIGHT({ANIO},2)')
    TRAMO_PREVIO = derivado("tramo_previo", "Acumulado del año anterior",
                            f'=CHOOSE({N_TRIM},"1T","1S","9M","FY")&RIGHT({ANIO}-1,2)')
    FY_ULTIMO = derivado("fy", "Último ejercicio cerrado", f"={ANIO}-IF({N_TRIM}=4,0,1)")
    SUFIJO = derivado("sufijo", "Sufijo de segmento", f'=IF({SEGI}>1," · "&{SEG},"")')
    textos = {
        "cabecera": f'="Trimestre "&{SEL}&" · "&{SEG}',
        "heroe": f'=IF({SEGI}=1,"EBITDA ajustado · ","EBITDA · ")&{SEL}&{SUFIJO}',
        "heroe_cmp": f'="EBITDA contra "&{CMP}',
        "heroe_contable": f'=IF({SEGI}=1,"De los estados (res. operativo + D&A)","")',
        "aviso_ebitda": f'=IF({SEGI}>1,"● Sin ajustes: resultado operativo + depreciación","")',
        "aviso_operativo": f'=IF({SEGI}>1,"● Solo consolidado","")',
        "mapa": f'="Shale operado por YPF · "&{SEL}&" contra "&{CMP}&" · boe/d, bruto"',
        "operativo_sub": f'="Producción y precio del crudo, doce trimestres hasta "&{SEL}',
        "comparacion": f'="contra "&{CMP}',
        "capex_serie": f'=IF({SEGI}>1,"Capex devengado del segmento","")',
        # Las tarjetas de análisis (export/tablero_analisis.py).
        "puente_sub": f'="De "&{CMP}&" a "&{SEL}&": de dónde salió la variación, en millones de US$"',
        "simulador_sub": '="Modelo estimado sobre quince trimestres · R² 0,91 · no es una proyección de la compañía"',
        "deuda_sub": '="Instrumentos vigentes al último balance, en millones de US$"',
        "comparables_sub": '="Mismo cálculo para los tres · Vista y Pampa también presentan 20-F"',
        "territorio_sub": f'={DIMENSION}&" · "&{SEL}&" · boe/d promedio del trimestre, bruto operado"',
        # Por segmento el EBITDA no es el ajustado: el título lo dice.
        "serie": f'=IF({SEGI}>1,SUBSTITUTE({MET},"ajustado","del segmento"),{MET})&{SUFIJO}'
                 f'&" · doce trimestres hasta "&{SEL}&", en millones de US$"',
        "radar": f'={SEL}&" contra "&{CMP}&", sobre ingresos"',
        "radar_sel": f'="■ "&{SEL}',
        "radar_cmp": f'="■ "&{CMP}',
        "semestre": f'={TRAMO}&" contra "&{TRAMO_PREVIO}',
        "semestre_sub": f'="Lo que va del año"&{SUFIJO}&"; la barra llena es el doble"',
        "destino": f'={SEL}&", en millones de US$"',
        "capex": f'={SEL}&": capex devengado por negocio, en millones de US$"',
        "lineas": f'="Doce trimestres hasta "&{SEL}&{SUFIJO}',
        "ejercicios": f'=IF({SEGI}=1,"EBITDA ajustado contra capex pagado","EBITDA contra capex devengado")&{SUFIJO}',
        "aviso": f'=IF({SEGI}>1,"● Solo consolidado","")',
        "aviso_serie": f'=IF(AND({SEGI}>1,{METI}>4),"● "&{MET}&" solo existe consolidado","")',
        "aviso_flujo":f'=IF({SEGI}>1,"● El flujo operativo no se abre por segmento","")',
    }
    for clave, formula in textos.items():
        derivado(clave, f"Texto: {clave}", formula, f_texto_izq)
    fila += 1

    # --- referencias dinámicas ----------------------------------------------
    def fila_de(hoja_nombre: str, fila_hoja: int) -> str:
        return f"'{hoja_nombre}'!${fila_hoja + 1}:${fila_hoja + 1}"

    def en(hoja_nombre: str, fila_hoja: int, atras="0", columna: str | None = None, numero: bool = True) -> str:
        """El valor de una línea en el trimestre elegido menos `atras` trimestres."""
        indice = columna if columna else (K if str(atras) == "0" else f"{K}-{atras}")
        expresion = f"INDEX({fila_de(hoja_nombre, fila_hoja)},{indice})"
        return f"N({expresion})" if numero else expresion

    R = lambda clave, atras="0", columna=None: en(hojas["resultados"], mapas["resultados"][clave], atras, columna)  # noqa: E731
    F = lambda clave, atras="0", columna=None: en(hojas["flujo"], mapas["flujo"][clave], atras, columna)  # noqa: E731
    A = lambda clave, atras="0", columna=None: en("Análisis", analisis[clave], atras, columna)  # noqa: E731

    cfo = "net cash flows from operating activities"
    capex = "acquisition of property plant and equipment and intangible assets | net cash flows used in investing activities"

    clave_ebitda = "ebitda_ajustado" if analisis.get("ebitda_ajustado") is not None else "ebitda"

    def variacion(actual: str, base: str) -> str:
        """Contra el valor absoluto de la base: de −637 a 265 es una suba, no una caída de 142%."""
        return f'IFERROR(IF(N({base})=0,"",({actual}-{base})/ABS({base})),"")'

    def consolidado(metrica: str, atras="0", columna=None) -> str:
        return {
            "Ingresos": R("revenues", atras, columna),
            EBITDA: A(clave_ebitda, atras, columna),
            "Resultado operativo": R("operating profit", atras, columna),
            "Capex": f"(-{F(capex, atras, columna)})",
            "Flujo operativo": F(cfo, atras, columna),
            "Flujo de caja libre": A("fcf", atras, columna),
            "Resultado neto": R("net profit", atras, columna),
        }[metrica]

    def de_segmento(metrica: str, segmento: str, atras="0", columna=None) -> str | None:
        def S(concepto: str) -> str:
            if clave_segmento(concepto, segmento) not in segmentos:
                return "0"
            return en("Segmentos", segmentos[clave_segmento(concepto, segmento)], atras, columna)
        return {
            "Ingresos": S("ingresos_totales"),
            # EBITDA de segmento: resultado operativo más depreciación de bienes
            # de uso, que es lo que abre la nota de segmentos.
            EBITDA: f"({S('resultado_operativo')}+{S('depreciacion_ppe')})",
            "Resultado operativo": S("resultado_operativo"),
            "Capex": S("capex_ppe"),
        }.get(metrica)

    def filtrado(metrica: str, atras="0", columna=None, sin_dato: str = "NA()", base: str | None = None) -> str:
        """La métrica del segmento elegido; lo que no se abre por segmento queda sin dato."""
        base_consolidada = base if base is not None else consolidado(metrica, atras, columna)
        if not segmentos_filtro or de_segmento(metrica, segmentos_filtro[0]) is None:
            return f"IF({SEGI}=1,{base_consolidada},{sin_dato})"
        ramas = ",".join(de_segmento(metrica, s, atras, columna) for s in segmentos_filtro)
        return f"IF({SEGI}=1,{base_consolidada},CHOOSE({SEGI}-1,{ramas}))"

    # --- 3. indicadores -----------------------------------------------------
    bloque("Indicadores del trimestre elegido", ["Valor"])
    ind = {}
    ind["ebitda"] = renglon(EBITDA, [(f"={filtrado(EBITDA)}", f_millones)])
    ind["ebitda_contable"] = renglon("EBITDA de los estados (consolidado)", [
        (f'=IF({SEGI}=1,{A("ebitda")},"")', f_millones_vacio)
    ])
    ind["ingresos"] = renglon("Ingresos", [(f"={filtrado('Ingresos')}", f_millones)])
    sel["aviso_segmento"] = local(renglon("Texto: aviso_segmento", [(
        f'=IF(AND({SEGI}>1,{local(ind["ingresos"], 0)}=0),"● "&{SEG}&" no se reportaba en "&{SEL},'
        f'{sel["aviso_ebitda"]})',
        f_texto_izq,
    )]), 0)
    ind["margen"] = renglon("Margen EBITDA", [(f"=IFERROR({local(ind['ebitda'], 0)}/{local(ind['ingresos'], 0)},0)", f_porcentaje)])
    ind["margen_resto"] = renglon("Resto hasta 100% (para la torta)",
                                  [(f"=MAX(0,1-MAX(0,{local(ind['margen'], 0)}))", f_porcentaje)])
    ind["ebitda_cmp"] = renglon("EBITDA contra la comparación",
                                [(f"={variacion(local(ind['ebitda'], 0), filtrado(EBITDA, D))}", f_variacion)])
    ind["deuda_ebitda"] = renglon("Deuda neta / EBITDA UDM",
                                  [(f"=IFERROR({en('Análisis', analisis['deuda_ebitda'], numero=False)}*1,\"\")", f_multiplo)])
    if valuacion.get("ev_ebitda"):
        ind["ev_ebitda"] = renglon("EV / EBITDA UDM", [
            (f"=IFERROR({en('Valuación', valuacion['ev_ebitda'], numero=False)}*1,\"\")", f_multiplo)
        ])
    fila += 1

    # --- 4. serie trimestral ------------------------------------------------
    columnas_serie = METRICAS
    bloque("Serie trimestral", [*columnas_serie, "Métrica elegida"])
    serie_inicio = fila
    for atras in range(HISTORIA - 1, -1, -1):
        valores = [(f"={filtrado(m, atras)}", f_millones) for m in columnas_serie]
        eleccion = ",".join(local(fila, i) for i in range(len(columnas_serie)))
        valores.append((f"=CHOOSE({METI},{eleccion})", f_millones))
        renglon(f"=INDEX({L_ETIQUETAS},{POS}-{atras})", valores)
    serie_fin = fila - 1
    col_ebitda, col_cfo, col_metrica = 1, 4, len(columnas_serie)
    udm = renglon("Métrica elegida, últimos doce meses", [
        (f"=IFERROR(SUM({local(serie_fin - 3, col_metrica)}:{local(serie_fin, col_metrica)}),\"\")", f_millones)
    ])
    fila += 1

    # --- 5. márgenes (consolidados) -----------------------------------------
    # El radar no dibuja negativos: el eje empieza en cero y un margen de −11%
    # deforma la figura. Se grafica el piso en cero y se avisa.
    bloque("Márgenes consolidados", [f"={SEL}", f"={CMP}", "Gráfico: elegido", "Gráfico: comparación"])
    encabezado_margenes = fila - 1
    margenes_inicio = fila
    for etiqueta, numerador in [
        ("Bruto", lambda a: R("gross profit", a)),
        ("Operativo", lambda a: R("operating profit", a)),
        ("EBITDA", lambda a: consolidado(EBITDA, a)),
        ("Neto", lambda a: R("net profit", a)),
        ("Flujo operativo", lambda a: F(cfo, a)),
    ]:
        renglon(etiqueta, [
            (f"=IFERROR({numerador('0')}/{R('revenues')},\"\")", f_porcentaje_decimal),
            (f"=IFERROR({numerador(D)}/{R('revenues', D)},\"\")", f_porcentaje_decimal),
            (f"=IFERROR(MAX(0,{local(fila, 0)}),0)", f_porcentaje_decimal),
            (f"=IFERROR(MAX(0,{local(fila, 1)}),0)", f_porcentaje_decimal),
        ])
    margenes_fin = fila - 1
    negativos = f"MIN({local(margenes_inicio, 0)}:{local(margenes_fin, 1)})<0"
    sel["aviso_radar"] = local(renglon("Texto: aviso_radar", [(
        f'=IF({SEGI}>1,"● Solo consolidado",IF({negativos},"● Los márgenes negativos se dibujan en cero",""))',
        f_texto_izq,
    )]), 0)
    fila += 1

    # --- 6. lo que va del año -----------------------------------------------
    bloque("Acumulado del año contra el anterior", [f"={TRAMO}", f"={TRAMO_PREVIO}", "Variación", "Barra", "Pista"])
    semestre_inicio = fila
    semestre_metricas = ["Ingresos", EBITDA, "Flujo operativo", "Capex"]
    for metrica in semestre_metricas:
        # Suma los trimestres del año hasta el elegido: el término t entra solo
        # si el trimestre elegido es al menos el t+1 del año.
        actual = "+".join(f"IF({N_TRIM}>{t},{filtrado(metrica, t, sin_dato='0')},0)" for t in range(4))
        previo = "+".join(f"IF({N_TRIM}>{t},{filtrado(metrica, t + 4, sin_dato='0')},0)" for t in range(4))
        disponible = "TRUE" if de_segmento(metrica, "Upstream") is not None else f"{SEGI}=1"
        ahora, antes = local(fila, 0), local(fila, 1)
        # La barra es el acumulado sobre el del año anterior, con tope. Con un
        # año anterior negativo el cociente no significa nada: llena si mejoró.
        barra = f"IF({antes}>0,MIN(MAX({ahora}/{antes},0),{TOPE}),IF({ahora}>{antes},{TOPE},0))"
        renglon(metrica, [
            (f'=IF({disponible},{actual},"")', f_millones),
            (f'=IF({disponible},{previo},"")', f_millones),
            (f"={variacion(ahora, antes)}", f_variacion),
            (f"=IFERROR({barra},0)", f_numero),
            (f"={TOPE}-{local(fila, 3)}", f_numero),
        ])
    semestre_fin = fila - 1
    fila += 1

    # --- 7. destino de los ingresos (consolidado) ---------------------------
    # Las porciones son lo que se lleva cada partida y la parte es sobre los
    # ingresos. Con pérdida operativa los gastos superan a los ingresos: la
    # torta muestra en qué se fueron y la columna "Mostrado" dice la pérdida.
    bloque("Destino de los ingresos (consolidado)", ["Porción", "Sobre ingresos", "Mostrado"])
    destino_inicio = fila
    gastos = [
        ("Costos de producción", "costs"),
        ("Comercialización", "selling expenses"),
        ("Administración", "administrative expenses"),
        ("Exploración", "exploration expenses"),
    ]
    ingresos_trimestre = R("revenues")
    resultado_operativo = R("operating profit")
    for etiqueta, clave in gastos:
        renglon(etiqueta, [(f"=MAX(0,-{R(clave)})", f_millones),
                           (f"=IFERROR({local(fila, 0)}/{ingresos_trimestre},0)", f_porcentaje_chico),
                           (f"={local(fila, 0)}", f_millones)])
    # "Otros" es lo que queda entre ingresos, gastos y resultado operativo:
    # otros resultados operativos y deterioros. Va contra el resultado sin
    # recortar, así una pérdida por deterioro aparece acá y no desaparece.
    suma_gastos = "+".join(local(destino_inicio + i, 0) for i in range(len(gastos)))
    renglon("Otros y deterioros", [
        (f"=MAX(0,{ingresos_trimestre}-({suma_gastos})-{resultado_operativo})", f_millones),
        (f"=IFERROR({local(fila, 0)}/{ingresos_trimestre},0)", f_porcentaje_chico),
        (f"={local(fila, 0)}", f_millones),
    ])
    renglon("Resultado operativo", [
        (f"=MAX(0,{resultado_operativo})", f_millones),
        (f"=IFERROR({resultado_operativo}/{ingresos_trimestre},0)", f_porcentaje),
        (f"={resultado_operativo}", f_millones),
    ])
    destino_fin = fila - 1
    total_destino = renglon("Ingresos", [(f"={ingresos_trimestre}", f_millones), (None, f_texto), (None, f_texto)])
    sel["aviso_destino"] = local(renglon("Texto: aviso_destino", [(
        f'=IF({SEGI}>1,"● Solo consolidado",IF({resultado_operativo}<0,"● Pérdida operativa: los gastos superaron a los ingresos",""))',
        f_texto_izq,
    )]), 0)
    fila += 1

    # --- 8. caja (consolidada) ----------------------------------------------
    bloque("Caja del trimestre (consolidada)", ["Monto", "Barra", "Pista", "Sobre flujo"])
    caja_inicio = fila
    renglon("Flujo operativo", [(f"={F(cfo)}", f_millones),
                                (f"=IF({local(fila, 0)}>0,1,0)", f_porcentaje),
                                (f"=1-{local(fila, 1)}", f_porcentaje),
                                (None, f_texto)])
    renglon("Capex pagado", [(f"=-{F(capex)}", f_millones),
                             (f"=IFERROR(MAX(0,MIN({local(fila, 0)}/{local(caja_inicio, 0)},1)),0)", f_porcentaje),
                             (f"=1-{local(fila, 1)}", f_porcentaje),
                             (f'=IFERROR(IF({local(caja_inicio, 0)}>0,{local(fila, 0)}/{local(caja_inicio, 0)},""),"")',
                              f_porcentaje)])
    caja_fin = fila - 1
    libre = renglon("Flujo de caja libre (operativo − capex pagado)",
                    [(f"={A('fcf')}", f_millones), (None, f_texto), (None, f_texto), (None, f_texto)])
    reinversion_texto = renglon("Texto: reinversión", [(
        f'=IF({local(caja_fin, 3)}="","",TEXT({local(caja_fin, 3)},"0%")&" del flujo")', f_texto_izq,
    )])
    sel["aviso_caja"] = local(renglon("Texto: aviso_caja", [(
        f'=IF({SEGI}>1,"● Solo consolidado",IF(OR({local(caja_inicio, 0)}<=0,N({local(caja_fin, 3)})>1),'
        f'"● El capex superó al flujo operativo",""))',
        f_texto_izq,
    )]), 0)
    publicado = {}
    for clave, etiqueta in [("capex_publicado", "Capex publicado por YPF"), ("fcf_publicado", "Flujo libre publicado por YPF")]:
        if analisis.get(clave) is not None:
            publicado[clave] = renglon(etiqueta, [
                (f'=IFERROR({en("Análisis", analisis[clave], numero=False)}*1,"")', f_millones_vacio)
            ])
    fila += 1

    # --- 9. capex por segmento ----------------------------------------------
    segmentos_capex = [s for s in SEGMENTOS_CAPEX if ("capex_ppe", s) in segmentos]
    capex_inicio = capex_fin = total_capex = None
    if segmentos_capex:
        # Primero todos los segmentos; después los cinco mayores del trimestre,
        # ordenados. La apertura cambia con los años y la torta tiene que
        # mostrar los que existían en el trimestre elegido, no una lista fija.
        bloque("Capex por segmento", ["Monto", "Para ordenar"])
        crudo_inicio = fila
        # Donde la apertura reportada no existe (el 4T22) entra la homologada,
        # que solo suma si la reportada da cero: nunca cuentan las dos.
        homologados_capex = [s for s in (*SEGMENTOS_FILTRO_HOMOLOGADOS, "Administración central y otros")
                             if ("capex_ppe", s, APERTURA_HOMOLOGADA) in segmentos]
        total_filas = len(segmentos_capex) + len(homologados_capex)
        reportada = f"{local(crudo_inicio, 0)}:{local(crudo_inicio + len(segmentos_capex) - 1, 0)}"
        for i, segmento in enumerate(segmentos_capex):
            # El desempate por posición evita que dos segmentos con el mismo
            # monto (dos ceros) devuelvan el mismo nombre.
            renglon(segmento, [
                (f"=MAX(0,{en('Segmentos', segmentos[('capex_ppe', segmento)])})", f_millones),
                (f"={local(fila, 0)}+{total_filas - i}/1000", f_numero),
            ])
        for j, segmento in enumerate(homologados_capex):
            referencia = en("Segmentos", segmentos[("capex_ppe", segmento, APERTURA_HOMOLOGADA)])
            renglon(segmento, [
                (f"=IF(SUM({reportada})=0,MAX(0,{referencia}),0)", f_millones),
                (f"={local(fila, 0)}+{total_filas - len(segmentos_capex) - j}/1000", f_numero),
            ])
        crudo_fin = fila - 1
        sel["aviso_capex"] = local(renglon("Texto: aviso_capex", [(
            f'=IF(AND(SUM({reportada})=0,SUM({local(crudo_inicio, 0)}:{local(crudo_fin, 0)})>0),'
            f'"● Sin apertura reportada: se muestra la homologada","")',
            f_texto_izq,
        )]), 0)
        montos = f"{local(crudo_inicio, 0)}:{local(crudo_fin, 0)}"
        orden = f"{local(crudo_inicio, 1)}:{local(crudo_fin, 1)}"
        nombres = f"{local(crudo_inicio, None)}:{local(crudo_fin, None)}"
        fila += 1

        bloque("Capex por segmento, ordenado", ["Monto", "Parte", "Segmento", "Viñeta", "Texto parte"])
        capex_inicio = fila
        total_capex_fila = capex_inicio + PORCIONES_CAPEX + 1

        def leyenda(nombre_formula: str) -> list:
            # Una fila sin monto no se muestra en la leyenda: ni nombre, ni
            # viñeta, ni un "0%".
            con_monto = f"{local(fila, 0)}>0"
            return [
                (f"=IFERROR({local(fila, 0)}/{local(total_capex_fila, 0)},0)", f_porcentaje_chico),
                (f"=IF({con_monto},{nombre_formula},\"\")", f_texto_izq),
                (f"=IF({con_monto},\"●\",\"\")", f_texto),
                (f"=IF({con_monto},{local(fila, 1)},\"\")", f_porcentaje_chico),
            ]

        for k in range(1, PORCIONES_CAPEX + 1):
            posicion = f"MATCH(LARGE({orden},{k}),{orden},0)"
            renglon(f"=INDEX({nombres},{posicion})",
                    [(f"=INDEX({montos},{posicion})", f_millones_vacio), *leyenda(local(fila, None))])
        renglon("Resto", [
            (f"=MAX(0,SUM({montos})-SUM({local(capex_inicio, 0)}:{local(fila - 1, 0)}))", f_millones_vacio),
            *leyenda('"Resto"'),
        ])
        capex_fin = fila - 1
        total_capex = renglon("Total", [(f"=SUM({montos})", f_millones)])
        fila += 1

    # --- 10. ejercicios -----------------------------------------------------
    # El EBITDA ajustado se publica por trimestre: el del ejercicio es la suma
    # de sus cuatro. Los segmentos y el capex sí tienen columna anual.
    bloque("Ejercicios", ["EBITDA", "Capex", "Columna"])
    ejercicios_inicio = fila
    encabezado_estados = f"'{hojas['resultados']}'!$4:$4"
    for atras in (2, 1, 0):
        etiqueta = f'="FY"&RIGHT({FY_ULTIMO}-{atras},2)'
        columna_fy = local(fila, 2)
        suma_trimestres = "+".join(
            consolidado(EBITDA, columna=f'MATCH(({FY_ULTIMO}-{atras})&"Q{q}",{encabezado_estados},0)')
            for q in range(1, 5)
        )
        renglon(etiqueta, [
            (f"=IFERROR({filtrado(EBITDA, columna=columna_fy, sin_dato='0', base=suma_trimestres)},0)", f_millones),
            (f"=IFERROR({filtrado('Capex', columna=columna_fy, sin_dato='0')},0)", f_millones),
            (f"=IFERROR(MATCH({local(fila, None)},{encabezado_estados},0),1)", f_texto),
        ])
    ejercicios_fin = fila - 1
    fila += 1

    # --- 11. operativo (consolidado, del release) ---------------------------
    kpi = (operativo or {}).get("kpi", {})
    O = lambda campo, atras="0": en("Operativo", kpi[campo], atras, numero=False)  # noqa: E731
    tarjetas_operativo = [
        ("produccion_kboed", "Producción", "kboe/d", f_decimal),
        ("shale_oil_kbbld", "Petróleo shale", "kbbl/d", f_decimal),
        ("precio_crudo_usd_bbl", "Precio del crudo", "US$/bbl", f_decimal),
        ("lifting_cost_usd_boe", "Lifting cost", "US$/boe", f_decimal),
    ]
    tarjetas_operativo = [t for t in tarjetas_operativo if t[0] in kpi]
    operativo_inicio = operativo_serie_inicio = operativo_serie_fin = None
    if tarjetas_operativo:
        bloque("Operativo (release, consolidado)", [f"={SEL}", f"={CMP}", "Variación"])
        operativo_inicio = fila
        for campo, etiqueta, _, formato in tarjetas_operativo:
            actual, base_cmp = local(fila, 0), local(fila, 1)
            renglon(etiqueta, [
                (f'=IFERROR(IF(ISNUMBER({O(campo)}),{O(campo)},""),"")', formato),
                (f'=IFERROR(IF(ISNUMBER({O(campo, D)}),{O(campo, D)},""),"")', formato),
                (f'=IF(OR({actual}="",{base_cmp}=""),"",{variacion(actual, base_cmp)})', f_variacion),
            ])
        fila += 1

        series_operativo = [c for c in ("produccion_kboed", "shale_oil_kbbld", "precio_crudo_usd_bbl") if c in kpi]
        bloque("Operativo, doce trimestres", [dict((t[0], t[1]) for t in tarjetas_operativo)[c] for c in series_operativo])
        operativo_serie_inicio = fila
        for atras in range(HISTORIA - 1, -1, -1):
            renglon(f"=INDEX({L_ETIQUETAS},{POS}-{atras})", [
                (f'=IFERROR(IF(ISNUMBER({O(c, atras)}),{O(c, atras)},NA()),NA())', f_decimal) for c in series_operativo
            ])
        operativo_serie_fin = fila - 1
        fila += 1

    # --- 12. mapa -----------------------------------------------------------
    mapa_inicio = None
    if datos_mapa and datos_mapa.get("concesiones"):
        concesiones = datos_mapa["concesiones"]
        # Una fila por trimestre y una columna por concesión, con el total al
        # final: son los números de transform/tablero_mapa.py tal cual.
        columnas_mapa = [c["nombre"] for c in concesiones] + ["Total shale operado"]
        bloque("Mapa: boe/d por concesión (transform/tablero_mapa.py)", columnas_mapa)
        tabla_inicio = fila
        for i, periodo in enumerate(datos_mapa["trimestres"]):
            renglon(etiqueta_trimestre(periodo), [
                *((c["boed"][i], f_entero) for c in concesiones),
                (datos_mapa["total_boed"][i], f_entero),
            ])
        tabla_fin = fila - 1
        fila += 1

        def en_tabla(indice_columna: int, trimestre: str) -> str:
            columna = letra(DATOS_VALORES[indice_columna][0])
            etiquetas = f"{local(tabla_inicio, None)}:{local(tabla_fin, None)}"
            return (f"IFERROR(INDEX(${columna}${tabla_inicio + 1}:${columna}${tabla_fin + 1},"
                    f"MATCH({trimestre},{etiquetas},0)),\"\")")

        n = len(concesiones)
        ultima_valor = letra(DATOS_VALORES[n - 1][0])
        maximo = f"MAX({local(tabla_inicio, 0)}:${ultima_valor}${tabla_fin + 1})"

        encabezados = ["x", "y", "Elegido", "Comparación", "Variación", "Tamaño", "Cae", "Orden", "Rótulo"]
        series_mapa = [(t, c) for c in range(len(MAPA_COLORES)) for t in range(len(TAMANIOS_BURBUJA))]
        bloque("Mapa: burbujas del trimestre elegido",
               encabezados + [f"Serie {TAMANIOS_BURBUJA[t]} · {'sube' if c == 0 else 'baja'}" for t, c in series_mapa])
        mapa_inicio = fila
        for i, concesion in enumerate(concesiones):
            v, b, var, tam, cae, orden = (local(fila, k) for k in (2, 3, 4, 5, 6, 7))
            valores = [
                (concesion["x"], f_decimal),
                # El eje vertical del gráfico crece hacia arriba y el lienzo
                # hacia abajo: se invierte el signo.
                (-concesion["y"], f_decimal),
                (f"=N({en_tabla(i, SEL)})", f_entero),
                (f"={en_tabla(i, CMP)}", f_entero),
                (f"={variacion(v, b)}", f_variacion),
                (f"=IF({v}<=0,0,MIN({len(TAMANIOS_BURBUJA)},ROUNDUP({len(TAMANIOS_BURBUJA)}*SQRT({v}/{maximo}),0)))", f_texto),
                (f'=IF(N({var})<0,1,0)', f_texto),
                (f"={v}+{n - i}/1000", f_numero),
                # En el mapa, el rótulo es el puesto en la lista del costado: tres
                # concesiones grandes a veinte kilómetros no dejan lugar a nombres.
                (f'=IF({v}>0,IF(RANK({orden},${letra(DATOS_VALORES[7][0])}${mapa_inicio + 1}:'
                 f'${letra(DATOS_VALORES[7][0])}${mapa_inicio + n},0)<={MAPA_ROTULOS},'
                 f'RANK({orden},${letra(DATOS_VALORES[7][0])}${mapa_inicio + 1}:'
                 f'${letra(DATOS_VALORES[7][0])}${mapa_inicio + n},0),""),"")', f_texto),
            ]
            for t, c in series_mapa:
                valores.append((f"=IF(AND({tam}={t + 1},{cae}={c}),{local(fila, 1)},NA())", f_decimal))
            renglon(concesion["nombre"], valores)
        mapa_fin = fila - 1
        fila += 1

        # La lista del costado: las concesiones ordenadas por lo que produjeron.
        orden_rango = f"{local(mapa_inicio, 7)}:{local(mapa_fin, 7)}"
        bloque("Mapa: ranking del trimestre", ["boe/d", "Variación"])
        lista_inicio = fila
        for k in range(1, min(MAPA_LISTA, n) + 1):
            posicion = f"MATCH(LARGE({orden_rango},{k}),{orden_rango},0)"
            renglon(f'="{k}   "&INDEX({local(mapa_inicio, None)}:{local(mapa_fin, None)},{posicion})', [
                (f"=INDEX({local(mapa_inicio, 2)}:{local(mapa_fin, 2)},{posicion})", f_miles),
                (f"=INDEX({local(mapa_inicio, 4)}:{local(mapa_fin, 4)},{posicion})", f_variacion_corta),
            ])
        lista_fin = fila - 1
        total_col = n
        mapa_total = renglon("Total shale operado", [
            (f"=N({en_tabla(total_col, SEL)})", f_miles),
            (f"={variacion(local(fila, 0), en_tabla(total_col, CMP))}", f_variacion),
        ])
        fila += 1

    # --- 13. mercado --------------------------------------------------------
    eventos_inicio = mercado_sel = mercado_serie_inicio = mercado_serie_fin = None
    if mercado and mercado.get("eventos"):
        f_retorno = libro.add_format({**base, "font_color": TEXTO, "align": "right",
                                      "num_format": '"+"0.0%;"−"0.0%;0.0%'})
        f_precio = libro.add_format({**base, "font_color": TEXTO, "align": "right", "num_format": '"US$ "0.00'})
        f_t = libro.add_format({**base, "font_color": TEXTO, "align": "right", "num_format": '0.00;−0.00'})
        f_pb = libro.add_format({**base, "font_color": TEXTO, "align": "right", "num_format": '#,##0" pb"'})

        # Los eventos tal cual los deja transform/market_reaction.py, uno por balance.
        campos_evento = [
            ("fecha_reporte", "Reporte", f_texto), ("precio_ypf", "Precio del ADR", f_precio),
            ("retorno_dia", "Retorno del día", f_retorno), ("retorno_anormal_dia", "Retorno anormal", f_retorno),
            ("car_0_3", "Anormal acumulado 0–3", f_retorno), ("t_estadistico", "t", f_t),
            ("retorno_vist_dia", "Vista, el día", f_retorno), ("retorno_brent_dia", "Brent, el día", f_retorno),
            ("embi_dia", "Riesgo país", f_pb),
        ]
        bloque("Mercado: reacción a cada balance (transform/market_reaction.py)", [c[1] for c in campos_evento])
        eventos_inicio = fila
        for evento in mercado["eventos"]:
            valores = []
            for campo, _, formato in campos_evento:
                valor = evento.get(campo)
                if campo == "fecha_reporte" and valor:
                    valor = fecha_corta(valor)
                valores.append((valor if valor is not None else "", formato))
            renglon(etiqueta_trimestre(evento["trimestre"]), valores)
        eventos_fin = fila - 1
        fila += 1

        etiquetas_eventos = f"{local(eventos_inicio, None)}:{local(eventos_fin, None)}"

        def del_evento(indice: int, trimestre: str, vacio: str = '""') -> str:
            columna = letra(DATOS_VALORES[indice][0])
            return (f"IFERROR(INDEX(${columna}${eventos_inicio + 1}:${columna}${eventos_fin + 1},"
                    f"MATCH({trimestre},{etiquetas_eventos},0)),{vacio})")

        bloque("Mercado: balance elegido", [c[1] for c in campos_evento])
        mercado_sel = renglon(f"={SEL}", [(f"={del_evento(i, SEL)}", c[2]) for i, c in enumerate(campos_evento)])
        t_celda = local(mercado_sel, 5)
        sel["mercado_sub"] = local(renglon("Texto: mercado_sub", [(
            f'=IF({local(mercado_sel, 0)}="","Sin estudio de evento para "&{SEL},'
            f'"Balance de "&{SEL}&", presentado el "&{local(mercado_sel, 0)}&" · primera rueda después del 6-K")',
            f_texto_izq,
        )]), 0)
        sel["mercado_t"] = local(renglon("Texto: mercado_t", [(
            f'=IF({t_celda}="","",IF(ABS({t_celda})>=1.96,"● Significativo al 5%","● Dentro de la variación normal"))',
            f_texto_izq,
        )]), 0)
        fila += 1

        bloque("Mercado: doce balances", ["Retorno anormal", "Anormal acumulado 0–3"])
        mercado_serie_inicio = fila
        for atras in range(HISTORIA - 1, -1, -1):
            trimestre = f"INDEX({L_ETIQUETAS},{POS}-{atras})"
            renglon(f"={trimestre}", [
                (f"={del_evento(3, trimestre, 'NA()')}", f_retorno),
                (f"={del_evento(4, trimestre, 'NA()')}", f_retorno),
            ])
        mercado_serie_fin = fila - 1
        fila += 1

    # --- cuadros de texto ---------------------------------------------------
    def texto(x: float, y: float, w: float, h: float, contenido: str = "", tamanio: int = 10,
              color: str = TEXTO, negrita: bool = False, alinear: str = "left", enlace: str | None = None) -> None:
        opciones = {
            **lugar(x, y), "width": int(w), "height": int(h),
            "font": {"name": FUENTE, "size": tamanio, "color": color, "bold": negrita},
            "align": {"vertical": "middle", "horizontal": alinear},
            "fill": {"none": True}, "line": {"none": True},
        }
        if enlace:
            opciones["textlink"] = enlace
        hoja.insert_textbox(0, 0, contenido, opciones)

    def saltar() -> None:
        """Una fila en blanco entre bloques del pie de datos."""
        nonlocal fila
        fila += 1

    def validar(celda: str, opciones: list[str], titulo: str) -> None:
        """Una lista desplegable escrita en la propia validación, sin rango aparte."""
        hoja.data_validation(celda.replace("$", ""), {
            "validate": "list", "source": opciones,
            "input_title": titulo, "input_message": "Elegí de la lista",
            "error_title": titulo, "error_message": "El valor tiene que salir de la lista.",
        })

    def texto_de(clave: str) -> str:
        return f"='{nombre}'!{sel[clave]}"

    def poner_icono(nombre_icono: str, x: float, y: float, lado: int, **opciones) -> None:
        """Un ícono de export/iconos.py, dibujado al doble y achicado para que se vea nítido."""
        hoja.insert_image(0, 0, f"icono_{nombre_icono}_{int(x)}_{int(y)}.png", {
            "image_data": iconos.png(nombre_icono, lado * 2, **opciones), "x_scale": 0.5, "y_scale": 0.5,
            **lugar(x, y), "decorative": True,
        })

    def titulo_tarjeta(clave: str, titulo: str, subtitulo: str | None = None,
                       ancho: int | None = None, icono: str | None = None) -> tuple[int, int, int, int]:
        x, y, w, h = TARJETAS[clave]
        # El ícono va a la izquierda del título y corre el texto.
        corrido = 0
        if icono:
            poner_icono(icono, x + 12, y + 14, 34)
            corrido = 42
        # Un cuadro de texto encima de una lista no deja hacer clic en ella: el
        # título de las tarjetas con lista se corta antes.
        texto(x + 12 + corrido, y + 17, (ancho or w - 24) - (corrido if ancho is None else 0), 26, titulo, 12,
              TEXTO, negrita=True)
        if subtitulo:
            texto(x + 12 + corrido, y + 40, w - 24 - corrido, 20, "", 8, TEXTO_TENUE, enlace=texto_de(subtitulo))
        return x, y, w, h

    def aviso(x: float, y: float, w: float, clave: str = "aviso", alinear: str = "right") -> None:
        texto(x, y, w, 20, "", 8, AMBAR, negrita=True, alinear=alinear, enlace=texto_de(clave))

    # --- gráficos: estilo común ---------------------------------------------
    def insertar(grafico, x: float, y: float, w: float, h: float) -> None:
        grafico.set_size({"width": int(w), "height": int(h)})
        grafico.set_chartarea({"border": {"none": True}, "fill": {"none": True}})
        grafico.set_legend({"none": True})
        # Sin datos (un segmento que no abre esa línea) el gráfico queda vacío
        # en vez de dibujar ceros.
        grafico.show_na_as_empty_cell()
        hoja.insert_chart(0, 0, grafico, lugar(x, y))

    fuente_eje = {"name": FUENTE, "size": 8, "color": TEXTO_SUAVE}

    def eje_oculto(**extra) -> dict:
        return {"visible": False, "line": {"none": True}, "major_tick_mark": "none",
                "major_gridlines": {"visible": False}, "minor_gridlines": {"visible": False}, **extra}

    def ejes_limpios(grafico, formato_y: str = '#,##0,,"M"', grilla: bool = True, ver_y: bool = True) -> None:
        grafico.set_plotarea({"fill": {"none": True}, "border": {"none": True}})
        grafico.set_x_axis({"num_font": fuente_eje, "line": {"none": True}, "major_tick_mark": "none",
                            "label_position": "low"})
        grafico.set_y_axis({
            "num_font": fuente_eje, "num_format": formato_y, "line": {"none": True},
            "major_tick_mark": "none", "visible": ver_y,
            "major_gridlines": {"visible": grilla, "line": {"color": GRILLA, "width": 0.75, "dash_type": "dash"}},
        })

    # --- cabecera -----------------------------------------------------------
    cx, cy, cw, ch = CABECERA
    hoja.insert_image(0, 0, "logo.png", {
        "image_data": _png(iconos.logo(88)), "x_scale": 0.5, "y_scale": 0.5, **lugar(cx + 6, cy + 8),
        "decorative": True,
    })
    texto(cx + 44, cy + 6, 220, 28, "YPF · ATLAS", 14, TEXTO, negrita=True)
    texto(cx + 44, cy + 30, 250, 22, "", 8, TEXTO_SUAVE, enlace=texto_de("cabecera"))

    navegacion = [("Resumen", "Resumen"), ("Resultados", hojas["resultados"]),
                  ("Análisis", "Análisis"), ("Valuación", "Valuación"), ("Deuda", "Deuda")]
    hojas_existentes = {h.get_name() for h in libro.worksheets()}
    x_pastilla = 320
    for rotulo, destino in navegacion:
        if destino not in hojas_existentes:
            continue
        hoja.insert_image(0, 0, f"nav_{rotulo}.png", {
            "image_data": imagen_de_pastilla(rotulo),
            "x_scale": 1 / ESCALA_IMAGEN, "y_scale": 1 / ESCALA_IMAGEN,
            **lugar(x_pastilla, cy + 14),
            "url": f"internal:'{destino}'!A1", "tip": f"Ir a {destino}",
        })
        x_pastilla += 104

    x_c, _, _, _ = CONTROLES["trimestre"]
    texto(x_c - MARCO_IZQ - 84, cy + 18, 84, 24, "Trimestre", 8, TEXTO_SUAVE, alinear="right")
    # Entre la pastilla del trimestre y la del segmento hay setenta píxeles:
    # el rótulo va centrado en ese hueco, sin tocar ninguna de las dos.
    x_t, _, w_t, _ = CONTROLES["trimestre"]
    x_c, _, _, _ = CONTROLES["segmento"]
    hueco = (x_t + w_t + MARCO_DER, x_c - MARCO_IZQ)
    texto(hueco[0] + 4, cy + 18, hueco[1] - hueco[0] - 8, 24, "Segmento", 8, TEXTO_SUAVE, alinear="center")

    chips = [("Deuda neta/EBITDA", ind["deuda_ebitda"])]
    if "ev_ebitda" in ind:
        chips.append(("EV/EBITDA", ind["ev_ebitda"]))
    ancho_chip = 110
    x_chip = cx + cw - 12 - ancho_chip * len(chips)
    for rotulo, fila_ind in chips:
        texto(x_chip, cy + 6, ancho_chip, 20, rotulo, 8, TEXTO_TENUE, alinear="right")
        texto(x_chip, cy + 24, ancho_chip, 30, "", 14, TEXTO, negrita=True, alinear="right", enlace=vinculo(fila_ind))
        x_chip += ancho_chip

    # --- tarjeta héroe: el trimestre ---------------------------------------
    x, y, w, h = TARJETAS["heroe"]
    poner_icono("gota", x + 12, y + 12, 22, ficha=False, tinte="blanco")
    texto(x + 36, y + 12, 226, 22, "", 10, "#cfe0ff", enlace=texto_de("heroe"))
    texto(x + 12, y + 32, 250, 48, "", 26, "#ffffff", negrita=True, enlace=vinculo(ind["ebitda"]))
    texto(x + 12, y + 86, 250, 30, "", 15, "#ffffff", negrita=True, enlace=vinculo(ind["ingresos"]))
    texto(x + 12, y + 110, 250, 20, "Ingresos del trimestre", 8, "#a9c3ee")
    # Consolidado: el EBITDA de los estados al lado del ajustado. Por segmento:
    # el aviso de que ese EBITDA no tiene ajustes. Los dos cuadros se pisan y
    # siempre uno está vacío.
    texto(x + 12, y + 128, 200, 18, "", 7, "#a9c3ee", enlace=texto_de("heroe_contable"))
    texto(x + 200, y + 128, 110, 18, "", 8, "#ffffff", negrita=True, enlace=vinculo(ind["ebitda_contable"]))
    texto(x + 12, y + 128, 340, 18, "", 8, AMBAR, negrita=True, enlace=texto_de("aviso_segmento"))

    torta_margen = libro.add_chart({"type": "doughnut"})
    torta_margen.add_series({
        "categories": categorias(ind["margen"], ind["margen_resto"]),
        "values": serie(ind["margen"], ind["margen_resto"], 0),
        "points": [{"fill": {"color": CIAN}, "border": {"none": True}},
                   {"fill": {"color": "#ffffff", "transparency": 85}, "border": {"none": True}}],
    })
    torta_margen.set_hole_size(78)
    insertar(torta_margen, x + w - 112, y + 10, 100, 100)
    texto(x + w - 110, y + 44, 96, 22, "", 11, "#ffffff", negrita=True, alinear="center", enlace=vinculo(ind["margen"]))
    texto(x + w - 110, y + 106, 96, 18, "margen EBITDA", 7, "#a9c3ee", alinear="center")

    chispa = libro.add_chart({"type": "line"})
    chispa_inicio = serie_fin - 7
    chispa.add_series({
        "categories": categorias(chispa_inicio, serie_fin),
        "values": serie(chispa_inicio, serie_fin, col_ebitda),
        "smooth": True,
        "line": {"color": "#bfe9ff", "width": 2.25},
        "marker": {"type": "none"},
        "points": [None] * 7 + [{"fill": {"color": CIAN}, "border": {"color": "#ffffff", "width": 1.5}}],
    })
    chispa.set_plotarea({"fill": {"none": True}, "border": {"none": True},
                         "layout": {"x": 0.02, "y": 0.08, "width": 0.96, "height": 0.72}})
    chispa.set_x_axis({"num_font": {"name": FUENTE, "size": 7, "color": "#a9c3ee"}, "line": {"none": True},
                       "major_tick_mark": "none", "label_position": "low"})
    chispa.set_y_axis({"visible": False, "major_gridlines": {"visible": False}})
    insertar(chispa, x + 6, y + 148, w - 12, 96)

    texto(x + 12, y + h - 36, 200, 24, "", 8, "#a9c3ee", enlace=texto_de("heroe_cmp"))
    texto(x + w - 150, y + h - 38, 138, 28, "", 12, CIAN, negrita=True, alinear="right", enlace=vinculo(ind["ebitda_cmp"]))

    # --- serie trimestral ---------------------------------------------------
    x, y, w, h = titulo_tarjeta("ingresos", "Serie", "serie", ancho=170, icono="velas")
    texto(x + w - 232, y + 8, 220, 20, "Últimos doce meses", 8, TEXTO_TENUE, alinear="right")
    texto(x + w - 262, y + 24, 250, 34, "", 18, TEXTO, negrita=True, alinear="right", enlace=vinculo(udm))

    barras = libro.add_chart({"type": "column"})
    destacadas = 3
    barras.add_series({
        "categories": categorias(serie_inicio, serie_fin),
        "values": serie(serie_inicio, serie_fin, col_metrica),
        "gap": 55,
        "fill": {"color": BARRA_APAGADA},
        "border": {"none": True},
        "invert_if_negative": False,
        "points": [None] * (HISTORIA - destacadas) + [
            {"gradient": {"colors": [CIAN, AZUL_PROFUNDO], "angle": 90}, "border": {"none": True}}
        ] * destacadas,
        "data_labels": {
            "value": True, "position": "outside_end", "num_format": '#,##0,,"M"',
            "font": {"name": FUENTE, "size": 8, "bold": True, "color": TEXTO},
            "custom": [{"delete": True}] * (HISTORIA - destacadas) + [None] * destacadas,
        },
    })
    ejes_limpios(barras)
    barras.set_plotarea({"fill": {"none": True}, "border": {"none": True},
                         "layout": {"x": 0.08, "y": 0.06, "width": 0.9, "height": 0.8}})
    insertar(barras, x + 6, y + 66, w - 12, h - 72)
    texto(x + 60, y + h / 2 + 10, w - 120, 26, "", 11, AMBAR, negrita=True, alinear="center",
          enlace=texto_de("aviso_serie"))

    # --- márgenes: radar ----------------------------------------------------
    x, y, w, h = titulo_tarjeta("margenes", "Márgenes", "radar", ancho=130, icono="porcentaje")
    x_c, _, _, _ = CONTROLES["comparar"]
    texto(x_c - MARCO_IZQ - 66, y + 17, 66, 26, "contra", 9, TEXTO_SUAVE, alinear="right")
    radar = libro.add_chart({"type": "radar", "subtype": "filled"})
    radar.add_series({
        "name": [nombre, encabezado_margenes, DATOS_VALORES[1][0]],
        "categories": categorias(margenes_inicio, margenes_fin),
        "values": serie(margenes_inicio, margenes_fin, 3),
        "fill": {"color": "#a5b4fc", "transparency": 70},
        "border": {"color": "#c7d2fe", "width": 1.5, "dash_type": "dash"},
    })
    radar.add_series({
        "name": [nombre, encabezado_margenes, DATOS_VALORES[0][0]],
        "categories": categorias(margenes_inicio, margenes_fin),
        "values": serie(margenes_inicio, margenes_fin, 2),
        "fill": {"color": CIAN, "transparency": 60},
        "border": {"color": CIAN, "width": 2},
    })
    radar.set_x_axis({"num_font": fuente_eje, "line": {"color": GRILLA}})
    radar.set_y_axis({
        "num_font": {"name": FUENTE, "size": 7, "color": TEXTO_TENUE}, "num_format": ";;;",
        "line": {"none": True}, "major_tick_mark": "none",
        "major_gridlines": {"visible": True, "line": {"color": GRILLA, "width": 0.75}},
    })
    radar.set_plotarea({"fill": {"none": True}, "border": {"none": True},
                        "layout": {"x": 0.2, "y": 0.06, "width": 0.6, "height": 0.84}})
    insertar(radar, x + 6, y + 60, w - 12, h - 90)
    texto(x + 12, y + h - 30, 70, 20, "", 8, CIAN, negrita=True, enlace=texto_de("radar_sel"))
    texto(x + 82, y + h - 30, 80, 20, "", 8, "#c7d2fe", enlace=texto_de("radar_cmp"))
    aviso(x + w - 252, y + h - 30, 240, clave="aviso_radar")

    # --- lo que va del año --------------------------------------------------
    x, y, w, h = TARJETAS["semestre"]
    poner_icono("calendario", x + 12, y + 14, 34)
    texto(x + 54, y + 17, w - 66, 26, "", 12, TEXTO, negrita=True, enlace=texto_de("semestre"))
    texto(x + 54, y + 40, w - 66, 20, "", 8, TEXTO_TENUE, enlace=texto_de("semestre_sub"))
    renglones = semestre_fin - semestre_inicio + 1
    banda = 42
    y_lista = y + 60
    for i, metrica in enumerate(semestre_metricas):
        fila_dato = semestre_inicio + i
        yy = y_lista + i * banda
        texto(x + 12, yy - 2, 130, 22, metrica, 9, TEXTO_SUAVE)
        texto(x + 120, yy - 2, 160, 22, "", 9, TEXTO, negrita=True, alinear="right", enlace=vinculo(fila_dato, 0))
        texto(x + w - 96, yy - 2, 84, 22, "", 9, CIAN, negrita=True, alinear="right", enlace=vinculo(fila_dato, 2))

    # Barras apiladas: el valor y lo que le falta hasta el tope. Apiladas, la
    # pista y la barra no pueden desalinearse.
    progreso = libro.add_chart({"type": "bar", "subtype": "stacked"})
    progreso.add_series({
        "categories": categorias(semestre_inicio, semestre_fin),
        "values": serie(semestre_inicio, semestre_fin, 3),
        "gradient": {"colors": [AZUL_PROFUNDO, CIAN], "angle": 0}, "border": {"none": True},
        "gap": 420, "overlap": 100,
    })
    progreso.add_series({
        "categories": categorias(semestre_inicio, semestre_fin),
        "values": serie(semestre_inicio, semestre_fin, 4),
        "fill": {"color": "#1c3150"}, "border": {"none": True},
    })
    progreso.set_plotarea({"fill": {"none": True}, "border": {"none": True},
                           "layout": {"x": 0, "y": 0, "width": 1, "height": 1}})
    # En un gráfico de barras horizontales el eje x es el de valores.
    progreso.set_x_axis(eje_oculto(min=0, max=TOPE))
    progreso.set_y_axis(eje_oculto(reverse=True))
    insertar(progreso, x + 18, y_lista + 10, w - 36, banda * renglones)

    # --- destino de los ingresos --------------------------------------------
    x, y, w, h = titulo_tarjeta("destino", "Adónde va cada dólar de ingresos", "destino", icono="dolar")
    aviso(x + 160, y + 40, 300, clave="aviso_destino", alinear="left")
    torta = libro.add_chart({"type": "doughnut"})
    porciones_destino = destino_fin - destino_inicio + 1
    torta.add_series({
        "categories": categorias(destino_inicio, destino_fin),
        "values": serie(destino_inicio, destino_fin, 0),
        "points": [{"fill": {"color": PORCIONES[i % len(PORCIONES)]}, "border": {"color": "#0e1f38", "width": 1.5}}
                   for i in range(porciones_destino)],
    })
    torta.set_hole_size(66)
    lado = h - 70
    insertar(torta, x + 12, y + 62, lado, lado)
    texto(x + 12, y + 62 + lado / 2 - 20, lado, 26, "", 12, TEXTO, negrita=True, alinear="center",
          enlace=vinculo(total_destino))
    texto(x + 12, y + 62 + lado / 2 + 4, lado, 18, "ingresos", 8, TEXTO_TENUE, alinear="center")

    x_lista = x + lado + 26
    rotulos_destino = ["Costos de producción", "Comercialización", "Administración",
                       "Exploración", "Otros y deterioros", "Resultado operativo"]
    for i in range(porciones_destino):
        fila_dato = destino_inicio + i
        yy = y + 62 + i * 27
        texto(x_lista, yy, 20, 22, "●", 10, PORCIONES[i % len(PORCIONES)])
        texto(x_lista + 16, yy, 150, 22, rotulos_destino[i], 8, TEXTO_SUAVE)
        texto(x_lista + 126, yy, 60, 22, "", 8, TEXTO, negrita=True, alinear="right", enlace=vinculo(fila_dato, 1))
        texto(x_lista + 180, yy, 84, 22, "", 8, TEXTO_SUAVE, alinear="right", enlace=vinculo(fila_dato, 2))

    # Flujo operativo contra capex, a la derecha.
    x_caja = x + w - RECUADRO_W - 20
    texto(x_caja - 6, y + 12, 130, 20, "Cuánto se reinvierte", 8, TEXTO_TENUE)
    texto(x_caja + 104, y + 12, RECUADRO_W - 98, 20, "", 8, CIAN, negrita=True, alinear="right",
          enlace=vinculo(reinversion_texto))
    banda_caja = 40
    for i, rotulo in enumerate(["Flujo operativo", "Capex pagado"]):
        yy = y + 36 + i * banda_caja
        texto(x_caja - 6, yy, 110, 20, rotulo, 8, TEXTO_SUAVE)
        texto(x_caja + 96, yy, RECUADRO_W - 90, 20, "", 8, TEXTO, negrita=True, enlace=vinculo(caja_inicio + i, 0))
    aviso(x_caja - 6, y + 118, RECUADRO_W + 12, clave="aviso_caja", alinear="left")
    reinversion = libro.add_chart({"type": "bar", "subtype": "stacked"})
    reinversion.add_series({
        "categories": categorias(caja_inicio, caja_fin),
        "values": serie(caja_inicio, caja_fin, 1),
        "points": [{"gradient": {"colors": [AZUL_PROFUNDO, CIAN], "angle": 0}, "border": {"none": True}},
                   {"gradient": {"colors": ["#1e3a8a", "#60a5fa"], "angle": 0}, "border": {"none": True}}],
        "gap": 480, "overlap": 100,
    })
    reinversion.add_series({
        "categories": categorias(caja_inicio, caja_fin),
        "values": serie(caja_inicio, caja_fin, 2),
        "fill": {"color": "#1c3150"}, "border": {"none": True},
    })
    reinversion.set_plotarea({"fill": {"none": True}, "border": {"none": True},
                              "layout": {"x": 0, "y": 0, "width": 1, "height": 1}})
    reinversion.set_x_axis(eje_oculto(min=0, max=1))
    reinversion.set_y_axis(eje_oculto(reverse=True))
    insertar(reinversion, x_caja, y + 48, RECUADRO_W, banda_caja * 2)
    texto(x_caja + 4, y + h - 94, RECUADRO_W - 8, 18, "Flujo libre (operativo − capex pagado)", 7, "#a9c3ee")
    texto(x_caja + 4, y + h - 78, RECUADRO_W - 8, 30, "", 15, "#ffffff", negrita=True, enlace=vinculo(libre))
    if "fcf_publicado" in publicado:
        texto(x_caja + 4, y + h - 46, 110, 18, "Publicado por YPF", 7, "#a9c3ee")
        texto(x_caja + 96, y + h - 46, RECUADRO_W - 100, 18, "", 8, "#cfe0ff", negrita=True, alinear="right",
              enlace=vinculo(publicado["fcf_publicado"]))

    # --- capex por segmento -------------------------------------------------
    x, y, w, h = titulo_tarjeta("capex", "Capex por segmento", "capex", icono="casco")
    if capex_inicio is not None:
        aviso(x + 12, y + 244, w - 24, clave="aviso_capex", alinear="center")
        torta_capex = libro.add_chart({"type": "doughnut"})
        porciones_capex = capex_fin - capex_inicio + 1
        torta_capex.add_series({
            "categories": categorias(capex_inicio, capex_fin),
            "values": serie(capex_inicio, capex_fin, 0),
            "points": [{"fill": {"color": PORCIONES[i % len(PORCIONES)]}, "border": {"color": "#0e1f38", "width": 2}}
                       for i in range(porciones_capex)],
        })
        torta_capex.set_hole_size(64)
        torta_capex.set_rotation(20)
        lado = 200
        x_torta = x + (w - lado) / 2
        insertar(torta_capex, x_torta, y + 60, lado, lado)
        texto(x_torta, y + 60 + lado / 2 - 26, lado, 32, "", 16, TEXTO, negrita=True, alinear="center",
              enlace=vinculo(total_capex))
        texto(x_torta, y + 60 + lado / 2 + 4, lado, 20, "devengado", 8, TEXTO_TENUE, alinear="center")

        for i in range(porciones_capex):
            fila_dato = capex_inicio + i
            yy = y + 270 + i * 22
            texto(x + 16, yy, 20, 24, "", 11, PORCIONES[i % len(PORCIONES)], enlace=vinculo(fila_dato, 3))
            texto(x + 34, yy, 220, 24, "", 9, TEXTO_SUAVE, enlace=vinculo(fila_dato, 2))
            texto(x + w - 172, yy, 60, 24, "", 9, TEXTO, negrita=True, alinear="right", enlace=vinculo(fila_dato, 4))
            texto(x + w - 116, yy, 104, 24, "", 9, TEXTO_SUAVE, alinear="right", enlace=vinculo(fila_dato, 0))

    # Los tres capex del trimestre, con su nombre: el devengado de la torta, el
    # pagado del flujo de efectivo y el que publica la compañía.
    comparacion_capex = [("Pagado (flujo de efectivo)", vinculo(caja_fin))]
    if "capex_publicado" in publicado:
        comparacion_capex.append(("Publicado por YPF", vinculo(publicado["capex_publicado"])))
    texto(x + 16, y + h - 40 - 22 * len(comparacion_capex), w - 32, 18, "Otras lecturas del capex del trimestre",
          7, TEXTO_TENUE)
    for i, (rotulo, enlace) in enumerate(comparacion_capex):
        yy = y + h - 30 - 22 * (len(comparacion_capex) - i - 1) - 8
        texto(x + 16, yy, 220, 20, rotulo, 9, TEXTO_SUAVE)
        texto(x + w - 136, yy, 124, 20, "", 9, TEXTO, negrita=True, alinear="right", enlace=enlace)

    # --- EBITDA y flujo operativo -------------------------------------------
    x, y, w, h = titulo_tarjeta("caja", "EBITDA y flujo operativo", "lineas", icono="flujo")
    texto(x + w - 250, y + 12, 120, 20, "━ EBITDA ajustado", 8, CIAN, negrita=True, alinear="right")
    texto(x + w - 130, y + 12, 118, 20, "┅ Flujo operativo", 8, "#818cf8", negrita=True, alinear="right")
    aviso(x + w - 312, y + 32, 300, clave="aviso_flujo")
    lineas = libro.add_chart({"type": "line"})
    lineas.add_series({
        "name": "EBITDA",
        "categories": categorias(serie_inicio, serie_fin),
        "values": serie(serie_inicio, serie_fin, col_ebitda),
        "smooth": True, "line": {"color": CIAN, "width": 2.5},
        "marker": {"type": "circle", "size": 5, "fill": {"color": "#0b182c"}, "border": {"color": CIAN, "width": 1.5}},
    })
    lineas.add_series({
        "name": "Flujo operativo",
        "categories": categorias(serie_inicio, serie_fin),
        "values": serie(serie_inicio, serie_fin, col_cfo),
        "smooth": True, "line": {"color": "#818cf8", "width": 2, "dash_type": "dash"},
        "marker": {"type": "none"},
    })
    ejes_limpios(lineas)
    lineas.set_plotarea({"fill": {"none": True}, "border": {"none": True},
                         "layout": {"x": 0.08, "y": 0.06, "width": 0.9, "height": 0.76}})
    insertar(lineas, x + 6, y + 58, w - 12, h - 64)

    # --- ejercicios ---------------------------------------------------------
    x, y, w, h = titulo_tarjeta("ejercicios", "Ejercicios", "ejercicios", icono="refineria")
    texto(x + w - 190, y + 12, 90, 20, "■ EBITDA", 8, CIAN, negrita=True, alinear="right")
    texto(x + w - 100, y + 12, 88, 20, "□ Capex", 8, "#93c5fd", negrita=True, alinear="right")
    anual = libro.add_chart({"type": "column"})
    anual.add_series({
        "name": "EBITDA",
        "categories": categorias(ejercicios_inicio, ejercicios_fin),
        "values": serie(ejercicios_inicio, ejercicios_fin, 0),
        "gradient": {"colors": [CIAN, AZUL_PROFUNDO], "angle": 90}, "border": {"none": True},
        "gap": 90, "overlap": -12,
        "data_labels": {"value": True, "position": "outside_end", "num_format": '#,##0,,"M"',
                        "font": {"name": FUENTE, "size": 8, "bold": True, "color": TEXTO}},
    })
    anual.add_series({
        "name": "Capex",
        "categories": categorias(ejercicios_inicio, ejercicios_fin),
        "values": serie(ejercicios_inicio, ejercicios_fin, 1),
        "fill": {"color": "#3b82f6", "transparency": 85}, "border": {"color": "#93c5fd", "width": 1.25},
        "gap": 90, "overlap": -12,
        # Adentro de la barra: afuera choca con la etiqueta del EBITDA de al lado
        # cuando los dos números se parecen.
        "data_labels": {"value": True, "position": "inside_end", "num_format": '#,##0,,"M"',
                        "font": {"name": FUENTE, "size": 8, "color": "#93c5fd"}},
    })
    ejes_limpios(anual, grilla=False, ver_y=False)
    anual.set_x_axis({"num_font": {"name": FUENTE, "size": 9, "color": TEXTO, "bold": True},
                      "line": {"color": GRILLA}, "major_tick_mark": "none", "label_position": "low"})
    anual.set_plotarea({"fill": {"none": True}, "border": {"none": True},
                        "layout": {"x": 0.04, "y": 0.12, "width": 0.92, "height": 0.74}})
    insertar(anual, x + 6, y + 54, w - 12, h - 60)

    # --- mapa ---------------------------------------------------------------
    x, y, w, h = titulo_tarjeta("mapa", "Vaca Muerta: dónde produce YPF", "mapa", icono="pin")
    if mapa_inicio is not None:
        mx, my, mw, mh = recuadro_del_mapa(datos_mapa)
        ventana = datos_mapa["ventana"]
        burbujas = libro.add_chart({"type": "scatter"})
        filas_burbuja = range(mapa_inicio, mapa_fin + 1)
        for k, (t, c) in enumerate(series_mapa):
            color = MAPA_COLORES[c]
            columna_serie = len(encabezados) + k
            burbujas.add_series({
                "categories": serie(mapa_inicio, mapa_fin, 0),
                "values": serie(mapa_inicio, mapa_fin, columna_serie),
                "marker": {"type": "circle", "size": TAMANIOS_BURBUJA[t],
                           "fill": {"color": color, "transparency": 35},
                           "border": {"color": color, "width": 1.25}},
                # El rótulo de cada punto es la celda del nombre, que queda
                # vacía salvo para las mayores. Un punto sin dato no dibuja
                # rótulo.
                "data_labels": {
                    "value": True, "position": "right",
                    "font": {"name": FUENTE, "size": 8, "bold": True, "color": "#e2e8f0"},
                    "custom": [{"value": f"='{nombre}'!{local(f, 8)}"} for f in filas_burbuja],
                },
            })
        burbujas.set_x_axis(eje_oculto(min=ventana["x"], max=ventana["x"] + ventana["ancho"]))
        burbujas.set_y_axis(eje_oculto(min=-(ventana["y"] + ventana["alto"]), max=-ventana["y"]))
        burbujas.set_plotarea({"fill": {"none": True}, "border": {"none": True},
                               "layout": {"x": 0, "y": 0, "width": 1, "height": 1}})
        burbujas.set_chartarea({"border": {"none": True}, "fill": {"none": True}})
        burbujas.set_legend({"none": True})
        burbujas.set_size({"width": mw, "height": mh})
        hoja.insert_chart(0, 0, burbujas, lugar(mx, my))

        # Al costado: el total y las concesiones de mayor a menor.
        lx = mx + mw + 20
        lw = x + w - 16 - lx
        texto(lx, y + 64, lw, 18, "Total shale operado", 8, TEXTO_TENUE)
        texto(lx, y + 80, lw - 80, 30, "", 17, TEXTO, negrita=True, enlace=vinculo(mapa_total, 0))
        texto(lx + lw - 90, y + 86, 90, 22, "", 10, CIAN, negrita=True, alinear="right", enlace=vinculo(mapa_total, 1))
        texto(lx, y + 108, lw, 18, "", 7, TEXTO_TENUE, enlace=texto_de("comparacion"))
        for i in range(lista_fin - lista_inicio + 1):
            fila_dato = lista_inicio + i
            yy = y + 134 + i * 28
            texto(lx, yy, lw - 130, 22, "", 8, TEXTO_SUAVE, enlace=vinculo(fila_dato, None))
            texto(lx + lw - 130, yy, 64, 22, "", 8, TEXTO, negrita=True, alinear="right", enlace=vinculo(fila_dato, 0))
            texto(lx + lw - 64, yy, 64, 22, "", 8, TEXTO_SUAVE, alinear="right", enlace=vinculo(fila_dato, 1))
        texto(lx, y + h - 52, 90, 16, "● creció", 8, CIAN, negrita=True)
        texto(lx + 80, y + h - 52, 90, 16, "● cayó", 8, AMBAR, negrita=True)
        texto(lx, y + h - 36, lw, 28,
              "Bruto operado, con la parte de los socios: no es la producción neta del release.", 7, TEXTO_TENUE)

    # --- operativo -----------------------------------------------------------
    x, y, w, h = titulo_tarjeta("operativo", "Precio o volumen", "operativo_sub", icono="barril")
    aviso(x + w - 212, y + 17, 200, clave="aviso_operativo")
    if operativo_inicio is not None:
        ancho_tile = (w - 24 - 12 * (len(tarjetas_operativo) - 1)) / len(tarjetas_operativo)
        iconos_operativo = {"produccion_kboed": "cigueña", "shale_oil_kbbld": "gota",
                            "precio_crudo_usd_bbl": "barril", "lifting_cost_usd_boe": "engranaje"}
        for i, (campo, etiqueta, unidad, _) in enumerate(tarjetas_operativo):
            tx = x + 12 + i * (ancho_tile + 12)
            fila_dato = operativo_inicio + i
            poner_icono(iconos_operativo.get(campo, "gota"), tx, y + 62, 24)
            texto(tx + 30, y + 64, ancho_tile - 30, 18, f"{etiqueta} · {unidad}", 8, TEXTO_TENUE)
            texto(tx, y + 82, ancho_tile, 32, "", 18, TEXTO, negrita=True, enlace=vinculo(fila_dato, 0))
            texto(tx, y + 114, ancho_tile, 20, "", 9, CIAN, negrita=True, enlace=vinculo(fila_dato, 2))
            texto(tx, y + 132, ancho_tile, 18, "", 7, TEXTO_TENUE, enlace=texto_de("comparacion"))

        nombres_series = [dict((t[0], t[1]) for t in tarjetas_operativo)[c] for c in series_operativo]
        columnas_op = libro.add_chart({"type": "column"})
        colores_col = {"produccion_kboed": BARRA_APAGADA, "shale_oil_kbbld": CIAN}
        for k, campo in enumerate(series_operativo):
            if campo == "precio_crudo_usd_bbl":
                continue
            columnas_op.add_series({
                "name": nombres_series[k],
                "categories": categorias(operativo_serie_inicio, operativo_serie_fin),
                "values": serie(operativo_serie_inicio, operativo_serie_fin, k),
                "fill": {"color": colores_col.get(campo, AZUL_PROFUNDO)}, "border": {"none": True},
                "gap": 70, "overlap": 100,
            })
        if "precio_crudo_usd_bbl" in series_operativo:
            k = series_operativo.index("precio_crudo_usd_bbl")
            precio = libro.add_chart({"type": "line"})
            precio.add_series({
                "name": nombres_series[k],
                "categories": categorias(operativo_serie_inicio, operativo_serie_fin),
                "values": serie(operativo_serie_inicio, operativo_serie_fin, k),
                "y2_axis": True, "smooth": True,
                "line": {"color": AMBAR, "width": 2.5},
                "marker": {"type": "circle", "size": 5, "fill": {"color": "#0b182c"}, "border": {"color": AMBAR, "width": 1.5}},
                "data_labels": {"value": True, "position": "above", "num_format": "0",
                                "font": {"name": FUENTE, "size": 7, "color": AMBAR},
                                "custom": [{"delete": True}] * (HISTORIA - 1) + [None]},
            })
            precio.set_y2_axis({"num_font": {**fuente_eje, "color": AMBAR}, "num_format": '0', "line": {"none": True},
                                "major_tick_mark": "none", "min": 0,
                                "major_gridlines": {"visible": False}})
            columnas_op.combine(precio)
        ejes_limpios(columnas_op, formato_y="0")
        columnas_op.set_y_axis({"num_font": fuente_eje, "num_format": "0", "line": {"none": True}, "min": 0,
                                "major_tick_mark": "none",
                                "major_gridlines": {"visible": True, "line": {"color": GRILLA, "width": 0.75, "dash_type": "dash"}}})
        columnas_op.set_plotarea({"fill": {"none": True}, "border": {"none": True},
                                  "layout": {"x": 0.06, "y": 0.08, "width": 0.86, "height": 0.78}})
        insertar(columnas_op, x + 6, y + 180, w - 12, h - 186)
        texto(x + 12, y + 156, 170, 20, "■ Producción total, kboe/d", 8, "#6b8bb8", negrita=True)
        texto(x + 186, y + 156, 170, 20, "■ Petróleo shale, kbbl/d", 8, CIAN, negrita=True)
        texto(x + w - 212, y + 156, 200, 20, "━ Precio del crudo, US$/bbl", 8, AMBAR, negrita=True, alinear="right")

    # --- mercado ------------------------------------------------------------
    x, y, w, h = titulo_tarjeta("mercado", "Cómo reaccionó el mercado al balance", icono="velas")
    if mercado_sel is not None:
        texto(x + 54, y + 40, w - 66, 20, "", 8, TEXTO_TENUE, enlace=texto_de("mercado_sub"))
        fichas = [
            (1, "Precio del ADR", TEXTO), (2, "Retorno del día", TEXTO),
            (3, "Anormal, contra Vista y Brent", CIAN), (4, "Acumulado, cuatro ruedas", CIAN),
        ]
        ancho_ficha = 205
        for i, (indice, rotulo, color) in enumerate(fichas):
            fx = x + 12 + (i % 2) * (ancho_ficha + 12)
            fy = y + 70 + (i // 2) * 76
            poner_icono(("dolar", "velas", "rayo", "flujo")[i], fx, fy, 18, ficha=False)
            texto(fx + 22, fy, ancho_ficha - 22, 18, rotulo, 8, TEXTO_TENUE)
            texto(fx, fy + 18, ancho_ficha, 34, "", 20, color, negrita=True, enlace=vinculo(mercado_sel, indice))
        texto(x + 12, y + 226, 170, 20, "", 8, AMBAR, negrita=True, enlace=texto_de("mercado_t"))
        texto(x + 180, y + 226, 34, 20, "t =", 8, TEXTO_TENUE, alinear="right")
        texto(x + 214, y + 226, 50, 20, "", 8, TEXTO, negrita=True, enlace=vinculo(mercado_sel, 5))
        texto(x + 12, y + 248, 150, 20, "Riesgo país ese día", 8, TEXTO_TENUE)
        texto(x + 150, y + 248, 110, 20, "", 8, TEXTO, negrita=True, alinear="right", enlace=vinculo(mercado_sel, 8))
        texto(x + 12, y + h - 30, 430, 22,
              "Anormal: lo que se movió la acción más allá de lo que explican Vista y el Brent ese día.",
              7, TEXTO_TENUE)

        gx = x + 470
        texto(gx, y + 64, 300, 20, "Retorno anormal en cada balance, doce trimestres", 8, TEXTO_SUAVE)
        texto(x + w - 212, y + 64, 200, 20, "◆ anormal acumulado, 4 ruedas", 8, "#818cf8", negrita=True, alinear="right")
        reaccion = libro.add_chart({"type": "column"})
        reaccion.add_series({
            "name": "Retorno anormal",
            "categories": categorias(mercado_serie_inicio, mercado_serie_fin),
            "values": serie(mercado_serie_inicio, mercado_serie_fin, 0),
            "fill": {"color": BARRA_APAGADA}, "border": {"none": True}, "gap": 60,
            "invert_if_negative": True, "invert_if_negative_color": "#7c5a1e",
            "points": [None] * (HISTORIA - 1) + [{"fill": {"color": AMBAR}, "border": {"none": True}}],
            "data_labels": {"value": True, "position": "outside_end", "num_format": '"+"0.0%;"−"0.0%',
                            "font": {"name": FUENTE, "size": 8, "bold": True, "color": TEXTO},
                            "custom": [{"delete": True}] * (HISTORIA - 1) + [None]},
        })
        acumulado = libro.add_chart({"type": "line"})
        acumulado.add_series({
            "name": "Anormal acumulado 0–3",
            "categories": categorias(mercado_serie_inicio, mercado_serie_fin),
            "values": serie(mercado_serie_inicio, mercado_serie_fin, 1),
            "line": {"none": True},
            "marker": {"type": "diamond", "size": 7, "fill": {"color": "#818cf8"}, "border": {"none": True}},
        })
        reaccion.combine(acumulado)
        ejes_limpios(reaccion, formato_y='0%')
        reaccion.set_plotarea({"fill": {"none": True}, "border": {"none": True},
                               "layout": {"x": 0.07, "y": 0.06, "width": 0.91, "height": 0.8}})
        insertar(reaccion, gx - 6, y + 86, w - 470, h - 92)

    # --- sensibilidad --------------------------------------------------------
    x, y, w, h = titulo_tarjeta("sensibilidad", "Qué mueve a la acción", icono="balanza")
    if mercado:
        texto(x + 54, y + 40, w - 66, 20, "Retornos diarios desde 2021 (transform/market_reaction.py)", 8, TEXTO_TENUE)
        riesgo = mercado.get("riesgo_pais", {})
        resumen = mercado.get("resumen", {})
        f_pp = libro.add_format({**base, "font_color": TEXTO, "num_format": '"+"0.0%;"−"0.0%'})
        f_x = libro.add_format({**base, "font_color": TEXTO, "num_format": '0.00'})
        f_n = libro.add_format({**base, "font_color": TEXTO, "num_format": '0'})
        # Constantes del estudio: no dependen del trimestre elegido, pero se
        # escriben en el bloque de datos como todo lo demás.
        bloque("Mercado: sensibilidades (constantes del estudio)", ["Valor"])
        constantes = {}
        for clave, etiqueta, valor, formato in [
            ("pb", "Efecto de 100 pb de riesgo país", riesgo.get("efecto_100pb_riesgo_pais"), f_pp),
            ("brent", "Beta contra el Brent", riesgo.get("beta_brent"), f_x),
            ("r2", "R² del modelo", riesgo.get("r2"), f_porcentaje),
            ("negativos", "Balances con reacción negativa", resumen.get("con_reaccion_negativa"), f_n),
            ("balances", "Balances estudiados", resumen.get("balances"), f_n),
            ("mediano", "Retorno anormal mediano", resumen.get("retorno_anormal_mediano"), f_pp),
        ]:
            if valor is not None:
                constantes[clave] = renglon(etiqueta, [(valor, formato)])
        filas_sens = [
            ("pb", "Cada 100 pb más de riesgo país", "en la acción, el mismo día"),
            ("brent", "Beta contra el Brent", "por cada 1% que se mueve el crudo"),
            ("mediano", "Retorno anormal mediano", "el día de cada balance"),
        ]
        for i, (clave, rotulo, detalle) in enumerate(filas_sens):
            if clave not in constantes:
                continue
            yy = y + 70 + i * 58
            poner_icono({"pb": "rayo", "brent": "barril", "mediano": "velas"}[clave], x + 12, yy + 2, 32)
            texto(x + 52, yy, w - 170, 20, rotulo, 9, TEXTO_SUAVE)
            texto(x + 52, yy + 18, w - 170, 18, detalle, 7, TEXTO_TENUE)
            texto(x + w - 130, yy, 118, 32, "", 17, CIAN, negrita=True, alinear="right", enlace=vinculo(constantes[clave]))
        if "negativos" in constantes and "balances" in constantes:
            texto(x + 12, y + h - 52, 44, 30, "", 17, AMBAR, negrita=True, alinear="right",
                  enlace=vinculo(constantes["negativos"]))
            texto(x + 56, y + h - 50, 40, 26, "de", 9, TEXTO_SUAVE, alinear="center")
            texto(x + 96, y + h - 52, 44, 30, "", 17, TEXTO, negrita=True, enlace=vinculo(constantes["balances"]))
            texto(x + 140, y + h - 54, w - 152, 36, "balances cayeron más de lo que explicaban Vista y el Brent", 8,
                  TEXTO_SUAVE)

    # --- tarjetas de análisis ------------------------------------------------
    # El puente, el simulador, la deuda, los comparables y el territorio viven
    # en su propio módulo: son otra lectura y ya son medio tablero.
    from types import SimpleNamespace

    contexto = SimpleNamespace(
        libro=libro, hoja=hoja, nombre=nombre, letra=letra, FUENTE=FUENTE, CONTROLES=CONTROLES,
        SEL=SEL, CMP=CMP, COMP=COMP, SEG=SEG, DIMENSION=DIMENSION,
        texto=texto, texto_de=texto_de, poner_icono=poner_icono, titulo_tarjeta=titulo_tarjeta, aviso=aviso,
        insertar=insertar, ejes_limpios=ejes_limpios, eje_oculto=eje_oculto,
        bloque=bloque, renglon=renglon, local=local, vinculo=vinculo, serie=serie, categorias=categorias,
        control=control, validar=validar, etiqueta_trimestre=etiqueta_trimestre,
        fila=lambda: fila, saltar=saltar, columna_valor=lambda i: DATOS_VALORES[i][0],
        fmt={
            "millones": f_millones, "millones_vacio": f_millones_vacio, "porcentaje": f_porcentaje,
            "porcentaje_decimal": f_porcentaje_decimal, "porcentaje_chico": f_porcentaje_chico,
            "variacion": f_variacion, "variacion_corta": f_variacion_corta, "numero": f_numero,
            "decimal": f_decimal, "entero": f_entero, "miles": f_miles, "multiplo": f_multiplo,
            "texto": f_texto, "texto_izq": f_texto_izq,
        },
    )
    tablero_analisis.escribir(contexto, procesados or PROCESADOS_POR_DEFECTO)

    # --- pie ----------------------------------------------------------------
    texto(PANEL_X + 24, FILA_H_Y + FILA_H_H + 1, PANEL_W - 48, 20,
          "Las cuatro listas cambian todo el tablero. Los botones llevan a cada hoja; los datos que alimentan "
          "cada tarjeta están al pie de esta hoja.", 7, TEXTO_TENUE)

    # Protegida sin contraseña: las listas se pueden cambiar y el resto se
    # puede seleccionar y auditar, pero no se arrastra una tarjeta sin querer.
    hoja.protect("", {"select_locked_cells": True, "select_unlocked_cells": True})
    hoja.activate()
