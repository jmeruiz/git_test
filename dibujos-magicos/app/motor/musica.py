"""
Música para los videos: un sintetizador pequeñito hecho con numpy.

Canciones de dominio público (Estrellita, Canción de cuna de Brahms, La cucaracha)
y dos originales hechas para este proyecto (Fiesta de colores y Saltarín).
Cada canción se repite hasta llenar el video y termina con un desvanecido suave.

Uso:  escribir_wav("fiesta", segundos=10, ruta="musica.wav")
"""
import math
import wave

import numpy as np

SR = 44100
NOTAS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi(nombre):
    """'C4' -> 60, 'F#5' -> 78, 'Bb3' -> 58"""
    letra, resto = nombre[0], nombre[1:]
    alter = 0
    while resto and resto[0] in "#b":
        alter += 1 if resto[0] == "#" else -1
        resto = resto[1:]
    return 12 * (int(resto) + 1) + NOTAS[letra] + alter


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


ACORDES = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10)}


def notas_acorde(nombre, octava=3):
    raiz = nombre[0]
    resto = nombre[1:]
    if resto[:1] in ("#", "b"):
        raiz += resto[0]
        resto = resto[1:]
    base = midi(f"{raiz}{octava}")
    return [base + i for i in ACORDES.get(resto, ACORDES[""])]


# ------------------------------------------------------------------ canciones
# melodía: lista de (nota, duración en tiempos); "R" es silencio.
# acordes: lista de (acorde, tiempos). Ambas tienen que sumar lo mismo.

def _m(texto):
    """'C5:1 G5:.5 R:.5' -> [("C5", 1.0), ("G5", .5), ("R", .5)]"""
    return [(n, float(d)) for n, d in (x.split(":") for x in texto.split())]


CANCIONES = {
    "estrellita": {
        "nombre": "Estrellita", "icono": "⭐", "bpm": 96, "compas": 4, "estilo": "suave", "instrumento": "cajita",
        "melodia": _m("""C5:1 C5:1 G5:1 G5:1  A5:1 A5:1 G5:2  F5:1 F5:1 E5:1 E5:1  D5:1 D5:1 C5:2
                         G5:1 G5:1 F5:1 F5:1  E5:1 E5:1 D5:2  G5:1 G5:1 F5:1 F5:1  E5:1 E5:1 D5:2
                         C5:1 C5:1 G5:1 G5:1  A5:1 A5:1 G5:2  F5:1 F5:1 E5:1 E5:1  D5:1 D5:1 C5:2"""),
        "acordes": _m("""C:4 F:2 C:2 F:2 C:2 G:2 C:2  C:2 F:2 C:2 G:2 C:2 F:2 C:2 G:2
                         C:4 F:2 C:2 F:2 C:2 G:2 C:2"""),
    },
    "cuna": {
        "nombre": "Canción de cuna", "icono": "🌙", "bpm": 80, "compas": 3, "estilo": "cuna", "instrumento": "cajita",
        "intro": _m("R:2 E5:.5 E5:.5"), "intro_acordes": _m("C:3"),
        "melodia": _m("""G5:2 E5:.5 E5:.5  G5:2 E5:.5 G5:.5  C6:1 B5:1.5 A5:.5  A5:1 G5:1 D5:.5 E5:.5
                         F5:1 D5:1 D5:.5 E5:.5  F5:2 D5:.5 F5:.5  B5:1 A5:1 G5:.5 B5:.5  C6:2 E5:.5 E5:.5"""),
        "acordes": _m("C:3 C:3 G7:3 C:3 G7:3 G7:3 G7:3 C:3"),
    },
    "cucaracha": {
        "nombre": "La cucaracha", "icono": "🪇", "bpm": 132, "compas": 4, "estilo": "baile", "instrumento": "marimba",
        "melodia": _m("""C5:.5 C5:.5 C5:.5 F5:1.5 A5:1   C5:.5 C5:.5 C5:.5 F5:1.5 A5:1
                         F5:.5 F5:.5 E5:.5 E5:.5 D5:.5 D5:.5 C5:1   R:4
                         C5:.5 C5:.5 C5:.5 E5:1.5 G5:1   C5:.5 C5:.5 C5:.5 E5:1.5 G5:1
                         C6:.5 D6:.5 C6:.5 Bb5:.5 A5:.5 G5:.5 F5:1   R:4"""),
        "acordes": _m("F:4 F:4 C7:4 C7:4 C7:4 C7:4 C7:2 F:2 F:4"),
    },
    "fiesta": {
        "nombre": "Fiesta de colores", "icono": "🎉", "bpm": 116, "compas": 4, "estilo": "baile", "instrumento": "marimba",
        "melodia": _m("""E5:.5 G5:.5 C6:.5 G5:.5 E5:.5 G5:.5 A5:.5 G5:.5
                         A5:.5 C6:.5 E6:.5 C6:.5 A5:.5 C6:.5 B5:.5 A5:.5
                         F5:.5 A5:.5 C6:.5 A5:.5 G5:.5 F5:.5 E5:.5 F5:.5
                         G5:1 R:.5 G5:.5 A5:.5 B5:.5 D6:1
                         E6:1 D6:.5 C6:.5 G5:1 E5:1
                         A5:1 C6:.5 B5:.5 A5:1 E5:1
                         F5:.5 G5:.5 A5:.5 C6:.5 D6:1 C6:1
                         B5:.5 A5:.5 G5:.5 F5:.5 E5:1 D5:1"""),
        "acordes": _m("C:4 Am:4 F:4 G:4 C:4 Am:4 F:4 G:4"),
    },
    "saltarin": {
        "nombre": "Saltarín", "icono": "🐸", "bpm": 126, "compas": 4, "estilo": "rebote", "instrumento": "xilofono",
        "melodia": _m("""C5:.5 C6:.5 R:.5 G5:.5 E5:.5 G5:.5 C6:1
                         A5:.5 F5:.5 R:.5 A5:.5 C6:.5 A5:.5 F5:1
                         G5:.5 B5:.5 D6:.5 B5:.5 G5:.5 R:.5 D5:1
                         E5:.5 G5:.5 C6:.5 E6:.5 C6:1 R:1"""),
        "acordes": _m("C:4 F:4 G:4 C:4"),
    },
}

