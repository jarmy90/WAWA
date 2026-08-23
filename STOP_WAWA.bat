@echo off
REM STOP_WAWA (Windows) — detiene la web local.
taskkill /FI "WINDOWTITLE eq WAWA server*" /T /F >nul 2>&1
if errorlevel 1 (
  echo No se encontro la ventana de WAWA. Puede que ya este detenida.
) else (
  echo WAWA detenida.
)
