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
  throw "This overwrites the current DB and var/. Confirm with ZHANGE_RESTORE_CONFIRM=YES"
}

$tar = Get-Command tar -ErrorAction SilentlyContinue
if (-not $tar) { throw "tar not found" }
$mysqlExe = Get-MysqlTool "mysql"

$work = Join-Path $env:TEMP ("zhange-restore-" + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Force -Path $work | Out-Null
try {
  & $tar.Source -xzf $archive -C $work
  $sqlPath = Join-Path $work "zhange.sql"
  if (-not (Test-Path $sqlPath)) { throw "Archive has no zhange.sql" }

  Write-Host "[restore] stopping app"
  Invoke-Stop

  $restoreEnv = Join-Path $work ".env"
  $envFile = Join-Path $RepoRoot ".env"
  if (-not (Test-Path $restoreEnv)) { $restoreEnv = $envFile }
  if (-not (Test-Path $restoreEnv)) { throw "No .env to parse DATABASE_URL" }

  $db = Get-DatabaseUrlParts $restoreEnv
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

  if (Test-Path (Join-Path $work ".env")) {
    Copy-Item (Join-Path $work ".env") $envFile -Force
  }
  $varDir = Join-Path $RepoRoot "var"
  New-Item -ItemType Directory -Force -Path $varDir | Out-Null
  foreach ($name in @("data", "uploads")) {
    $src = Join-Path $work "var\$name"
    if (Test-Path $src) {
      $dest = Join-Path $varDir $name
      if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
      Copy-Item $src $dest -Recurse
    }
  }

  Write-Host "[restore] starting app"
  Ensure-ZhangeDeps
  Invoke-Start
  Write-Host "[restore] done"
} finally {
  Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
}
