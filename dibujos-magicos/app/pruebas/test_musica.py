import numpy as np
import pytest

from motor import musica


@pytest.mark.parametrize("nombre,esperado", [("C4", 60), ("A4", 69), ("Bb3", 58), ("F#5", 78)])
def test_midi(nombre, esperado):
    assert musica.midi(nombre) == esperado


@pytest.mark.parametrize("cid", list(musica.CANCIONES))
def test_melodia_y_acordes_duran_lo_mismo(cid):
    c = musica.CANCIONES[cid]
    mel = sum(d for _, d in c["melodia"])
    aco = sum(d for _, d in c["acordes"])
    assert mel == aco, "la melodía y los acordes se desfasan al repetir"
    assert mel % c["compas"] == 0, "la canción tiene que terminar al final de un compás"
    assert sum(d for _, d in c.get("intro", [])) == sum(d for _, d in c.get("intro_acordes", []))
    for nota, _ in c["melodia"]:
        if nota != "R":
            assert 48 <= musica.midi(nota) <= 96


@pytest.mark.parametrize("cid", list(musica.CANCIONES))
def test_sintetizar_duracion_y_volumen(cid):
    x = musica.sintetizar(cid, 4.0)
    assert x.shape == (4 * musica.SR, 2)
    assert np.abs(x).max() <= 1.0
    rms = float(np.sqrt((x ** 2).mean()))
    assert 0.05 < rms < 0.2, "ni muy bajito ni muy fuerte"
    assert np.abs(x[-200:]).max() < 0.02, "termina desvanecida"


def test_duracion_en_compases():
    c = musica.CANCIONES["fiesta"]
    compas = c["compas"] * 60 / c["bpm"]
    d = musica.duracion_en_compases("fiesta", 8.0)
    assert d >= 8.0 and abs(d / compas - round(d / compas)) < 1e-9
    assert musica.duracion_en_compases("no-existe", 8.0) == 8.0


def test_wav(tmp_path):
    ruta = tmp_path / "x.wav"
    musica.escribir_wav("estrellita", 2.0, ruta)
    import wave
    with wave.open(str(ruta)) as w:
        assert (w.getnchannels(), w.getframerate()) == (2, musica.SR)
        assert w.getnframes() == 2 * musica.SR
