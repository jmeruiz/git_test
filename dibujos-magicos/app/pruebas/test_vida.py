"""Dibujado a mano (tembleque), fondos con vida, efectos de animación y de sonido."""
import numpy as np
import pytest

from motor import catalogo, efectos, musica, render, sonidos
from motor.escenario import Escenario
from motor.estilo import Temblor
from pruebas.conftest import flujos


def test_temblor_cambia_poquito_y_se_repite():
    img = np.zeros((200, 200, 4), np.uint8)
    img[50:150, 98:102] = 255                        # una raya vertical
    t = Temblor()
    a, b, c = t.aplicar(img, 0.0), t.aplicar(img, 0.1), t.aplicar(img, 0.3)
    assert not np.array_equal(a, b), "cambia de un dibujo al siguiente"
    assert np.array_equal(a, c), "ciclo de 3 dibujos, como los animadores"
    assert abs(int(a[:, :, 3].sum()) - int(img[:, :, 3].sum())) < img[:, :, 3].sum() * 0.1, "no deforma de más"


@pytest.mark.parametrize("fondo", [f["id"] for f in catalogo.FONDOS])
def test_fondos_con_vida(fondo):
    e = Escenario(fondo, 640, 360)
    for s in (0.0, 1.3, 6.5):
        c = np.full((360, 640, 3), 120, np.uint8)
        e.atras_lejos(c, s)
        e.atras(c, s)
        e.adelante(c, s)
    if fondo != "papel":
        c1, c2 = np.full((360, 640, 3), 120, np.uint8), np.full((360, 640, 3), 120, np.uint8)
        for c, s in ((c1, 0.5), (c2, 2.0)):
            e.atras(c, s)
            e.adelante(c, s)
        assert not np.array_equal(c1, c2), "el fondo se mueve"


def test_efectos_de_baile():
    c = np.zeros((360, 640, 3), np.uint8)
    efectos.corazones(c, 320, 200, 0.3)
    efectos.confeti(c, 320, 200, 0.4)
    efectos.arcoiris(c, 320, 250, 150, 10)
    assert c.any()
    cajas = [(320, 100, 300), None]
    for baile in ("aplaudir", "hurra", "marchar", "bailar"):
        render.efectos_baile(np.zeros((360, 640, 3), np.uint8), baile, cajas, 1.1, 0.5)


def test_impacto_y_lineas_de_velocidad():
    c = np.zeros((360, 640, 3), np.uint8)
    efectos.impacto(c, 320, 300, 120, 0.2)
    efectos.lineas_velocidad(c, 320, 150, 100, 120, True, 0.4)
    assert c.any()
    vacio = np.zeros_like(c)
    efectos.impacto(vacio, 320, 300, 120, 1.0)       # ya pasó: no dibuja nada
    assert not vacio.any()


@pytest.mark.parametrize("nombre", list(sonidos.SONIDOS))
def test_cada_sonido(nombre):
    s = sonidos.SONIDOS[nombre]()
    assert len(s) > 1000 and np.isfinite(s).all() and np.abs(s).max() < 3


def test_eventos_al_pulso():
    ev = sonidos.eventos(["cohete"], 120, 9.0)        # pulso de 0,5 s; ciclo de 8 pulsos = 4 s
    assert (1.0, "fiuu") in ev and (0.0, "retumbo") in ev
    assert (0.0, "golpe") not in ev and (4.0, "golpe") in ev, "el golpe es al aterrizar"
    pista = sonidos.mezclar(np.zeros((9 * musica.SR, 2), np.float32), ev)
    assert 0.05 < np.abs(pista).max() <= 0.95


@pytest.mark.lento
@pytest.mark.parametrize("con_sonidos", [True, False])
def test_audio_sin_musica(tmp_path, foto, sin_modelos, con_sonidos):
    import json
    import subprocess
    import sys

    from motor import anotar
    pj = tmp_path / "pj"
    pj.mkdir()
    anotar.anotar(foto("garabato.jpg"), pj)
    escena = {"fondo": "mar", "musica": "ninguna", "sonidos": con_sonidos, "a_mano": True,
              "personajes": [{"carpeta": str(pj), "modo": "gelatina", "movimiento": "rebotar"}],
              "salida": str(tmp_path / "v.mp4"), "miniatura": str(tmp_path / "v.jpg")}
    (tmp_path / "e.json").write_text(json.dumps(escena))
    r = subprocess.run([sys.executable, "-m", "motor.render", str(tmp_path / "e.json")],
                       cwd=str(render.Path(render.__file__).parents[1]), capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-1500:]
    assert sorted(flujos(tmp_path / "v.mp4")) == (["audio", "video"] if con_sonidos else ["video"])
