#!/usr/bin/env bash
# Para Mac o Linux: ./iniciar.sh
set -e
cd "$(dirname "$0")"
if ! docker info >/dev/null 2>&1; then
  echo "Docker no está abierto. Abra Docker Desktop y vuelva a intentar."; exit 1
fi
if [[ "$(uname)" == "Darwin" ]]; then
  DIRECCION_LAN="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
else
  DIRECCION_LAN="$(hostname -I 2>/dev/null | awk '{print $1}')"
fi
export DIRECCION_LAN
echo "La primera vez tarda entre 20 y 60 minutos; después arranca en segundos."
docker compose up -d --build
until curl -fs http://localhost:8000/api/salud >/dev/null; do sleep 2; done
echo "Listo: http://localhost:8000"
[[ -n "$DIRECCION_LAN" ]] && echo "En el celular (mismo WiFi): http://$DIRECCION_LAN:8000"
(command -v open >/dev/null && open http://localhost:8000) || (command -v xdg-open >/dev/null && xdg-open http://localhost:8000) || true
