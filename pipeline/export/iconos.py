"""Los íconos de los tableros: barril, gota, cigüeña de bombeo, llama, refinería.

Se dibujan acá, con Pillow, y no se bajan de ningún set: así tienen todos el
mismo trazo y la misma paleta que el tablero, y no hay licencias de por medio.
Los usan el tablero de Excel (export/tablero.py) y el de Power BI
(export/powerbi_tablero.py), así que un ícono cambia en los dos a la vez.

Cómo están hechos: cada ícono es una silueta blanca dibujada en una grilla de
100 × 100 a cuatro veces el tamaño final, que se pinta con un degradado cian a
azul y se apoya en una ficha redondeada oscura. Dibujar grande y achicar es lo
que le da bordes suaves: Pillow no suaviza los polígonos.
"""

from __future__ import annotations

import base64
import io
import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SOBREMUESTREO = 4
BASE = 100  # la grilla en la que se dibuja cada silueta

CIAN = (34, 211, 238)
AZUL = (59, 130, 246)
AMBAR = (251, 191, 36)
FICHA_ARRIBA = (22, 52, 88)
FICHA_ABAJO = (10, 28, 52)
FICHA_BORDE = (56, 104, 160)


# --------------------------------------------------------------------------- #
# Primitivas
# --------------------------------------------------------------------------- #
class Lienzo:
    """Una silueta en coordenadas 0–100 sobre una máscara en escala de grises."""

    def __init__(self, lado: int):
        self.lado = lado
        self.mascara = Image.new("L", (lado, lado), 0)
        self.d = ImageDraw.Draw(self.mascara)
        self.k = lado / BASE

    def p(self, x: float, y: float) -> tuple[float, float]:
        return x * self.k, y * self.k

    def caja(self, x0, y0, x1, y1) -> tuple[float, float, float, float]:
        return (*self.p(x0, y0), *self.p(x1, y1))

    def poligono(self, puntos, lleno: int = 255) -> None:
        self.d.polygon([self.p(x, y) for x, y in puntos], fill=lleno)

    def linea(self, puntos, ancho: float, lleno: int = 255, redonda: bool = True) -> None:
        pts = [self.p(x, y) for x, y in puntos]
        w = max(1, round(ancho * self.k))
        self.d.line(pts, fill=lleno, width=w, joint="curve")
        if redonda:
            r = w / 2
            for x, y in (pts[0], pts[-1]):
                self.d.ellipse((x - r, y - r, x + r, y + r), fill=lleno)

    def elipse(self, x0, y0, x1, y1, lleno: int | None = 255, borde: int | None = None, ancho: float = 0) -> None:
        self.d.ellipse(self.caja(x0, y0, x1, y1), fill=lleno, outline=borde,
                       width=max(1, round(ancho * self.k)) if borde is not None else 0)

    def rect(self, x0, y0, x1, y1, radio: float = 0, lleno: int | None = 255, borde: int | None = None,
             ancho: float = 0) -> None:
        self.d.rounded_rectangle(self.caja(x0, y0, x1, y1), radius=radio * self.k, fill=lleno, outline=borde,
                                 width=max(1, round(ancho * self.k)) if borde is not None else 0)

    def arco(self, x0, y0, x1, y1, desde: float, hasta: float, ancho: float, lleno: int = 255) -> None:
        self.d.arc(self.caja(x0, y0, x1, y1), desde, hasta, fill=lleno, width=max(1, round(ancho * self.k)))

    def texto(self, x: float, y: float, contenido: str, tamanio: float, lleno: int = 255) -> None:
        fuente = fuente_negrita(round(tamanio * self.k))
        caja = self.d.textbbox((0, 0), contenido, font=fuente)
        cx, cy = self.p(x, y)
        self.d.text((cx - (caja[0] + caja[2]) / 2, cy - (caja[1] + caja[3]) / 2), contenido, font=fuente, fill=lleno)


