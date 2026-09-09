#Requires -Version 5.1
# Install local deps: .env paths, MariaDB, venv, pip. Does not write APP_ENV.

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_lib.ps1"
Ensure-ZhangeDeps -ForcePip
Write-Host "[install] done. Start: powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\win\run.ps1"
