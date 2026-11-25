# Contenedor "modelos": los modelos de IA de Meta (Animated Drawings) que
# encuentran el dibujo en la foto y adivinan dónde están brazos, piernas y cabeza.
# Basado en torchserve/Dockerfile de facebookresearch/AnimatedDrawings (licencia MIT).
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git build-essential openjdk-17-jre-headless python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Python 3.8 (lo que piden las librerías de Meta), instalado con uv
RUN pip3 install --no-cache-dir uv==0.5.11 \
    && uv python install 3.8.20 \
    && uv venv --seed --python 3.8.20 /opt/venv
ENV PATH=/opt/venv/bin:$PATH

# PyTorch solo-CPU (no hace falta tarjeta de video)
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir --index-url ${TORCH_INDEX_URL} torch==2.0.0 torchvision==0.15.1

# Librerías de detección y pose (OpenMMLab). mmcv-full usa un paquete ya compilado
# si lo encuentra; si no, lo compila (puede tardar 20-40 minutos la primera vez).
ENV MAX_JOBS=4
RUN pip install --no-cache-dir "setuptools<70" wheel \
    && pip install --no-cache-dir --no-build-isolation mmcv-full==1.7.0 \
        -f https://download.openmmlab.com/mmcv/dist/cpu/torch2.0/index.html
RUN pip install --no-cache-dir mmdet==2.27.0 \
    && pip install --no-cache-dir cython "numpy==1.24.4" \
    && pip install --no-cache-dir --no-build-isolation "xtcocotools @ git+https://github.com/jin-s13/xtcocoapi.git@17252e742ed4306a6323d74055f4c15c75cba6ad" \
    && pip install --no-cache-dir mmpose==0.29.0 \
    && pip install --no-cache-dir torchserve==0.12.0 "numpy==1.24.4"

# Librerías del sistema que necesita OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

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
