"""
Paso 2: de uno o varios personajes a un video con música.

Se ejecuta como proceso aparte:  python -m motor.render escena.json
La escena trae:
  {"fondo": "parque", "musica": "fiesta" | "ninguna",
   "personajes": [{"carpeta": "...", "modo": "esqueleto" | "gelatina", "movimiento": "bailar"}, ...],
   "salida": ".../video.mp4", "miniatura": ".../mini.jpg"}

Cómo se arma cada cuadro:
  1. Los personajes "con esqueleto" los anima Animated Drawings (todos juntos, sobre el fondo).
     Si no hay ninguno, la base es solo el fondo.
  2. Encima se pegan los personajes "gelatina", moviéndose al ritmo de la música.
  3. Se le pone la música y se guarda en MP4 H.264 (se ve en navegador, celular y tele).
Imprime "PROGRESO <0-100>" para que el servidor muestre la barra de avance.
"""
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
import yaml

from motor import bailes, catalogo, efectos, musica

ANCHO, ALTO, FPS = 1280, 720, 30
SEGUNDOS_MINIMOS = 7.5


def progreso(p):
    print(f"PROGRESO {int(p)}", flush=True)


def miniatura(video, salida):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1.5", "-i", str(video),
                    "-frames:v", "1", "-vf", "scale=640:-2", str(salida)], check=True)


