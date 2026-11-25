import json
import math
import subprocess
import sys

import pytest

from pruebas.conftest import flujos, hay_animated_drawings
from motor import anotar, render


def test_x_mundo_centro_y_simetria():
    cam = render.camara_escena(3, "bailar")
    assert render.x_mundo(0.5, cam, -0.5) == pytest.approx(cam["CAMERA_POS"][0])
    assert render.x_mundo(0.2, cam, -0.5) == pytest.approx(-render.x_mundo(0.8, cam, -0.5))


@pytest.mark.parametrize("n", [2, 3, 4, 5])
def test_camara_de_fiesta_deja_los_pies_en_el_suelo(n):
    cam = render.camara_escena(n, "bailar")
    (_, cy, cz), fwd = cam["CAMERA_POS"], cam["CAMERA_FWD"]
    dz = cz + 0.5
    inclinacion = math.atan2(fwd[1], fwd[2])
    pies = math.atan((cy - render.PIES_Y) / dz)
    altura_pantalla = 0.5 + 0.5 * math.tan(pies - inclinacion) / render.TAN_MEDIO_FOV
    assert altura_pantalla == pytest.approx(render.SUELO_FIESTA, abs=0.01)


def test_retarget_movido_solo_cambia_la_x(tmp_path):
    original = tmp_path / "r.yaml"
    original.write_text("char_starting_location: [0.0, 0.0, -0.5]\nchar_joint_bvh_joints_mapping:\n"
                        "  left_elbow: !!python/tuple\n  - LeftArm\n")
    ruta, z = render.retarget_movido(original, 1.25, tmp_path, 0)
    nuevo = open(ruta).read().splitlines()
    assert nuevo[0] == "char_starting_location: [1.2500, 0.0, -0.5]" and z == -0.5
    assert nuevo[1:] == original.read_text().splitlines()[1:]


def _escena(tmp_path, personajes, musica="saltarin"):
    salida = tmp_path / "v.mp4"
    escena = {"fondo": "playa", "musica": musica, "personajes": personajes,
              "salida": str(salida), "miniatura": str(tmp_path / "v.jpg")}
    ruta = tmp_path / "escena.json"
    ruta.write_text(json.dumps(escena))
    r = subprocess.run([sys.executable, "-m", "motor.render", str(ruta)], cwd=str(render.Path(render.__file__).parents[1]),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:]
    assert "PROGRESO 100" in r.stdout
    return salida


@pytest.mark.lento
def test_video_gelatina_con_musica(tmp_path, foto, sin_modelos):
    pj = tmp_path / "pj"
    pj.mkdir()
    anotar.anotar(foto("garabato.jpg"), pj)
    salida = _escena(tmp_path, [{"carpeta": str(pj), "modo": "gelatina", "movimiento": "rebotar"}])
    assert sorted(flujos(salida)) == ["audio", "video"]
    assert render.duracion(salida) >= 7.5
    assert (tmp_path / "v.jpg").exists()


@pytest.mark.lento
@pytest.mark.necesita_ad
@pytest.mark.skipif(not hay_animated_drawings(), reason="Animated Drawings solo está dentro del contenedor")
def test_fiesta_con_esqueleto_y_gelatina(tmp_path, foto, sin_modelos):
    personajes = []
    for i, (nombre, modo, mov) in enumerate([("persona.jpg", "esqueleto", "saltar"), ("garabato.jpg", "gelatina", "rebotar")]):
        pj = tmp_path / f"pj{i}"
        pj.mkdir()
        anotar.anotar(foto(nombre), pj)
        personajes.append({"carpeta": str(pj), "modo": modo, "movimiento": mov})
    salida = _escena(tmp_path, personajes, musica="ninguna")
    assert flujos(salida) == ["video"]
    assert render.duracion(salida) >= 7.5
