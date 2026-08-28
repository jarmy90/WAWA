$ErrorActionPreference = 'Stop'
$Source = Split-Path -Parent $MyInvocation.MyCommand.Path
$Target = 'C:\WAWA'
New-Item -ItemType Directory -Force -Path $Target | Out-Null
Copy-Item -Path (Join-Path $Source '*') -Destination $Target -Recurse -Force
Set-Location $Target
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw 'Instala Python 3.10+ y vuelve a ejecutar INSTALL_WAWA.ps1.' }
& $python -m venv (Join-Path $Target '.venv')
$venvPython = Join-Path $Target '.venv\Scripts\python.exe'
& $venvPython -m pip install -e '.[dev]'
New-Item -ItemType Directory -Force -Path (Join-Path $Target 'data\backups'), (Join-Path $Target 'data\runtime\logs') | Out-Null
if (Test-Path (Join-Path $Target 'scripts\WAWA_INSTALL_STARTUP.ps1')) { & (Join-Path $Target 'scripts\WAWA_INSTALL_STARTUP.ps1') }
& (Join-Path $Target 'scripts\WAWA_START.ps1')
& (Join-Path $Target 'scripts\WAWA_STATUS.ps1')
Write-Host 'WAWA instalado en C:\WAWA.'
Write-Host 'Owner Command Center: http://127.0.0.1:8000'
