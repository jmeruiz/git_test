# Contenedor "modelos": los modelos de IA de Meta (Animated Drawings) que
# encuentran el dibujo en la foto y adivinan dónde están brazos, piernas y cabeza.
# Basado en torchserve/Dockerfile de facebookresearch/AnimatedDrawings (licencia MIT).
# Las líneas "--mount=type=cache" guardan las descargas entre construcciones (BuildKit, que viene con
# Docker Desktop): si algo cambia, reconstruir no vuelve a bajar PyTorch ni a compilar desde cero.
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git build-essential openjdk-17-jre-headless python3-pip \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Python 3.8 (lo que piden las librerías de Meta), instalado con uv
RUN --mount=type=cache,target=/root/.cache pip3 install uv==0.5.11 \
    && uv python install 3.8.20 \
    && uv venv --seed --python 3.8.20 /opt/venv
ENV PATH=/opt/venv/bin:$PATH

# PyTorch solo-CPU (no hace falta tarjeta de video)
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --index-url ${TORCH_INDEX_URL} torch==2.0.0 torchvision==0.15.1

# Librerías de detección y pose (OpenMMLab). mmcv-full usa un paquete ya compilado
# si lo encuentra; si no, lo compila (puede tardar 20-40 minutos la primera vez).
ENV MAX_JOBS=4
ARG MMCV_PAQUETES=https://download.openmmlab.com/mmcv/dist/cpu/torch2.0/index.html
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install "setuptools<70" wheel opencv-python==4.6.0.66 \
    && pip install --no-build-isolation mmcv-full==1.7.0 ${MMCV_PAQUETES:+-f $MMCV_PAQUETES}
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install mmdet==2.27.0 \
    && pip install cython "numpy==1.24.4" \
    && pip install --no-build-isolation "xtcocotools @ git+https://github.com/jin-s13/xtcocoapi.git@17252e742ed4306a6323d74055f4c15c75cba6ad" \
    && pip install mmpose==0.29.0 \
    && pip install torchserve==0.12.0 "numpy==1.24.4"

# Los dos modelos entrenados por Meta
RUN mkdir -p /home/torchserve/model-store \
    && curl -fL -o /home/torchserve/model-store/drawn_humanoid_detector.mar \
        https://github.com/facebookresearch/AnimatedDrawings/releases/download/v0.0.1/drawn_humanoid_detector.mar \
    && curl -fL -o /home/torchserve/model-store/drawn_humanoid_pose_estimator.mar \
        https://github.com/facebookresearch/AnimatedDrawings/releases/download/v0.0.1/drawn_humanoid_pose_estimator.mar
COPY config.properties /home/torchserve/config.properties

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=20 \
    CMD curl -fs http://localhost:8080/ping | grep -q Healthy || exit 1
CMD ["torchserve", "--start", "--foreground", "--ncs", "--disable-token-auth", "--ts-config", "/home/torchserve/config.properties"]
