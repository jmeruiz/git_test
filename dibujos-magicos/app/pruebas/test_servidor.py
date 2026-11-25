import io
import base64

import cv2
import numpy as np
import pytest

from pruebas.conftest import FIXTURES, flujos


def subir(srv, nombre, titulo="Prueba"):
    with open(FIXTURES / nombre, "rb") as f:
        r = srv.cliente.post("/api/personajes", data={"foto": (io.BytesIO(f.read()), nombre), "nombre": titulo,
                                                      "artista": "Vale"}, content_type="multipart/form-data")
    assert r.status_code == 201, r.json
    srv.procesar_pendientes()
    return r.json["id"]


def test_paginas_y_catalogo(servidor):
    for ruta in ("/", "/nuevo", "/fiesta", "/funcion", "/ayuda", "/personaje/abc", "/static/manifest.webmanifest"):
        assert servidor.cliente.get(ruta).status_code == 200
    cat = servidor.cliente.get("/api/catalogo").json
    assert {"esqueleto", "gelatina", "fondos", "musica"} <= set(cat)
    assert all(m.get("musica") for m in cat["esqueleto"] + cat["gelatina"])


def test_muestra_de_musica(servidor):
    r = servidor.cliente.get("/api/musica/estrellita.wav")
    assert r.status_code == 200 and r.mimetype == "audio/wav" and len(r.data) > 100_000
    assert servidor.cliente.get("/api/musica/nada.wav").status_code == 404


def test_subir_y_editar(servidor):
    pid = subir(servidor, "persona.jpg")
    info = servidor.cliente.get(f"/api/personajes/{pid}").json
    assert info["estado"] == "revisar" and len(info["puntos"]) == 16

    puntos = dict(info["puntos"])
    puntos["neck"] = [puntos["neck"][0] + 3, puntos["neck"][1]]
    mascara = np.zeros((info["alto"], info["ancho"]), np.uint8)
    cv2.rectangle(mascara, (10, 10), (info["ancho"] - 10, info["alto"] - 10), 255, -1)
    png = "data:image/png;base64," + base64.b64encode(cv2.imencode(".png", mascara)[1].tobytes()).decode()
    r = servidor.cliente.put(f"/api/personajes/{pid}/anotaciones", json={"puntos": puntos, "mascara": png})
    assert r.status_code == 200 and r.json["piezas"] == 1

    sin_pie = {k: v for k, v in puntos.items() if k != "left_foot"}
    assert servidor.cliente.put(f"/api/personajes/{pid}/anotaciones", json={"puntos": sin_pie}).status_code == 400
    vacia = "data:image/png;base64," + base64.b64encode(cv2.imencode(".png", mascara * 0)[1].tobytes()).decode()
    assert servidor.cliente.put(f"/api/personajes/{pid}/anotaciones", json={"mascara": vacia}).status_code == 400


def test_ids_raros_no_pasan(servidor):
    assert servidor.cliente.get("/api/personajes/..%2F..%2Fetc").status_code == 404
    assert servidor.cliente.get("/api/personajes/NOEXISTE1234").status_code == 404
    assert servidor.cliente.delete("/api/fiestas/../x").status_code == 404


def test_foto_que_no_es_imagen(servidor):
    r = servidor.cliente.post("/api/personajes", data={"foto": (io.BytesIO(b"hola"), "x.jpg")},
                              content_type="multipart/form-data")
    assert r.status_code == 400 and "imagen" in r.json["error"]


@pytest.mark.lento
def test_video_y_fiesta_gelatina(servidor):
    a = subir(servidor, "garabato.jpg", "Bolita")
    b = subir(servidor, "ajo.jpg", "Ajo")

    r = servidor.cliente.post(f"/api/personajes/{a}/videos", json={"movimiento": "menear", "fondo": "noche",
                                                                    "musica": "cucaracha"})
    assert r.status_code == 202
    servidor.procesar_pendientes()
    assert servidor.trabajos[r.json["id"]]["estado"] == "listo"
    info = servidor.cliente.get(f"/api/personajes/{a}").json
    assert info["estado"] == "listo" and info["videos"][0]["musica"] == "cucaracha"
    video = servidor.DATOS / "personajes" / a / "videos" / info["videos"][0]["archivo"]
    assert sorted(flujos(video)) == ["audio", "video"]

    assert servidor.cliente.post("/api/fiestas", json={"personajes": [{"id": a}], "movimiento": "bailar"}).status_code == 400
    r = servidor.cliente.post("/api/fiestas", json={"personajes": [{"id": a, "modo": "gelatina"}, {"id": b, "modo": "gelatina"}],
                                                    "movimiento": "saltar", "fondo": "mar", "musica": "saltarin"})
    assert r.status_code == 202
    assert [p["movimiento"] for p in r.json["personajes"]] == ["rebotar", "rebotar"]
    servidor.procesar_pendientes()
    fiestas = servidor.cliente.get("/api/fiestas").json
    assert fiestas[0]["estado"] == "listo" and fiestas[0]["url"].endswith("fiesta.mp4")

    funcion = servidor.cliente.get("/api/funcion").json
    assert len(funcion) == 2 and any(v.get("invitados") == ["Bolita", "Ajo"] for v in funcion)

    assert servidor.cliente.delete(f"/api/fiestas/{fiestas[0]['id']}").status_code == 200
    assert servidor.cliente.delete(f"/api/personajes/{a}").status_code == 200
    assert servidor.cliente.get(f"/api/personajes/{a}").status_code == 404