@lru_cache(maxsize=16)
def fuente_negrita(tamanio: int) -> ImageFont.ImageFont:
    for ruta in ("C:/Windows/Fonts/seguibl.ttf", "C:/Windows/Fonts/segoeuib.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(ruta, tamanio)
        except OSError:
            continue
    return ImageFont.load_default(size=tamanio)


def gota_puntos(cx: float, cy_punta: float, alto: float, ancho: float, pasos: int = 90) -> list[tuple[float, float]]:
    """La silueta de una gota: punta arriba, panza redonda abajo."""
    puntos = []
    for i in range(pasos):
        t = 2 * math.pi * i / pasos
        x = math.sin(t) * math.sin(t / 2) ** 1.25
        y = (1 - math.cos(t)) / 2
        puntos.append((cx + x * ancho / 2, cy_punta + y * alto))
    return puntos


# --------------------------------------------------------------------------- #
# Siluetas
# --------------------------------------------------------------------------- #
def gota(c: Lienzo) -> None:
    c.poligono(gota_puntos(50, 10, 82, 62))
    # El brillo: una media luna recortada adentro.
    c.arco(30, 50, 62, 82, 150, 215, 5, lleno=0)


def barril(c: Lienzo) -> None:
    # Cuerpo levemente abombado: dos elipses aplastadas en los costados.
    c.rect(24, 16, 76, 86, radio=10)
    c.elipse(18, 16, 34, 86)
    c.elipse(66, 16, 82, 86)
    # Aros y la tapa.
    for y in (30, 72):
        c.linea([(20, y), (80, y)], 5, lleno=0, redonda=False)
    c.elipse(30, 10, 70, 22, lleno=255)
    c.elipse(36, 13, 64, 19, lleno=0)
    # La gota en el medio del barril.
    c.poligono(gota_puntos(50, 38, 28, 20), lleno=0)


def cigüeña(c: Lienzo) -> None:
    """El aparato de bombeo: balancín, cabeza de caballo y contrapeso."""
    c.linea([(8, 88), (92, 88)], 5)
    # Caballete en A.
    c.linea([(38, 86), (50, 40), (62, 86)], 6)
    c.linea([(42, 70), (58, 70)], 4)
    # Balancín inclinado y la cabeza curva en el extremo.
    c.linea([(18, 44), (80, 30)], 7)
    c.arco(70, 22, 94, 50, 280, 80, 7)
    # Varilla hacia el pozo y el contrapeso.
    c.linea([(86, 50), (86, 86)], 3)
    c.elipse(10, 44, 30, 64)
    c.elipse(46, 32, 56, 42, lleno=0)


def llama(c: Lienzo) -> None:
    puntos = []
    for i in range(120):
        t = 2 * math.pi * i / 120
        r = 1 + 0.18 * math.sin(3 * t)
        x = math.sin(t) * math.sin(t / 2) ** 1.6 * r
        y = (1 - math.cos(t)) / 2
        puntos.append((50 + x * 30, 8 + y * 84))
    c.poligono(puntos)
    c.poligono(gota_puntos(50, 46, 42, 26), lleno=0)
    c.poligono(gota_puntos(50, 60, 26, 14))


def refineria(c: Lienzo) -> None:
    c.linea([(6, 88), (94, 88)], 5)
    # Dos torres de destilación con anillos.
    c.rect(18, 30, 34, 86, radio=4)
    c.rect(40, 18, 56, 86, radio=4)
    for y in (44, 60):
        c.linea([(16, y), (36, y)], 3, lleno=0, redonda=False)
    for y in (34, 52, 70):
        c.linea([(38, y), (58, y)], 3, lleno=0, redonda=False)
    # Tanque y chimenea con su llama.
    c.rect(62, 58, 90, 86, radio=6)
    c.rect(72, 30, 80, 58)
    c.poligono(gota_puntos(76, 10, 20, 12))


def dolar(c: Lienzo) -> None:
    c.elipse(10, 10, 90, 90)
    c.elipse(18, 18, 82, 82, lleno=0)
    c.texto(50, 50, "$", 52)


def casco(c: Lienzo) -> None:
    """Casco de obra: la inversión en el campo."""
    c.d.pieslice(c.caja(18, 22, 82, 86), 180, 360, fill=255)
    c.rect(8, 52, 92, 64, radio=6)
    c.rect(44, 18, 56, 54, radio=4, lleno=0)
    c.rect(47, 24, 53, 50, radio=2)


def velas(c: Lienzo) -> None:
    for x, (y0, y1, m0, m1) in zip((24, 50, 76), ((40, 72, 30, 84), (26, 58, 16, 70), (46, 76, 38, 88))):
        c.linea([(x, m0), (x, m1)], 3)
        c.rect(x - 9, y0, x + 9, y1, radio=3)
    c.linea([(8, 62), (32, 50), (54, 58), (92, 20)], 5)
    c.poligono([(92, 20), (78, 20), (92, 34)])


def pin(c: Lienzo) -> None:
    """El marcador de mapa: una gota dada vuelta, con la punta en el lugar."""
    c.poligono([(x, 100 - y) for x, y in gota_puntos(50, 6, 86, 66)])
    c.elipse(37, 20, 63, 46, lleno=0)
    c.elipse(30, 86, 70, 96, lleno=None, borde=255, ancho=3)


def balanza(c: Lienzo) -> None:
    c.linea([(50, 14), (50, 84)], 5)
    c.linea([(30, 86), (70, 86)], 6)
    c.linea([(14, 26), (86, 26)], 5)
    c.elipse(44, 8, 56, 20)
    for x in (22, 78):
        c.linea([(x, 28), (x - 12, 56)], 2)
        c.linea([(x, 28), (x + 12, 56)], 2)
        c.d.chord(c.caja(x - 16, 44, x + 16, 70), 0, 180, fill=255)


def porcentaje(c: Lienzo) -> None:
    c.elipse(14, 14, 42, 42, lleno=None, borde=255, ancho=8)
    c.elipse(58, 58, 86, 86, lleno=None, borde=255, ancho=8)
    c.linea([(78, 16), (22, 84)], 8)


def calendario(c: Lienzo) -> None:
    c.rect(12, 18, 88, 88, radio=10)
    c.rect(20, 36, 80, 80, radio=4, lleno=0)
    for x in (32, 68):
        c.rect(x - 4, 8, x + 4, 28, radio=3)
    for i, (x, y) in enumerate([(32, 48), (50, 48), (68, 48), (32, 66), (50, 66)]):
        c.rect(x - 6, y - 6, x + 6, y + 6, radio=2)


def engranaje(c: Lienzo) -> None:
    dientes = []
    for i in range(16):
        t = 2 * math.pi * i / 16
        r = 42 if i % 2 == 0 else 32
        for dt in (-0.14, 0.14):
            dientes.append((50 + r * math.cos(t + dt), 50 + r * math.sin(t + dt)))
    c.poligono(dientes)
    c.elipse(34, 34, 66, 66, lleno=0)
    c.elipse(42, 42, 58, 58)
    c.elipse(46, 46, 54, 54, lleno=0)


def flujo(c: Lienzo) -> None:
    """Flechas en círculo alrededor de una gota: la caja que da vuelta."""
    c.arco(12, 12, 88, 88, 200, 340, 8)
    c.arco(12, 12, 88, 88, 20, 160, 8)
    c.poligono([(84, 36), (94, 52), (74, 50)])
    c.poligono([(16, 64), (6, 48), (26, 50)])
    c.poligono(gota_puntos(50, 30, 42, 28))


def ducto(c: Lienzo) -> None:
    c.linea([(8, 30), (46, 30), (46, 70), (92, 70)], 12, redonda=False)
    for x, y, vertical in ((24, 30, True), (46, 50, False), (72, 70, True)):
        if vertical:
            c.rect(x - 4, y - 12, x + 4, y + 12, radio=2)
        else:
            c.rect(x - 12, y - 4, x + 12, y + 4, radio=2)
    c.elipse(40, 10, 52, 22)


def rayo(c: Lienzo) -> None:
    c.poligono([(58, 6), (22, 56), (46, 56), (38, 94), (78, 40), (54, 40)])


SILUETAS = {
    "gota": gota,
    "barril": barril,
    "cigueña": cigüeña,
    "llama": llama,
    "refineria": refineria,
    "dolar": dolar,
    "casco": casco,
    "velas": velas,
    "pin": pin,
    "balanza": balanza,
    "porcentaje": porcentaje,
    "calendario": calendario,
    "engranaje": engranaje,
    "flujo": flujo,
    "ducto": ducto,
    "rayo": rayo,
}


# --------------------------------------------------------------------------- #
# Composición
# --------------------------------------------------------------------------- #
def _degradado(lado: int, arriba: tuple, abajo: tuple) -> Image.Image:
    t = np.linspace(0, 1, lado)[:, None]
    x = np.linspace(0, 1, lado)[None, :]
    mezcla = (t * 0.75 + x * 0.25)[..., None]
    rgb = np.array(arriba) * (1 - mezcla) + np.array(abajo) * mezcla
    return Image.fromarray(rgb.astype(np.uint8), "RGB")


@lru_cache(maxsize=128)
def silueta(nombre: str, lado: int) -> Image.Image:
    """La máscara suavizada del ícono, a `lado` píxeles."""
    grande = Lienzo(lado * SOBREMUESTREO)
    SILUETAS[nombre](grande)
    return grande.mascara.resize((lado, lado), Image.LANCZOS)


@lru_cache(maxsize=128)
def icono(nombre: str, lado: int = 64, ficha: bool = True, tinte: str = "cian") -> Image.Image:
    """El ícono listo: silueta con degradado, con o sin ficha redondeada detrás."""
    colores = {"cian": (CIAN, AZUL), "ambar": (AMBAR, (234, 88, 12)), "blanco": ((255, 255, 255), (186, 230, 253))}
    arriba, abajo = colores[tinte]
    lienzo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    interior = lado
    if ficha:
        grande = lado * SOBREMUESTREO
        fondo = _degradado(grande, FICHA_ARRIBA, FICHA_ABAJO).convert("RGBA")
        mascara = Image.new("L", (grande, grande), 0)
        ImageDraw.Draw(mascara).rounded_rectangle((0, 0, grande - 1, grande - 1), radius=grande * 0.26, fill=255)
        borde = Image.new("L", (grande, grande), 0)
        ImageDraw.Draw(borde).rounded_rectangle((0, 0, grande - 1, grande - 1), radius=grande * 0.26,
                                                outline=255, width=max(2, grande // 40))
        fondo.putalpha(mascara)
        linea = Image.new("RGBA", (grande, grande), (*FICHA_BORDE, 255))
        linea.putalpha(borde)
        fondo.alpha_composite(linea)
        lienzo.alpha_composite(fondo.resize((lado, lado), Image.LANCZOS))
        interior = round(lado * 0.64)

    forma = silueta(nombre, interior)
    color = _degradado(interior, arriba, abajo).convert("RGBA")
    # Un halo apenas más ancho que la silueta: el ícono "brilla" sobre el fondo oscuro.
    halo = Image.new("RGBA", (interior, interior), (*arriba, 0))
    halo.putalpha(forma.filter(ImageFilter.GaussianBlur(max(1, interior / 18))).point(lambda v: v * 0.45))
    color.putalpha(forma)
    desplazamiento = ((lado - interior) // 2, (lado - interior) // 2)
    lienzo.alpha_composite(halo, desplazamiento)
    lienzo.alpha_composite(color, desplazamiento)
    return lienzo


def marca_de_agua(nombre: str, lado: int, alfa: int = 28) -> Image.Image:
    """La silueta en blanco muy tenue, para el fondo de una tarjeta."""
    forma = silueta(nombre, lado).point(lambda v: v * alfa // 255)
    capa = Image.new("RGBA", (lado, lado), (190, 225, 255, 0))
    capa.putalpha(forma)
    return capa


def png(nombre: str, lado: int = 64, **opciones) -> io.BytesIO:
    salida = io.BytesIO()
    icono(nombre, lado, **opciones).save(salida, format="PNG")
    salida.seek(0)
    return salida


def data_uri(nombre: str, lado: int = 96, **opciones) -> str:
    return "data:image/png;base64," + base64.b64encode(png(nombre, lado, **opciones).getvalue()).decode()


def logo(lado: int = 128) -> Image.Image:
    """La marca del tablero: una gota dentro de un hexágono, con una torre adentro."""
    grande = lado * SOBREMUESTREO
    c = Lienzo(grande)
    hexagono = [(50 + 46 * math.cos(math.radians(a)), 50 + 46 * math.sin(math.radians(a))) for a in range(-90, 270, 60)]
    c.poligono(hexagono)
    c.poligono([(50 + 38 * math.cos(math.radians(a)), 50 + 38 * math.sin(math.radians(a))) for a in range(-90, 270, 60)],
               lleno=0)
    c.poligono(gota_puntos(50, 20, 62, 44))
    # Cigüeña mínima recortada dentro de la gota.
    c.linea([(38, 70), (64, 62)], 4, lleno=0)
    c.linea([(46, 80), (52, 64), (58, 80)], 3, lleno=0)
    forma = c.mascara.resize((lado, lado), Image.LANCZOS)
    color = _degradado(lado, CIAN, AZUL).convert("RGBA")
    color.putalpha(forma)
    halo = Image.new("RGBA", (lado, lado), (*CIAN, 0))
    halo.putalpha(forma.filter(ImageFilter.GaussianBlur(lado / 20)).point(lambda v: v * 0.5))
    salida = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    salida.alpha_composite(halo)
    salida.alpha_composite(color)
    return salida


def hoja_de_muestra(ruta: str, lado: int = 96) -> None:
    """Todos los íconos en una imagen, para mirarlos juntos."""
    nombres = list(SILUETAS)
    columnas = 6
    filas = math.ceil((len(nombres) + 1) / columnas)
    hoja = Image.new("RGBA", (columnas * (lado + 24) + 24, filas * (lado + 24) + 24), (5, 11, 22, 255))
    for i, nombre in enumerate(["logo", *nombres]):
        x, y = 24 + (i % columnas) * (lado + 24), 24 + (i // columnas) * (lado + 24)
        imagen = logo(lado) if nombre == "logo" else icono(nombre, lado)
        hoja.alpha_composite(imagen, (x, y))
    hoja.convert("RGB").save(ruta)
