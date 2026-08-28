$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
& "$PSScriptRoot\BACKUP_WAWA.ps1"
git pull --ff-only origin main
if ($LASTEXITCODE -ne 0) { throw 'Actualización no aplicada; usa RESTORE_WAWA.ps1 si procede.' }
python -m pip install -e '.[dev]'
python -m pytest -q
