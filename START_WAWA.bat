@echo off
REM START_WAWA (Windows) — arranca Autonomous Business Lab en local.
REM Iteración 022: UN solo punto de entrada. NO hace falta abrir PowerShell
REM ni escribir comandos: se detecta y aplica la activación comercial
REM automáticamente antes de abrir el navegador.
REM Uso: doble clic, o:  START_WAWA.bat [puerto]
setlocal
cd /d "%~dp0"

set HOST=127.0.0.1
if "%1"=="" (set PORT=8000) else (set PORT=%1)
set URL=http://%HOST%:%PORT%

echo ==============================================
echo   Autonomous Business Lab - inicio local
echo ==============================================

echo [1/7] Preparando entorno...
if not exist ".venv" (
  echo       Creando entorno virtual...
  python -m venv .venv
  if errorlevel 1 (
    echo ERROR: no se encontro Python. Instala Python 3.10+ desde python.org
    echo y marca "Add Python to PATH", luego vuelve a ejecutar este archivo.
    pause
    exit /b 1
  )
)
call ".venv\Scripts\activate.bat"

echo [2/7] Inicializando base local...
python -c "import fastapi, uvicorn, pydantic" >nul 2>&1
if errorlevel 1 (
  echo       Instalando dependencias...
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -e ".[dev]"
)
if not exist "data" mkdir data
if not exist "logs" mkdir logs
python -c "from app.repositories.db import init_db; from app.core.config import get_settings; init_db(get_settings()); print('      SQLite inicializado')"

echo [3/7] Comprobando campana...
python -c "from app.core.config import get_settings; from app.core.container import build_container; c=build_container(get_settings()); s=c.bootstrap.status(); print('      Campana: ' + str(s.get('run_state') or 'sin run (se creara)') + ' | bootstrap aplicado: ' + str(s.get('applied'))); c.close()"

echo [4/7] Aplicando investigacion verificada...
echo [5/7] Seleccionando ganadora...
echo [6/7] Verificando READY_TO_CONNECT_SERVICES...
python "scripts\startup_bootstrap.py"

echo [7/7] Abriendo WAWA...
start "WAWA server" cmd /c "call .venv\Scripts\activate.bat && python -m uvicorn app.main:app --host %HOST% --port %PORT% > logs\wawa.log 2>&1"

echo       Esperando a que el servidor responda...
set /a i=0
:waitloop
curl -fsS "%URL%/api/health" >nul 2>&1
if not errorlevel 1 goto ready
set /a i+=1
if %i% GEQ 30 goto timeout
timeout /t 1 /nobreak >nul
goto waitloop

:ready
echo   OK - la web esta lista en %URL%
start "" "%URL%"
goto done

:timeout
echo   AVISO: el servidor no respondio en 30 s. Revisa logs\wawa.log

:done
echo.
echo Web abierta en: %URL%
echo Para detener:   STOP_WAWA.bat
echo.
echo Siguiente paso: en el panel, abre CANDIDATAS para ver las 3 candidatas
echo y copiar los expedientes GPT/Grok/Gemini (comite).
endlocal
