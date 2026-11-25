"""
Paso 2: del personaje a un video.

Se ejecuta como proceso aparte:  python -m motor.render trabajo.json
El JSON trae: modo ("esqueleto" o "gelatina"), movimiento, fondo, carpeta del personaje, salida.
Imprime "PROGRESO <0-100>" para que el servidor muestre la barra de avance.
"""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
import yaml

from motor import catalogo

ANCHO, ALTO, FPS = 1280, 720, 30


def progreso(p):
    print(f"PROGRESO {int(p)}", flush=True)


def a_mp4_navegador(entrada, salida, fps_salida=FPS):
    """Convierte a H.264 (se ve en cualquier navegador, celular o tele)."""
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(entrada),
        "-vf", f"fps={fps_salida},format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "20", "-movflags", "+faststart", str(salida)], check=True)


def miniatura(video, salida):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1.5", "-i", str(video),
                    "-frames:v", "1", "-vf", "scale=640:-2", str(salida)], check=True)


# ---------------------------------------------------------------- esqueleto (Meta)

def camara(posicion, mira_a):
    """Cámara en `posicion` mirando al punto `mira_a` (Animated Drawings usa posición − punto)."""
    return {"CAMERA_POS": posicion, "CAMERA_FWD": [posicion[i] - mira_a[i] for i in range(3)]}


# Encuadres probados con 1280x720 para que los pies queden cerca del suelo de los fondos.
CAMARA_NORMAL = camara([0.0, 0.70, 1.75], [0.0, 0.41, 0.0])
CAMARAS = {
    # al saltar el personaje avanza hacia la derecha: cámara más lejos y centrada en el recorrido
    "saltar": camara([0.42, 0.72, 2.3], [0.42, 0.38, 0.0]),
}


def render_esqueleto(t):
    from animated_drawings import render as ad_render  # importa OpenGL, solo aquí

    _, mov = catalogo.movimiento(t["movimiento"])
    carpeta = Path(t["carpeta"]).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        crudo = Path(tmp) / "crudo.mp4"
        vista = {"USE_MESA": True, "WINDOW_DIMENSIONS": [ANCHO, ALTO],
                 "BACKGROUND_IMAGE": catalogo.ruta_fondo(t["fondo"])}
        vista.update(t.get("camara") or CAMARAS.get(mov["id"], CAMARA_NORMAL))
        cfg = {
            "scene": {"ANIMATED_CHARACTERS": [{
                "character_cfg": str(carpeta / "char_cfg.yaml"),
                "motion_cfg": catalogo.motion_cfg(mov),
                "retarget_cfg": catalogo.retarget_cfg(mov),
            }]},
            "view": vista,
            "controller": {"MODE": "video_render", "OUTPUT_VIDEO_PATH": str(crudo), "OUTPUT_VIDEO_CODEC": "mp4v"},
        }
        ruta_cfg = Path(tmp) / "mvc.yaml"
        ruta_cfg.write_text(yaml.dump(cfg))

        # Animated Drawings muestra su avance con tqdm; lo traducimos a PROGRESO.
        import tqdm as tqdm_mod
        original = tqdm_mod.tqdm.update

        def update(self, n=1):
            r = original(self, n)
            if self.total:
                progreso(5 + 85 * self.n / self.total)
            return r
        tqdm_mod.tqdm.update = update

        os.chdir(catalogo.AD_ROOT)
        ad_render.start(str(ruta_cfg))
        progreso(92)
        a_mp4_navegador(crudo, t["salida"])


# ---------------------------------------------------------------- gelatina (propio)

