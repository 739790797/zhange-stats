#Requires -Version 5.1
# Apply GitHub Release (add/update/delete whitelist + frontend sync + static + pip + migrate), then restart.

param(
  [string]$Version = "latest",
  [switch]$Check,
  [switch]$NoRestart,
  [switch]$Force,
  [string]$Proxy = ""
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_lib.ps1"
Ensure-ZhangeDeps

$updatePy = Join-Path $RepoRoot "scripts\common\update.py"
if (-not (Test-Path $updatePy)) {
  throw "Missing $updatePy"
}

$pyArgs = @($updatePy)
if ($Check) { $pyArgs += "--check" }
if ($Force) { $pyArgs += "--force" }
if ($NoRestart) { $pyArgs += "--no-restart" }
if ($Version -and $Version -ne "latest") { $pyArgs += @("--version", $Version) }
elseif (-not $Check) { $pyArgs += @("--version", "latest") }
if ($Proxy) { $pyArgs += @("--proxy", $Proxy) }

& $PythonExe @pyArgs
$rc = $LASTEXITCODE

if ($Check -or $NoRestart) {
  exit $rc
}
if ($rc -eq 2) {
  Write-Host "[update] already latest; skipped restart"
  exit 0
}
if ($rc -ne 0) {
  exit $rc
}

Invoke-Restart
Write-Host "[update] done and restarted."
