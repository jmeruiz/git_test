# Desarrollar Dibujos Mágicos

Guía para cambiar o agrandar el proyecto. Para *usarlo*, ver [README.md](README.md).

## Cómo está armado

```
celular / compu ──HTTP──▶ app (Flask + waitress, :8000) ──HTTP──▶ modelos (TorchServe, :8080)
                              │                                   IA de Meta: detector + pose
                              ├─ trabajador (un hilo, una cola): anotar · video · fiesta
                              │     └─ python -m motor.render escena.json   (proceso aparte)
                              └─ datos/  (fotos, recortes, esqueletos, videos; todo en archivos)
```

| Carpeta | Qué hay |
|---|---|
| `modelos/` | Contenedor de la IA de Meta. Casi nunca hay que tocarlo. |
| `app/servidor.py` | Rutas web y API, almacenamiento en `datos/`, cola de trabajos. |
| `app/motor/anotar.py` | Foto → recorte, máscara, papel blanqueado y esqueleto (con plan B si la IA no está). |
| `app/motor/render.py` | Escena (personajes + fondo + música) → MP4. Animated Drawings para los de esqueleto, OpenCV para gelatina. |
| `app/motor/musica.py` | Sintetizador y canciones. |
| `app/motor/catalogo.py` | Movimientos, fondos y sus valores por defecto. |
| `app/static/` | Páginas (HTML/CSS/JS sin frameworks ni compilación). |
| `app/pruebas/` | Pruebas automáticas y fotos de ejemplo. |
| `desarrollo/` | Ayudas para entornos especiales (la nube). |

Decisiones que conviene mantener:

- **Todo local y en archivos.** Cada personaje es una carpeta con `info.json`. No hay base de datos: es fácil de respaldar (copiar `datos/`) y de inspeccionar. Si algún día hace falta, `leer_info` / `guardar_info` son el único punto a cambiar.
- **Un trabajo a la vez.** Crear videos usa todo el procesador. La cola está en memoria. Al reiniciar, `recuperar_pendientes()` retoma lo que quedó a medias.
- **El render corre en otro proceso.** OpenGL (OSMesa) y Animated Drawings quedan aislados, y si algo falla no se cae el servidor.
- **Python 3.8.** Lo exige Animated Drawings. Nada de sintaxis más nueva (`match`, `list[str]` en tiempo de ejecución, `X | None`). ruff lo revisa con `target-version = "py38"`.
- **Versiones fijadas** en Dockerfiles y `requirements*.txt`. Animated Drawings está archivado: su versión no va a cambiar, y las nuestras tampoco deberían cambiar sin probar.
- **Español** en nombres, mensajes y comentarios. Los nombres en inglés que aparecen (`skeleton`, `char_cfg`…) son los que exige Animated Drawings.

## Comandos

Todo desde `dibujos-magicos/` con `./dev.sh` (en Windows, desde Git Bash o WSL):

| Comando | Qué hace |
|---|---|
| `./dev.sh arrancar` | Construye lo que haga falta y levanta en **modo desarrollo** (usa `datos-dev/`). |
| `./dev.sh reiniciar` | Después de cambiar código: reinicia la app en segundos, sin reconstruir. |
| `./dev.sh rapidas` | Pruebas rápidas (~2 s). Córranlas seguido. |
| `./dev.sh pruebas` | Todas las pruebas, incluidas las que crean videos de verdad (~1 min). |
| `./dev.sh e2e` | Punta a punta contra la app levantada, con la IA de verdad. Limpia lo que crea. |
| `./dev.sh revisar` | Estilo y errores comunes con ruff. |
| `./dev.sh logs` / `parar` | Registros / detener. |
| `./dev.sh limpiar` | Borra imágenes y capas viejas de Docker, pero conserva la caché de descargas. |

En modo desarrollo (`docker-compose.dev.yml`) la carpeta `app/` se monta dentro del contenedor, así que los cambios en Python, HTML o CSS no requieren reconstruir. Solo hay que reconstruir (`./dev.sh arrancar`) si cambian los `Dockerfile` o los `requirements*.txt`.

Las construcciones usan caché de BuildKit (`--mount=type=cache`): cambiar una dependencia no vuelve a descargar PyTorch ni a compilar `mmcv` desde cero. Medido en la nube: la primera construcción tardó 15,6 min (9 compilando `mmcv`) y una reconstrucción completa con caché, 4,5 min (`mmcv` en 5 s).

### Pruebas

- `pruebas/test_musica.py`: que cada canción cuadre (melodía y acordes iguales, compases completos) y que el audio no sature.
- `pruebas/test_anotar.py`: blanqueo de papel, recorte, plan B sin IA.
- `pruebas/test_render.py`: geometría de la cámara de las fiestas, videos gelatina y una fiesta con esqueleto.
- `pruebas/test_servidor.py`: la API completa con el cliente de pruebas de Flask, con datos temporales y sin IA.
- `pruebas/e2e_api.py`: el sistema entero con la IA de verdad.

Marcas: `lento` (crea videos) y `necesita_ad` (necesita Animated Drawings; en GitHub Actions se salta sola).

GitHub Actions (`.github/workflows/dibujos-magicos.yml`) corre ruff y las pruebas en cada cambio, sin Docker.

## Recetas

**Agregar una canción.** En `motor/musica.py`, agreguen una entrada a `CANCIONES`: `bpm`, `compas`, `estilo` (`suave`, `cuna`, `baile`, `rebote`), `instrumento` (`cajita`, `marimba`, `xilofono`), `melodia` y `acordes` en el formato `"C5:1 G5:.5 R:.5"`. La melodía y los acordes tienen que sumar los mismos tiempos (la prueba lo revisa). Solo usen melodías propias o de dominio público.

**Agregar un fondo.** Una imagen de 1280×720 en `static/fondos/<id>.jpg`, con el suelo más o menos al 85 % de la altura, y una línea en `FONDOS` de `catalogo.py`.

**Agregar un movimiento gelatina.** Una línea en `MOVIMIENTOS_GELATINA` y un caso en `Gelatina.dibujar()` (`render.py`). Midan el tiempo en pulsos (`b`) para que vaya al ritmo de la música.

**Agregar un movimiento con esqueleto.** Hace falta un archivo BVH (captura de movimiento) y sus configuraciones de *motion* y *retarget* de Animated Drawings (ver `examples/config` en su repositorio). Después, una línea en `MOVIMIENTOS_ESQUELETO`. Revisen el encuadre: si el personaje se desplaza, agreguen su cámara en `render.py` (ver `saltar`).

**Cambiar algo del render.** Para probar sin pasar por la página:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm --no-deps app \
  python -m motor.render /datos/mi-escena.json     # formato de la escena: ver arriba de render.py
```

## Entorno de Claude en la nube

Allí la salida a internet pasa por un proxy, Docker Hub limita descargas y `download.pytorch.org` / `download.openmmlab.com` están bloqueados. Antes de nada:

```bash
desarrollo/preparar-nube.sh   # enciende Docker, crea la imagen base con el proxy y docker-compose.local.yml
./dev.sh arrancar
```

`docker-compose.local.yml` no se sube a git y `dev.sh` lo agrega solo si existe. En una computadora normal no hace falta nada de esto.

## Antes de subir cambios

1. `./dev.sh revisar` y `./dev.sh pruebas` en verde.
2. Si se tocó la IA, el render o la API: `./dev.sh e2e`.
3. Si cambió algo visible: probarlo en la página, también en tamaño celular.
4. Si cambió cómo se usa: actualizar `README.md`.
