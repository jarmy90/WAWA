$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$backup = Get-ChildItem (Join-Path $Root 'data\backups\*.db') | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $backup) { throw 'No hay backup SQLite disponible.' }
& "$PSScriptRoot\STOP_WAWA.ps1"
Copy-Item $backup.FullName (Join-Path $Root 'data\abl.db') -Force
Write-Host "Restaurado backup: $($backup.Name)"
