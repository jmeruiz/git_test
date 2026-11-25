"""Configuración común de las pruebas. Se corren con ./dev.sh pruebas (o pytest dentro de app/)."""
import importlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


def hay_animated_drawings():
    return importlib.util.find_spec("animated_drawings") is not None


def flujos(video):
    """Tipos de flujo de un video, por ejemplo ['video', 'audio']."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True, check=True)
    return r.stdout.split()


@pytest.fixture
def foto(tmp_path):
    """Copia una foto de fixtures a una carpeta temporal y devuelve su ruta."""
    def copiar(nombre):
        destino = tmp_path / nombre
        shutil.copy(FIXTURES / nombre, destino)
        return destino
    return copiar


@pytest.fixture
def sin_modelos(monkeypatch):
    """Hace como si el contenedor de la IA estuviera apagado (se usa el plan B)."""
    from motor import anotar
    monkeypatch.setattr(anotar, "MODELOS_URL", "http://127.0.0.1:9")
    return anotar


@pytest.fixture
def servidor(tmp_path, monkeypatch, sin_modelos):
    """Un servidor nuevo con su propia carpeta de datos vacía y cliente de pruebas de Flask."""
    monkeypatch.setenv("DATOS", str(tmp_path / "datos"))
    monkeypatch.setenv("MODELOS_URL", "http://127.0.0.1:9")
    if "servidor" in sys.modules:
        del sys.modules["servidor"]
    srv = importlib.import_module("servidor")
    srv.app.config["TESTING"] = True
    srv.cliente = srv.app.test_client()
    return srv
