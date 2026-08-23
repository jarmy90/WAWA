@echo off
REM START_WAWA (Windows) — arranca Autonomous Business Lab en local.
REM Uso: doble clic, o:  START_WAWA.bat [puerto]
setlocal
cd /d "%~dp0"

set HOST=127.0.0.1
if "%1"=="" (set PORT=8000) else (set PORT=%1)
set URL=http://%HOST%:%PORT%

echo ==============================================
echo   Autonomous Business Lab - inicio local
echo ==============================================

REM 1) Entorno virtual
if not exist ".venv" (
  echo [1/5] Creando entorno virtual...
  python -m venv .venv
)
call .venv\Scripts\activate.bat

REM 2) Dependencias
python -c "import fastapi, uvicorn, pydantic" >nul 2>&1
if errorlevel 1 (
  echo [2/5] Instalando dependencias...
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -e ".[dev]"
)

REM 3) Base de datos
echo [3/5] Preparando datos locales...
if not exist data mkdir data
if not exist logs mkdir logs
if not exist "data\abl.db" (
  python -c "from app.repositories.db import init_db; from app.core.config import Settings; s=Settings(); init_db(s.database_path); print('SQLite inicializado')"
)

REM 4) Arrancar la API (solo local)
echo [4/5] Arrancando la web en %URL% ...
start "WAWA server" cmd /c "call .venv\Scripts\activate.bat && python -m uvicorn app.main:app --host %HOST% --port %PORT% > logs\wawa.log 2>&1"

REM 5) Esperar a /api/health y abrir el navegador
echo [5/5] Esperando a que el servidor responda...
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
endlocal