def duracion(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


# ---------------------------------------------------------------- cámara y lugares

def camara(posicion, mira_a):
    """Cámara en `posicion` mirando al punto `mira_a` (Animated Drawings usa posición − punto)."""
    return {"CAMERA_POS": posicion, "CAMERA_FWD": [posicion[i] - mira_a[i] for i in range(3)]}


# Encuadres probados con 1280x720 para que los pies queden cerca del suelo de los fondos.
CAMARA_NORMAL = camara([0.0, 0.70, 1.75], [0.0, 0.41, 0.0])
CAMARA_SALTAR = camara([0.42, 0.72, 2.3], [0.42, 0.38, 0.0])  # al saltar avanza hacia la derecha

# Dónde se para cada personaje (fracción del ancho) y qué tan lejos va la cámara, según cuántos son.
LUGARES = {1: [.5], 2: [.32, .68], 3: [.2, .5, .8], 4: [.14, .38, .62, .86], 5: [.11, .3, .5, .7, .89]}
DISTANCIA = {1: 1.75, 2: 2.1, 3: 2.6, 4: 3.1, 5: 3.5}
SUELO_FIESTA = 0.86          # a qué altura de la pantalla quedan los pies en una fiesta
ALTO_PERSONAJE_MUNDO = 0.64  # altura típica de un personaje animado, medida en sus videos
PIES_Y = -0.28               # Animated Drawings deja los pies un poco debajo de y=0 (medido)
TAN_MEDIO_FOV = math.tan(math.radians(17.5))  # Animated Drawings usa 35° de campo vertical


def camara_escena(n, mov_id, z_personaje=-0.5):
    if n == 1:
        return CAMARA_SALTAR if mov_id == "saltar" else CAMARA_NORMAL
    # Cámara calculada para que los pies queden a SUELO_FIESTA de la pantalla.
    dz = DISTANCIA[n] - z_personaje
    cy = PIES_Y + 0.435 * dz  # misma inclinación hacia los pies que en los videos de un personaje
    abajo = math.atan((SUELO_FIESTA - 0.5) * 2 * TAN_MEDIO_FOV)   # ángulo del suelo bajo el centro
    inclinacion = math.atan((cy - PIES_Y) / dz) - abajo
    ty = cy - dz * math.tan(inclinacion)
    cx = 0.42 if mov_id == "saltar" else 0.0
    return camara([cx, cy, DISTANCIA[n]], [cx, ty, z_personaje])


def x_mundo(fraccion, cam, z_personaje):
    """Convierte 'fracción del ancho de la pantalla' a la coordenada x del mundo 3D."""
    cx, cz = cam["CAMERA_POS"][0], cam["CAMERA_POS"][2]
    ancho_mundo = 2 * (cz - z_personaje) * TAN_MEDIO_FOV * ANCHO / ALTO
    return cx + (fraccion - 0.5) * ancho_mundo


def retarget_movido(ruta, x, carpeta_tmp, i):
    """Copia el archivo de retarget cambiando solo la x de donde arranca el personaje."""
    texto = Path(ruta).read_text()
    m = re.search(r"^char_starting_location:\s*\[([^\]]*)\]", texto, re.M)
    y, z = (float(v) for v in m.group(1).split(",")[1:3])
    texto = texto[:m.start()] + f"char_starting_location: [{x:.4f}, {y}, {z}]" + texto[m.end():]
    nueva = Path(carpeta_tmp) / f"retarget_{i}.yaml"
    nueva.write_text(texto)
    return str(nueva), z


def z_inicial(ruta):
    m = re.search(r"^char_starting_location:\s*\[([^\]]*)\]", Path(ruta).read_text(), re.M)
    return float(m.group(1).split(",")[2])


# ---------------------------------------------------------------- esqueleto (Animated Drawings de Meta)

def render_esqueletos(personajes, fondo, n_total, tmp, bpm, segundos):
    """Anima con Animated Drawings a los personajes con esqueleto. Devuelve la ruta del video crudo."""
    from animated_drawings import render as ad_render  # importa OpenGL, solo aquí

    mov_id = personajes[0]["movimiento"]
    _, mov = catalogo.movimiento(mov_id)
    if mov.get("propio"):
        # baile hecho por código, al pulso de la canción (ver motor/bailes.py)
        motion_cfg, retarget_base = bailes.generar(mov_id, bpm, segundos, tmp), bailes.RETARGET
    else:
        motion_cfg, retarget_base = catalogo.motion_cfg(mov), catalogo.retarget_cfg(mov)
    cam = camara_escena(n_total, mov_id, z_inicial(retarget_base))
    lista = []
    for i, p in enumerate(personajes):
        retarget = retarget_base
        if n_total > 1:
            x = x_mundo(p["lugar"], cam, z_inicial(retarget))
            retarget, _ = retarget_movido(retarget, x, tmp, i)
        lista.append({"character_cfg": str(Path(p["carpeta"]).resolve() / "char_cfg.yaml"),
                      "motion_cfg": motion_cfg, "retarget_cfg": retarget})

    crudo = Path(tmp) / "esqueletos.mp4"
    vista = {"USE_MESA": True, "WINDOW_DIMENSIONS": [ANCHO, ALTO], "BACKGROUND_IMAGE": catalogo.ruta_fondo(fondo)}
    vista.update(cam)
    cfg = {"scene": {"ANIMATED_CHARACTERS": lista}, "view": vista,
           "controller": {"MODE": "video_render", "OUTPUT_VIDEO_PATH": str(crudo), "OUTPUT_VIDEO_CODEC": "mp4v"}}
    ruta_cfg = Path(tmp) / "mvc.yaml"
    ruta_cfg.write_text(yaml.dump(cfg))

    # Animated Drawings muestra su avance con tqdm; lo traducimos a PROGRESO.
    import tqdm as tqdm_mod
    original = tqdm_mod.tqdm.update

    def update(self, n=1):
        r = original(self, n)
        if self.total:
            progreso(5 + 50 * self.n / self.total)
        return r
    tqdm_mod.tqdm.update = update

    antes = os.getcwd()
    os.chdir(catalogo.AD_ROOT)
    try:
        ad_render.start(str(ruta_cfg))
    finally:
        os.chdir(antes)
    return crudo


def cuadros_base(crudo, fondo_img, total, vueltas):
    """Da `total` cuadros BGR: los del video de Animated Drawings (repetido) o el fondo quieto."""
    if crudo is None:
        for _ in range(total):
            yield fondo_img.copy()
        return
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-stream_loop", str(vueltas - 1), "-i", str(crudo),
                          "-vf", f"fps={FPS},scale={ANCHO}:{ALTO}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         stdout=subprocess.PIPE)
    tam = ANCHO * ALTO * 3
    ultimo = fondo_img
    for _ in range(total):
        datos = p.stdout.read(tam)
        if len(datos) == tam:
            ultimo = np.frombuffer(datos, np.uint8).reshape(ALTO, ANCHO, 3).copy()
        yield ultimo.copy()
    p.stdout.close()
    p.wait()


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
    for _ in range(n):
        x = rng.uniform(0.15, 0.85) * ANCHO
        y = rng.uniform(0.1, 0.8) * ALTO
        fase = rng.uniform(0, 2 * math.pi)
        brillo = (math.sin(t * 3 + fase) + 1) / 2
        r = int(3 + 5 * brillo)
        color = (180 + int(70 * brillo), 240, 255)
        cv2.line(fondo, (int(x - r), int(y)), (int(x + r), int(y)), color, 2, cv2.LINE_AA)
        cv2.line(fondo, (int(x), int(y - r)), (int(x), int(y + r)), color, 2, cv2.LINE_AA)


class Gelatina:
    """Un personaje gelatina: su recorte, su lugar y cómo se mueve al ritmo (pulsos por minuto)."""

    def __init__(self, carpeta, movimiento, lugar, n_total, bpm):
        self.mov = movimiento
        self.pulso = 60.0 / bpm
        pj = recorte_rgba(carpeta)
        ph, pw = pj.shape[:2]
        if n_total == 1:
            alto_max, ancho_max, self.suelo = 0.58 * ALTO, 0.42 * ANCHO, 0.88 * ALTO
            self.amplitud = 0.14 * ANCHO
        else:
            # más o menos del tamaño de los personajes con esqueleto a esa distancia de cámara
            dz = DISTANCIA[n_total] + 0.5
            alto_max = 0.9 * ALTO_PERSONAJE_MUNDO / (2 * dz * TAN_MEDIO_FOV) * ALTO
            separacion = (LUGARES[n_total][1] - LUGARES[n_total][0]) * ANCHO
            ancho_max, self.suelo = 0.75 * separacion, SUELO_FIESTA * ALTO
            self.amplitud = 0.25 * separacion
        escala = min(alto_max / ph, ancho_max / pw)
        self.img = cv2.resize(pj, (max(2, int(pw * escala)), max(2, int(ph * escala))), interpolation=cv2.INTER_AREA)
        self.cx = lugar * ANCHO

    def dibujar(self, cuadro, s):
        ph, pw = self.img.shape[:2]
        b = s / self.pulso  # cuántos pulsos de música van
        cx, base, sx, sy, ang, onda = self.cx, self.suelo, 1.0, 1.0, 0.0, 0.0
        if self.mov == "rebotar":
            fase = (b % 2) / 2
            altura = math.sin(math.pi * fase)
            base = self.suelo - 0.32 * ph * altura
            aplasta = max(0.0, 1 - altura / 0.22)
            sy, sx = 1 - 0.16 * aplasta + 0.06 * altura, 1 + 0.12 * aplasta - 0.03 * altura
            sombra(cuadro, cx, self.suelo, pw * (0.9 - 0.35 * altura), 0.35 - 0.15 * altura)
        elif self.mov == "bambolear":
            onda = 0.16 * pw * math.sin(math.pi * b)
            sy = 1 + 0.04 * math.sin(2 * math.pi * b)
            sx = 2 - sy
            sombra(cuadro, cx, self.suelo, pw * 0.9, 0.3)
        elif self.mov == "flotar":
            base = self.suelo - 0.2 * ph - 0.08 * ph * math.sin(2 * math.pi * b / 8)
            ang = 7 * math.sin(2 * math.pi * b / 6)
            cx = self.cx + 0.35 * self.amplitud * math.sin(2 * math.pi * b / 12)
            sombra(cuadro, cx, self.suelo, pw * 0.6, 0.18)
        elif self.mov == "trompo":
            giro = math.cos(math.pi * b)                 # una vuelta cada 2 pulsos
            sx = max(0.08, abs(giro))
            espejo = giro < 0                            # de espaldas se ve al revés
            base = self.suelo - 0.04 * ph * abs(math.sin(2 * math.pi * b))
            sombra(cuadro, cx, self.suelo, pw * 0.8, 0.3)
            efectos.polvo(cuadro, cx, self.suelo, pw, s)
            if sx < 0.6:
                efectos.rayitas(cuadro, cx, base - ph * 0.5, pw * 0.65, ph * 0.5, s)
            img, pivote = transformar(self.img[:, ::-1] if espejo else self.img, sx, sy, 0, 0)
            pegar(cuadro, img, cx, base, pivote)
            return
        elif self.mov == "nadar":
            fase = math.sin(2 * math.pi * b / 16)        # va y viene cada 16 pulsos
            vel = math.cos(2 * math.pi * b / 16)
            cx = self.cx + 2.2 * self.amplitud * fase
            base = self.suelo - 0.35 * ph + 0.06 * ph * math.sin(math.pi * b)
            ang = (-12 if vel > 0 else 12) + 5 * math.sin(math.pi * b)
            onda = 0.05 * pw * math.sin(2 * math.pi * b)
            frente = cx + (pw * 0.45 if vel > 0 else -pw * 0.45)
            efectos.burbujas(cuadro, frente, base - ph * 0.5, s, semilla=int(self.cx))
            img, pivote = transformar(self.img if vel > 0 else self.img[:, ::-1], sx, sy, ang, onda)
            pegar(cuadro, img, cx, base, pivote)
            return
        elif self.mov == "cohete":
            # ciclo de 8 pulsos: tiembla (0-2), despega (2-5), baja suavecito (5-8)
            c = b % 8
            if c < 2:
                altura, fuerza = 0.0, 0.12 + 0.12 * c
                cx = self.cx + 0.012 * pw * math.sin(40 * s)  # tiembla antes de despegar
                efectos.humo(cuadro, cx, self.suelo, pw, s, cantidad=0.4 + 0.3 * c)
            elif c < 5:
                k = (c - 2) / 3
                altura, fuerza = (k ** 2) * (self.suelo + ph * 0.2), 1.0
                sy, sx = 1.12, 0.92
                efectos.humo(cuadro, self.cx, self.suelo, pw, s, cantidad=max(0.0, 1 - 2 * k))
            else:
                k = (c - 5) / 3
                altura, fuerza = ((1 - k) ** 2) * (self.suelo + ph * 0.2), 0.45
            base = self.suelo - altura
            sombra(cuadro, self.cx, self.suelo, pw * max(0.2, 0.8 - altura / ALTO), 0.3 * max(0.2, 1 - altura / ALTO))
            efectos.fuego(cuadro, cx, base, pw * 0.5, s, fuerza)
            img, pivote = transformar(self.img, sx, sy, 0, 0)
            pegar(cuadro, img, cx, base, pivote)
            return
        elif self.mov == "voltereta":
            c = b % 4                                    # salta y da la vuelta en 2 pulsos, descansa 2
            if c < 2:
                k = c / 2
                alto_salto = math.sin(math.pi * k) * 0.45 * ph
                angulo = -360 * (k * k * (3 - 2 * k))    # empieza y termina suavecito
                centro_y = self.suelo - ph / 2 - alto_salto
                sombra(cuadro, cx, self.suelo, pw * (0.8 - 0.3 * math.sin(math.pi * k)), 0.25)
                img, pivote = transformar(self.img, 1, 1, angulo, 0)
                a = math.radians(angulo)
                # gira alrededor del centro: el punto de apoyo se mueve con el giro
                px, py = cx + (ph / 2) * math.sin(a), centro_y + (ph / 2) * math.cos(a)
                pegar(cuadro, img, px, py, pivote)
                return
            k = (c - 2) / 2
            aplasta = math.exp(-6 * k) * 0.2
            sy, sx = 1 - aplasta, 1 + aplasta * 0.7
            sombra(cuadro, cx, self.suelo, pw * 0.85, 0.3)
            img, pivote = transformar(self.img, sx, sy, 0, 0)
            pegar(cuadro, img, cx, self.suelo, pivote)
            efectos.estrellas(cuadro, cx, self.suelo - ph * 0.55, pw, k)  # encima del dibujo
            return
        else:  # menear
            lado = math.sin(math.pi * b)
            cx = self.cx + self.amplitud * lado
            ang = -13 * lado
            salto = abs(math.sin(math.pi * b))
            base = self.suelo - 0.08 * ph * salto
            onda = 0.06 * pw * math.sin(math.pi * b + 1)
            sombra(cuadro, cx, self.suelo, pw * 0.85, 0.3 - 0.1 * salto)
        img, pivote = transformar(self.img, sx, sy, ang, onda)
        pegar(cuadro, img, cx, base, pivote)


# ---------------------------------------------------------------- escena completa

def render(escena):
    pjs = escena["personajes"]
    n = len(pjs)
    for p, lugar in zip(pjs, LUGARES[n]):
        p["lugar"] = lugar
    cancion = escena.get("musica")
    if not musica.existe(cancion):
        cancion = None
    fondo_img = cv2.resize(cv2.imread(catalogo.ruta_fondo(escena["fondo"])), (ANCHO, ALTO))
    esqueletos = [p for p in pjs if p["modo"] == "esqueleto"]
    gelatinas = [p for p in pjs if p["modo"] != "esqueleto"]

    bpm = musica.bpm_de(cancion) if cancion else 116
    segundos_musicales = musica.duracion_en_compases(cancion, 8.0) if cancion else 8.0

    with tempfile.TemporaryDirectory() as tmp:
        crudo, vueltas = None, 1
        if esqueletos:
            crudo = render_esqueletos(esqueletos, escena["fondo"], n, tmp, bpm, segundos_musicales)
            d = duracion(crudo)
            vueltas = max(1, math.ceil(SEGUNDOS_MINIMOS / d))  # los movimientos cortos se repiten
            segundos = d * vueltas
        else:
            segundos = segundos_musicales
        total = int(round(segundos * FPS))
        inicio = 55 if esqueletos else 5

        figuras = [Gelatina(p["carpeta"], p["movimiento"], p["lugar"], n, bpm) for p in gelatinas]
        flota = any(p["movimiento"] == "flotar" for p in gelatinas)

        entrada_audio = []
        if cancion:
            wav = Path(tmp) / "musica.wav"
            musica.escribir_wav(cancion, segundos, wav)
            entrada_audio = ["-i", str(wav), "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "160k", "-shortest"]
        ff = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{ANCHO}x{ALTO}",
             "-r", str(FPS), "-i", "-"] + entrada_audio +
            ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", str(escena["salida"])], stdin=subprocess.PIPE)
        for f, cuadro in enumerate(cuadros_base(crudo, fondo_img, total, vueltas)):
            s = f / FPS
            if flota:
                chispitas(cuadro, s)
            for g in figuras:
                g.dibujar(cuadro, s)
            ff.stdin.write(cuadro.tobytes())
            if f % 15 == 0:
                progreso(inicio + (95 - inicio) * f / total)
        ff.stdin.close()
        if ff.wait() != 0:
            raise RuntimeError("ffmpeg no pudo crear el video")


def main():
    escena = json.loads(Path(sys.argv[1]).read_text())
    progreso(2)
    render(escena)
    miniatura(escena["salida"], escena["miniatura"])
    progreso(100)


if __name__ == "__main__":
    main()
