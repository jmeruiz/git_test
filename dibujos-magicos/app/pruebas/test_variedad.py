"""Bailes generados por código, movimientos gelatina con efectos y "Mis canciones"."""
import io
import subprocess

import numpy as np
import pytest

from motor import bailes, catalogo, efectos, musica, render
from pruebas.conftest import flujos, hay_animated_drawings


# ---------------------------------------------------------------- catálogo

def test_catalogo_coherente():
    ids_gel = {m["id"] for m in catalogo.MOVIMIENTOS_GELATINA}
    for m in catalogo.MOVIMIENTOS_ESQUELETO:
        assert m["musica"] in musica.CANCIONES
        assert m["gelatina"] in ids_gel, "en una fiesta, los gelatina necesitan su versión de este baile"
        assert bool(m.get("propio")) == (m["id"] in bailes.BAILES)
    for m in catalogo.MOVIMIENTOS_GELATINA:
        assert m["musica"] in musica.CANCIONES
    for f in catalogo.FONDOS:
        assert render.Path(catalogo.ruta_fondo(f["id"])).exists(), f["id"]


# ---------------------------------------------------------------- bailes propios

@pytest.mark.skipif(not hay_animated_drawings(), reason="usa el BVH de ejemplo de Animated Drawings")
@pytest.mark.parametrize("baile", list(bailes.BAILES))
def test_generar_baile(tmp_path, baile):
    from motor.bvh import BVH
    cfg = bailes.generar(baile, 120, 4.0, tmp_path)
    b = BVH.leer(tmp_path / f"{baile}.bvh")
    assert b.cuadros.shape[0] == 4 * bailes.FPS
    assert b.tiempo_cuadro == pytest.approx(1 / bailes.FPS, rel=1e-3)
    assert b.cuadros.std(axis=0).max() > 1, "el baile se mueve"
    assert str(tmp_path) in open(cfg).read()


def test_bailes_van_al_pulso():
    # a 120 pulsos por minuto, cada baile se repite exacto cada 2 pulsos (1 s) o cada 4
    for nombre, f in bailes.BAILES.items():
        periodo = 4 if nombre == "avion" else 2
        a, b = f(0.3), f(0.3 + periodo)
        assert all(abs(a[k] - b[k]) < 1e-6 for k in a), nombre


# ---------------------------------------------------------------- gelatina y efectos

@pytest.mark.parametrize("mov", [m["id"] for m in catalogo.MOVIMIENTOS_GELATINA])
def test_gelatina_dibuja(tmp_path, foto, sin_modelos, mov):
    from motor import anotar
    anotar.anotar(foto("garabato.jpg"), tmp_path)
    for n in (1, 3):
        g = render.Gelatina(str(tmp_path), mov, render.LUGARES[n][0], n, 116)
        for s in (0.0, 0.7, 1.4, 2.3, 3.1):
            cuadro = np.full((render.ALTO, render.ANCHO, 3), 200, np.uint8)
            g.dibujar(cuadro, s)
            assert (cuadro != 200).any()


def test_efectos_no_se_salen_del_cuadro():
    cuadro = np.zeros((360, 640, 3), np.uint8)
    for s in (0.0, 0.5, 1.7):
        efectos.fuego(cuadro, 630, 350, 120, s, 1.0)       # en la esquina: no debe fallar
        efectos.humo(cuadro, 5, 355, 200, s)
        efectos.burbujas(cuadro, 320, 10, s)
        efectos.polvo(cuadro, 320, 350, 100, s)
        efectos.rayitas(cuadro, 320, 180, 100, 60, s)
        efectos.estrellas(cuadro, 320, 180, 100, 0.3)
    assert cuadro.any()


# ---------------------------------------------------------------- mis canciones

def _mp3(tmp_path, cancion="fiesta", segundos=20):
    wav, mp3 = tmp_path / "x.wav", tmp_path / "x.mp3"
    musica.escribir_wav(cancion, segundos, wav)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-b:a", "128k", str(mp3)], check=True)
    return mp3


@pytest.mark.parametrize("cancion", ["fiesta", "saltarin", "cumbia"])
def test_estimar_ritmo(tmp_path, cancion):
    from motor import canciones
    bpm = canciones.estimar_bpm(_mp3(tmp_path, cancion))
    assert bpm == pytest.approx(musica.CANCIONES[cancion]["bpm"], abs=2)


@pytest.mark.lento
def test_mis_canciones_por_api(servidor, tmp_path):
    datos = _mp3(tmp_path).read_bytes()
    malo = servidor.cliente.post("/api/canciones", data={"archivo": (io.BytesIO(b"hola"), "nota.txt")},
                                 content_type="multipart/form-data")
    assert malo.status_code == 400
    falso = servidor.cliente.post("/api/canciones", data={"archivo": (io.BytesIO(b"no es audio"), "x.mp3")},
                                  content_type="multipart/form-data")
    assert falso.status_code == 400

    r = servidor.cliente.post("/api/canciones", data={"archivo": (io.BytesIO(datos), "Nuestra canción.mp3"), "inicio": "2"},
                              content_type="multipart/form-data")
    assert r.status_code == 201, r.json
    c = r.json
    assert c["nombre"] == "Nuestra canción" and c["inicio"] == 2 and c["bpm"] == pytest.approx(116, abs=2)
    assert servidor.cliente.get(c["url"]).status_code == 200
    assert any(m["id"] == c["id"] for m in servidor.cliente.get("/api/catalogo").json["musica"])

    r = servidor.cliente.patch(f"/api/canciones/{c['id']}", json={"inicio": 999, "nombre": "La de la casa"})
    assert r.json["nombre"] == "La de la casa" and r.json["inicio"] <= c["duracion"] - 3

    # usarla en un video
    with open(render.Path(__file__).parent / "fixtures" / "garabato.jpg", "rb") as f:
        pid = servidor.cliente.post("/api/personajes", data={"foto": (io.BytesIO(f.read()), "g.jpg")},
                                    content_type="multipart/form-data").json["id"]
    servidor.procesar_pendientes()
    t = servidor.cliente.post(f"/api/personajes/{pid}/videos", json={"movimiento": "cohete", "fondo": "espacio",
                                                                      "musica": c["id"]}).json
    servidor.procesar_pendientes()
    assert servidor.trabajos[t["id"]]["estado"] == "listo", servidor.trabajos[t["id"]]["mensaje"]
    v = servidor.cliente.get(f"/api/personajes/{pid}").json["videos"][0]
    assert v["musica"] == c["id"]
    assert sorted(flujos(servidor.DATOS / "personajes" / pid / "videos" / v["archivo"])) == ["audio", "video"]

    assert servidor.cliente.delete(f"/api/canciones/{c['id']}").status_code == 200
    assert servidor.cliente.get("/api/canciones").json == []