CANCIONES.update({
    "martinillo": {
        "nombre": "Martinillo", "icono": "🔔", "bpm": 112, "compas": 4, "estilo": "suave", "instrumento": "xilofono",
        "melodia": _m("""C5:1 D5:1 E5:1 C5:1  C5:1 D5:1 E5:1 C5:1  E5:1 F5:1 G5:2  E5:1 F5:1 G5:2
                         G5:.5 A5:.5 G5:.5 F5:.5 E5:1 C5:1  G5:.5 A5:.5 G5:.5 F5:.5 E5:1 C5:1
                         C5:1 G4:1 C5:2  C5:1 G4:1 C5:2"""),
        "acordes": _m("C:4 C:4 C:4 C:4 C:4 C:4 C:2 G:2 C:4"),
    },
    "alegria": {
        "nombre": "Himno de la alegría", "icono": "🎻", "bpm": 104, "compas": 4, "estilo": "suave", "instrumento": "cajita",
        "melodia": _m("""E5:1 E5:1 F5:1 G5:1  G5:1 F5:1 E5:1 D5:1  C5:1 C5:1 D5:1 E5:1  E5:1.5 D5:.5 D5:2
                         E5:1 E5:1 F5:1 G5:1  G5:1 F5:1 E5:1 D5:1  C5:1 C5:1 D5:1 E5:1  D5:1.5 C5:.5 C5:2"""),
        "acordes": _m("C:4 G:4 C:4 G:4 C:4 G:4 C:4 G:2 C:2"),
    },
    "granja": {
        "nombre": "El viejo MacDonald", "icono": "🐮", "bpm": 120, "compas": 4, "estilo": "rebote", "instrumento": "xilofono",
        "melodia": _m("""C5:1 C5:1 C5:1 G4:1  A4:1 A4:1 G4:2  E5:1 E5:1 D5:1 D5:1  C5:3 G4:1
                         C5:1 C5:1 C5:1 G4:1  A4:1 A4:1 G4:2  E5:1 E5:1 D5:1 D5:1  C5:4"""),
        "acordes": _m("C:4 F:2 C:2 C:2 G:2 C:4 C:4 F:2 C:2 C:2 G:2 C:4"),
    },
    "cumbia": {
        "nombre": "Cumbia alegre", "icono": "🥁", "bpm": 100, "compas": 4, "estilo": "cumbia", "instrumento": "acordeon",
        "melodia": _m("""E5:.5 A5:.5 C6:.5 B5:.5 A5:1 E5:1   F5:.5 A5:.5 D6:.5 C6:.5 A5:1 F5:1
                         G5:.5 B5:.5 D6:.5 C6:.5 B5:.5 A5:.5 G5:1   E5:.5 G5:.5 C6:1 E6:1 R:1
                         A5:.5 A5:.5 B5:.5 C6:.5 E6:1 C6:1   D6:.5 C6:.5 B5:.5 A5:.5 F5:1 A5:1
                         G#5:.5 B5:.5 E6:.5 D6:.5 B5:.5 G#5:.5 E5:1   A5:1.5 E5:.5 A5:1 R:1"""),
        "acordes": _m("Am:4 Dm:4 G:4 C:4 Am:4 Dm:4 E7:4 Am:4"),
    },
})

