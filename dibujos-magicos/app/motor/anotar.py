"""
Paso 1: de una foto a un "personaje" listo para animar.

1. Busca el dibujo en la foto (modelo de Meta). Si no lo encuentra, usa la tinta del papel.
2. Recorta el dibujo del papel (máscara).
3. Adivina dónde están cabeza, brazos y piernas (modelo de Meta). Si no puede,
   pone un esqueleto de plantilla que luego se acomoda a mano.

Basado en examples/image_to_annotations.py de facebookresearch/AnimatedDrawings (MIT).
"""
import json
import logging
import os
from pathlib import Path

import cv2
import numpy as np
import requests
import yaml
from PIL import Image, ImageOps
from scipy import ndimage

MODELOS_URL = os.environ.get("MODELOS_URL", "http://modelos:8080")
LADO_MAX = 1000

# Nombres de articulaciones que usa Animated Drawings, en el orden del archivo.
# "right" es la derecha del personaje (o sea, la izquierda en la imagen).
ARTICULACIONES = [
    ("root", None), ("hip", "root"), ("torso", "hip"), ("neck", "torso"),
    ("right_shoulder", "torso"), ("right_elbow", "right_shoulder"), ("right_hand", "right_elbow"),
    ("left_shoulder", "torso"), ("left_elbow", "left_shoulder"), ("left_hand", "left_elbow"),
    ("right_hip", "root"), ("right_knee", "right_hip"), ("right_foot", "right_knee"),
    ("left_hip", "root"), ("left_knee", "left_hip"), ("left_foot", "left_knee"),
]

# Plantilla de persona (fracciones de la caja del dibujo), para cuando la IA no encuentra el esqueleto.
PLANTILLA = {
    "neck": (0.50, 0.16), "torso": (0.50, 0.36), "hip": (0.50, 0.58), "root": (0.50, 0.58),
    "right_shoulder": (0.32, 0.34), "right_elbow": (0.20, 0.46), "right_hand": (0.09, 0.56),
    "left_shoulder": (0.68, 0.34), "left_elbow": (0.80, 0.46), "left_hand": (0.91, 0.56),
    "right_hip": (0.40, 0.60), "right_knee": (0.38, 0.78), "right_foot": (0.36, 0.95),
    "left_hip": (0.60, 0.60), "left_knee": (0.62, 0.78), "left_foot": (0.64, 0.95),
}


class ErrorAnotacion(Exception):
    pass


def cargar_foto(ruta):
    """Abre la foto respetando la orientación del celular y la reduce a 1000 px."""
    im = Image.open(ruta)
    im = ImageOps.exif_transpose(im).convert("RGB")
    w, h = im.size
    if max(w, h) > LADO_MAX:
        s = LADO_MAX / max(w, h)
        im = im.resize((round(w * s), round(h * s)), Image.LANCZOS)
    return cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR)


def modelos_listos(timeout=2):
    try:
        r = requests.get(MODELOS_URL + "/ping", timeout=timeout)
        return r.ok and "Healthy" in r.text
    except requests.RequestException:
        return False


def _predecir(modelo, img_bgr):
    datos = {"data": cv2.imencode(".png", img_bgr)[1].tobytes()}
    r = requests.post(f"{MODELOS_URL}/predictions/{modelo}", files=datos, timeout=120)
    if r.status_code >= 300:
        raise ErrorAnotacion(f"El modelo {modelo} respondió {r.status_code}")
    res = json.loads(r.content)
    if isinstance(res, dict):
        raise ErrorAnotacion(f"El modelo {modelo} respondió: {res}")
    return res


