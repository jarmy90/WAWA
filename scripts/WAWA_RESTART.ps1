$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'WAWA_STOP.ps1')
Start-Sleep -Milliseconds 500
& (Join-Path $PSScriptRoot 'WAWA_START.ps1')
