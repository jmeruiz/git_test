"""
Dibujos Mágicos: servidor web.

Guarda todo en la carpeta DATOS (en su computadora, nada sale de la casa):
  personajes/<id>/foto.jpg        la foto original
  personajes/<id>/texture.png     el dibujo recortado
  personajes/<id>/mask.png        qué parte es dibujo (blanco) y qué es papel (negro)
  personajes/<id>/char_cfg.yaml   el esqueleto
  personajes/<id>/info.json       nombre, artista, videos...
  personajes/<id>/videos/*.mp4
"""
import base64
import io
import json
import logging
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, abort, jsonify, request, send_from_directory

from motor import catalogo
from motor.anotar import (ErrorAnotacion, ajustar_puntos, anotar, guardar_char_cfg, leer_puntos,
                          modelos_listos, validar_puntos)

AQUI = Path(__file__).resolve().parent
DATOS = Path(os.environ.get("DATOS", AQUI / "datos"))
PERSONAJES = DATOS / "personajes"
PERSONAJES.mkdir(parents=True, exist_ok=True)
DIRECCION_LAN = os.environ.get("DIRECCION_LAN", "").strip()
PUERTO = int(os.environ.get("PUERTO", "8000"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
app = Flask(__name__, static_folder=str(AQUI / "static"), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024

candado = threading.Lock()
trabajos = {}            # id -> dict con estado del trabajo
cola = queue.Queue()

ID_VALIDO = re.compile(r"^[a-z0-9]{8,32}$")


# ------------------------------------------------------------------ utilidades

def nuevo_id():
    return uuid.uuid4().hex[:12]


def carpeta_de(pid):
    if not ID_VALIDO.match(pid or ""):
        abort(404)
    c = PERSONAJES / pid
    if not (c / "info.json").exists():
        abort(404)
    return c


def leer_info(c):
    with open(c / "info.json", encoding="utf-8") as f:
        return json.load(f)


def guardar_info(c, info):
    tmp = c / "info.json.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    os.replace(tmp, c / "info.json")


def actualizar_info(c, **cambios):
    with candado:
        info = leer_info(c)
        info.update(cambios)
        guardar_info(c, info)
        return info


def ahora():
    return datetime.now().isoformat(timespec="seconds")


def publico(info):
    """Lo que ve la página de un personaje."""
    pid = info["id"]
    v = info.get("version", 0)
    d = dict(info)
    d["textura"] = f"/datos/personajes/{pid}/texture.png?v={v}"
    d["mascara"] = f"/datos/personajes/{pid}/mask.png?v={v}"
    d["videos"] = [dict(x, url=f"/datos/personajes/{pid}/videos/{x['archivo']}",
                        miniatura_url=f"/datos/personajes/{pid}/videos/{x['miniatura']}")
                   for x in info.get("videos", [])]
    d["trabajos"] = [t for t in trabajos.values() if t["personaje"] == pid and t["estado"] in ("en_cola", "trabajando")]
    return d


# ------------------------------------------------------------------ trabajador

def trabajador():
    while True:
        tid = cola.get()
        t = trabajos[tid]
        t["estado"] = "trabajando"
        t["inicio"] = time.time()
        try:
            if t["tipo"] == "anotar":
                hacer_anotacion(t)
            else:
                hacer_video(t)
            t["estado"] = "listo"
            t["progreso"] = 100
        except Exception as e:  # noqa: BLE001 — cualquier error se le muestra al usuario
            logging.exception("Trabajo %s falló", tid)
            t["estado"] = "error"
            t["mensaje"] = str(e) or e.__class__.__name__
            if t["tipo"] == "anotar":
                actualizar_info(PERSONAJES / t["personaje"], estado="error", mensaje=t["mensaje"])
        finally:
            t["fin"] = time.time()
            cola.task_done()


def hacer_anotacion(t):
    c = PERSONAJES / t["personaje"]
    try:
        res = anotar(c / "foto.jpg", c)
    except ErrorAnotacion as e:
        raise RuntimeError(str(e))
    info = leer_info(c)
    actualizar_info(c, estado="revisar", ia=res, ancho=res["ancho"], alto=res["alto"],
                    version=info.get("version", 0) + 1, mensaje="")


def hacer_video(t):
    c = PERSONAJES / t["personaje"]
    (c / "videos").mkdir(exist_ok=True)
    vid = nuevo_id()
    archivo, mini = f"{t['movimiento']}-{t['fondo']}-{vid}.mp4", f"{vid}.jpg"
    trabajo = {"modo": t["modo"], "movimiento": t["movimiento"], "fondo": t["fondo"], "carpeta": str(c),
               "salida": str(c / "videos" / archivo), "miniatura": str(c / "videos" / mini)}
    ruta_json = c / f"trabajo-{vid}.json"
    ruta_json.write_text(json.dumps(trabajo))
    try:
        p = subprocess.Popen([sys.executable, "-m", "motor.render", str(ruta_json)], cwd=str(AQUI),
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        ultimas = []
        for linea in p.stdout:
            m = re.match(r"PROGRESO (\d+)", linea)
            if m:
                t["progreso"] = int(m.group(1))
            else:
                ultimas = (ultimas + [linea.strip()])[-15:]
        if p.wait(timeout=60 * 30) != 0:
            logging.error("Render falló:\n%s", "\n".join(ultimas))
            raise RuntimeError("No se pudo crear el video. " + pista_error("\n".join(ultimas)))
    finally:
        ruta_json.unlink(missing_ok=True)
    _, mov = catalogo.movimiento(t["movimiento"])
    with candado:
        info = leer_info(c)
        info.setdefault("videos", []).insert(0, {
            "id": vid, "archivo": archivo, "miniatura": mini, "movimiento": t["movimiento"],
            "movimiento_nombre": mov["nombre"], "fondo": t["fondo"], "creado": ahora()})
        info["estado"] = "listo"
        guardar_info(c, info)
    t["video"] = vid


def pista_error(texto):
    if "contour" in texto.lower():
        return "Revisa el recorte: parece que quedó vacío."
    return "Prueba con otro movimiento o revisa el esqueleto."


def encolar(tipo, personaje, **extra):
    tid = nuevo_id()
    trabajos[tid] = dict(id=tid, tipo=tipo, personaje=personaje, estado="en_cola", progreso=0,
                         mensaje="", creado=time.time(), **extra)
    cola.put(tid)
    return trabajos[tid]


# ------------------------------------------------------------------ páginas

@app.get("/")
def pagina_inicio():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/nuevo")
def pagina_nuevo():
    return send_from_directory(app.static_folder, "nuevo.html")


@app.get("/personaje/<pid>")
def pagina_personaje(pid):
    return send_from_directory(app.static_folder, "personaje.html")


@app.get("/funcion")
def pagina_funcion():
    return send_from_directory(app.static_folder, "funcion.html")


@app.get("/datos/<path:ruta>")
def archivos_datos(ruta):
    r = send_from_directory(DATOS, ruta)
    r.headers["Cache-Control"] = "no-cache"
    return r


# ------------------------------------------------------------------ API

@app.get("/api/salud")
def salud():
    return jsonify(ok=True)


@app.get("/api/estado")
def estado():
    return jsonify(modelos=modelos_listos(), direccion_lan=DIRECCION_LAN,
                   url_telefono=f"http://{DIRECCION_LAN}:{PUERTO}" if DIRECCION_LAN else "",
                   en_cola=sum(1 for t in trabajos.values() if t["estado"] in ("en_cola", "trabajando")))


@app.get("/api/catalogo")
def api_catalogo():
    return jsonify(esqueleto=catalogo.MOVIMIENTOS_ESQUELETO, gelatina=catalogo.MOVIMIENTOS_GELATINA,
                   fondos=[dict(f, url=f"/static/fondos/{f['id']}.jpg") for f in catalogo.FONDOS])


@app.get("/api/qr.svg")
def qr():
    import qrcode
    import qrcode.image.svg
    url = request.args.get("url", "")[:200]
    if not url:
        abort(400)
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue(), 200, {"Content-Type": "image/svg+xml"}


@app.get("/api/personajes")
def lista():
    res = []
    for c in sorted(PERSONAJES.iterdir(), reverse=True):
        if (c / "info.json").exists():
            try:
                res.append(publico(leer_info(c)))
            except (ValueError, KeyError):
                logging.warning("info.json dañado en %s", c)
    res.sort(key=lambda i: i.get("creado", ""), reverse=True)
    return jsonify(res)


@app.post("/api/personajes")
def crear():
    foto = request.files.get("foto")
    if not foto:
        return jsonify(error="Falta la foto del dibujo."), 400
    nombre = (request.form.get("nombre") or "").strip()[:60] or "Mi dibujo"
    artista = (request.form.get("artista") or "").strip()[:40]
    pid = nuevo_id()
    c = PERSONAJES / pid
    c.mkdir(parents=True)
    try:
        from PIL import Image, ImageOps
        im = ImageOps.exif_transpose(Image.open(foto.stream)).convert("RGB")
        im.thumbnail((2400, 2400))
        im.save(c / "foto.jpg", quality=92)
    except Exception:  # noqa: BLE001
        shutil.rmtree(c, ignore_errors=True)
        return jsonify(error="No pude abrir esa imagen. Prueba con una foto JPG o PNG."), 400
    info = {"id": pid, "nombre": nombre, "artista": artista, "creado": ahora(), "estado": "procesando",
            "videos": [], "version": 0}
    guardar_info(c, info)
    encolar("anotar", pid)
    return jsonify(publico(info)), 201


@app.get("/api/personajes/<pid>")
def ver(pid):
    c = carpeta_de(pid)
    info = publico(leer_info(c))
    if info["estado"] in ("revisar", "listo"):
        info["puntos"] = leer_puntos(c)
    return jsonify(info)


@app.patch("/api/personajes/<pid>")
def renombrar(pid):
    c = carpeta_de(pid)
    datos = request.get_json(force=True)
    cambios = {}
    if "nombre" in datos:
        cambios["nombre"] = str(datos["nombre"]).strip()[:60] or "Mi dibujo"
    if "artista" in datos:
        cambios["artista"] = str(datos["artista"]).strip()[:40]
    return jsonify(publico(actualizar_info(c, **cambios)))


@app.delete("/api/personajes/<pid>")
def borrar(pid):
    c = carpeta_de(pid)
    shutil.rmtree(c)
    return jsonify(ok=True)


@app.post("/api/personajes/<pid>/reintentar")
def reintentar(pid):
    c = carpeta_de(pid)
    actualizar_info(c, estado="procesando", mensaje="")
    encolar("anotar", pid)
    return jsonify(ok=True)


@app.put("/api/personajes/<pid>/anotaciones")
def guardar_anotaciones(pid):
    """Guarda los cambios del editor: puntos del esqueleto y/o máscara."""
    c = carpeta_de(pid)
    info = leer_info(c)
    datos = request.get_json(force=True)
    ancho, alto = info["ancho"], info["alto"]
    piezas = None

    if datos.get("mascara"):
        b64 = datos["mascara"].split(",", 1)[-1]
        arr = np.frombuffer(base64.b64decode(b64), np.uint8)
        m = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
        if m is None:
            return jsonify(error="No pude leer el recorte."), 400
        if m.ndim == 3:
            # el editor manda blanco (dibujo) sobre negro (papel), sin transparencia
            m = cv2.cvtColor(m[:, :, :3], cv2.COLOR_BGR2GRAY)
        m = cv2.resize(m, (ancho, alto), interpolation=cv2.INTER_NEAREST)
        m = np.where(m > 127, 255, 0).astype(np.uint8)
        if m.sum() == 0:
            return jsonify(error="El recorte quedó vacío. Pinta el dibujo con el pincel."), 400
        cv2.imwrite(str(c / "mask.png"), m)

    if datos.get("puntos"):
        puntos = {k: [int(round(v[0])), int(round(v[1]))] for k, v in datos["puntos"].items()}
        error = validar_puntos(puntos, ancho, alto)
        if error:
            return jsonify(error=error), 400
        guardar_char_cfg(c, ajustar_puntos(puntos, ancho, alto), ancho, alto)

    m = cv2.imread(str(c / "mask.png"), cv2.IMREAD_GRAYSCALE)
    piezas = cv2.connectedComponents((m > 0).astype(np.uint8))[0] - 1
    info = actualizar_info(c, version=info.get("version", 0) + 1, piezas=int(piezas),
                           estado="listo" if info.get("videos") else "revisar")
    return jsonify(publico(info))


@app.post("/api/personajes/<pid>/videos")
def crear_video(pid):
    c = carpeta_de(pid)
    info = leer_info(c)
    if info["estado"] not in ("revisar", "listo"):
        return jsonify(error="El dibujo todavía se está preparando."), 409
    datos = request.get_json(force=True)
    modo, mov = catalogo.movimiento(datos.get("movimiento"))
    if not mov:
        return jsonify(error="Ese movimiento no existe."), 400
    fondo = datos.get("fondo") or "papel"
    t = encolar("video", pid, modo=modo, movimiento=mov["id"], fondo=fondo)
    return jsonify(t), 202


@app.delete("/api/personajes/<pid>/videos/<vid>")
def borrar_video(pid, vid):
    c = carpeta_de(pid)
    with candado:
        info = leer_info(c)
        quedan = []
        for v in info.get("videos", []):
            if v["id"] == vid:
                for nombre in (v["archivo"], v["miniatura"]):
                    (c / "videos" / nombre).unlink(missing_ok=True)
            else:
                quedan.append(v)
        info["videos"] = quedan
        guardar_info(c, info)
    return jsonify(ok=True)


@app.get("/api/trabajos/<tid>")
def ver_trabajo(tid):
    t = trabajos.get(tid)
    if not t:
        abort(404)
    pos = 0
    if t["estado"] == "en_cola":
        pos = sum(1 for x in trabajos.values() if x["estado"] in ("en_cola", "trabajando") and x["creado"] < t["creado"])
    return jsonify(dict(t, delante=pos))


@app.get("/api/funcion")
def lista_funcion():
    """Todos los videos, para el modo función (tele)."""
    res = []
    for c in PERSONAJES.iterdir():
        if not (c / "info.json").exists():
            continue
        try:
            info = leer_info(c)
        except ValueError:
            continue
        for v in info.get("videos", []):
            res.append({"url": f"/datos/personajes/{info['id']}/videos/{v['archivo']}",
                        "nombre": info["nombre"], "artista": info.get("artista", ""), "creado": v["creado"]})
    res.sort(key=lambda x: x["creado"], reverse=True)
    return jsonify(res)


def recuperar_pendientes():
    """Si el programa se cerró a medio trabajo, vuelve a preparar esos dibujos."""
    for c in PERSONAJES.iterdir():
        try:
            info = leer_info(c)
        except (OSError, ValueError):
            continue
        if info.get("estado") == "procesando":
            encolar("anotar", info["id"])


if __name__ == "__main__":
    threading.Thread(target=trabajador, daemon=True).start()
    recuperar_pendientes()
    from waitress import serve
    logging.info("Dibujos Mágicos listo en http://localhost:%s", PUERTO)
    serve(app, host="0.0.0.0", port=PUERTO, threads=8)