def mascara_tinta(img_bgr):
    """
    Separa el dibujo del papel. Igual que el método de Meta (umbral adaptativo + relleno
    desde los bordes), pero conserva todas las partes grandes del dibujo, no solo la mayor,
    para que los garabatos con trazos sueltos no pierdan pedazos.
    """
    gris = np.min(img_bgr, axis=2)
    tinta = cv2.adaptiveThreshold(gris, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 115, 8)
    tinta = cv2.bitwise_not(tinta)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    tinta = cv2.morphologyEx(tinta, cv2.MORPH_CLOSE, k, iterations=2)
    tinta = cv2.morphologyEx(tinta, cv2.MORPH_DILATE, k, iterations=1)

    relleno = ndimage.binary_fill_holes(tinta > 0)
    n, etiquetas, stats, _ = cv2.connectedComponentsWithStats(relleno.astype(np.uint8), connectivity=8)
    if n <= 1:
        raise ErrorAnotacion("No encontré ningún trazo en la foto.")
    areas = stats[1:, cv2.CC_STAT_AREA]
    mayor = int(np.argmax(areas)) + 1
    h, w = gris.shape
    mascara = np.zeros((h, w), np.uint8)
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        toca_borde = x <= 1 or y <= 1 or x + bw >= w - 1 or y + bh >= h - 1
        if i == mayor or (area >= 0.04 * areas.max() and not toca_borde):
            mascara[etiquetas == i] = 255
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, k, iterations=1)
    return mascara


