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

from motor import canciones, catalogo, musica
from motor.anotar import (ErrorAnotacion, ajustar_puntos, anotar, guardar_char_cfg, leer_puntos,
                          modelos_listos, validar_puntos)

AQUI = Path(__file__).resolve().parent
DATOS = Path(os.environ.get("DATOS", AQUI / "datos"))
PERSONAJES = DATOS / "personajes"
FIESTAS = DATOS / "fiestas"
CACHE = DATOS / "cache"
for _c in (PERSONAJES, FIESTAS, CACHE):
    _c.mkdir(parents=True, exist_ok=True)
DIRECCION_LAN = os.environ.get("DIRECCION_LAN", "").strip()
PUERTO = int(os.environ.get("PUERTO", "8000"))
# El puerto por el que se entra desde afuera del contenedor (puede ser otro, ver .env)
PUERTO_PUBLICO = int(os.environ.get("PUERTO_PUBLICO", PUERTO))

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

MANEJADORES = {}  # tipo de trabajo -> función; se llenan abajo


def procesar(tid):
    """Hace un trabajo de la cola y guarda su resultado (o su error) en `trabajos`."""
    t = trabajos[tid]
    t["estado"] = "trabajando"
    t["inicio"] = time.time()
    try:
        MANEJADORES[t["tipo"]](t)
        t["estado"] = "listo"
        t["progreso"] = 100
    except Exception as e:  # noqa: BLE001 — cualquier error se le muestra al usuario
        logging.exception("Trabajo %s falló", tid)
        t["estado"] = "error"
        t["mensaje"] = str(e) or e.__class__.__name__
        if t["tipo"] == "anotar":
            actualizar_info(PERSONAJES / t["personaje"], estado="error", mensaje=t["mensaje"])
        if t["tipo"] == "fiesta":
            actualizar_info(FIESTAS / t["fiesta"], estado="error", mensaje=t["mensaje"])
    finally:
        t["fin"] = time.time()


def trabajador():
    """Hilo que hace los trabajos de uno en uno (crear videos usa todo el procesador)."""
    while True:
        tid = cola.get()
        try:
            procesar(tid)
        finally:
            cola.task_done()


def procesar_pendientes():
    """Hace ahora mismo todo lo que está en la cola. Para las pruebas."""
    while not cola.empty():
        tid = cola.get()
        procesar(tid)
        cola.task_done()


def hacer_anotacion(t):
    c = PERSONAJES / t["personaje"]
    try:
        res = anotar(c / "foto.jpg", c)
    except ErrorAnotacion as e:
        raise RuntimeError(str(e)) from e
    info = leer_info(c)
    actualizar_info(c, estado="revisar", ia=res, ancho=res["ancho"], alto=res["alto"],
                    version=info.get("version", 0) + 1, mensaje="")


def correr_render(t, escena, carpeta):
    """Corre motor.render en otro proceso y va actualizando el progreso del trabajo."""
    ruta_json = carpeta / f"escena-{nuevo_id()}.json"
    ruta_json.write_text(json.dumps(escena))
    try:
        p = subprocess.Popen([sys.executable, "-m", "motor.render", str(ruta_json)], cwd=str(AQUI),
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        ultimas = []
        for linea in p.stdout:
            m = re.match(r"PROGRESO (\d+)", linea)
            if m:
                t["progreso"] = int(m.group(1))
            elif "it/s]" not in linea:
                ultimas = (ultimas + [linea.strip()])[-15:]
        if p.wait(timeout=60 * 30) != 0:
            logging.error("Render falló:\n%s", "\n".join(ultimas))
            raise RuntimeError("No se pudo crear el video. " + pista_error("\n".join(ultimas)))
    finally:
        ruta_json.unlink(missing_ok=True)


def hacer_video(t):
    """Video de un solo personaje."""
    c = PERSONAJES / t["personaje"]
    (c / "videos").mkdir(exist_ok=True)
    vid = nuevo_id()
    archivo, mini = f"{t['movimiento']}-{t['fondo']}-{vid}.mp4", f"{vid}.jpg"
    escena = {"fondo": t["fondo"], "musica": t["musica"],
              "personajes": [{"carpeta": str(c), "modo": t["modo"], "movimiento": t["movimiento"]}],
              "salida": str(c / "videos" / archivo), "miniatura": str(c / "videos" / mini)}
    correr_render(t, escena, c)
    _, mov = catalogo.movimiento(t["movimiento"])
    with candado:
        info = leer_info(c)
        info.setdefault("videos", []).insert(0, {
            "id": vid, "archivo": archivo, "miniatura": mini, "movimiento": t["movimiento"],
            "movimiento_nombre": mov["nombre"], "fondo": t["fondo"], "musica": t["musica"], "creado": ahora()})
        info["estado"] = "listo"
        info["modo_preferido"] = t["modo"]
        guardar_info(c, info)
    t["video"] = vid


def hacer_fiesta(t):
    """Video con varios personajes juntos."""
    c = FIESTAS / t["fiesta"]
    info = leer_info(c)
    escena = {"fondo": info["fondo"], "musica": info["musica"],
              "personajes": [{"carpeta": str(PERSONAJES / p["id"]), "modo": p["modo"], "movimiento": p["movimiento"]}
                             for p in info["personajes"]],
              "salida": str(c / "fiesta.mp4"), "miniatura": str(c / "fiesta.jpg")}
    correr_render(t, escena, c)
    actualizar_info(c, estado="listo", mensaje="")


MANEJADORES.update(anotar=hacer_anotacion, video=hacer_video, fiesta=hacer_fiesta)


def pista_error(texto):
    if "contour" in texto.lower():
        return "Revisa el recorte: parece que quedó vacío."
    return "Prueba con otro movimiento o revisa el esqueleto."


def encolar(tipo, personaje=None, **extra):
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


@app.get("/fiesta")
def pagina_fiesta():
    return send_from_directory(app.static_folder, "fiesta.html")


@app.get("/canciones")
def pagina_canciones():
    return send_from_directory(app.static_folder, "canciones.html")


@app.get("/ayuda")
def pagina_ayuda():
    return send_from_directory(app.static_folder, "ayuda.html")


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
                   url_telefono=f"http://{DIRECCION_LAN}:{PUERTO_PUBLICO}" if DIRECCION_LAN else "",
                   en_cola=sum(1 for t in trabajos.values() if t["estado"] in ("en_cola", "trabajando")))


