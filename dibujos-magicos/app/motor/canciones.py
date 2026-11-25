"""
"Mis canciones": música propia de la familia (archivos MP3, M4A, WAV…).

Se guarda en DATOS/canciones/<id>/ y nunca sale de la computadora:
  original.<ext>   el archivo tal como lo subieron
  muestra.mp3      unos segundos desde el punto de inicio, para escucharla en la página
  info.json        nombre, desde qué segundo empieza, duración y ritmo (pulsos por minuto)

Al usarla en un video se corta desde el inicio elegido, se empareja el volumen y se
desvanece al final. El ritmo se estima solo, para que los personajes se muevan al compás.
"""
import json
import math
import os
import re
import subprocess
from pathlib import Path

import numpy as np

PREFIJO = "propia-"
EXTENSIONES = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".oga", ".flac", ".opus", ".webm", ".mp4"}
SEGUNDOS_MUESTRA = 12
VOLUMEN = "loudnorm=I=-18:TP=-2:LRA=11"   # parejo y un poquito más bajo que la radio


class ErrorCancion(Exception):
    pass


def carpeta():
    c = Path(os.environ.get("DATOS", "/datos")) / "canciones"
    c.mkdir(parents=True, exist_ok=True)
    return c


def es_propia(cancion_id):
    return isinstance(cancion_id, str) and cancion_id.startswith(PREFIJO)


def _cid(cancion_id):
    cid = cancion_id[len(PREFIJO):] if es_propia(cancion_id) else cancion_id
    if not re.match(r"^[a-z0-9]{8,32}$", cid or ""):
        raise ErrorCancion("Esa canción no existe.")
    return cid


def leer(cancion_id):
    """El info.json de una canción propia, o None si no existe."""
    try:
        ruta = carpeta() / _cid(cancion_id) / "info.json"
        return json.loads(ruta.read_text()) if ruta.exists() else None
    except (ErrorCancion, ValueError):
        return None


def guardar(info):
    c = carpeta() / info["id"]
    tmp = c / "info.json.tmp"
    tmp.write_text(json.dumps(info, ensure_ascii=False, indent=1))
    os.replace(tmp, c / "info.json")


def lista():
    res = []
    for c in carpeta().iterdir():
        info = leer(c.name)
        if info:
            res.append(info)
    res.sort(key=lambda i: i.get("creado", ""), reverse=True)
    return res


def original(info):
    return carpeta() / info["id"] / info["archivo"]


def duracion(ruta):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_type:format=duration",
                        "-of", "json", str(ruta)], capture_output=True, text=True)
    try:
        datos = json.loads(r.stdout)
        if not datos.get("streams"):
            raise ErrorCancion("Ese archivo no tiene sonido.")
        return float(datos["format"]["duration"])
    except (ValueError, KeyError) as e:
        raise ErrorCancion("No pude leer ese archivo de música. Prueben con un MP3 o M4A.") from e


def _pcm(ruta, inicio, segundos, sr):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(inicio), "-t", str(segundos), "-i", str(ruta),
                        "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0


def estimar_bpm(ruta, inicio=0.0, segundos=40.0):
    """
    Estima el ritmo: busca cada cuánto se repiten los golpes (autocorrelación del "flujo
    espectral", o sea de cuánto aumenta el sonido de un instante al otro). Devuelve entre 70 y 160.
    """
    sr, ventana, salto = 22050, 1024, 512
    x = _pcm(ruta, inicio, segundos, sr)
    if len(x) < sr * 4:
        return 110.0
    n = 1 + (len(x) - ventana) // salto
    marcos = np.lib.stride_tricks.as_strided(x, (n, ventana), (x.strides[0] * salto, x.strides[0]))
    espectro = np.log1p(30 * np.abs(np.fft.rfft(marcos * np.hanning(ventana), axis=1)))
    flujo = np.maximum(0, np.diff(espectro, axis=0)).sum(axis=1)
    flujo -= np.convolve(flujo, np.ones(16) / 16, mode="same")   # quitar la tendencia lenta
    flujo = np.maximum(flujo, 0)
    fps = sr / salto
    auto = np.correlate(flujo, flujo, mode="full")[len(flujo) - 1:]
    def en(lag):
        i = int(lag)
        return auto[i] * (1 - (lag - i)) + auto[i + 1] * (lag - i) if i + 1 < len(auto) else 0.0

    mejor, puntaje = 110.0, -1.0
    for bpm in np.arange(70, 160.5, 0.5):
        lag = fps * 60 / bpm
        # un pulso verdadero también se repite a los 2, 3 y 4 pulsos: así no se confunde
        # con ritmos "de tresillo" (2/3 del real), que es el error más común
        valor = sum(en(lag * k) / k for k in (1, 2, 3, 4))
        valor *= math.exp(-0.5 * (math.log2(bpm / 115) / 0.9) ** 2)   # preferir ritmos de baile comunes
        if valor > puntaje:
            mejor, puntaje = float(bpm), valor
    return round(mejor, 1)


