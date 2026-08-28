$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$task = 'WAWA Autonomous Runtime'
$action = New-ScheduledTaskAction -Execute 'PowerShell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Root\scripts\START_WAWA.ps1`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger -Description 'WAWA local runtime; no OmniRoute configuration changes' -Force | Out-Null
Write-Host "Tarea instalada: $task"
