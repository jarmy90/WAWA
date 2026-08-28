$ErrorActionPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $Root 'data\wawa.pid'
if (Test-Path $pidFile) { Stop-Process -Id (Get-Content $pidFile) -Force; Remove-Item $pidFile -Force }
Write-Host 'WAWA detenido.'
