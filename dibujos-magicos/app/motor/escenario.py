"""
Fondos con vida: cosas que se mueven en cada fondo.

Cada fondo tiene una parte "atrás" (se dibuja antes que los personajes: nubes, estrellas,
peces lejanos) y una parte "adelante" (después: copos de nieve grandes, hojas, burbujas),
que da sensación de profundidad. Todo se calcula a partir del tiempo, sin guardar estado.
"""
import math

import cv2
import numpy as np

from motor.efectos import _azar, _mezclar


class Escenario:
    def __init__(self, fondo, ancho, alto):
        self.fondo, self.w, self.h = fondo, ancho, alto

    # ------------------------------------------------------------ atrás
    def atras(self, c, s):
        f = self.fondo
        if f in ("parque", "granja", "playa", "jardin", "nieve"):
            self._nubes(c, s)
        if f in ("noche", "espacio"):
            self._titilar(c, s)
            self._estrella_fugaz(c, s)
        if f == "mar":
            self._rayos(c, s)
            self._peces(c, s)
        if f in ("jardin", "parque"):
            self._mariposas(c, s)
        if f == "playa":
            self._brillos_agua(c, s)
        if f == "granja":
            self._pajaritos(c, s)

    # ------------------------------------------------------------ adelante
    def adelante(self, c, s):
        f = self.fondo
        if f == "nieve":
            self._nieve(c, s, cerca=True)
        if f == "mar":
            self._burbujas_frente(c, s)
        if f == "bosque":
            self._hojas(c, s)
        if f == "jardin":
            self._petalos(c, s)

    def atras_lejos(self, c, s):
        if self.fondo == "nieve":
            self._nieve(c, s, cerca=False)

    # ------------------------------------------------------------ piezas
    def _nubes(self, c, s):
        capa, mascara = c.copy(), np.zeros(c.shape[:2], np.uint8)
        for k in range(3):
            vel = 12 + 10 * _azar(k, 1)                       # pixeles por segundo, despacito
            x = (_azar(k, 2) * (self.w + 400) + s * vel) % (self.w + 400) - 200
            y = self.h * (0.06 + 0.16 * _azar(k, 3))
            ancho = 90 + 80 * _azar(k, 4)
            for j in range(4):
                cx = int(x + (j - 1.5) * ancho * 0.35)
                cy = int(y + math.sin(j * 1.7) * 8)
                r = int(ancho * (0.22 + 0.08 * math.sin(j * 2.3 + k)))
                cv2.circle(capa, (cx, cy), r, (252, 252, 255), -1, cv2.LINE_AA)
                cv2.circle(mascara, (cx, cy), r, 255, -1, cv2.LINE_AA)
        _mezclar(c, capa, mascara, 0.55)

    def _titilar(self, c, s):
        for k in range(26):
            x, y = int(_azar(k, 5) * self.w), int(_azar(k, 6) * self.h * 0.45)
            brillo = 0.5 + 0.5 * math.sin(s * (2 + 3 * _azar(k, 7)) + k)
            if brillo > 0.55:
                r = int(2 + 5 * (brillo - 0.55) / 0.45)
                color = (220, 245, 255)
                cv2.line(c, (x - r, y), (x + r, y), color, 2, cv2.LINE_AA)
                cv2.line(c, (x, y - r), (x, y + r), color, 2, cv2.LINE_AA)

    def _estrella_fugaz(self, c, s):
        ciclo = 7.0
        k = int(s // ciclo)
        t = (s % ciclo) / 1.1                                  # dura 1.1 s cada 7 s
        if t > 1:
            return
        x0, y0 = self.w * (0.15 + 0.5 * _azar(k, 8)), self.h * (0.05 + 0.12 * _azar(k, 9))
        x, y = x0 + t * self.w * 0.35, y0 + t * self.h * 0.15
        for j in range(12):                                    # cola que se desvanece
            a = j / 12
            px, py = x - a * 110, y - a * 47
            cv2.circle(c, (int(px), int(py)), max(1, int(4 * (1 - a))), (230, 250, 255), -1, cv2.LINE_AA)

    def _rayos(self, c, s):
        capa, mascara = c.copy(), np.zeros(c.shape[:2], np.uint8)
        for k in range(4):
            x = self.w * (0.2 + 0.2 * k) + math.sin(s * 0.5 + k) * 40
            pts = np.array([(x - 30, 0), (x + 30, 0), (x + 110, self.h * 0.75), (x + 10, self.h * 0.75)], np.int32)
            cv2.fillPoly(capa, [pts], (255, 255, 240), cv2.LINE_AA)
            cv2.fillPoly(mascara, [pts], int(70 + 50 * math.sin(s * 0.8 + k * 2)), cv2.LINE_AA)
        _mezclar(c, capa, mascara, 0.35)

    def _peces(self, c, s):
        colores = [(60, 160, 255), (230, 170, 80), (120, 220, 255)]
        for k in range(3):
            vel = 50 + 30 * _azar(k, 10)
            dir_ = 1 if k % 2 == 0 else -1
            x = (_azar(k, 11) * (self.w + 200) + dir_ * s * vel) % (self.w + 200) - 100
            y = self.h * (0.25 + 0.25 * _azar(k, 12)) + math.sin(s * 2 + k) * 10
            tam = 16 + 8 * _azar(k, 13)
            color = colores[k % 3]
            cv2.ellipse(c, (int(x), int(y)), (int(tam), int(tam * 0.55)), 0, 0, 360, color, -1, cv2.LINE_AA)
            cola = np.array([(x - dir_ * tam * 0.9, y), (x - dir_ * tam * 1.6, y - tam * 0.5),
                             (x - dir_ * tam * 1.6, y + tam * 0.5)], np.int32)
            cv2.fillPoly(c, [cola], color, cv2.LINE_AA)
            cv2.circle(c, (int(x + dir_ * tam * 0.5), int(y - tam * 0.12)), 2, (40, 30, 30), -1, cv2.LINE_AA)

    def _mariposas(self, c, s):
        colores = [(80, 140, 255), (230, 120, 200), (60, 210, 250)]
        for k in range(3):
            x = self.w * (0.1 + 0.8 * _azar(k, 14)) + math.sin(s * 0.7 + k * 2) * 120
            y = self.h * (0.2 + 0.2 * _azar(k, 15)) + math.sin(s * 1.3 + k) * 40
            aleteo = abs(math.sin(s * 14 + k))                  # alas que se abren y cierran rápido
            tam = 11
            for lado in (-1, 1):
                cv2.ellipse(c, (int(x + lado * tam * 0.6 * aleteo), int(y)), (max(2, int(tam * aleteo)), tam), 0, 0, 360,
                            colores[k], -1, cv2.LINE_AA)
            cv2.line(c, (int(x), int(y - tam)), (int(x), int(y + tam)), (60, 50, 50), 2, cv2.LINE_AA)

    def _brillos_agua(self, c, s):
        for k in range(16):
            x, y = int(_azar(k, 16) * self.w), int(self.h * (0.28 + 0.12 * _azar(k, 17)))
            b = math.sin(s * 3 + k * 1.9)
            if b > 0.6:
                r = int(3 + 6 * (b - 0.6) / 0.4)
                cv2.line(c, (x - r, y), (x + r, y), (255, 255, 255), 2, cv2.LINE_AA)
                cv2.line(c, (x, y - r // 2), (x, y + r // 2), (255, 255, 255), 2, cv2.LINE_AA)

    def _pajaritos(self, c, s):
        for k in range(3):
            x = (_azar(k, 18) * self.w + s * 70) % (self.w + 100) - 50
            y = self.h * (0.1 + 0.1 * _azar(k, 19)) + k * 18
            ala = 8 * math.sin(s * 9 + k)
            cv2.polylines(c, [np.array([(x - 12, y - ala), (x, y), (x + 12, y - ala)], np.int32)], False,
                          (70, 60, 60), 2, cv2.LINE_AA)

    def _nieve(self, c, s, cerca):
        n, tam, vel = (14, 7, 110) if cerca else (45, 3, 45)
        for k in range(n):
            sal = 20 if cerca else 30
            x = (_azar(k, sal) * self.w + math.sin(s * 1.2 + k) * 25) % self.w
            y = (_azar(k, sal + 1) * self.h + s * vel * (0.7 + 0.6 * _azar(k, sal + 2))) % (self.h + 20) - 10
            cv2.circle(c, (int(x), int(y)), int(tam * (0.7 + 0.6 * _azar(k, sal + 3))), (255, 255, 255), -1, cv2.LINE_AA)

    def _burbujas_frente(self, c, s):
        for k in range(7):
            x = _azar(k, 40) * self.w + math.sin(s * 2 + k) * 15
            y = self.h - ((s * (60 + 40 * _azar(k, 41)) + _azar(k, 42) * self.h) % (self.h + 40))
            r = int(6 + 8 * _azar(k, 43))
            cv2.circle(c, (int(x), int(y)), r, (255, 245, 220), 2, cv2.LINE_AA)

    def _hojas(self, c, s):
        colores = [(40, 150, 230), (50, 110, 200), (60, 170, 120)]
        for k in range(6):
            x = (_azar(k, 50) * self.w + math.sin(s * 1.1 + k) * 60 + s * 20) % self.w
            y = (_azar(k, 51) * self.h + s * 55) % (self.h + 40) - 20
            ang = (s * 90 + k * 60) % 360
            cv2.ellipse(c, (int(x), int(y)), (12, 6), ang, 0, 360, colores[k % 3], -1, cv2.LINE_AA)

    def _petalos(self, c, s):
        for k in range(6):
            x = (_azar(k, 60) * self.w + s * 35 + math.sin(s + k) * 40) % self.w
            y = (_azar(k, 61) * self.h + s * 40) % (self.h + 40) - 20
            cv2.ellipse(c, (int(x), int(y)), (7, 4), (s * 120 + k * 50) % 360, 0, 360, (200, 170, 255), -1, cv2.LINE_AA)
