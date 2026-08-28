$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$name = 'WAWA Autonomous Runtime'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSScriptRoot\WAWA_START.ps1`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Description 'Arranque local de WAWA; no configura OmniRoute ni activa producción.' -Force | Out-Null
Write-Host "Tarea instalada: $name"
