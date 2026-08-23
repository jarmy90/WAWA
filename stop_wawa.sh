#!/usr/bin/env sh
# STOP_WAWA (Linux/macOS) — detiene la web local.
set -e
cd "$(dirname "$0")"
if [ -f "logs/wawa.pid" ]; then
  PID="$(cat logs/wawa.pid)"
  if kill -0 "${PID}" 2>/dev/null; then
    kill "${PID}"
    echo "WAWA detenida (PID ${PID})."
  else
    echo "El proceso ${PID} ya no estaba activo."
  fi
  rm -f logs/wawa.pid
else
  echo "No hay PID guardado. ¿Está WAWA en marcha?"
fi
