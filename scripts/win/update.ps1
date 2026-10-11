#Requires -Version 5.1
# Apply a GitHub Release (sha256 check, staging, pip, whitelist add/update/delete + frontend sync,
# migrate, static swap), then restart.
# -StaticOnly: only fetch the prebuilt static of the local VERSION (fresh install; no restart).

param(
  [string]$Version = "latest",
  [switch]$Check,
  [switch]$NoRestart,
  [switch]$Force,
  [switch]$StaticOnly,
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
if ($StaticOnly) { $pyArgs += "--static-only" }
if ($Check) { $pyArgs += "--check" }
if ($Force) { $pyArgs += "--force" }
if ($NoRestart) { $pyArgs += "--no-restart" }
if ($Version -and $Version -ne "latest") { $pyArgs += @("--version", $Version) }
elseif (-not $Check) { $pyArgs += @("--version", "latest") }
if ($Proxy) { $pyArgs += @("--proxy", $Proxy) }

& $PythonExe @pyArgs
$rc = $LASTEXITCODE

if ($Check -or $NoRestart -or $StaticOnly) {
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
