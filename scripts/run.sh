#!/usr/bin/env sh
# Arranca la API + dashboard local.
# Uso: sh scripts/run.sh [puerto]
set -e
PORT="${1:-8000}"
echo "Arrancando Autonomous Business Lab en http://localhost:${PORT}"
echo "Dashboard: http://localhost:${PORT}  |  Docs: http://localhost:${PORT}/docs"
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
