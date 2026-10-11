#Requires -Version 5.1
# Restore from a backup.ps1 tar.gz: check version -> stop app -> optional DB import -> replace config/ and data/ -> start.
# Requires:
#   $env:ZHANGE_RESTORE_CONFIRM = "YES"
#   $env:ZHANGE_RESTORE_ARCHIVE = "C:\path\zhange-YYYYMMDD-HHMMSS.tar.gz"

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_lib.ps1"

$archive = $env:ZHANGE_RESTORE_ARCHIVE
if (-not $archive -or -not (Test-Path $archive)) {
  throw "Set ZHANGE_RESTORE_ARCHIVE to a backup tar.gz"
}
if ($env:ZHANGE_RESTORE_CONFIRM -ne "YES") {
  throw "This overwrites the current DB, config/, and data/. Confirm with ZHANGE_RESTORE_CONFIRM=YES"
}
$archive = (Resolve-Path $archive).Path

$util = Join-Path $RepoRoot "scripts\common\backup_util.py"
$spec = Get-ProvisionPython
New-Item -ItemType Directory -Force -Path $TmpDir | Out-Null
$work = Join-Path $TmpDir ("zhange-restore-" + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Force -Path $work | Out-Null
try {
  Invoke-Python $spec @($util, "unpack", "--archive", $archive, "--dest", $work)
  Invoke-Python $spec @($util, "inspect", "--root", "$RepoRoot", "--dir", $work)

  Write-Host "[restore] stopping app"
  Invoke-Stop

  & $spec.File @($spec.Prefix + @($util, "load-db", "--root", "$RepoRoot", "--dir", $work))
  if ($LASTEXITCODE -ne 0) {
    throw "[restore] DB import failed: config/ and data/ are untouched and the app stays stopped; fix it and re-run restore"
  }

  $configSrc = Join-Path $work "config"
  if (Test-Path $configSrc) {
    $configDest = Join-Path $RepoRoot "config"
    if (Test-Path $configDest) { Remove-Item $configDest -Recurse -Force }
    Copy-Item $configSrc $configDest -Recurse
  }
  if (Test-Path (Join-Path $work ".env")) {
    Copy-Item (Join-Path $work ".env") (Join-Path $RepoRoot ".env") -Force
  }

  function Copy-Tree([string]$Src, [string]$Dest) {
    if (-not (Test-Path $Src)) { return }
    $parent = Split-Path $Dest -Parent
    if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
    Copy-Item $Src $Dest -Recurse
  }

  $dataRoot = Join-Path $RepoRoot "data"
  New-Item -ItemType Directory -Force -Path $dataRoot | Out-Null
  Copy-Tree (Join-Path $work "data\runtime") (Join-Path $dataRoot "runtime")
  Copy-Tree (Join-Path $work "data\uploads") (Join-Path $dataRoot "uploads")
  Copy-Tree (Join-Path $work "data\models") (Join-Path $dataRoot "models")
  if (-not (Test-Path (Join-Path $work "data\runtime"))) {
    Copy-Tree (Join-Path $work "var\data") (Join-Path $dataRoot "runtime")
  }
  if (-not (Test-Path (Join-Path $work "data\uploads"))) {
    Copy-Tree (Join-Path $work "var\uploads") (Join-Path $dataRoot "uploads")
  }

  Write-Host "[restore] starting app"
  Ensure-ZhangeDeps
  Invoke-Start
  Write-Host "[restore] done"
} finally {
  Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
}
