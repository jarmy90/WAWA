$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$StateDir = Join-Path $Root 'data\runtime'
$LogDir = Join-Path $StateDir 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$PidFile = Join-Path $StateDir 'wawa.pid'
if (Test-Path $PidFile) {
  $old = Get-Content $PidFile -ErrorAction SilentlyContinue
  if ($old -and (Get-Process -Id ([int]$old) -ErrorAction SilentlyContinue)) { Write-Host 'WAWA ya está iniciado.'; exit 0 }
  Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw 'Python no está disponible en PATH.' }
& $python -c "import fastapi,uvicorn,pydantic"
if ($LASTEXITCODE -ne 0) { throw 'Faltan dependencias. Ejecuta: python -m pip install -e .[dev]' }
$health = Invoke-WebRequest -Uri 'http://127.0.0.1:20128/v1/models' -TimeoutSec 3 -UseBasicParsing -ErrorAction SilentlyContinue
if (-not $health) { Write-Warning 'OmniRoute no responde; WAWA queda en modo seguro y no se activan jobs LLM.' }
$log = Join-Path $LogDir ('wawa-' + (Get-Date -Format 'yyyyMMdd') + '.log')
$p = Start-Process -FilePath $python -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' -RedirectStandardOutput $log -RedirectStandardError $log -PassThru -WindowStyle Hidden
$p.Id | Set-Content $PidFile
Write-Host "WAWA iniciado. PID $($p.Id). URL: http://127.0.0.1:8000"
