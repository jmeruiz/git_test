"""
Efectos para los movimientos gelatina: fuego y humo (cohete), burbujas (nadar),
polvo y rayitas (trompo) y estrellas (voltereta).

No guardan estado: cada partícula se calcula a partir del tiempo `s` y de un número fijo,
así cada cuadro se puede dibujar solo y el video sale igual cada vez.
"""
import math

import cv2
import numpy as np


def _azar(k, sal=0.0):
    """Número entre 0 y 1 que parece al azar pero siempre es el mismo para el mismo k."""
    v = math.sin(k * 12.9898 + sal * 78.233) * 43758.5453
    return v - math.floor(v)


def _mezclar(cuadro, capa, mascara, opacidad):
    """Pega `capa` sobre `cuadro` donde `mascara` > 0, con la opacidad dada (0 a 1). Solo trabaja en esa zona."""
    filas, cols = np.where(mascara.any(axis=1))[0], np.where(mascara.any(axis=0))[0]
    if not len(filas):
        return
    h, w = mascara.shape
    y0, y1 = max(0, filas[0] - 6), min(h, filas[-1] + 7)
    x0, x1 = max(0, cols[0] - 6), min(w, cols[-1] + 7)
    a = (cv2.GaussianBlur(mascara[y0:y1, x0:x1], (0, 0), 2).astype(np.float32) / 255.0 * opacidad)[:, :, None]
    zona = cuadro[y0:y1, x0:x1]
    zona[:] = (capa[y0:y1, x0:x1].astype(np.float32) * a + zona.astype(np.float32) * (1 - a)).astype(np.uint8)


def _llama(ancho, largo, x, y, s, fase):
    """Contorno de una llama que cuelga desde (x, y): ancha arriba, punta abajo, ondulando."""
    izq, der = [], []
    for i in range(25):
        t = i / 24
        medio = ancho / 2 * (1 - t) ** 0.65 * (1 + 0.12 * math.sin(s * 23 + t * 9 + fase))
        centro = x + math.sin(t * 4 + s * 17 + fase) * ancho * 0.12 * t
        py = y + t * largo
        izq.append((centro - medio, py))
        der.append((centro + medio, py))
    return np.array(izq + der[::-1], np.int32)


def _region(cuadro, x0, y0, x1, y1):
    h, w = cuadro.shape[:2]
    x0, y0, x1, y1 = max(0, int(x0)), max(0, int(y0)), min(w, int(x1)), min(h, int(y1))
    return (x0, y0, x1, y1) if x0 < x1 and y0 < y1 else None