LISTA = [{"id": k, "nombre": v["nombre"], "icono": v["icono"]} for k, v in CANCIONES.items()]


def bpm_de(cancion_id):
    c = CANCIONES.get(cancion_id)
    return c["bpm"] if c else 120


# ------------------------------------------------------------------ instrumentos

def _t(seg):
    return np.arange(int(seg * SR)) / SR


def _ataque(n, seg=0.004):
    a = np.ones(n)
    k = min(n, max(1, int(seg * SR)))
    a[:k] = np.linspace(0, 1, k)
    return a


def instrumento(tipo, f, dur):
    """Una nota con su propia resonancia (puede durar más que `dur`)."""
    if tipo == "cajita":       # cajita de música: brillante, con resonancia larga
        t = _t(max(dur, 1.6))
        parciales = [(1, 1.0, 1.1), (2, .35, .55), (3, .12, .3), (4.2, .08, .12), (6.8, .04, .06)]
    elif tipo == "marimba":    # cálida y redondita
        t = _t(max(dur, .9))
        parciales = [(1, 1.0, .5), (3.93, .32, .09), (9.2, .08, .03)]
    elif tipo == "acordeon":   # dos voces apenas desafinadas, como un acordeón "musette"
        t = _t(dur + 0.08)
        env = np.minimum(1, t / .03) * np.clip((dur + 0.08 - t) / .08, 0, 1)
        s = sum((np.sin(2 * math.pi * f * k * t) + np.sin(2 * math.pi * f * 1.004 * k * t)) / k ** 1.15
                for k in range(1, 8) if f * k < SR / 2.2)
        return s * env * .35
    else:                      # xilófono: seco y alegre
        t = _t(max(dur, .55))
        parciales = [(1, 1.0, .28), (3.0, .3, .07), (6.2, .12, .03)]
    s = sum(a * np.sin(2 * math.pi * f * p * t) * np.exp(-t / tau) for p, a, tau in parciales if f * p < SR / 2.2)
    return s * _ataque(len(t))


def bajo(f, dur):
    t = _t(dur)
    s = np.sin(2 * math.pi * f * t) + .25 * np.sin(4 * math.pi * f * t)
    env = _ataque(len(t), .01) * (0.55 + 0.45 * np.exp(-t / .15))
    cola = min(len(t), int(.05 * SR))
    env[-cola:] *= np.linspace(1, 0, cola)
    return s * env


