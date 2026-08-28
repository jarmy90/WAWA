$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$reportDir = Join-Path $Root 'data\runtime'
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$reportPath = Join-Path $reportDir 'runtime_activation_report.json'
$errors = @()
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw 'Python no está disponible en PATH.' }
try { & $python -c "import fastapi,uvicorn,pydantic" } catch { throw 'Dependencias Python no instaladas.' }
$omni = $false
$catalog = $null
try {
  $r = Invoke-WebRequest -Uri 'http://127.0.0.1:20128/v1/models' -TimeoutSec 5 -UseBasicParsing
  $catalog = $r.Content | ConvertFrom-Json
  $omni = $true
} catch { $errors += 'OmniRoute no responde en 127.0.0.1:20128.' }
$model = $null
if ($catalog -and $catalog.data) { $model = @($catalog.data | ForEach-Object { $_.id } | Where-Object { $_ })[0] }
if (-not $model) { $errors += 'Catálogo sin modelo utilizable.' }
$report = [ordered]@{
  schema_version='1.0'; timestamp=(Get-Date).ToUniversalTime().ToString('o');
  omniroute_reachable=$omni; catalog_valid=[bool]$catalog; real_model=$model;
  completion_validated=$false; request_id=$null; latency_ms=$null; tokens=$null; cost=$null;
  api=$false; scheduler=$false; worker=$false; operator=$false; heartbeat=$false;
  smoke_job_id=$null; transitions=@(); next_job_id=$null; preflight=$null;
  safe_pause=$false; errors=$errors
}
$health = $null
try { Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2 -UseBasicParsing | Out-Null; $report.api=$true } catch {}
$report | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $reportPath
& (Join-Path $PSScriptRoot 'WAWA_START.ps1')
Write-Host "Informe local: $reportPath"
Write-Host 'La activación real de OmniRoute requiere que el gateway local responda y que el modelo aparezca en el catálogo.'
Start-Process 'http://127.0.0.1:8000'