def fuego(cuadro, x, y, ancho, s, fuerza=1.0):
    """
    Llama de cohete que nace en (x, y) —un poquito dentro del dibujo, que se pinta encima
    y la tapa, así se ve pegada— y cae hacia abajo. `ancho` es el ancho de la boca.

    Como en los efectos de cine 2D: capas con bordes difuminados (rojo-naranja afuera,
    amarillo y casi blanco en el centro, más corto, para que el calor parezca salir de la boca),
    pintadas con transparencia suave, y encima un resplandor que se SUMA como luz.
    """
    if fuerza <= 0:
        return
    largo = ancho * (0.9 + 1.7 * fuerza) * (1 + 0.07 * math.sin(s * 31))
    margen = ancho * 0.9 + 24
    r = _region(cuadro, x - ancho - margen, y - margen, x + ancho + margen, y + largo + margen)
    if not r:
        return
    x0, y0, x1, y1 = r
    h, w = y1 - y0, x1 - x0
    # todo lo difuminado se calcula a 1/3 del tamaño y después se agranda: es borroso
    # a propósito, así que no se nota, y es unas 9 veces más rápido
    q = 1 / 3
    hc, wc = max(2, int(h * q)), max(2, int(w * q))
    color = np.zeros((hc, wc, 3), np.float32)   # color ya multiplicado por su transparencia
    alfa = np.zeros((hc, wc), np.float32)
    capas = (  # (ancho, largo, color BGR, opacidad, difuminado)
        (1.00, 1.00, (35, 85, 240), 0.80, 0.10),
        (0.74, 0.74, (20, 150, 255), 0.90, 0.07),
        (0.46, 0.42, (170, 235, 255), 0.95, 0.05),
    )
    for i, (fa, fl, bgr, op, dif) in enumerate(capas):
        m = np.zeros((hc, wc), np.uint8)
        forma = (_llama(ancho * fa, largo * fl, x, y, s, fase=i * 1.3) - np.array([x0, y0])) * q
        cv2.fillPoly(m, [forma.astype(np.int32)], 255, cv2.LINE_AA)
        m = cv2.GaussianBlur(m, (0, 0), max(0.6, ancho * dif * q)).astype(np.float32) / 255.0 * op
        color = color * (1 - m[..., None]) + np.array(bgr, np.float32)[None, None] / 255.0 * m[..., None]
        alfa = alfa * (1 - m) + m

    # resplandor y chispas: se suman como luz ("screen"), brillan más sobre fondos oscuros
    luz = np.zeros((hc, wc), np.uint8)
    cv2.ellipse(luz, (int((x - x0) * q), int((y - y0 + largo * 0.25) * q)), (int(ancho * 0.95 * q), int(largo * 0.55 * q)),
                0, 0, 360, 255, -1)
    for k in range(int(12 * fuerza) + 3):
        edad = (s * 1.8 + _azar(k, 7)) % 1.0
        px = x - x0 + (_azar(k, 8) - 0.5) * ancho * (0.5 + 1.1 * edad)
        py = y - y0 + largo * (0.45 + 0.75 * edad)
        cv2.circle(luz, (int(px * q), int(py * q)), max(1, int(4 * q * (1 - edad)) + 1), int(255 * (1 - edad)), -1, cv2.LINE_AA)
    luz = cv2.GaussianBlur(luz, (0, 0), max(1.0, ancho * 0.18 * q)).astype(np.float32) / 255.0 * (0.35 + 0.35 * fuerza)

    # de vuelta al tamaño real
    color = cv2.resize(color, (w, h), interpolation=cv2.INTER_LINEAR)
    alfa = cv2.resize(alfa, (w, h), interpolation=cv2.INTER_LINEAR)
    luz = cv2.resize(luz, (w, h), interpolation=cv2.INTER_LINEAR)
    zona = cuadro[y0:y1, x0:x1].astype(np.float32) / 255.0
    zona = zona * (1 - alfa[..., None]) + color
    brillo = luz[..., None] * np.array((60, 170, 255), np.float32)[None, None] / 255.0
    zona = 1 - (1 - zona) * (1 - brillo)
    cuadro[y0:y1, x0:x1] = np.clip(zona * 255, 0, 255).astype(np.uint8)


def resplandor(cuadro, x, y, radio, intensidad):
    """Luz cálida que la llama echa sobre la parte de abajo del dibujo y el suelo (se suma como luz)."""
    if intensidad <= 0:
        return
    r = _region(cuadro, x - radio, y - radio, x + radio, y + radio)
    if not r:
        return
    x0, y0, x1, y1 = r
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    d = np.sqrt((xx - x) ** 2 + (yy - y) ** 2) / radio
    luz = (np.clip(1 - d, 0, 1) ** 2 * intensidad)[..., None] * np.array((50, 150, 255), np.float32)[None, None] / 255.0
    zona = cuadro[y0:y1, x0:x1].astype(np.float32) / 255.0
    cuadro[y0:y1, x0:x1] = np.clip((1 - (1 - zona) * (1 - luz)) * 255, 0, 255).astype(np.uint8)


def humo(cuadro, x, y, ancho, s, cantidad=1.0, n=30):
    """Nubes de humo que se esparcen a los lados desde el suelo."""
    if cantidad <= 0.02:
        return
    capa = cuadro.copy()
    mascara = np.zeros(cuadro.shape[:2], np.uint8)
    for k in range(n):
        edad = (s * 0.8 + _azar(k, 3)) % 1.0
        lado = -1 if k % 2 else 1
        px = x + lado * (0.1 + 1.1 * edad) * ancho * (0.7 + 0.3 * _azar(k, 4))
        py = y - edad * ancho * 0.3 + (_azar(k, 5) - 0.5) * 20
        r = int(ancho * (0.12 + 0.22 * edad))
        gris = int(225 + 25 * _azar(k, 6))
        cv2.circle(capa, (int(px), int(py)), r, (gris, gris, gris), -1, cv2.LINE_AA)
        cv2.circle(mascara, (int(px), int(py)), r, int(255 * (1 - edad)), -1, cv2.LINE_AA)
    _mezclar(cuadro, capa, mascara, 0.85 * min(1.0, cantidad))


