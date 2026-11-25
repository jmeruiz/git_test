#!/usr/bin/env bash
# Para Ubuntu (también dentro de Windows con WSL), Linux o Mac:  ./iniciar.sh
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "No encuentro el comando docker."
  echo "Si está en Ubuntu dentro de Windows: Docker Desktop → Settings → Resources → WSL integration → activen Ubuntu."
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker no está corriendo. Abran Docker Desktop, esperen a que diga 'Engine running' y vuelvan a intentar."
  exit 1
fi

# Puerto: 8000, salvo que el archivo .env diga otro (PUERTO=8010)
PUERTO=8000
if [[ -f .env ]] && grep -q '^PUERTO=' .env; then PUERTO="$(grep '^PUERTO=' .env | tail -1 | cut -d= -f2 | tr -d '\r ')"; fi

# Dirección de la computadora en el WiFi, para el código QR del celular
if grep -qi microsoft /proc/version 2>/dev/null; then
  # WSL: hay que preguntarle a Windows (la de Ubuntu es una dirección interna)
  DIRECCION_LAN="$(powershell.exe -NoProfile -Command \
    "\$c = Get-NetIPConfiguration | Where-Object { \$_.IPv4DefaultGateway -ne \$null -and \$_.NetAdapter.Status -eq 'Up' } | Select-Object -First 1; if (\$c) { \$c.IPv4Address.IPAddress }" \
    2>/dev/null | tr -d '\r' | head -1 || true)"
elif [[ "$(uname)" == "Darwin" ]]; then
  DIRECCION_LAN="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
else
  DIRECCION_LAN="$(hostname -I 2>/dev/null | awk '{print $1}')"
fi
export DIRECCION_LAN

echo "La primera vez tarda entre 20 y 60 minutos (descarga e instala todo). Después arranca en segundos."
if ! docker compose up -d --build; then
  echo
  echo "Algo falló. Si arriba dice 'port is already allocated', el puerto $PUERTO ya lo usa otro programa:"
  echo "  echo PUERTO=8010 > .env    y vuelvan a correr ./iniciar.sh"
  exit 1
fi

printf "Esperando a que la página esté lista"
until curl -fs "http://localhost:$PUERTO/api/salud" >/dev/null 2>&1; do printf "."; sleep 2; done
URL="http://localhost:$PUERTO"
echo
echo "==========================================================="
echo " Listo: $URL"
[[ -n "$DIRECCION_LAN" ]] && echo " En el celular (mismo WiFi): http://$DIRECCION_LAN:$PUERTO"
echo " Para apagarlo: docker compose stop"
echo "==========================================================="
if grep -qi microsoft /proc/version 2>/dev/null; then explorer.exe "$URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null; then open "$URL"
elif command -v xdg-open >/dev/null; then xdg-open "$URL" >/dev/null 2>&1 || true
fi
