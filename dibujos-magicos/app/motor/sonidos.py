"""
Efectos de sonido, hechos con el mismo sintetizador que la música (sin archivos ni derechos).

Cada movimiento dice en qué pulsos suena qué (ver EVENTOS). Como los movimientos también se
miden en pulsos de la canción, el *boing* cae justo cuando el dibujo toca el suelo.
"""
import math

import numpy as np

from motor.musica import SR, _t, hz, instrumento, midi, palmas

_ruido = np.random.RandomState(5).uniform(-1, 1, SR * 2)


def _paso_bajo(x, inicio_hz, fin_hz):
    """Filtro que deja pasar los graves, con el corte cambiando de inicio_hz a fin_hz."""
    corte = np.linspace(inicio_hz, fin_hz, len(x))
    a = 1 - np.exp(-2 * math.pi * corte / SR)
    y = np.empty_like(x)
    acumulado = 0.0
    for i in range(len(x)):
        acumulado += a[i] * (x[i] - acumulado)
        y[i] = acumulado
    return y


def boing():
    t = _t(0.42)
    f = 150 + 280 * np.exp(-t / 0.045) + 30 * np.sin(2 * math.pi * 11 * t) * np.exp(-t / 0.3)
    return np.sin(2 * math.pi * np.cumsum(f) / SR) * np.exp(-t / 0.2) * 0.9


def bamboleo():
    t = _t(0.5)
    f = 110 + 40 * np.sin(2 * math.pi * 7 * t)
    return np.sin(2 * math.pi * np.cumsum(f) / SR) * np.exp(-t / 0.25) * 0.6


def swish(dur=0.28):
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = np.sin(math.pi * t / dur) ** 2
    return _paso_bajo(_ruido[:n], 600, 3500) * env * 2.2


def fiuu():
    """Despegue: un soplido que sube, con un tono que también sube."""
    n = int(1.3 * SR)
    t = np.arange(n) / SR
    env = np.minimum(1, t / 0.15) * np.exp(-np.maximum(0, t - 0.6) / 0.35)
    soplido = _paso_bajo(_ruido[:n], 300, 4000) * 2.4
    tono = np.sin(2 * math.pi * np.cumsum(220 + 700 * t / 1.3) / SR) * 0.18
    return (soplido + tono) * env


def retumbo(dur=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    grave = _paso_bajo(_ruido[SR // 2:SR // 2 + n], 90, 90) * 6
    env = np.minimum(1, t / 0.2) * np.clip((dur - t) / 0.3, 0, 1) * (0.7 + 0.3 * np.sin(2 * math.pi * 9 * t))
    return (grave + np.sin(2 * math.pi * 48 * t) * 0.35) * env


def golpe(fuerza=1.0):
    t = _t(0.3)
    f = 45 + 90 * np.exp(-t / 0.03)
    return np.sin(2 * math.pi * np.cumsum(f) / SR) * np.exp(-t / 0.12) * fuerza


def burbujas():
    salida = np.zeros(int(0.5 * SR))
    for k, inicio in enumerate((0.0, 0.09, 0.2, 0.32)):
        t = _t(0.07)
        f = (350 + 120 * k) * (1 + 2.2 * t / 0.07)
        blip = np.sin(2 * math.pi * np.cumsum(f) / SR) * np.exp(-t / 0.03) * 0.6
        i = int(inicio * SR)
        salida[i:i + len(blip)] += blip
    return salida


def tada():
    salida = np.zeros(int(1.4 * SR))
    for k, nota in enumerate(("C5", "E5", "G5", "C6")):
        s = instrumento("cajita", hz(midi(nota)), 0.6)
        i = int(k * 0.07 * SR)
        n = min(len(s), len(salida) - i)
        salida[i:i + n] += s[:n] * 0.45
    return salida


def campanita():
    a = instrumento("cajita", hz(midi("E6")), 0.5) * 0.4
    b = instrumento("cajita", hz(midi("B6")), 0.5) * 0.3
    salida = np.zeros(max(len(a), len(b) + int(0.08 * SR)))
    salida[:len(a)] += a
    salida[int(0.08 * SR):int(0.08 * SR) + len(b)] += b
    return salida


def aplauso():
    return palmas() * 0.9


def paso():
    return golpe(0.45)


SONIDOS = {"boing": boing, "bamboleo": bamboleo, "swish": swish, "fiuu": fiuu, "retumbo": retumbo,
           "golpe": golpe, "burbujas": burbujas, "tada": tada, "campanita": campanita,
           "aplauso": aplauso, "paso": paso}

# movimiento -> [(cada cuántos pulsos se repite, en qué pulso del ciclo, sonido), ...]
EVENTOS = {
    "rebotar":   [(2, 0, "boing")],
    "bambolear": [(2, 1, "bamboleo")],
    "flotar":    [(4, 0, "campanita")],
    "menear":    [(2, 0, "swish")],
    "trompo":    [(1, 0, "swish")],
    "nadar":     [(2, 1, "burbujas")],
    "cohete":    [(8, 0, "retumbo"), (8, 2, "fiuu"), (8, 0, "golpe")],
    "voltereta": [(4, 0, "swish"), (4, 2, "tada")],
    "aplaudir":  [(2, 1, "aplauso")],
    "marchar":   [(1, 0, "paso")],
    "avion":     [(4, 1, "swish")],
    "hurra":     [(2, 1, "campanita")],
}
NO_AL_INICIO = {("cohete", "golpe"), ("rebotar", "boing")}  # el golpe es al aterrizar, no antes de salir


def eventos(movimientos, bpm, segundos):
    """Lista ordenada de (segundo, sonido) para los movimientos que hay en la escena."""
    pulso = 60.0 / bpm
    res = set()
    for mov in set(movimientos):
        for cada, en, nombre in EVENTOS.get(mov, []):
            b = en
            while b * pulso < segundos - 0.3:
                if not (b == 0 and (mov, nombre) in NO_AL_INICIO):
                    res.add((round(b * pulso, 3), nombre))
                b += cada
    return sorted(res)


def mezclar(pista, lista, volumen=0.33):
    """Suma los efectos a la pista estéreo (float, -1 a 1) y evita que sature."""
    cache = {}
    for t, nombre in lista:
        if nombre not in cache:
            cache[nombre] = SONIDOS[nombre]()
        s = cache[nombre] * volumen
        i = int(t * SR)
        n = min(len(s), len(pista) - i)
        if n > 0:
            pista[i:i + n] += s[:n, None]
    pico = np.abs(pista).max()
    if pico > 0.95:
        pista *= 0.95 / pico
    return pista
