$ErrorActionPreference = 'Stop'
$Target = 'C:\WAWA'
if (Test-Path (Join-Path $Target 'scripts\WAWA_STOP.ps1')) { & (Join-Path $Target 'scripts\WAWA_STOP.ps1') }
if (Test-Path (Join-Path $Target 'scripts\WAWA_UNINSTALL_STARTUP.ps1')) { & (Join-Path $Target 'scripts\WAWA_UNINSTALL_STARTUP.ps1') }
Write-Host 'Runtime detenido y arranque automático eliminado. Los datos de C:\WAWA se conservan.'
