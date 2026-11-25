"""Movimientos y fondos disponibles."""
import os

AD_ROOT = os.environ.get("AD_ROOT", "/opt/AnimatedDrawings")

# Movimientos con esqueleto: usan capturas de movimiento de personas reales (Meta).
# (archivo de movimiento, archivo de "retarget" que adapta el movimiento al dibujo)
MOVIMIENTOS_ESQUELETO = [
    {"id": "bailar",  "nombre": "Bailar",          "icono": "💃", "motion": "jesse_dance",   "retarget": "mixamo_fff"},
    {"id": "saludar", "nombre": "Saludar",         "icono": "👋", "motion": "wave_hello",    "retarget": "fair1_ppf"},
    {"id": "saltar",  "nombre": "Saltar",          "icono": "🦘", "motion": "jumping",       "retarget": "fair1_ppf"},
    {"id": "brincos", "nombre": "Brincos tijera",  "icono": "⭐", "motion": "jumping_jacks", "retarget": "cmu1_pfp"},
    {"id": "dab",     "nombre": "Pose de dab",     "icono": "🙆", "motion": "dab",           "retarget": "fair1_ppf"},
]

# Movimientos "gelatina": funcionan con cualquier dibujo, aunque no tenga brazos ni piernas.
MOVIMIENTOS_GELATINA = [
    {"id": "rebotar",   "nombre": "Rebotar",   "icono": "🏀"},
    {"id": "bambolear", "nombre": "Bambolear", "icono": "🍮"},
    {"id": "flotar",    "nombre": "Flotar",    "icono": "🎈"},
    {"id": "menear",    "nombre": "Menearse",  "icono": "🎶"},
]

FONDOS = [
    {"id": "parque",  "nombre": "Parque"},
    {"id": "playa",   "nombre": "Playa"},
    {"id": "noche",   "nombre": "Noche de estrellas"},
    {"id": "mar",     "nombre": "Fondo del mar"},
    {"id": "espacio", "nombre": "Espacio"},
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
