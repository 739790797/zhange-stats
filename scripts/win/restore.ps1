#Requires -Version 5.1
# Restore from backup.ps1 tar.gz. Requires:
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

$tar = Get-Command tar -ErrorAction SilentlyContinue
if (-not $tar) { throw "tar not found" }

New-Item -ItemType Directory -Force -Path $TmpDir | Out-Null
$work = Join-Path $TmpDir ("zhange-restore-" + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Force -Path $work | Out-Null
try {
  & $tar.Source -xzf $archive -C $work

  Write-Host "[restore] stopping app"
  Invoke-Stop

  $configSrc = Join-Path $work "config"
  if (Test-Path $configSrc) {
    $configDest = Join-Path $RepoRoot "config"
    if (Test-Path $configDest) { Remove-Item $configDest -Recurse -Force }
    Copy-Item $configSrc $configDest -Recurse
  }
  if (Test-Path (Join-Path $work ".env")) {
    Copy-Item (Join-Path $work ".env") (Join-Path $RepoRoot ".env") -Force
  }

  $sqlPath = Join-Path $work "zhange.sql"
  if (Test-Path $sqlPath) {
    $code = @'
import json, os, sys
from pathlib import Path
root = Path(sys.argv[1])
url = (os.environ.get("DATABASE_URL") or "").strip()
cfg = root / "config" / "database.json"
if cfg.is_file():
    try:
        data = json.loads(cfg.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        data = {}
    url = url or str(data.get("url") or "").strip()
print(url)
'@
    $spec = Get-ProvisionPython
    $dbUrl = (& $spec.File @($spec.Prefix + @("-c", $code, "$RepoRoot"))).Trim()
    if (-not $dbUrl) { throw "Archive has zhange.sql but no MySQL URL" }
    $tmpEnv = Join-Path $work "url.env"
    Set-Content -Path $tmpEnv -Value "DATABASE_URL=$dbUrl" -Encoding ascii
    $db = Get-DatabaseUrlParts $tmpEnv
    $mysqlExe = Get-MysqlTool "mysql"
    Write-Host "[restore] import $($db.Name)"
    $env:MYSQL_PWD = $db.Password
    try {
      $p = Start-Process -FilePath $mysqlExe -ArgumentList @(
        "--default-character-set=utf8mb4",
        "-h", $db.Host, "-P", $db.Port, "-u", $db.User, $db.Name
      ) -RedirectStandardInput $sqlPath -Wait -PassThru -NoNewWindow
      if ($p.ExitCode -ne 0) { throw "mysql import failed" }
    } finally {
      Remove-Item Env:MYSQL_PWD -ErrorAction SilentlyContinue
    }
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
