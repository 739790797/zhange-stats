#Requires -Version 5.1
# Backup: mysqldump + var/data + var/uploads + .env -> var/backups/zhange-*.tar.gz
# Override: $env:ZHANGE_BACKUP_DIR  $env:ZHANGE_BACKUP_KEEP_DAYS (default 14)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_lib.ps1"

$envFile = Join-Path $RepoRoot ".env"
if (-not (Test-Path $envFile)) { throw "Missing $envFile" }

$backupRoot = $env:ZHANGE_BACKUP_DIR
if (-not $backupRoot) { $backupRoot = Join-Path $RepoRoot "var\backups" }
$keepDays = 14
if ($env:ZHANGE_BACKUP_KEEP_DAYS) { $keepDays = [int]$env:ZHANGE_BACKUP_KEEP_DAYS }
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

$dumpExe = Get-MysqlTool "mysqldump"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$work = Join-Path $env:TEMP ("zhange-backup-" + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Force -Path $work | Out-Null

try {
  $db = Get-DatabaseUrlParts $envFile
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

  $archive = Join-Path $backupRoot "zhange-$stamp.tar.gz"
  $tar = Get-Command tar -ErrorAction SilentlyContinue
  if (-not $tar) { throw "tar not found (Windows 10+ includes tar.exe)" }

  $dataSrc = Join-Path $RepoRoot "var\data"
  $uploadSrc = Join-Path $RepoRoot "var\uploads"
  if ((Test-Path (Join-Path $RepoRoot "data")) -and -not (Test-Path (Join-Path $RepoRoot "var\data\.secret_key"))) {
    $dataSrc = Join-Path $RepoRoot "data"
    $uploadSrc = Join-Path $RepoRoot "uploads"
  }

  $stage = Join-Path $work "stage"
  New-Item -ItemType Directory -Force -Path (Join-Path $stage "var") | Out-Null
  Copy-Item $sqlPath (Join-Path $stage "zhange.sql")
  Copy-Item $envFile (Join-Path $stage ".env")
  if (Test-Path $dataSrc) { Copy-Item $dataSrc (Join-Path $stage "var\data") -Recurse }
  if (Test-Path $uploadSrc) { Copy-Item $uploadSrc (Join-Path $stage "var\uploads") -Recurse }

  Push-Location $stage
  try {
    & $tar.Source -czf $archive "zhange.sql" ".env" "var"
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
