$ErrorActionPreference = 'Stop'
Unregister-ScheduledTask -TaskName 'WAWA Autonomous Runtime' -Confirm:$false -ErrorAction SilentlyContinue
Write-Host 'Tarea WAWA Autonomous Runtime eliminada.'