@app.get("/api/catalogo")
def api_catalogo():
    return jsonify(esqueleto=catalogo.MOVIMIENTOS_ESQUELETO, gelatina=catalogo.MOVIMIENTOS_GELATINA,
                   fondos=[dict(f, url=f"/static/fondos/{f['id']}.jpg") for f in catalogo.FONDOS],
                   musica=[dict(m, url=f"/api/musica/{m['id']}.wav") for m in musica.LISTA]
                   + [publico_cancion(c) for c in canciones.lista()])


def publico_cancion(c):
    return {"id": canciones.PREFIJO + c["id"], "nombre": c["nombre"], "icono": "🎵", "propia": True,
            "url": f"/datos/canciones/{c['id']}/muestra.mp3?v={c['inicio']}", "inicio": c["inicio"],
            "duracion": c["duracion"], "bpm": c["bpm"]}


# ------------------------------------------------------------------ mis canciones

@app.get("/api/canciones")
def lista_canciones():
    return jsonify([publico_cancion(c) for c in canciones.lista()])


@app.post("/api/canciones")
def subir_cancion():
    archivo = request.files.get("archivo")
    if not archivo or not archivo.filename:
        return jsonify(error="Falta el archivo de la canción."), 400
    try:
        info = canciones.crear(nuevo_id(), archivo, archivo.filename, request.form.get("nombre", "").strip(),
                               request.form.get("inicio") or 0, ahora())
    except (canciones.ErrorCancion, ValueError) as e:
        return jsonify(error=str(e)), 400
    return jsonify(publico_cancion(info)), 201


@app.patch("/api/canciones/<cid>")
def cambiar_cancion(cid):
    datos = request.get_json(force=True)
    try:
        info = canciones.cambiar(cid, nombre=datos.get("nombre"), inicio=datos.get("inicio"))
    except (canciones.ErrorCancion, ValueError) as e:
        return jsonify(error=str(e)), 400
    return jsonify(publico_cancion(info))


@app.delete("/api/canciones/<cid>")
def borrar_cancion(cid):
    info = canciones.leer(cid)
    if not info:
        abort(404)
    shutil.rmtree(canciones.carpeta() / info["id"])
    return jsonify(ok=True)


candado_musica = threading.Lock()


@app.get("/api/musica/<cancion>.wav")
def muestra_musica(cancion):
    """Diez segunditos de la canción, para escucharla antes de elegirla."""
    if cancion not in musica.CANCIONES:
        abort(404)
    ruta = CACHE / f"muestra-{cancion}.wav"
    with candado_musica:
        if not ruta.exists():
            musica.escribir_wav(cancion, musica.duracion_en_compases(cancion, 9.0), ruta)
    return send_from_directory(CACHE, ruta.name, mimetype="audio/wav")


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
    cancion = datos.get("musica")
    if not musica.existe(cancion):
        cancion = "ninguna"
    t = encolar("video", pid, modo=modo, movimiento=mov["id"], fondo=fondo, musica=cancion)
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


# ------------------------------------------------------------------ fiestas

def publico_fiesta(info):
    fid = info["id"]
    d = dict(info)
    if info.get("estado") == "listo":
        d["url"] = f"/datos/fiestas/{fid}/fiesta.mp4"
        d["miniatura_url"] = f"/datos/fiestas/{fid}/fiesta.jpg"
    d["trabajo"] = next((t["id"] for t in trabajos.values()
                         if t.get("fiesta") == fid and t["estado"] in ("en_cola", "trabajando")), None)
    return d


