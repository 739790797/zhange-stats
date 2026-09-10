#Requires -Version 5.1
# Install local deps: venv, pip. Does not write APP_ENV or provision MariaDB.

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_lib.ps1"
Ensure-ZhangeDeps -ForcePip
Write-Host "[install] done. Start: powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\win\run.ps1"
