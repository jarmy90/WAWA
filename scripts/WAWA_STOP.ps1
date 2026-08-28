$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $Root 'data\runtime\wawa.pid'
if (-not (Test-Path $PidFile)) { Write-Host 'WAWA no está iniciado.'; exit 0 }
$id = [int](Get-Content $PidFile)
$p = Get-Process -Id $id -ErrorAction SilentlyContinue
if ($p) { Stop-Process -Id $id -Force }
Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
Write-Host 'WAWA detenido.'
