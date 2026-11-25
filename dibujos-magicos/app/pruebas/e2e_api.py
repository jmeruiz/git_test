"""
Prueba de punta a punta contra Dibujos Mágicos ya levantado, con la IA de verdad.
Uso:  ./dev.sh e2e      (o: python -m pruebas.e2e_api http://localhost:8000)

Sube dos dibujos, revisa que la IA los reconozca bien, crea un video con esqueleto y
música y una fiesta mezclada, y al final borra lo que creó.
"""
import subprocess
import sys
import time
from pathlib import Path

import requests

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def esperar_trabajo(base, tid, limite=600):
    inicio = time.time()
    while time.time() - inicio < limite:
        t = requests.get(f"{base}/api/trabajos/{tid}", timeout=10).json()
        if t["estado"] in ("listo", "error"):
            assert t["estado"] == "listo", t.get("mensaje")
            return t
        time.sleep(1)
    raise TimeoutError(tid)


def esperar_personaje(base, pid, limite=120):
    for _ in range(limite):
        p = requests.get(f"{base}/api/personajes/{pid}", timeout=10).json()
        if p["estado"] != "procesando":
            assert p["estado"] == "revisar", p.get("mensaje")
            return p
        time.sleep(1)
    raise TimeoutError(pid)


def paso(texto):
    print(f"• {texto}", flush=True)


def main(base):
    creados = []
    try:
        assert requests.get(f"{base}/api/estado", timeout=10).json()["modelos"], "la IA (contenedor modelos) no está lista"
        ids = {}
        for nombre in ("persona.jpg", "garabato.jpg"):
            with open(FIXTURES / nombre, "rb") as f:
                r = requests.post(f"{base}/api/personajes", files={"foto": f}, data={"nombre": "e2e " + nombre}, timeout=60)
            r.raise_for_status()
            ids[nombre] = r.json()["id"]
            creados.append(("personajes", ids[nombre]))
        persona = esperar_personaje(base, ids["persona.jpg"])
        garabato = esperar_personaje(base, ids["garabato.jpg"])
        assert persona["ia"]["ia_pose"], "la IA debería ver brazos y piernas en persona.jpg"
        assert not garabato["ia"]["ia_pose"], "la IA no debería ver brazos y piernas en el garabato"
        paso("la IA reconoce la figura y el garabato")

        inicio = time.time()
        r = requests.post(f"{base}/api/personajes/{ids['persona.jpg']}/videos",
                          json={"movimiento": "saludar", "fondo": "parque", "musica": "estrellita"}, timeout=10)
        esperar_trabajo(base, r.json()["id"])
        v = requests.get(f"{base}/api/personajes/{ids['persona.jpg']}", timeout=10).json()["videos"][0]
        datos = requests.get(base + v["url"], timeout=30).content
        assert len(datos) > 100_000
        paso(f"video con esqueleto y música en {time.time() - inicio:.0f} s ({len(datos) // 1024} KB)")

        inicio = time.time()
        r = requests.post(f"{base}/api/fiestas", json={
            "personajes": [{"id": ids["persona.jpg"], "modo": "esqueleto"}, {"id": ids["garabato.jpg"], "modo": "gelatina"}],
            "movimiento": "brincos", "fondo": "mar", "musica": "saltarin"}, timeout=10)
        r.raise_for_status()
        creados.append(("fiestas", r.json()["id"]))
        esperar_trabajo(base, r.json()["trabajo"])
        f = next(x for x in requests.get(f"{base}/api/fiestas", timeout=10).json() if x["id"] == r.json()["id"])
        ruta = Path("/tmp/e2e-fiesta.mp4")
        ruta.write_bytes(requests.get(base + f["url"], timeout=30).content)
        tipos = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(ruta)],
                               capture_output=True, text=True).stdout.split()
        assert sorted(tipos) == ["audio", "video"], tipos
        paso(f"fiesta mezclada con música en {time.time() - inicio:.0f} s")
        print("✔ todo bien")
    finally:
        for tipo, i in reversed(creados):
            requests.delete(f"{base}/api/{tipo}/{i}", timeout=10)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000")