def blanquear_papel(img_bgr):
    """
    Hace que el papel se vea blanco parejo (quita sombras y el tono gris de la foto)
    sin cambiar los colores del dibujo: divide cada canal entre una estimación del papel.
    """
    k = max(15, (min(img_bgr.shape[:2]) // 20) | 1)
    papel = cv2.morphologyEx(img_bgr, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    papel = cv2.GaussianBlur(papel, (0, 0), k / 2)
    limpio = np.clip(img_bgr.astype(np.float32) / np.maximum(papel.astype(np.float32), 1) * 255 * 1.03, 0, 255)
    return limpio.astype(np.uint8)


def _caja(mascara, margen=0.04):
    ys, xs = np.where(mascara > 0)
    if len(xs) == 0:
        raise ErrorAnotacion("La máscara quedó vacía.")
    h, w = mascara.shape
    l, r, t, b = xs.min(), xs.max(), ys.min(), ys.max()
    mx, my = int((r - l) * margen) + 4, int((b - t) * margen) + 4
    return max(0, l - mx), max(0, t - my), min(w, r + mx + 1), min(h, b + my + 1)


def esqueleto_plantilla(mascara):
    l, t, r, b = _caja(mascara, margen=0)
    bw, bh = r - l, b - t
    return {n: [int(l + fx * bw), int(t + fy * bh)] for n, (fx, fy) in PLANTILLA.items()}


def esqueleto_desde_puntos(k):
    """Convierte los 17 puntos COCO del modelo de pose al esqueleto de Animated Drawings."""
    p = lambda a: [int(round(v)) for v in a]
    return {
        "root": p((k[11] + k[12]) / 2), "hip": p((k[11] + k[12]) / 2), "torso": p((k[5] + k[6]) / 2),
        "neck": p(k[0]),
        "right_shoulder": p(k[6]), "right_elbow": p(k[8]), "right_hand": p(k[10]),
        "left_shoulder": p(k[5]), "left_elbow": p(k[7]), "left_hand": p(k[9]),
        "right_hip": p(k[12]), "right_knee": p(k[14]), "right_foot": p(k[16]),
        "left_hip": p(k[11]), "left_knee": p(k[13]), "left_foot": p(k[15]),
    }


def guardar_char_cfg(carpeta, puntos, ancho, alto):
    esqueleto = [{"loc": [int(puntos[n][0]), int(puntos[n][1])], "name": n, "parent": padre}
                 for n, padre in ARTICULACIONES]
    with open(Path(carpeta) / "char_cfg.yaml", "w") as f:
        yaml.dump({"skeleton": esqueleto, "height": int(alto), "width": int(ancho)}, f)


def leer_puntos(carpeta):
    with open(Path(carpeta) / "char_cfg.yaml") as f:
        cfg = yaml.safe_load(f)
    return {j["name"]: j["loc"] for j in cfg["skeleton"]}


def ajustar_puntos(puntos, ancho, alto):
    """Mete al borde los puntos que hayan quedado un poquito fuera del dibujo."""
    return {n: [int(min(max(x, 0), ancho - 1)), int(min(max(y, 0), alto - 1))] for n, (x, y) in puntos.items()}


def validar_puntos(puntos, ancho, alto):
    faltan = [n for n, _ in ARTICULACIONES if n not in puntos]
    if faltan:
        return "Faltan puntos: " + ", ".join(faltan)
    for x, y in puntos.values():
        if not (-50 <= x < ancho + 50 and -50 <= y < alto + 50):
            return "Hay un punto fuera del dibujo."
    return None


def anotar(ruta_foto, carpeta):
    """
    Crea image.png, texture.png, mask.png y char_cfg.yaml en `carpeta`.
    Devuelve un dict con lo que hizo la IA, para avisarle al usuario qué revisar.
    """
    carpeta = Path(carpeta)
    img = cargar_foto(ruta_foto)
    cv2.imwrite(str(carpeta / "image.png"), img)
    h, w = img.shape[:2]
    resultado = {"ia_detecto": False, "ia_pose": False}

    caja = None
    if modelos_listos(timeout=5):
        try:
            dets = _predecir("drawn_humanoid_detector", img)
            dets.sort(key=lambda d: d["score"], reverse=True)
            if dets and dets[0]["score"] >= 0.3:
                l, t, r, b = [int(round(v)) for v in dets[0]["bbox"]]
                mx, my = int((r - l) * 0.03), int((b - t) * 0.03)
                caja = (max(0, l - mx), max(0, t - my), min(w, r + mx), min(h, b + my))
                resultado["ia_detecto"] = True
                resultado["confianza"] = round(float(dets[0]["score"]), 2)
        except (requests.RequestException, ErrorAnotacion, KeyError, ValueError) as e:
            logging.warning("Detección falló: %s", e)

    if caja is None:
        caja = _caja(mascara_tinta(img))

    l, t, r, b = caja
    recorte = img[t:b, l:r].copy()
    if recorte.shape[0] < 20 or recorte.shape[1] < 20:
        raise ErrorAnotacion("El dibujo salió demasiado pequeño en la foto.")
    mascara = mascara_tinta(recorte)

    puntos = None
    if resultado["ia_detecto"]:
        try:
            poses = _predecir("drawn_humanoid_pose_estimator", recorte)
            if poses:
                kp = np.array(poses[0]["keypoints"])
                puntos = esqueleto_desde_puntos(kp[:, :2])
                if validar_puntos(puntos, recorte.shape[1], recorte.shape[0]) is None:
                    puntos = ajustar_puntos(puntos, recorte.shape[1], recorte.shape[0])
                    # Confianza de hombros, codos, manos, caderas, rodillas y pies.
                    # Figuras con brazos y piernas dan ~0.9; garabatos, ~0.3.
                    confianza = float(kp[5:17, 2].mean()) if kp.shape[1] > 2 else 1.0
                    resultado["confianza_pose"] = round(confianza, 2)
                    resultado["ia_pose"] = confianza >= 0.55
                else:
                    puntos = None
        except (requests.RequestException, ErrorAnotacion, KeyError, ValueError, IndexError) as e:
            logging.warning("Pose falló: %s", e)
    if puntos is None:
        puntos = esqueleto_plantilla(mascara)

    cv2.imwrite(str(carpeta / "texture.png"), cv2.cvtColor(blanquear_papel(recorte), cv2.COLOR_BGR2BGRA))
    cv2.imwrite(str(carpeta / "mask.png"), mascara)
    guardar_char_cfg(carpeta, puntos, recorte.shape[1], recorte.shape[0])
    resultado.update({"ancho": recorte.shape[1], "alto": recorte.shape[0]})
    return resultado
