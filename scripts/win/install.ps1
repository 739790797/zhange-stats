#Requires -Version 5.1
# Install local deps: venv, pip, prebuilt static. Does not write APP_ENV or provision MariaDB.

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_lib.ps1"
Ensure-ZhangeDeps -ForcePip
Ensure-StaticAssets
Write-Host "[install] done. Start: powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\win\run.ps1"