def burbujas(cuadro, x, y, s, n=9, semilla=0):
    """Burbujas que suben haciendo ondas desde (x, y)."""
    for k in range(n):
        edad = (s * 0.55 + k / n + semilla * 0.013) % 1.0
        px = x + math.sin(s * 3 + k * 2.3) * 14 + math.sin(k * 5.1) * 25
        py = y - edad * 260
        r = int(5 + 9 * math.sin(k * 1.7) ** 2 + 6 * edad)
        cv2.circle(cuadro, (int(px), int(py)), r, (255, 245, 225), 2, cv2.LINE_AA)
        cv2.circle(cuadro, (int(px - r * 0.35), int(py - r * 0.35)), max(1, r // 4), (255, 255, 255), -1, cv2.LINE_AA)


def polvo(cuadro, x, y, ancho, s, n=10):
    """Polvito que se levanta a los pies del trompo."""
    capa = cuadro.copy()
    mascara = np.zeros(cuadro.shape[:2], np.uint8)
    for k in range(n):
        edad = (s * 1.4 + k / n) % 1.0
        lado = -1 if k % 2 else 1
        px = x + lado * ancho * (0.3 + 0.35 * edad)
        py = y - edad * 18
        r = int(4 + 10 * edad)
        cv2.circle(capa, (int(px), int(py)), r, (170, 200, 215), -1, cv2.LINE_AA)
        cv2.circle(mascara, (int(px), int(py)), r, int(255 * (1 - edad)), -1, cv2.LINE_AA)
    _mezclar(cuadro, capa, mascara, 0.6)


def rayitas(cuadro, x, y, rx, ry, s):
    """Rayitas curvas de velocidad alrededor de algo que gira."""
    for k in range(3):
        inicio = (s * 720 + k * 120) % 360
        cv2.ellipse(cuadro, (int(x), int(y)), (int(rx), int(ry * 0.35)), 0, inicio, inicio + 50, (255, 255, 255), 4, cv2.LINE_AA)


def _estrella(cuadro, x, y, r, color):
    puntos = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        radio = r if i % 2 == 0 else r * 0.45
        puntos.append((x + radio * math.cos(a), y + radio * math.sin(a)))
    cv2.fillPoly(cuadro, [np.array(puntos, np.int32)], color, cv2.LINE_AA)


def estrellas(cuadro, x, y, ancho, k, n=6):
    """Estrellitas que salen alrededor al aterrizar (k de 0 a 1 = tiempo desde que aterrizó)."""
    if k > 0.85:
        return
    colores = [(60, 200, 255), (80, 120, 255), (255, 180, 90), (140, 230, 120)]
    for i in range(n):
        a = math.pi * (0.05 + 0.9 * i / (n - 1))                # abanico hacia arriba
        d = ancho * (0.6 + 0.7 * k)
        px, py = x - math.cos(a) * d, y - math.sin(a) * d * 0.8
        _estrella(cuadro, int(px), int(py), int(22 * (1 - k) + 8), colores[i % len(colores)])


def lineas_velocidad(cuadro, x, y, ancho, alto, hacia_arriba, s, n=5):
    """
    Líneas de velocidad (como en el anime y los cómics): rayitas detrás de algo que va rápido.
    Si sube, van debajo; si baja, van arriba.
    """
    capa = cuadro.copy()
    mascara = np.zeros(cuadro.shape[:2], np.uint8)
    lado = 1 if hacia_arriba else -1
    for k in range(n):
        px = x + (k - (n - 1) / 2) * ancho * 0.22 + math.sin(s * 20 + k) * 3
        inicio = y + lado * (alto * 0.55 + 10 * _azar(k, 70))
        largo = alto * (0.25 + 0.35 * _azar(k + int(s * 12), 71))
        p0, p1 = (int(px), int(inicio)), (int(px), int(inicio + lado * largo))
        cv2.line(capa, p0, p1, (255, 255, 255), 4, cv2.LINE_AA)
        cv2.line(mascara, p0, p1, 200, 4, cv2.LINE_AA)
    _mezclar(cuadro, capa, mascara, 0.75)


def impacto(cuadro, x, y, ancho, k, n=9):
    """
    Golpe al aterrizar (el "cuadro de impacto" del anime): un abanico de rayitas que sale del
    punto de contacto y dos nubecitas de polvo. k de 0 a 1 = lo que va del golpe.
    """
    if k >= 1:
        return
    capa = cuadro.copy()
    mascara = np.zeros(cuadro.shape[:2], np.uint8)
    for i in range(n):
        a = math.pi * (0.08 + 0.84 * i / (n - 1))            # abanico hacia arriba
        r0, r1 = ancho * (0.55 + 0.4 * k), ancho * (0.75 + 0.7 * k)
        p0 = (int(x - math.cos(a) * r0), int(y - math.sin(a) * r0 * 0.45))
        p1 = (int(x - math.cos(a) * r1), int(y - math.sin(a) * r1 * 0.45))
        cv2.line(capa, p0, p1, (255, 255, 255), 5, cv2.LINE_AA)
        cv2.line(mascara, p0, p1, int(255 * (1 - k)), 5, cv2.LINE_AA)
    for lado in (-1, 1):
        cx, r = int(x + lado * ancho * (0.45 + 0.5 * k)), int(ancho * (0.08 + 0.12 * k))
        cv2.circle(capa, (cx, int(y - r * 0.5)), r, (225, 230, 235), -1, cv2.LINE_AA)
        cv2.circle(mascara, (cx, int(y - r * 0.5)), r, int(220 * (1 - k)), -1, cv2.LINE_AA)
    _mezclar(cuadro, capa, mascara, 0.85)


def _corazon(cuadro, x, y, r, color):
    cv2.circle(cuadro, (int(x - r * 0.5), int(y)), int(r * 0.55), color, -1, cv2.LINE_AA)
    cv2.circle(cuadro, (int(x + r * 0.5), int(y)), int(r * 0.55), color, -1, cv2.LINE_AA)
    pts = np.array([(x - r * 1.02, y + r * 0.15), (x + r * 1.02, y + r * 0.15), (x, y + r * 1.25)], np.int32)
    cv2.fillPoly(cuadro, [pts], color, cv2.LINE_AA)


def corazones(cuadro, x, y, k, n=5, semilla=0):
    """Corazoncitos que suben y se desvanecen desde (x, y). k de 0 a 1 = lo que va desde que salieron."""
    if not 0 <= k < 1:
        return
    capa = cuadro.copy()
    mascara = np.zeros(cuadro.shape[:2], np.uint8)
    colores = [(130, 90, 245), (170, 120, 255), (90, 70, 230)]
    for i in range(n):
        px = x + (i - (n - 1) / 2) * 34 + math.sin(k * 6 + i) * 10
        py = y - k * 150 - 25 * _azar(i, semilla)
        r = 11 + 6 * _azar(i, semilla + 1)
        _corazon(capa, px, py, r, colores[i % 3])
        _corazon(mascara, px, py, r, int(255 * (1 - k)))
    _mezclar(cuadro, capa, mascara, 0.95)


def confeti(cuadro, x, y, k, n=26, semilla=0):
    """Lluvia de papelitos de colores que salen hacia arriba y caen. k de 0 a 1."""
    if not 0 <= k < 1:
        return
    colores = [(60, 200, 255), (255, 140, 80), (120, 220, 120), (220, 120, 230), (80, 120, 255)]
    for i in range(n):
        a = math.pi * (0.15 + 0.7 * _azar(i, semilla + 2))
        v = 260 + 180 * _azar(i, semilla + 3)
        px = x - math.cos(a) * v * k
        py = y - math.sin(a) * v * k + 420 * k * k            # sube y después cae
        giro = (k * 720 + i * 40) % 180
        cv2.ellipse(cuadro, (int(px), int(py)), (7, 3), giro, 0, 360, colores[i % 5], -1, cv2.LINE_AA)


def arcoiris(cuadro, x, y, radio, grosor, opacidad=0.85):
    """Arco de arcoíris centrado en (x, y), detrás de algo (se dibuja antes que el personaje)."""
    if opacidad <= 0:
        return
    colores = [(60, 60, 235), (40, 150, 255), (60, 220, 255), (90, 200, 90), (230, 160, 60), (200, 90, 120)]
    capa = cuadro.copy()
    mascara = np.zeros(cuadro.shape[:2], np.uint8)
    for j, color in enumerate(colores):
        r = int(radio - j * grosor)
        if r <= 0:
            break
        cv2.ellipse(capa, (int(x), int(y)), (r, r), 0, 180, 360, color, grosor + 1, cv2.LINE_AA)
        cv2.ellipse(mascara, (int(x), int(y)), (r, r), 0, 180, 360, 255, grosor + 1, cv2.LINE_AA)
    _mezclar(cuadro, capa, mascara, opacidad)
