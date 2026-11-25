#!/usr/bin/env bash
# Prepara un entorno con salida a internet restringida (por ejemplo, la nube donde trabaja Claude)
# para poder construir y probar Dibujos Mágicos. En una computadora normal NO hace falta.
#
# Qué hace (se puede correr varias veces, solo hace lo que falta):
#  1. Enciende Docker si está apagado.
#  2. Crea una imagen base ubuntu:22.04 que confía en el certificado del proxy y usa apt por HTTPS
#     (se baja de mirror.gcr.io, porque Docker Hub suele limitar las descargas).
#  3. Escribe docker-compose.local.yml para construir con la red del anfitrión y bajar PyTorch de PyPI.
#
# Variables: HTTPS_PROXY (proxy de salida) y CA_PROXY (certificado; por defecto /root/.ccr/ca-bundle.crt).
set -euo pipefail
cd "$(dirname "$0")/.."
CA_PROXY="${CA_PROXY:-/root/.ccr/ca-bundle.crt}"
PROXY="${HTTPS_PROXY:-${https_proxy:-}}"

if ! docker info >/dev/null 2>&1; then
  echo "Encendiendo Docker…"
  (dockerd >/tmp/dockerd.log 2>&1 &)
  for _ in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 1; done
  docker info >/dev/null 2>&1 || { echo "Docker no arrancó; vean /tmp/dockerd.log"; exit 1; }
fi

if [[ -z "$PROXY" || ! -f "$CA_PROXY" ]]; then
  echo "No hay proxy ni certificado: no hace falta preparar nada más."; exit 0
fi

# La imagen guarda la dirección del proxy; si cambió (pasa entre sesiones), se vuelve a crear.
if [[ "$(docker image inspect ubuntu:22.04 --format '{{ index .Config.Labels "dibujos.proxy" }}' 2>/dev/null)" != "$PROXY" ]]; then
  echo "Creando la imagen base con el proxy…"
  tmp="$(mktemp -d)"
  cp "$CA_PROXY" "$tmp/proxy.crt"
  cat > "$tmp/Dockerfile" <<DOCKERFILE
FROM mirror.gcr.io/library/ubuntu:22.04
LABEL dibujos.proxy=$PROXY
COPY proxy.crt /usr/local/share/ca-certificates/proxy.crt
RUN sed -i 's|http://|https://|g' /etc/apt/sources.list \
 && printf 'Acquire::https::Proxy "$PROXY";\nAcquire::https::CAInfo "/usr/local/share/ca-certificates/proxy.crt";\n' > /etc/apt/apt.conf.d/99proxy
ENV HTTPS_PROXY=$PROXY https_proxy=$PROXY NO_PROXY=localhost,127.0.0.1,modelos no_proxy=localhost,127.0.0.1,modelos \
    SSL_CERT_FILE=/usr/local/share/ca-certificates/proxy.crt REQUESTS_CA_BUNDLE=/usr/local/share/ca-certificates/proxy.crt \
    PIP_CERT=/usr/local/share/ca-certificates/proxy.crt CURL_CA_BUNDLE=/usr/local/share/ca-certificates/proxy.crt \
    GIT_SSL_CAINFO=/usr/local/share/ca-certificates/proxy.crt UV_NATIVE_TLS=1
DOCKERFILE
  docker pull -q mirror.gcr.io/library/ubuntu:22.04 >/dev/null
  docker build -q --network host -t ubuntu:22.04 "$tmp" >/dev/null
  rm -rf "$tmp"
fi

cat > docker-compose.local.yml <<'YAML'
# Creado por desarrollo/preparar-nube.sh (no se sube a git): construir con la red del anfitrión
# para pasar por el proxy, y bajar PyTorch de PyPI (download.pytorch.org está bloqueado aquí).
services:
  modelos:
    build:
      network: host
      args:
        TORCH_INDEX_URL: https://pypi.org/simple
        MMCV_PAQUETES: ""   # download.openmmlab.com está bloqueado: compilar directo (queda en caché)
  app:
    build:
      network: host
YAML
echo "Listo. Ahora: ./dev.sh arrancar"
