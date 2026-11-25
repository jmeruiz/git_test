# Contenedor "app": la página web de Dibujos Mágicos y el motor que anima.
# Con DEV=1 (lo usa docker-compose.dev.yml) también instala las herramientas de prueba.
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git ffmpeg libosmesa6 libgl1 libglib2.0-0 python3-pip fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache pip3 install uv==0.5.11 \
    && uv python install 3.8.20 \
    && uv venv --seed --python 3.8.20 /opt/venv
ENV PATH=/opt/venv/bin:$PATH

# Animated Drawings de Meta (licencia MIT), fijado a su última versión
ARG AD_COMMIT=b859684857519c7424da51a0b0862fbd1fd258f4
RUN --mount=type=cache,target=/root/.cache/pip \
    git clone https://github.com/facebookresearch/AnimatedDrawings.git /opt/AnimatedDrawings \
    && git -C /opt/AnimatedDrawings checkout ${AD_COMMIT} \
    && pip install -e /opt/AnimatedDrawings

COPY requirements.txt requirements-dev.txt /tmp/
ARG DEV=0
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /tmp/requirements.txt \
    && if [ "$DEV" = "1" ]; then pip install -r /tmp/requirements-dev.txt; fi

COPY . /srv/app
WORKDIR /srv/app

ENV PYOPENGL_PLATFORM=osmesa \
    AD_ROOT=/opt/AnimatedDrawings \
    DATOS=/datos \
    MODELOS_URL=http://modelos:8080 \
    PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s CMD curl -fs http://localhost:8000/api/salud || exit 1
CMD ["python", "servidor.py"]
