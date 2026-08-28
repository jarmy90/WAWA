$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$dir = Join-Path $Root 'data\backups'
New-Item -ItemType Directory -Force $dir | Out-Null
$stamp = Get-Date -Format 'yyyyMMddTHHmmssK'
$db = Join-Path $Root 'data\abl.db'
if (Test-Path $db) { Copy-Item $db (Join-Path $dir "abl_$stamp.db") -Force; Write-Host 'Backup SQLite creado.' } else { Write-Host 'No existe SQLite todavía; se omitió backup.' }