def colchon(frecs, dur):
    """Acorde suave de fondo (estéreo: cada lado un poquito desafinado)."""
    t = _t(dur)
    env = np.minimum(1, t / .25) * np.minimum(1, (dur - t) / .3).clip(0, 1)
    izq = sum(np.sin(2 * math.pi * f * 1.002 * t) + .12 * np.sin(6 * math.pi * f * t) for f in frecs)
    der = sum(np.sin(2 * math.pi * f * 0.998 * t) + .12 * np.sin(6 * math.pi * f * t) for f in frecs)
    return np.stack([izq * env, der * env], axis=1) / max(1, len(frecs))


_ruido = np.random.RandomState(3).uniform(-1, 1, SR)


def bombo():
    t = _t(.3)
    f = 45 + 75 * np.exp(-t / .03)
    return np.sin(2 * math.pi * np.cumsum(f) / SR) * np.exp(-t / .12)


def palmas():
    n = int(.18 * SR)
    r = np.diff(_ruido[:n + 1])  # ruido "agudo"
    env = np.zeros(n)
    for i, ret in enumerate((0, .011, .022)):
        k = int(ret * SR)
        env[k:] += np.exp(-np.arange(n - k) / SR / (.012 if i < 2 else .06))
    return r * env * .5


def maraca():
    n = int(.07 * SR)
    r = np.diff(_ruido[1000:1001 + n])
    return r * np.exp(-np.arange(n) / SR / .018) * .35


