#Requires -Version 5.1
# Check deps then start backend :6130 and frontend :6131.

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_lib.ps1"
Ensure-ZhangeDeps
Invoke-Start
