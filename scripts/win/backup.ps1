#Requires -Version 5.1
# Backup: config/ + data/runtime + data/uploads + data/models + manifest.json (VERSION, migration revision).
# MySQL also dumps zhange.sql (utf8mb4); SQLite is copied through the online backup API.
# Update staging, locks and caches are skipped. The work is done by scripts\common\backup_util.py.
# Override: $env:ZHANGE_BACKUP_DIR  $env:ZHANGE_BACKUP_KEEP_DAYS (default 14)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_lib.ps1"

$backupRoot = $env:ZHANGE_BACKUP_DIR
if (-not $backupRoot) { $backupRoot = Join-Path $RepoRoot "data\backups" }
$keepDays = 14
if ($env:ZHANGE_BACKUP_KEEP_DAYS) { $keepDays = [int]$env:ZHANGE_BACKUP_KEEP_DAYS }
if ($keepDays -lt 0) { throw "ZHANGE_BACKUP_KEEP_DAYS must be a non-negative integer" }
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
New-Item -ItemType Directory -Force -Path $TmpDir | Out-Null
$work = Join-Path $TmpDir ("zhange-backup-" + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Force -Path $work | Out-Null

try {
  $archive = Join-Path $backupRoot "zhange-$stamp.tar.gz"
  $util = Join-Path $RepoRoot "scripts\common\backup_util.py"
  Invoke-Python (Get-ProvisionPython) @($util, "backup", "--root", "$RepoRoot", "--out", $archive, "--work", $work)

  Get-ChildItem $backupRoot -Filter "zhange-*.tar.gz" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$keepDays) } |
    Remove-Item -Force
} finally {
  Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
}
