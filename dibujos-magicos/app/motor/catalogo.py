"""Movimientos y fondos disponibles."""
import os

AD_ROOT = os.environ.get("AD_ROOT", "/opt/AnimatedDrawings")

# Movimientos con esqueleto: usan capturas de movimiento de personas reales (Meta).
# (archivo de movimiento, archivo de "retarget" que adapta el movimiento al dibujo)
MOVIMIENTOS_ESQUELETO = [
# "musica": canción sugerida; "gelatina": qué hace un personaje gelatina en una fiesta con este baile.
    {"id": "bailar",  "nombre": "Bailar",         "icono": "💃", "motion": "jesse_dance",   "retarget": "mixamo_fff", "musica": "fiesta",     "gelatina": "menear"},
    {"id": "saludar", "nombre": "Saludar",        "icono": "👋", "motion": "wave_hello",    "retarget": "fair1_ppf",  "musica": "estrellita", "gelatina": "bambolear"},
    {"id": "saltar",  "nombre": "Saltar",         "icono": "🦘", "motion": "jumping",       "retarget": "fair1_ppf",  "musica": "saltarin",   "gelatina": "rebotar"},
    {"id": "brincos", "nombre": "Brincos tijera", "icono": "⭐", "motion": "jumping_jacks", "retarget": "cmu1_pfp",   "musica": "saltarin",   "gelatina": "rebotar"},
    {"id": "dab",     "nombre": "Pose de dab",    "icono": "🙆", "motion": "dab",           "retarget": "fair1_ppf",  "musica": "cucaracha",  "gelatina": "menear"},
    # bailes hechos por código, al pulso de la canción (motor/bailes.py)
    {"id": "aplaudir", "nombre": "Aplaudir",      "icono": "👏", "propio": True, "musica": "martinillo", "gelatina": "rebotar"},
    {"id": "marchar",  "nombre": "Marchar",       "icono": "🥁", "propio": True, "musica": "granja",     "gelatina": "menear"},
    {"id": "avion",    "nombre": "Avión",         "icono": "✈️", "propio": True, "musica": "alegria",    "gelatina": "flotar"},
    {"id": "hurra",    "nombre": "¡Hurra!",       "icono": "🙌", "propio": True, "musica": "cumbia",     "gelatina": "rebotar"},
]

# Movimientos "gelatina": funcionan con cualquier dibujo, aunque no tenga brazos ni piernas.
MOVIMIENTOS_GELATINA = [
    {"id": "rebotar",   "nombre": "Rebotar",   "icono": "🏀", "musica": "saltarin"},
    {"id": "bambolear", "nombre": "Bambolear", "icono": "🍮", "musica": "cucaracha"},
    {"id": "flotar",    "nombre": "Flotar",    "icono": "🎈", "musica": "cuna"},
    {"id": "menear",    "nombre": "Menearse",  "icono": "🎶", "musica": "fiesta"},
    {"id": "trompo",    "nombre": "Trompo",    "icono": "🌀", "musica": "saltarin"},
    {"id": "nadar",     "nombre": "Nadar",     "icono": "🐟", "musica": "alegria"},
    {"id": "cohete",    "nombre": "Cohete",    "icono": "🚀", "musica": "fiesta"},
    {"id": "voltereta", "nombre": "Voltereta", "icono": "🤸", "musica": "saltarin"},
]

FONDOS = [
    {"id": "parque",  "nombre": "Parque"},
    {"id": "playa",   "nombre": "Playa"},
    {"id": "noche",   "nombre": "Noche de estrellas"},
    {"id": "mar",     "nombre": "Fondo del mar"},
    {"id": "espacio", "nombre": "Espacio"},
    {"id": "granja",  "nombre": "Granja"},
    {"id": "bosque",  "nombre": "Bosque"},
    {"id": "jardin",  "nombre": "Jardín de flores"},
    {"id": "nieve",   "nombre": "Nieve"},
    {"id": "papel",   "nombre": "Papel blanco"},
]

def movimiento(mov_id):
    for m in MOVIMIENTOS_ESQUELETO:
        if m["id"] == mov_id:
            return "esqueleto", m
    for m in MOVIMIENTOS_GELATINA:
        if m["id"] == mov_id:
            return "gelatina", m
    return None, None

def ruta_fondo(fondo_id):
    ids = {f["id"] for f in FONDOS}
    if fondo_id not in ids:
        fondo_id = "papel"
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "fondos", fondo_id + ".jpg")

def motion_cfg(m):
    return os.path.join(AD_ROOT, "examples", "config", "motion", m["motion"] + ".yaml")

def retarget_cfg(m):
    return os.path.join(AD_ROOT, "examples", "config", "retarget", m["retarget"] + ".yaml")
