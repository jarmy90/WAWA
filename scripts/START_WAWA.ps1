$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$pidFile = Join-Path $Root 'data\wawa.pid'
if (Test-Path $pidFile) { $old = Get-Content $pidFile; if (Get-Process -Id $old -ErrorAction SilentlyContinue) { Write-Host 'WAWA ya está ejecutándose.'; exit 0 } }
$proc = Start-Process -FilePath 'python' -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000','--workers','1' -WorkingDirectory $Root -PassThru
New-Item -ItemType Directory -Force (Join-Path $Root 'data') | Out-Null
Set-Content -Path $pidFile -Value $proc.Id
Write-Host "WAWA iniciado. PID $($proc.Id)"
