"""
Bailes propios para los personajes con brazos y piernas.

Se generan por código como archivos BVH, usando el esqueleto de la base de captura de movimiento
de CMU (el mismo de "brincos tijera" que trae Animated Drawings), y van al pulso de la canción.

Cómo se mueve cada articulación (medido renderizando una a la vez, ver DESARROLLO.md):
  - LeftShoulder/RightShoulder Zrotation: sube el brazo hacia el lado (izquierdo +, derecho −).
  - LeftElbow/RightElbow Zrotation: dobla el antebrazo hacia arriba (izquierdo +, derecho −).
  - LeftHip/RightHip Zrotation: abre la pierna hacia afuera (izquierda +, derecha −).
  - Chest Zrotation: inclina el cuerpo de lado.  Hips Yposition / Xposition: sube y baja / se mece.
Los giros hacia adelante o atrás no se ven, porque el dibujo es plano: por eso aquí todo pasa
"de frente" y se usa bailes/cmu1_fff.yaml, que proyecta de frente brazos, piernas y tronco.
"""
import math
import os
from pathlib import Path

import numpy as np
import yaml

from motor.bvh import BVH

AD_ROOT = os.environ.get("AD_ROOT", "/opt/AnimatedDrawings")
AQUI = Path(__file__).resolve().parents[1] / "bailes"
RETARGET = str(AQUI / "cmu1_fff.yaml")
FPS = 30


def _ola(x):
    """De 0 a 1 y de vuelta, suave (para x de 0 a 1)."""
    return 0.5 - 0.5 * math.cos(2 * math.pi * x)


def avion(b):
    lado = math.sin(math.pi * b / 2)            # se inclina de un lado al otro cada 4 pulsos
    rebote = abs(math.sin(math.pi * b))
    return {"LeftShoulder.Zrotation": 85 - 15 * lado, "RightShoulder.Zrotation": -85 - 15 * lado,
            "Chest.Zrotation": 14 * lado, "Hips.Xposition": 2.5 * lado, "Hips.Yposition": -1.0 * rebote,
            "LeftKnee.Xrotation": 12 * rebote, "RightKnee.Xrotation": 12 * rebote}


def aplaudir(b):
    u = math.sin(math.pi * ((b % 2) / 2)) ** 0.8  # 0 = brazos abiertos, 1 = aplauso arriba (en el 2.º pulso)
    return {"LeftShoulder.Zrotation": 40 + 115 * u, "RightShoulder.Zrotation": -(40 + 115 * u),
            "LeftElbow.Zrotation": 20 * (1 - u), "RightElbow.Zrotation": -20 * (1 - u),
            "Hips.Yposition": 1.5 * u, "LeftKnee.Xrotation": 15 * (1 - u), "RightKnee.Xrotation": 15 * (1 - u)}


def marchar(b):
    s = math.sin(math.pi * b)                   # un pie por pulso
    return {"LeftHip.Zrotation": 18 * max(s, 0), "RightHip.Zrotation": -18 * max(-s, 0),
            "LeftKnee.Xrotation": 30 * max(s, 0), "RightKnee.Xrotation": 30 * max(-s, 0),
            "LeftShoulder.Zrotation": 25 - 20 * s, "RightShoulder.Zrotation": -(25 + 20 * s),
            "LeftElbow.Zrotation": 70, "RightElbow.Zrotation": -70,
            "Chest.Zrotation": 4 * s, "Hips.Yposition": 1.2 * abs(s)}


def hurra(b):
    u = _ola((b % 2) / 2)                        # brazos arriba y abajo cada 2 pulsos
    return {"LeftShoulder.Zrotation": 10 + 125 * u, "RightShoulder.Zrotation": -(10 + 125 * u),
            "LeftElbow.Zrotation": 30 * u, "RightElbow.Zrotation": -30 * u,
            "Hips.Yposition": 2.0 * u, "LeftHip.Zrotation": 12 * u, "RightHip.Zrotation": -12 * u}


BAILES = {"avion": avion, "aplaudir": aplaudir, "marchar": marchar, "hurra": hurra}


def generar(baile, bpm, segundos, carpeta):
    """Escribe <carpeta>/<baile>.bvh y su configuración de movimiento. Devuelve la ruta de la configuración."""
    original = BVH.leer(Path(AD_ROOT) / "examples/bvh/cmu1/jumping_jacks.bvh")
    base = original.pose(0)                      # de pie, brazos abajo
    n = int(round(segundos * FPS))
    cuadros = np.repeat(base[None], n, axis=0)
    pulso = 60.0 / bpm
    for f in range(n):
        for canal, valor in BAILES[baile](f / FPS / pulso).items():
            articulacion, eje = canal.split(".")
            cuadros[f, original.col(articulacion, eje)] += valor
    ruta_bvh = Path(carpeta) / f"{baile}.bvh"
    original.escribir(ruta_bvh, cuadros, 1.0 / FPS)

    with open(Path(AD_ROOT) / "examples/config/motion/jumping_jacks.yaml") as f:
        movimiento = yaml.safe_load(f)
    movimiento.update(filepath=str(ruta_bvh), start_frame_idx=0, end_frame_idx=n)
    ruta_cfg = Path(carpeta) / f"{baile}_movimiento.yaml"
    ruta_cfg.write_text(yaml.dump(movimiento))
    return str(ruta_cfg)