def hacer_muestra(info):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(info["inicio"]), "-t", str(SEGUNDOS_MUESTRA),
                    "-i", str(original(info)),
                    "-af", f"{VOLUMEN},afade=t=in:d=0.3,afade=t=out:st={SEGUNDOS_MUESTRA - 1.5}:d=1.5",
                    "-ac", "2", "-ar", "44100", "-b:a", "128k", str(carpeta() / info["id"] / "muestra.mp3")], check=True)


def escribir_wav(cancion_id, segundos, ruta):
    """El pedacito de la canción que va en el video, con volumen parejo y final desvanecido."""
    info = leer(cancion_id)
    if not info:
        raise ErrorCancion("Esa canción ya no existe.")
    fin = max(0.1, segundos - 1.5)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(info["inicio"]), "-t", str(segundos),
                    "-i", str(original(info)),
                    "-af", f"{VOLUMEN},apad=whole_dur={segundos},afade=t=in:d=0.2,afade=t=out:st={fin}:d=1.5",
                    "-ac", "2", "-ar", "44100", "-t", str(segundos), str(ruta)], check=True)


def bpm_de(cancion_id):
    info = leer(cancion_id)
    return info["bpm"] if info else 110.0


def crear(cid, archivo_subido, nombre_archivo, nombre, inicio, ahora):
    """Guarda una canción subida y la prepara. Devuelve su info."""
    ext = Path(nombre_archivo or "").suffix.lower()
    if ext not in EXTENSIONES:
        raise ErrorCancion("Ese tipo de archivo no lo reconozco. Usen MP3, M4A, WAV, OGG o FLAC.")
    c = carpeta() / cid
    c.mkdir(parents=True)
    ruta = c / f"original{ext}"
    archivo_subido.save(str(ruta))
    try:
        dur = duracion(ruta)
        if dur < 3:
            raise ErrorCancion("La canción es demasiado corta.")
        inicio = min(max(0.0, float(inicio or 0)), max(0.0, dur - 3))
        info = {"id": cid, "nombre": (nombre or Path(nombre_archivo).stem)[:60], "archivo": ruta.name,
                "duracion": round(dur, 1), "inicio": round(inicio, 1), "bpm": estimar_bpm(ruta, inicio), "creado": ahora}
        guardar(info)
        hacer_muestra(info)
        return info
    except Exception:
        import shutil
        shutil.rmtree(c, ignore_errors=True)
        raise


def cambiar(cancion_id, nombre=None, inicio=None):
    info = leer(cancion_id)
    if not info:
        raise ErrorCancion("Esa canción ya no existe.")
    if nombre is not None:
        info["nombre"] = str(nombre).strip()[:60] or info["nombre"]
    if inicio is not None:
        nuevo = min(max(0.0, float(inicio)), max(0.0, info["duracion"] - 3))
        if abs(nuevo - info["inicio"]) > 0.05:
            info["inicio"] = round(nuevo, 1)
            info["bpm"] = estimar_bpm(original(info), info["inicio"])
            hacer_muestra(info)
    guardar(info)
    return info
