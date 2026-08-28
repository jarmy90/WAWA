$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
python -m compileall -q app tests
python -m pytest -q
if (Test-Path 'data\runtime_activation_report.json') { Write-Host 'Informe runtime disponible.' }