@app.get("/api/fiestas")
def lista_fiestas():
    res = []
    for c in FIESTAS.iterdir():
        try:
            res.append(publico_fiesta(leer_info(c)))
        except (OSError, ValueError, KeyError):
            continue
    res.sort(key=lambda f: f.get("creado", ""), reverse=True)
    return jsonify(res)


@app.post("/api/fiestas")
def crear_fiesta():
    datos = request.get_json(force=True)
    elegidos = datos.get("personajes") or []
    if not 2 <= len(elegidos) <= 5:
        return jsonify(error="Elijan entre 2 y 5 personajes para la fiesta."), 400
    baile_modo, baile = catalogo.movimiento(datos.get("movimiento"))
    if not baile:
        return jsonify(error="Ese baile no existe."), 400
    personajes = []
    for e in elegidos:
        pid = str(e.get("id", ""))
        if not ID_VALIDO.match(pid) or not (PERSONAJES / pid / "info.json").exists():
            return jsonify(error="Uno de los personajes ya no existe."), 400
        info = leer_info(PERSONAJES / pid)
        if info["estado"] not in ("revisar", "listo"):
            return jsonify(error=f"{info['nombre']} todavía se está preparando."), 409
        modo = "esqueleto" if e.get("modo") == "esqueleto" and baile_modo == "esqueleto" else "gelatina"
        # todos los de esqueleto hacen el mismo baile; los gelatina, su versión de ese baile
        mov = baile["id"] if modo == "esqueleto" else (baile.get("gelatina") or baile["id"])
        personajes.append({"id": pid, "nombre": info["nombre"], "artista": info.get("artista", ""),
                           "modo": modo, "movimiento": mov})
    cancion = datos.get("musica")
    if not musica.existe(cancion):
        cancion = "ninguna"
    fid = nuevo_id()
    c = FIESTAS / fid
    c.mkdir(parents=True)
    info = {"id": fid, "personajes": personajes, "movimiento": baile["id"], "movimiento_nombre": baile["nombre"],
            "fondo": datos.get("fondo") or "parque", "musica": cancion, "creado": ahora(), "estado": "creando"}
    guardar_info(c, info)
    t = encolar("fiesta", fiesta=fid)
    return jsonify(dict(publico_fiesta(info), trabajo=t["id"])), 202


@app.delete("/api/fiestas/<fid>")
def borrar_fiesta(fid):
    if not ID_VALIDO.match(fid or "") or not (FIESTAS / fid).is_dir():
        abort(404)
    shutil.rmtree(FIESTAS / fid)
    return jsonify(ok=True)


def videos_funcion():
    """Todos los videos y fiestas, del más nuevo al más viejo."""
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
    for c in FIESTAS.iterdir():
        try:
            f = leer_info(c)
        except (OSError, ValueError):
            continue
        if f.get("estado") == "listo":
            nombres = [p["nombre"] for p in f["personajes"]]
            res.append({"url": f"/datos/fiestas/{f['id']}/fiesta.mp4", "nombre": "¡Fiesta!",
                        "artista": "", "invitados": nombres, "creado": f["creado"]})
    res.sort(key=lambda x: x["creado"], reverse=True)
    return res


@app.get("/api/funcion")
def lista_funcion():
    """Todos los videos, para el modo función (tele)."""
    return jsonify(videos_funcion())


# ------------------------------------------------------------------ celular → tele
# El modo función pregunta cada pocos segundos; el celular puede pedirle que ponga un video ya.
tele = {"n": 0, "pedido": None, "visto": 0.0}


@app.get("/api/tele")
def estado_tele():
    tele["visto"] = time.time()
    return jsonify(n=tele["n"], pedido=tele["pedido"], total=len(videos_funcion()))


@app.post("/api/tele")
def pedir_a_tele():
    url = (request.get_json(force=True) or {}).get("url", "")
    video = next((v for v in videos_funcion() if v["url"] == url), None)
    if not video:
        return jsonify(error="Ese video ya no existe."), 404
    tele["n"] += 1
    tele["pedido"] = video
    conectada = time.time() - tele["visto"] < 10
    return jsonify(ok=True, conectada=conectada)





def recuperar_pendientes():
    """Si el programa se cerró a medio trabajo, vuelve a preparar esos dibujos."""
    for c in PERSONAJES.iterdir():
        try:
            info = leer_info(c)
        except (OSError, ValueError):
            continue
        if info.get("estado") == "procesando":
            encolar("anotar", info["id"])
    for c in FIESTAS.iterdir():
        try:
            info = leer_info(c)
        except (OSError, ValueError):
            continue
        if info.get("estado") == "creando":
            encolar("fiesta", fiesta=info["id"])


if __name__ == "__main__":
    threading.Thread(target=trabajador, daemon=True).start()
    recuperar_pendientes()
    from waitress import serve
    logging.info("Dibujos Mágicos listo en http://localhost:%s", PUERTO)
    serve(app, host="0.0.0.0", port=PUERTO, threads=8)
