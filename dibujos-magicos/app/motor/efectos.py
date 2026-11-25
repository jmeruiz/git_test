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
    """Pega `capa` sobre `cuadro` donde `mascara` > 0, con la opacidad dada (0 a 1)."""
    a = (cv2.GaussianBlur(mascara, (0, 0), 2).astype(np.float32) / 255.0 * opacidad)[:, :, None]
    cuadro[:] = (capa.astype(np.float32) * a + cuadro.astype(np.float32) * (1 - a)).astype(np.uint8)


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


def fuego(cuadro, x, y, ancho, s, fuerza=1.0):
    """Llama de cohete hacia abajo desde (x, y), en tres capas que titilan, con chispitas."""
    if fuerza <= 0:
        return
    capa = cuadro.copy()
    mascara = np.zeros(cuadro.shape[:2], np.uint8)
    largo = ancho * (0.5 + 1.1 * fuerza) * (1 + 0.08 * math.sin(s * 31))
    for escala, color, fase in ((1.0, (20, 70, 235), 0.0), (0.72, (0, 160, 255), 1.3), (0.42, (150, 240, 255), 2.1)):
        forma = _llama(ancho * 1.15 * escala, largo * escala, x, y - 2, s, fase)
        cv2.fillPoly(capa, [forma], color, cv2.LINE_AA)
        cv2.fillPoly(mascara, [forma], 255, cv2.LINE_AA)
    for k in range(int(14 * fuerza) + 4):          # chispitas que saltan
        edad = (s * 1.8 + _azar(k, 7)) % 1.0
        px = x + (_azar(k, 8) - 0.5) * ancho * (0.6 + 1.2 * edad)
        py = y + largo * (0.3 + 0.9 * edad)
        r = max(2, int(5 * (1 - edad)))
        cv2.circle(capa, (int(px), int(py)), r, (60, 200, 255), -1, cv2.LINE_AA)
        cv2.circle(mascara, (int(px), int(py)), r, int(255 * (1 - edad)), -1, cv2.LINE_AA)
    _mezclar(cuadro, capa, mascara, 0.95)


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
