import cv2
import numpy as np
import yaml

from motor import anotar


def test_blanquear_papel_quita_el_gris_sin_borrar_el_dibujo():
    img = np.full((400, 400, 3), 150, np.uint8)            # papel gris (foto con poca luz)
    img[:, :200] = 120                                      # con una sombra
    cv2.circle(img, (200, 200), 110, (30, 30, 120), -1)     # una zona grande pintada de rojo oscuro
    mascara = np.zeros((400, 400), np.uint8)
    cv2.circle(mascara, (200, 200), 112, 255, -1)
    limpio = anotar.blanquear_papel(img, mascara)
    assert limpio[10, 10].min() > 235 and limpio[10, 390].min() > 235, "el papel queda blanco"
    b, g, r = (int(v) for v in limpio[200, 200])
    assert r < 245 and r > b + 60 and r > g + 60, "el relleno sigue siendo rojo, no se lava a blanco"


def test_mascara_conserva_partes_sueltas():
    img = np.full((300, 300, 3), 255, np.uint8)
    cv2.circle(img, (100, 150), 50, (0, 0, 0), 4)
    cv2.circle(img, (220, 150), 30, (0, 0, 0), 4)   # parte suelta, más chica
    m = anotar.mascara_tinta(img)
    assert m[150, 100] == 255 and m[150, 220] == 255, "las dos partes (rellenas) quedan en el recorte"
    assert m[10, 10] == 0


def test_validar_y_ajustar_puntos():
    pts = anotar.esqueleto_plantilla(np.pad(np.full((100, 60), 255, np.uint8), 20))
    assert anotar.validar_puntos(pts, 100, 140) is None
    falta = dict(pts)
    del falta["left_foot"]
    assert "left_foot" in anotar.validar_puntos(falta, 100, 140)
    pts["left_hand"] = [-10, 500]
    assert anotar.ajustar_puntos(pts, 100, 140)["left_hand"] == [0, 139]


def test_anotar_sin_ia_usa_plan_b(tmp_path, foto, sin_modelos):
    res = anotar.anotar(foto("garabato.jpg"), tmp_path)
    assert res["ia_detecto"] is False and res["ia_pose"] is False
    tex = cv2.imread(str(tmp_path / "texture.png"), cv2.IMREAD_UNCHANGED)
    mask = cv2.imread(str(tmp_path / "mask.png"), cv2.IMREAD_GRAYSCALE)
    assert tex.shape[:2] == mask.shape == (res["alto"], res["ancho"])
    assert 0.1 < (mask > 0).mean() < 0.95, "el recorte no está vacío ni es toda la foto"
    cfg = yaml.safe_load((tmp_path / "char_cfg.yaml").read_text())
    nombres = {j["name"] for j in cfg["skeleton"]}
    assert len(nombres) == 16
    assert all(j["parent"] in nombres for j in cfg["skeleton"] if j["parent"])
