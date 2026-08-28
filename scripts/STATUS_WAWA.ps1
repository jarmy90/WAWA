$Root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $Root 'data\wawa.pid'
if (Test-Path $pidFile) { $pid = Get-Content $pidFile; $p = Get-Process -Id $pid -ErrorAction SilentlyContinue; if ($p) { Write-Host "WAWA RUNNING PID $pid" } else { Write-Host 'WAWA STOPPED (PID obsoleto)' } } else { Write-Host 'WAWA STOPPED' }
try { $h = Invoke-RestMethod 'http://127.0.0.1:8000/api/health'; Write-Host "API: OK $($h.version)" } catch { Write-Host 'API: no responde' }
