"""
"Dibujado a mano": el tembleque de las líneas (en inglés, *line boil*).

En la animación hecha a mano cada cuadro se vuelve a dibujar, y las líneas nunca quedan
exactamente iguales: tiemblan un poquito. Eso hace que un dibujo quieto se vea vivo.
Aquí se imita con 3 deformaciones suaves y al azar que se turnan unas 10 veces por segundo
(como los animadores, que repiten un ciclo de 3 dibujos).
"""
import cv2
import numpy as np

VARIANTES = 3
CAMBIOS_POR_SEGUNDO = 10


class Temblor:
    def __init__(self, semilla=11):
        self.semilla = semilla
        self._mapas = {}

    def _campos(self, h, w):
        clave = (h, w)
        if clave not in self._mapas:
            rng = np.random.RandomState(self.semilla + h * 7 + w)
            amplitud = float(np.clip(min(h, w) / 260.0, 0.9, 2.2))   # pixeles; un poquito más en dibujos grandes
            paso = 18                                                 # tamaño de las "ondas" del tembleque
            gh, gw = max(2, h // paso + 2), max(2, w // paso + 2)
            base_x, base_y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
            campos = []
            for _ in range(VARIANTES):
                dx = cv2.resize(rng.uniform(-1, 1, (gh, gw)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
                dy = cv2.resize(rng.uniform(-1, 1, (gh, gw)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
                campos.append((base_x + dx * amplitud, base_y + dy * amplitud))
            self._mapas[clave] = campos
        return self._mapas[clave]

    def aplicar(self, img, s):
        """Devuelve `img` (BGR o BGRA) con el tembleque que toca en el segundo `s`."""
        h, w = img.shape[:2]
        mx, my = self._campos(h, w)[int(s * CAMBIOS_POR_SEGUNDO) % VARIANTES]
        return cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