def recorte_rgba(carpeta):
    tex = cv2.imread(str(Path(carpeta) / "texture.png"), cv2.IMREAD_UNCHANGED)
    mask = cv2.imread(str(Path(carpeta) / "mask.png"), cv2.IMREAD_GRAYSCALE)
    if tex.shape[2] == 3:
        tex = cv2.cvtColor(tex, cv2.COLOR_BGR2BGRA)
    alfa = cv2.GaussianBlur(mask, (3, 3), 0)
    tex[:, :, 3] = alfa
    ys, xs = np.where(mask > 0)
    return tex[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def pegar(fondo, img, cx, base_y, pivote=None):
    """Pega img (BGRA) sobre fondo (BGR) poniendo su punto de apoyo en (cx, base_y)."""
    h, w = img.shape[:2]
    px, py = pivote if pivote else (w / 2, h)
    x0, y0 = int(round(cx - px)), int(round(base_y - py))
    x1, y1 = x0 + w, y0 + h
    fx0, fy0, fx1, fy1 = max(0, x0), max(0, y0), min(ANCHO, x1), min(ALTO, y1)
    if fx0 >= fx1 or fy0 >= fy1:
        return
    parte = img[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    a = parte[:, :, 3:4].astype(np.float32) / 255.0
    zona = fondo[fy0:fy1, fx0:fx1].astype(np.float32)
    fondo[fy0:fy1, fx0:fx1] = (parte[:, :, :3] * a + zona * (1 - a)).astype(np.uint8)


def sombra(fondo, cx, y, ancho, intensidad):
    capa = fondo.copy()
    cv2.ellipse(capa, (int(cx), int(y)), (max(4, int(ancho / 2)), max(3, int(ancho / 9))), 0, 0, 360, (40, 40, 40), -1)
    cv2.addWeighted(capa, intensidad, fondo, 1 - intensidad, 0, fondo)


def transformar(img, sx=1.0, sy=1.0, angulo=0.0, onda=0.0):
    """
    Ondula (cada fila se mueve de lado, la de abajo queda fija), escala y gira
    sobre el punto de abajo al centro. Devuelve (imagen, punto_de_apoyo).
    """
    h, w = img.shape[:2]
    if onda:
        pad = int(abs(onda)) + 2
        img = cv2.copyMakeBorder(img, 0, 0, pad, pad, cv2.BORDER_CONSTANT, value=(0, 0, 0, 0))
        h, w = img.shape[:2]
        filas = np.arange(h, dtype=np.float32)
        desplaz = onda * ((h - filas) / h) ** 1.6
        mapa_x = (np.arange(w, dtype=np.float32)[None, :] - desplaz[:, None]).astype(np.float32)
        mapa_y = np.repeat(filas[:, None], w, axis=1)
        img = cv2.remap(img, mapa_x, mapa_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    nw, nh = max(2, int(w * sx)), max(2, int(h * sy))
    img = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    pivote = (nw / 2, nh)
    if angulo:
        # lienzo con margen para que nada se corte al girar
        m = int(math.hypot(nw, nh))
        lienzo = cv2.copyMakeBorder(img, m, m, m, m, cv2.BORDER_CONSTANT, value=(0, 0, 0, 0))
        p = (m + nw / 2, m + nh)
        M = cv2.getRotationMatrix2D(p, angulo, 1.0)
        lienzo = cv2.warpAffine(lienzo, M, (lienzo.shape[1], lienzo.shape[0]), flags=cv2.INTER_LINEAR,
                                borderValue=(0, 0, 0, 0))
        ys, xs = np.where(lienzo[:, :, 3] > 0)
        if len(xs):
            x0, y0 = xs.min(), ys.min()
            img = lienzo[y0:ys.max() + 1, x0:xs.max() + 1]
            pivote = (p[0] - x0, p[1] - y0)
    return img, pivote


def chispitas(fondo, t, n=14, semilla=7):
    rng = np.random.RandomState(semilla)
    for i in range(n):
        x = rng.uniform(0.15, 0.85) * ANCHO
        y = rng.uniform(0.1, 0.8) * ALTO
        fase = rng.uniform(0, 2 * math.pi)
        brillo = (math.sin(t * 3 + fase) + 1) / 2
        r = int(3 + 5 * brillo)
        color = (180 + int(70 * brillo), 240, 255)
        cv2.line(fondo, (int(x - r), int(y)), (int(x + r), int(y)), color, 2, cv2.LINE_AA)
        cv2.line(fondo, (int(x), int(y - r)), (int(x), int(y + r)), color, 2, cv2.LINE_AA)


def render_gelatina(t):
    mov = t["movimiento"]
    pj = recorte_rgba(t["carpeta"])
    ph, pw = pj.shape[:2]
    escala = min(0.58 * ALTO / ph, 0.42 * ANCHO / pw)
    pj = cv2.resize(pj, (max(2, int(pw * escala)), max(2, int(ph * escala))), interpolation=cv2.INTER_AREA)
    ph, pw = pj.shape[:2]

    fondo = cv2.resize(cv2.imread(catalogo.ruta_fondo(t["fondo"])), (ANCHO, ALTO))
    suelo = int(ALTO * 0.88)
    segundos = 8
    total = segundos * FPS

    with tempfile.TemporaryDirectory() as tmp:
        crudo = Path(tmp) / "crudo.mp4"
        ff = subprocess.Popen([
            "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{ANCHO}x{ALTO}",
            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(crudo)], stdin=subprocess.PIPE)
        for f in range(total):
            s = f / FPS
            cuadro = fondo.copy()
            cx, base, sx, sy, ang, onda = ANCHO / 2, suelo, 1.0, 1.0, 0.0, 0.0
            if mov == "rebotar":
                T = 0.9
                fase = (s % T) / T
                altura = math.sin(math.pi * fase)
                base = suelo - 0.22 * ALTO * altura
                aplasta = max(0.0, 1 - altura / 0.22)
                sy, sx = 1 - 0.16 * aplasta + 0.06 * altura, 1 + 0.12 * aplasta - 0.03 * altura
                sombra(cuadro, cx, suelo, pw * (0.9 - 0.35 * altura), 0.35 - 0.15 * altura)
            elif mov == "bambolear":
                onda = 0.16 * pw * math.sin(2 * math.pi * s / 1.1)
                sy = 1 + 0.04 * math.sin(2 * math.pi * s / 0.55)
                sx = 2 - sy
                sombra(cuadro, cx, suelo, pw * 0.9, 0.3)
            elif mov == "flotar":
                base = suelo - 0.12 * ALTO - 0.05 * ALTO * math.sin(2 * math.pi * s / 3.2)
                ang = 7 * math.sin(2 * math.pi * s / 2.4)
                cx = ANCHO / 2 + 0.05 * ANCHO * math.sin(2 * math.pi * s / 5.0)
                chispitas(cuadro, s)
                sombra(cuadro, cx, suelo, pw * 0.6, 0.18)
            elif mov == "menear":
                T = 1.2
                lado = math.sin(2 * math.pi * s / T)
                cx = ANCHO / 2 + 0.14 * ANCHO * lado
                ang = -13 * lado
                salto = abs(math.sin(2 * math.pi * s / T * 2))
                base = suelo - 0.05 * ALTO * salto
                onda = 0.06 * pw * math.sin(2 * math.pi * s / T + 1)
                sombra(cuadro, cx, suelo, pw * 0.85, 0.3 - 0.1 * salto)
            img, pivote = transformar(pj, sx, sy, ang, onda)
            pegar(cuadro, img, cx, base, pivote)
            ff.stdin.write(cuadro.tobytes())
            if f % 10 == 0:
                progreso(5 + 85 * f / total)
        ff.stdin.close()
        if ff.wait() != 0:
            raise RuntimeError("ffmpeg no pudo crear el video")
        progreso(92)
        shutil.move(str(crudo), t["salida"])


def main():
    t = json.loads(Path(sys.argv[1]).read_text())
    progreso(2)
    if t["modo"] == "esqueleto":
        render_esqueleto(t)
    else:
        render_gelatina(t)
    miniatura(t["salida"], t["miniatura"])
    progreso(100)


if __name__ == "__main__":
    main()
