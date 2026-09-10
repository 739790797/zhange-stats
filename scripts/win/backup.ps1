#Requires -Version 5.1
# Backup: config/ + data/runtime + data/uploads + data/models; MySQL also dumps zhange.sql.
# Override: $env:ZHANGE_BACKUP_DIR  $env:ZHANGE_BACKUP_KEEP_DAYS (default 14)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_lib.ps1"

$backupRoot = $env:ZHANGE_BACKUP_DIR
if (-not $backupRoot) { $backupRoot = Join-Path $RepoRoot "data\backups" }
$keepDays = 14
if ($env:ZHANGE_BACKUP_KEEP_DAYS) { $keepDays = [int]$env:ZHANGE_BACKUP_KEEP_DAYS }
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
New-Item -ItemType Directory -Force -Path $TmpDir | Out-Null
$work = Join-Path $TmpDir ("zhange-backup-" + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Force -Path $work | Out-Null

try {
  $code = @'
import json, os, sys
from pathlib import Path
root = Path(sys.argv[1])
url = (os.environ.get("DATABASE_URL") or "").strip()
engine = ""
cfg = root / "config" / "database.json"
if cfg.is_file():
    try:
        data = json.loads(cfg.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        data = {}
    engine = str(data.get("engine") or "").strip().lower()
    url = url or str(data.get("url") or "").strip()
if not engine:
    if url.startswith("sqlite"):
        engine = "sqlite"
    elif url.startswith("mysql"):
        engine = "mysql"
print(engine + "\t" + url)
'@
  $spec = Get-ProvisionPython
  $raw = & $spec.File @($spec.Prefix + @("-c", $code, "$RepoRoot"))
  $fields = ("$raw").Trim().Split("`t")
  $engine = $fields[0]
  $dbUrl = if ($fields.Count -gt 1) { $fields[1] } else { "" }

  $sqlPath = $null
  if ($engine -eq "mysql") {
    if (-not $dbUrl) { throw "MySQL backup needs config/database.json url or DATABASE_URL" }
    $envFile = Join-Path $work "url.env"
    Set-Content -Path $envFile -Value "DATABASE_URL=$dbUrl" -Encoding ascii
    $db = Get-DatabaseUrlParts $envFile
    $dumpExe = Get-MysqlTool "mysqldump"
    Write-Host "[backup] mysqldump $($db.Name) @ $($db.Host):$($db.Port)"
    $sqlPath = Join-Path $work "zhange.sql"
    $env:MYSQL_PWD = $db.Password
    try {
      $p = Start-Process -FilePath $dumpExe -ArgumentList @(
        "--single-transaction", "--routines", "--events",
        "-h", $db.Host, "-P", $db.Port, "-u", $db.User,
        "--result-file=$sqlPath", $db.Name
      ) -Wait -PassThru -NoNewWindow
      if ($p.ExitCode -ne 0) { throw "mysqldump failed" }
    } finally {
      Remove-Item Env:MYSQL_PWD -ErrorAction SilentlyContinue
    }
  } else {
    Write-Host "[backup] engine=$engine (no mysqldump)"
  }

  $archive = Join-Path $backupRoot "zhange-$stamp.tar.gz"
  $tar = Get-Command tar -ErrorAction SilentlyContinue
  if (-not $tar) { throw "tar not found (Windows 10+ includes tar.exe)" }

  $runtimeSrc = Join-Path $RepoRoot "data\runtime"
  if (-not (Test-Path $runtimeSrc)) { $runtimeSrc = Join-Path $RepoRoot "var\data" }
  $uploadSrc = Join-Path $RepoRoot "data\uploads"
  if (-not (Test-Path $uploadSrc)) { $uploadSrc = Join-Path $RepoRoot "var\uploads" }
  $modelsSrc = Join-Path $RepoRoot "data\models"

  $stage = Join-Path $work "stage"
  New-Item -ItemType Directory -Force -Path (Join-Path $stage "data") | Out-Null
  if ($sqlPath -and (Test-Path $sqlPath)) {
    Copy-Item $sqlPath (Join-Path $stage "zhange.sql")
  }
  $configSrc = Join-Path $RepoRoot "config"
  if (Test-Path $configSrc) { Copy-Item $configSrc (Join-Path $stage "config") -Recurse }
  $envFileSrc = Join-Path $RepoRoot ".env"
  if (Test-Path $envFileSrc) { Copy-Item $envFileSrc (Join-Path $stage ".env") }
  if (Test-Path $runtimeSrc) { Copy-Item $runtimeSrc (Join-Path $stage "data\runtime") -Recurse }
  if (Test-Path $uploadSrc) { Copy-Item $uploadSrc (Join-Path $stage "data\uploads") -Recurse }
  if (Test-Path $modelsSrc) { Copy-Item $modelsSrc (Join-Path $stage "data\models") -Recurse }

  Push-Location $stage
  try {
    $names = @()
    if (Test-Path (Join-Path $stage "zhange.sql")) { $names += "zhange.sql" }
    if (Test-Path (Join-Path $stage "config")) { $names += "config" }
    if (Test-Path (Join-Path $stage ".env")) { $names += ".env" }
    if (Test-Path (Join-Path $stage "data")) { $names += "data" }
    & $tar.Source -czf $archive @names
    if ($LASTEXITCODE -ne 0) { throw "tar failed" }
  } finally {
    Pop-Location
  }

  Get-ChildItem $backupRoot -Filter "zhange-*.tar.gz" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$keepDays) } |
    Remove-Item -Force
  Write-Host "[backup] wrote $archive"
} finally {
  Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
}
