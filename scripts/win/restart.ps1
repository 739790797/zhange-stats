#Requires -Version 5.1
# Check deps then restart backend and frontend.

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_lib.ps1"
Ensure-ZhangeDeps
Invoke-Restart
