#!/usr/bin/env bash
# Comandos para desarrollar Dibujos Mágicos. Uso: ./dev.sh <comando>
#
#   arrancar     construye (si hace falta) y levanta todo en modo desarrollo
#   reiniciar    reinicia solo la app (después de cambiar código Python o HTML)
#   pruebas      pruebas automáticas (pasa argumentos a pytest, por ej. ./dev.sh pruebas -k musica)
#   rapidas      solo las pruebas rápidas (sin crear videos)
#   e2e          prueba de punta a punta contra la app levantada (con la IA de verdad)
#   revisar      revisa el estilo del código con ruff
#   logs         muestra los registros (Ctrl+C para salir)
#   parar        detiene todo
#   limpiar      borra imágenes y capas viejas de Docker (conserva la caché de descargas)
#
# Si existe docker-compose.local.yml (no se sube a git) se agrega solo: sirve para ajustes de una
# máquina en particular, por ejemplo el que crea desarrollo/preparar-nube.sh.
set -euo pipefail
cd "$(dirname "$0")"

ARCHIVOS=(-f docker-compose.yml -f docker-compose.dev.yml)
[[ -f docker-compose.local.yml ]] && ARCHIVOS+=(-f docker-compose.local.yml)
dc() { docker compose "${ARCHIVOS[@]}" "$@"; }

esperar_app() {
  printf "Esperando a la app"
  for _ in $(seq 1 90); do
    if curl -fs --noproxy '*' http://localhost:8000/api/salud >/dev/null 2>&1; then echo " lista: http://localhost:8000"; return 0; fi
    printf "."; sleep 2
  done
  echo; echo "La app no respondió. Revisen: ./dev.sh logs"; return 1
}

case "${1:-ayuda}" in
  arrancar)  mkdir -p datos-dev; dc up -d --build; esperar_app ;;
  reiniciar) dc restart app; esperar_app ;;
  pruebas)   shift; dc run --rm --no-deps -e DATOS=/tmp/datos-pruebas app python -m pytest "$@" ;;
  rapidas)   shift; dc run --rm --no-deps -e DATOS=/tmp/datos-pruebas app python -m pytest -m "not lento" "$@" ;;
  e2e)       dc exec app python -m pruebas.e2e_api http://localhost:8000 ;;
  revisar)   dc run --rm --no-deps app ruff check . ;;
  logs)      dc logs -f --tail 100 ;;
  parar)     dc stop ;;
  limpiar)   docker image prune -f && docker builder prune -f --filter "type!=exec.cachemount" && docker system df ;;
  *)         awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0" ;;
esac
