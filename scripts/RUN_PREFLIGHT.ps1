$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
try { (Invoke-RestMethod 'http://127.0.0.1:8000/api/runtime/preflight').psobject.Properties | ForEach-Object { Write-Host "$($_.Name): $($_.Value)" } } catch { Write-Host 'WAWA no responde; SAFE_PAUSE recomendado.' }
