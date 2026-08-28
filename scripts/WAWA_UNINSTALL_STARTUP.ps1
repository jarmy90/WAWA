$ErrorActionPreference = 'Stop'
Unregister-ScheduledTask -TaskName 'WAWA Autonomous Runtime' -Confirm:$false
Write-Host 'Tarea de inicio eliminada.'
