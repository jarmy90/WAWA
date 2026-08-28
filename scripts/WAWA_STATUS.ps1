$ErrorActionPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $Root 'data\runtime\wawa.pid'
$running = $false
if (Test-Path $PidFile) {
  $id = [int](Get-Content $PidFile)
  $running = [bool](Get-Process -Id $id)
}
$omni = $false
try { Invoke-WebRequest -Uri 'http://127.0.0.1:20128/v1/models' -TimeoutSec 2 -UseBasicParsing | Out-Null; $omni = $true } catch {}
$api = $false
try { Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2 -UseBasicParsing | Out-Null; $api = $true } catch {}
[pscustomobject]@{ WAWA=$running; API=$api; OmniRoute=$omni; Root=$Root } | Format-List
