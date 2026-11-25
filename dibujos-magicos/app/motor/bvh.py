"""
Leer y escribir archivos BVH (captura de movimiento) para crear bailes propios.

Un BVH tiene dos partes: la jerarquía del esqueleto (articulaciones y sus canales, por ejemplo
"Zrotation Xrotation Yrotation") y una tabla de movimiento con una fila por cuadro.
Aquí se lee esa tabla como un diccionario {(articulación, canal): columna} para poder
cambiar valores por nombre, por ejemplo  pose[("LeftShoulder", "Zrotation")] += 40.
"""
import re
from pathlib import Path

import numpy as np


class BVH:
    def __init__(self, jerarquia, canales, cuadros, tiempo_cuadro):
        self.jerarquia = jerarquia          # texto desde "HIERARCHY" hasta antes de "MOTION"
        self.canales = canales              # lista de (articulación, canal) en el orden de las columnas
        self.cuadros = cuadros              # np.array (n_cuadros, n_canales)
        self.tiempo_cuadro = tiempo_cuadro
        self.indice = {c: i for i, c in enumerate(canales)}

    @classmethod
    def leer(cls, ruta):
        texto = Path(ruta).read_text()
        jerarquia, movimiento = texto.split("MOTION", 1)
        canales, actual = [], None
        for linea in jerarquia.splitlines():
            m = re.match(r"\s*(ROOT|JOINT)\s+(\S+)", linea)
            if m:
                actual = m.group(2)
            m = re.match(r"\s*CHANNELS\s+\d+\s+(.*)", linea)
            if m:
                canales += [(actual, c) for c in m.group(1).split()]
        lineas = movimiento.strip().splitlines()
        tiempo = float(lineas[1].split(":")[1])
        cuadros = np.array([[float(v) for v in fila.split()] for fila in lineas[2:] if fila.strip()])
        assert cuadros.shape[1] == len(canales), "la tabla no coincide con la jerarquía"
        return cls(jerarquia, canales, cuadros, tiempo)

    def pose(self, cuadro):
        """Una copia de la fila `cuadro`, para usarla de base."""
        return self.cuadros[cuadro].copy()

    def col(self, articulacion, canal):
        return self.indice[(articulacion, canal)]

    def escribir(self, ruta, cuadros, tiempo_cuadro=None):
        tiempo_cuadro = tiempo_cuadro or self.tiempo_cuadro
        filas = "\n".join(" ".join(f"{v:.5f}" for v in fila) for fila in cuadros)
        Path(ruta).write_text(f"{self.jerarquia.rstrip()}\nMOTION\nFrames: {len(cuadros)}\n"
                              f"Frame Time: {tiempo_cuadro:.6f}\n{filas}\n")