def guiro(dur):
    """Raspado de güiro: ruido cortado en dientecitos."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    r = np.diff(_ruido[2000:2001 + n])
    dientes = (np.sin(2 * math.pi * 95 * t) > 0).astype(float)
    env = np.minimum(1, t / .01) * np.clip((dur - t) / .02, 0, 1)
    return r * dientes * env * .5


def cencerro():
    t = _t(.18)
    s = np.sign(np.sin(2 * math.pi * 562 * t)) * .5 + np.sign(np.sin(2 * math.pi * 845 * t)) * .5
    return s * np.exp(-t / .045) * .3


# ------------------------------------------------------------------ mezcla

def _poner(pista, sonido, inicio, ganancia=1.0, pan=0.0):
    i = int(inicio * SR)
    if i >= len(pista):
        return
    if sonido.ndim == 1:
        izq, der = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
        sonido = np.stack([sonido * izq * 1.41, sonido * der * 1.41], axis=1)
    n = min(len(sonido), len(pista) - i)
    pista[i:i + n] += sonido[:n] * ganancia


def _reverb(x, seg=1.2, mezcla=.16):
    rng = np.random.RandomState(11)
    n = int(seg * SR)
    imp = rng.uniform(-1, 1, (n, 2)) * np.exp(-np.arange(n) / SR / (seg / 5))[:, None]
    imp[:int(.012 * SR)] = 0
    tam = 1 << int(math.ceil(math.log2(len(x) + n)))
    salida = np.empty_like(x)
    for c in range(2):
        y = np.fft.irfft(np.fft.rfft(x[:, c], tam) * np.fft.rfft(imp[:, c], tam), tam)[:len(x)]
        salida[:, c] = y
    salida *= np.abs(x).max() / (np.abs(salida).max() + 1e-9)
    return x * (1 - mezcla) + salida * mezcla


def _secuencia(c, total_tiempos):
    """Repite la canción (después de la intro) hasta cubrir total_tiempos."""
    mel, aco = list(c.get("intro", [])), list(c.get("intro_acordes", []))
    while sum(d for _, d in mel) < total_tiempos:
        mel += c["melodia"]
        aco += c["acordes"]
    return mel, aco


def sintetizar(cancion_id, segundos):
    c = CANCIONES[cancion_id]
    tiempo = 60.0 / c["bpm"]
    total_tiempos = segundos / tiempo + 1
    mel, aco = _secuencia(c, total_tiempos)
    pista = np.zeros((int((segundos + 2) * SR), 2))
    estilo = c["estilo"]

    # melodía
    t = 0.0
    for nota, d in mel:
        if nota != "R":
            vel = .9 if (t % c["compas"]) == 0 else .75
            _poner(pista, instrumento(c["instrumento"], hz(midi(nota)), d * tiempo), t * tiempo, .30 * vel, pan=.1)
        t += d

    # acordes y bajo
    t = 0.0
    for acorde, d in aco:
        tonos = notas_acorde(acorde, 4)
        _poner(pista, colchon([hz(m) for m in tonos], d * tiempo), t * tiempo, .07 if estilo in ("baile", "rebote", "cumbia") else .10)
        raiz = hz(notas_acorde(acorde, 2)[0])
        if estilo == "cuna":
            _poner(pista, bajo(raiz, d * tiempo * .95), t * tiempo, .22)
        elif estilo == "vals":  # bajo en el 1, el resto lo llevan las maracas
            for k in range(0, int(d), 3):
                _poner(pista, bajo(raiz, .9 * tiempo), (t + k) * tiempo, .24)
        elif estilo == "cumbia":  # tónica y quinta alternadas
            for k in range(int(d)):
                f = raiz if k % 2 == 0 else raiz * 1.5
                _poner(pista, bajo(f, .8 * tiempo), (t + k) * tiempo, .26 if k % 2 == 0 else .18)
        elif estilo == "suave":
            for k in range(0, int(d), 2):
                _poner(pista, bajo(raiz, 1.8 * tiempo), (t + k) * tiempo, .22)
        else:
            k = 0.0
            while k < d:
                f = raiz if (k % 1) == 0 else raiz * 2
                _poner(pista, bajo(f, .42 * tiempo), (t + k) * tiempo, .24 if (k % 1) == 0 else .14)
                k += .5
        t += d

    # percusión
    if estilo in ("baile", "rebote"):
        tiempos = int(total_tiempos) + 1
        for b in range(tiempos):
            pos = b % c["compas"]
            if estilo == "rebote" or pos in (0, 2):
                _poner(pista, bombo(), b * tiempo, .45)
            if pos in (1, 3):
                _poner(pista, palmas(), b * tiempo, .32, pan=-.1)
            for medio in (0, .5):
                _poner(pista, maraca(), (b + medio) * tiempo, .5 if medio else .3, pan=.35)

    if estilo == "vals":
        for b in range(int(total_tiempos) + 1):
            if b % c["compas"]:
                _poner(pista, maraca(), b * tiempo, .35, pan=.3)
    if estilo == "cumbia":
        for b in range(int(total_tiempos) + 1):
            if b % 2 == 0:
                _poner(pista, bombo(), b * tiempo, .32)
            # güiro: largo-corto-corto en cada tiempo; cencerro en el contratiempo
            _poner(pista, guiro(.22 * tiempo), b * tiempo, .30, pan=-.3)
            _poner(pista, guiro(.1 * tiempo), (b + .5) * tiempo, .22, pan=-.3)
            _poner(pista, guiro(.1 * tiempo), (b + .75) * tiempo, .22, pan=-.3)
            _poner(pista, cencerro(), (b + .5) * tiempo, .16, pan=.35)

    pista = pista[:int(segundos * SR)]
    pista = _reverb(pista, mezcla=.22 if estilo in ("cuna", "suave", "vals") else .12)

    # volumen parejo y suave para oídos pequeños, con entrada y salida suaves
    rms = np.sqrt(np.mean(pista ** 2)) + 1e-9
    pista *= min(.11 / rms, .8 / (np.abs(pista).max() + 1e-9))
    n_in, n_out = int(.03 * SR), min(len(pista), int(1.2 * SR))
    pista[:n_in] *= np.linspace(0, 1, n_in)[:, None]
    pista[-n_out:] *= np.linspace(1, 0, n_out)[:, None] ** 1.5
    return np.clip(pista, -1, 1)


def escribir_wav(cancion_id, segundos, ruta):
    datos = (sintetizar(cancion_id, segundos) * 32000).astype("<i2")
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(datos.tobytes())


def duracion_en_compases(cancion_id, minimo):
    """Duración >= minimo que termina justo al final de un compás (para que el corte suene natural)."""
    c = CANCIONES.get(cancion_id)
    if not c:
        return minimo
    compas = c["compas"] * 60.0 / c["bpm"]
    return math.ceil(minimo / compas) * compas
