#!/usr/bin/env sh
# START_WAWA (Linux/macOS) — arranca Autonomous Business Lab en local.
# Uso: sh start_wawa.sh   (o ./start_wawa.sh)
set -e

cd "$(dirname "$0")"
HOST="127.0.0.1"
PORT="${1:-8000}"
URL="http://${HOST}:${PORT}"

echo "=============================================="
echo "  Autonomous Business Lab — inicio local"
echo "=============================================="

# 1) Entorno virtual
if [ ! -d ".venv" ]; then
  echo "[1/5] Creando entorno virtual..."
  python3 -m venv .venv
fi
. .venv/bin/activate

# 2) Dependencias
if ! python -c "import fastapi, uvicorn, pydantic" 2>/dev/null; then
  echo "[2/5] Instalando dependencias..."
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -e ".[dev]"
fi

# 3) Base de datos (SQLite se inicializa solo al arrancar; comprobamos la carpeta)
echo "[3/5] Preparando datos locales..."
mkdir -p data logs
if [ ! -f "data/abl.db" ]; then
  python - <<'PY'
from app.repositories.db import init_db
from app.core.config import Settings
s = Settings()
init_db(s)  # init_db espera un objeto Settings (iteración 011: corregido)
print("SQLite inicializado en", s.database_path)
PY
fi

# 4) Arrancar la API (solo local: 127.0.0.1, nunca 0.0.0.0)
echo "[4/5] Arrancando la web en ${URL} ..."
python -m uvicorn app.main:app --host "${HOST}" --port "${PORT}" > logs/wawa.log 2>&1 &
SERVER_PID=$!
echo "${SERVER_PID}" > logs/wawa.pid

# 5) Esperar a /api/health y abrir el navegador
echo "[5/5] Esperando a que el servidor responda..."
i=0
while [ $i -lt 30 ]; do
  if curl -fsS "${URL}/api/health" >/dev/null 2>&1; then
    echo "  OK — la web está lista en ${URL}"
    break
  fi
  i=$((i + 1))
  sleep 1
done
if [ $i -ge 30 ]; then
  echo "  AVISO: el servidor no respondió en 30 s. Revisa logs/wawa.log"
fi

if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "${URL}" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
  open "${URL}" >/dev/null 2>&1 || true
fi

echo ""
echo "Web abierta en: ${URL}"
echo "Para detener:   sh stop_wawa.sh"
echo "Idea exportada: data/exports/ (o pestaña Ideas → Descargar CSV)"
