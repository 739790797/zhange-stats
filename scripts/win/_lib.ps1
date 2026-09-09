#Requires -Version 5.1
# Shared by scripts/win/install.ps1, run.ps1, restart.ps1. Not a public command.

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$DevDir = Join-Path $RepoRoot "var\dev"
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"
$VenvDir = Join-Path $BackendDir ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$PipStamp = Join-Path $VenvDir ".zhange-req.stamp"
$StaticDir = Join-Path $RepoRoot "static"
$DataDir = Join-Path $RepoRoot "var\data"
$UploadDir = Join-Path $RepoRoot "var\uploads"
$env:PYTHONPYCACHEPREFIX = Join-Path $RepoRoot "var\cache\pycache"

$BackendPort = 6130
$FrontendPort = 6131
$BackendHost = "127.0.0.1"
$FrontendHost = "127.0.0.1"

$BackendPidFile = Join-Path $DevDir "backend.pid"
$FrontendPidFile = Join-Path $DevDir "frontend.pid"
$BackendOutLog = Join-Path $DevDir "backend.out.log"
$BackendErrLog = Join-Path $DevDir "backend.err.log"
$FrontendOutLog = Join-Path $DevDir "frontend.out.log"
$FrontendErrLog = Join-Path $DevDir "frontend.err.log"

function Ensure-DevDir {
  if (-not (Test-Path $DevDir)) {
    New-Item -ItemType Directory -Path $DevDir | Out-Null
  }
}

function Write-PidFile([string]$Path, [int]$ProcessId) {
  Ensure-DevDir
  Set-Content -Path $Path -Value $ProcessId -Encoding ascii
}

function Read-PidFile([string]$Path) {
  if (-not (Test-Path $Path)) { return $null }
  $raw = (Get-Content -Path $Path -TotalCount 1 -ErrorAction SilentlyContinue | Select-Object -First 1)
  if (-not $raw) { return $null }
  $parsed = 0
  if ([int]::TryParse("$raw".Trim(), [ref]$parsed) -and $parsed -gt 0) {
    return $parsed
  }
  return $null
}

function Test-PidAlive([int]$ProcessId) {
  if ($ProcessId -le 0) { return $false }
  return [bool](Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

function Get-ListenerPids([int]$Port) {
  $pids = @()
  try {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
      if ($c.OwningProcess -and $c.OwningProcess -gt 0) {
        $pids += [int]$c.OwningProcess
      }
    }
  } catch {
    $lines = netstat -ano | Select-String ":$Port\s+"
    foreach ($m in $lines) {
      if ($m.Line -match "LISTENING\s+(\d+)\s*$") {
        $pids += [int]$Matches[1]
      }
    }
  }
  return @($pids | Select-Object -Unique | Where-Object { $_ -gt 0 -and (Test-PidAlive $_) })
}

function Get-DescendantPids([int]$ProcessId) {
  $found = @()
  if ($ProcessId -le 0) { return $found }
  try {
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
      $cid = [int]$child.ProcessId
      $found += $cid
      $found += Get-DescendantPids $cid
    }
  } catch {}
  return @($found | Select-Object -Unique)
}

function Stop-ProcessTree([int]$ProcessId, [int]$GraceSeconds = 4) {
  if ($ProcessId -le 0) { return }

  $tree = @($ProcessId) + (Get-DescendantPids $ProcessId)
  $tree = @($tree | Select-Object -Unique | Where-Object { $_ -gt 0 })

  if (Test-PidAlive $ProcessId) {
    try { Stop-Process -Id $ProcessId -ErrorAction SilentlyContinue } catch {}
  }

  $deadline = (Get-Date).AddSeconds($GraceSeconds)
  while ((Get-Date) -lt $deadline) {
    $alive = @($tree | Where-Object { Test-PidAlive $_ })
    if ($alive.Count -eq 0) { return }
    Start-Sleep -Milliseconds 200
  }

  foreach ($procId in $tree) {
    if (Test-PidAlive $procId) {
      cmd.exe /c "taskkill /F /T /PID $procId >NUL 2>&1" | Out-Null
    }
  }
}

function Wait-PortFree([int]$Port, [int]$TimeoutSeconds = 15) {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    $listeners = Get-ListenerPids $Port
    if ($listeners.Count -eq 0) { return $true }
    Start-Sleep -Milliseconds 300
  }
  return ((Get-ListenerPids $Port).Count -eq 0)
}

function Wait-HttpReady([string]$Url, [int[]]$OkCodes, [int]$TimeoutSeconds = 45) {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $resp = Invoke-WebRequest -Uri $Url -TimeoutSec 2 -UseBasicParsing
      if ($OkCodes -contains [int]$resp.StatusCode) {
        return @{ Ok = $true; StatusCode = [int]$resp.StatusCode; Body = $resp.Content }
      }
    } catch {
      # keep polling
    }
    Start-Sleep -Seconds 1
  }
  return @{ Ok = $false; StatusCode = 0; Body = $null }
}

function Get-UvicornRelatedPids {
  $pids = @()
  try {
    $all = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $uvicorn = @($all | Where-Object {
      $_.CommandLine -and $_.CommandLine -match 'uvicorn app\.main:app'
    })
    foreach ($p in $uvicorn) {
      $pids += [int]$p.ProcessId
    }
    foreach ($p in $all) {
      if ($p.CommandLine -and $p.CommandLine -match 'multiprocessing\.spawn' -and ($pids -contains [int]$p.ParentProcessId)) {
        $pids += [int]$p.ProcessId
      }
    }
  } catch {}
  return @($pids | Select-Object -Unique)
}

function Stop-ServiceByPortAndPid(
  [string]$Name,
  [int]$Port,
  [string]$PidFile
) {
  $tracked = Read-PidFile $PidFile
  $targets = @()
  if ($tracked) { $targets += $tracked }
  $targets += Get-ListenerPids $Port
  if ($Name -eq "backend") {
    $targets += Get-UvicornRelatedPids
  }
  $expanded = @()
  foreach ($procId in ($targets | Select-Object -Unique)) {
    $expanded += $procId
    $expanded += Get-DescendantPids $procId
  }
  $targets = @($expanded | Select-Object -Unique | Where-Object { $_ -gt 0 })

  if ($targets.Count -eq 0 -and (Get-ListenerPids $Port).Count -eq 0) {
    Write-Host "[$Name] already stopped"
    if (Test-Path $PidFile) { Remove-Item $PidFile -Force -ErrorAction SilentlyContinue }
    return
  }

  foreach ($procId in $targets) {
    Write-Host "[$Name] stopping pid=$procId"
    Stop-ProcessTree -ProcessId $procId
  }

  $left = Get-ListenerPids $Port
  foreach ($procId in $left) {
    Write-Host "[$Name] force-clear listener pid=$procId"
    $tree = @($procId) + (Get-DescendantPids $procId)
    foreach ($t in ($tree | Select-Object -Unique)) {
      cmd.exe /c "taskkill /F /T /PID $t >NUL 2>&1" | Out-Null
      try { Stop-Process -Id $t -Force -ErrorAction SilentlyContinue } catch {}
    }
  }

  if (-not (Wait-PortFree -Port $Port -TimeoutSeconds 20)) {
    Start-Sleep -Seconds 2
    if (-not (Wait-PortFree -Port $Port -TimeoutSeconds 10)) {
      $still = Get-ListenerPids $Port
      throw "[$Name] port $Port still busy (pids: $($still -join ', '))"
    }
  }

  if (Test-Path $PidFile) { Remove-Item $PidFile -Force -ErrorAction SilentlyContinue }
  Write-Host "[$Name] stopped"
}

function Get-SystemPython {
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) {
    return @{ File = $py.Source; Prefix = @("-3") }
  }
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) {
    return @{ File = $python.Source; Prefix = @() }
  }
  throw "Python 3.11+ not found. Install Python and enable Add to PATH."
}

function Get-ProvisionPython {
  if (Test-Path $PythonExe) {
    return @{ File = $PythonExe; Prefix = @() }
  }
  return Get-SystemPython
}

function Invoke-Python([hashtable]$Spec, [string[]]$PyArgs) {
  & $Spec.File @($Spec.Prefix + $PyArgs)
  if ($LASTEXITCODE -ne 0) {
    throw "python exit $LASTEXITCODE"
  }
}

function Ensure-EnvKey([string]$Key, [string]$Value) {
  $envFile = Join-Path $RepoRoot ".env"
  $content = [IO.File]::ReadAllText($envFile)
  foreach ($line in $content.Split(@("`r`n", "`n"), [StringSplitOptions]::None)) {
    $trim = $line.Trim()
    if ($trim.StartsWith("#") -or -not $trim.StartsWith("$Key=")) {
      continue
    }
    return
  }
  $suffix = if ($content.Length -eq 0 -or $content.EndsWith("`n")) { "$Key=$Value`n" } else { "`n$Key=$Value`n" }
  [IO.File]::AppendAllText($envFile, $suffix)
  Write-Host "[env] appended $Key"
}

function Ensure-EnvFile {
  $envFile = Join-Path $RepoRoot ".env"
  $example = Join-Path $RepoRoot ".env.example"
  if (Test-Path $envFile) { return }
  if (-not (Test-Path $example)) {
    throw "Missing .env and .env.example"
  }
  Copy-Item $example $envFile
  Write-Host "[env] copied .env.example -> .env"
}

function Ensure-InstallPaths {
  New-Item -ItemType Directory -Force -Path $DataDir, $UploadDir, $StaticDir, $DevDir, (Join-Path $RepoRoot "var\backups") | Out-Null
  Ensure-EnvKey "APP_INSTALL_DIR" "$RepoRoot"
  Ensure-EnvKey "STATIC_DIR" "$StaticDir"
  Ensure-EnvKey "DATA_DIR" "$DataDir"
  Ensure-EnvKey "UPLOAD_DIR" "$UploadDir"
}

function Ensure-MariaDB {
  $script = Join-Path $RepoRoot "scripts\common\provision_mariadb.py"
  if (-not (Test-Path $script)) {
    throw "Missing $script"
  }
  $spec = Get-ProvisionPython
  Write-Host "[mariadb] ensuring local database..."
  & $spec.File @($spec.Prefix + @($script, "--root", "$RepoRoot"))
  if ($LASTEXITCODE -ne 0) {
    throw "MariaDB is not ready. Set DATABASE_URL or ZHANGE_SKIP_MARIADB=1"
  }
}

function Install-PythonDeps {
  $req = Join-Path $BackendDir "requirements.txt"
  if (-not (Test-Path $req)) {
    throw "Missing $req"
  }
  Write-Host "[pip] installing CPU torch + requirements..."
  & $PythonExe -m pip install -U pip
  if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
  & $PythonExe -m pip install torch torchvision --index-url "https://download.pytorch.org/whl/cpu"
  if ($LASTEXITCODE -ne 0) { throw "CPU torch install failed" }
  $constraint = Join-Path $env:TEMP ("zhange-torch-" + [guid]::NewGuid().ToString() + ".txt")
  try {
    $pinned = & $PythonExe -m pip freeze | Select-String -Pattern '^(torch|torchvision)=='
    $pinned | ForEach-Object { $_.Line } | Set-Content -Path $constraint -Encoding ascii
    if ((Get-Item $constraint).Length -gt 0) {
      & $PythonExe -m pip install -r $req -c $constraint
    } else {
      & $PythonExe -m pip install -r $req
    }
    if ($LASTEXITCODE -ne 0) { throw "pip install -r requirements.txt failed" }
  } finally {
    Remove-Item $constraint -ErrorAction SilentlyContinue
  }
  & $PythonExe -m pip uninstall -y opencv-python | Out-Null
  & $PythonExe -m pip install -q --force-reinstall --no-deps "opencv-python-headless>=4.8.0"
  if ($LASTEXITCODE -ne 0) { throw "opencv-python-headless install failed" }
  Set-Content -Path $PipStamp -Value ([DateTime]::UtcNow.ToString("o")) -Encoding ascii
}

function Ensure-Venv {
  if (Test-Path $PythonExe) { return }
  Write-Host "[venv] creating..."
  $sysPy = Get-SystemPython
  $verText = (& $sysPy.File @($sysPy.Prefix + @("-c", "import sys; print('%d.%d' % (sys.version_info[0], sys.version_info[1]))"))).Trim()
  $verParts = $verText.Split(".")
  if ([int]$verParts[0] -lt 3 -or ([int]$verParts[0] -eq 3 -and [int]$verParts[1] -lt 11)) {
    throw "Python 3.11+ required, found $verText"
  }
  Invoke-Python $sysPy @("-m", "venv", $VenvDir)
}

function Ensure-PythonDeps {
  param([switch]$ForcePip)
  Ensure-Venv
  $req = Join-Path $BackendDir "requirements.txt"
  $need = [bool]$ForcePip -or ($env:ZHANGE_FORCE_PIP -eq "1")
  if (-not $need) {
    if (-not (Test-Path $PipStamp) -or -not (Test-Path $req)) {
      $need = $true
    } elseif ((Get-Item $req).LastWriteTimeUtc -gt (Get-Item $PipStamp).LastWriteTimeUtc) {
      $need = $true
    }
  }
  if (-not $need) { return }
  Install-PythonDeps
}

function Ensure-FrontendDeps {
  $pkg = Join-Path $FrontendDir "package.json"
  $nm = Join-Path $FrontendDir "node_modules"
  if (-not (Test-Path $pkg) -or (Test-Path $nm)) { return }
  $npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
  if (-not $npmCmd) { $npmCmd = Get-Command npm -ErrorAction SilentlyContinue }
  if (-not $npmCmd) { return }
  Write-Host "[npm] installing frontend deps..."
  Push-Location $FrontendDir
  try {
    & $npmCmd.Source install --legacy-peer-deps
    if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
  } finally {
    Pop-Location
  }
}

function Ensure-ZhangeDeps {
  param([switch]$ForcePip)
  if (-not (Test-Path (Join-Path $RepoRoot "VERSION"))) {
    throw "VERSION not found; not an install root"
  }
  Ensure-EnvFile
  Ensure-InstallPaths
  Ensure-MariaDB
  Ensure-PythonDeps -ForcePip:$ForcePip
  Ensure-FrontendDeps
}

function Get-MysqlTool([string]$Name) {
  $cmd = Get-Command $Name -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $dist = Join-Path $RepoRoot "var\mariadb\dist"
  if (Test-Path $dist) {
    $hit = Get-ChildItem $dist -Recurse -Filter "$Name.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($hit) { return $hit.FullName }
  }
  throw "Missing $Name.exe. Run scripts\win\install.ps1 or add MariaDB client to PATH."
}

function Get-DatabaseUrlParts([string]$EnvPath) {
  $code = @'
from pathlib import Path
from urllib.parse import urlparse, unquote
import sys
url = ""
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    s = line.strip()
    if s.startswith("DATABASE_URL="):
        url = s.split("=", 1)[1].strip().strip('"').strip("'")
        break
url = url.replace("mysql+pymysql://", "mysql://", 1)
u = urlparse(url)
parts = [
    unquote(u.username or ""),
    unquote(u.password or ""),
    u.hostname or "127.0.0.1",
    str(u.port or 3306),
    (u.path or "").lstrip("/").split("?")[0],
]
print("\t".join(parts))
'@
  $spec = Get-ProvisionPython
  $raw = & $spec.File @($spec.Prefix + @("-c", $code, $EnvPath))
  if ($LASTEXITCODE -ne 0) { throw "Failed to parse DATABASE_URL" }
  $fields = ("$raw").Trim().Split("`t")
  if ($fields.Count -lt 5 -or -not $fields[4]) { throw "Cannot parse DATABASE_URL" }
  return @{
    User = $fields[0]
    Password = $fields[1]
    Host = $fields[2]
    Port = $fields[3]
    Name = $fields[4]
  }
}

function Start-Backend {
  if (-not (Test-Path $PythonExe)) {
    throw "Missing venv python: $PythonExe"
  }

  $listeners = Get-ListenerPids $BackendPort
  if ($listeners.Count -gt 0) {
    $existing = Read-PidFile $BackendPidFile
    Write-Host "[backend] already listening on ${BackendHost}:${BackendPort} (pids: $($listeners -join ', '); tracked=$existing)"
    return
  }

  Ensure-DevDir
  foreach ($f in @($BackendOutLog, $BackendErrLog)) {
    if (Test-Path $f) { Remove-Item $f -Force -ErrorAction SilentlyContinue }
  }

  $argList = @(
    "-m", "uvicorn", "app.main:app",
    "--reload",
    "--reload-dir", "app",
    "--host", $BackendHost,
    "--port", "$BackendPort"
  )

  $proc = Start-Process `
    -FilePath $PythonExe `
    -ArgumentList $argList `
    -WorkingDirectory $BackendDir `
    -PassThru `
    -WindowStyle Hidden `
    -RedirectStandardOutput $BackendOutLog `
    -RedirectStandardError $BackendErrLog

  Write-PidFile $BackendPidFile $proc.Id
  Write-Host "[backend] started pid=$($proc.Id) -> http://${BackendHost}:${BackendPort}"

  $ready = Wait-HttpReady -Url "http://${BackendHost}:${BackendPort}/health" -OkCodes @(200, 503) -TimeoutSeconds 60
  if (-not $ready.Ok) {
    throw "[backend] /health not ready within timeout (see $BackendErrLog)"
  }
  Write-Host "[backend] ready $($ready.Body)"
}

function Start-Frontend {
  $npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
  if (-not $npmCmd) { $npmCmd = Get-Command npm -ErrorAction SilentlyContinue }
  if (-not $npmCmd) { throw "npm not found in PATH" }

  $listeners = Get-ListenerPids $FrontendPort
  if ($listeners.Count -gt 0) {
    $existing = Read-PidFile $FrontendPidFile
    Write-Host "[frontend] already listening on ${FrontendHost}:${FrontendPort} (pids: $($listeners -join ', '); tracked=$existing)"
    return
  }

  Ensure-DevDir
  foreach ($f in @($FrontendOutLog, $FrontendErrLog)) {
    if (Test-Path $f) { Remove-Item $f -Force -ErrorAction SilentlyContinue }
  }

  $env:VITE_DEV_PORT = "$FrontendPort"
  $env:VITE_API_PROXY = "http://${BackendHost}:${BackendPort}"

  $proc = Start-Process `
    -FilePath $npmCmd.Source `
    -ArgumentList @("run", "dev") `
    -WorkingDirectory $FrontendDir `
    -PassThru `
    -WindowStyle Hidden `
    -RedirectStandardOutput $FrontendOutLog `
    -RedirectStandardError $FrontendErrLog

  Write-PidFile $FrontendPidFile $proc.Id
  Write-Host "[frontend] started pid=$($proc.Id) -> http://${FrontendHost}:${FrontendPort}"

  $ready = Wait-HttpReady -Url "http://${FrontendHost}:${FrontendPort}/" -OkCodes @(200) -TimeoutSeconds 45
  if (-not $ready.Ok) {
    throw "[frontend] not ready within timeout (see $FrontendErrLog)"
  }
  Write-Host "[frontend] ready"
}

function Show-Status {
  $backendPid = Read-PidFile $BackendPidFile
  $frontendPid = Read-PidFile $FrontendPidFile
  $backendListeners = Get-ListenerPids $BackendPort
  $frontendListeners = Get-ListenerPids $FrontendPort

  $backendHealth = "down"
  try {
    $r = Invoke-WebRequest -Uri "http://${BackendHost}:${BackendPort}/health" -TimeoutSec 2 -UseBasicParsing
    $backendHealth = "$($r.StatusCode) $($r.Content)"
  } catch {}

  $frontendHealth = "down"
  try {
    $r2 = Invoke-WebRequest -Uri "http://${FrontendHost}:${FrontendPort}/" -TimeoutSec 2 -UseBasicParsing
    $frontendHealth = "$($r2.StatusCode)"
  } catch {}

  Write-Host "backend"
  Write-Host "  tracked_pid : $(if ($backendPid) { $backendPid } else { '-' }) alive=$(if ($backendPid) { Test-PidAlive $backendPid } else { $false })"
  Write-Host "  listeners   : $(if ($backendListeners.Count) { $backendListeners -join ', ' } else { '-' })"
  Write-Host "  health      : $backendHealth"
  Write-Host "  logs        : $BackendOutLog | $BackendErrLog"
  Write-Host "frontend"
  Write-Host "  tracked_pid : $(if ($frontendPid) { $frontendPid } else { '-' }) alive=$(if ($frontendPid) { Test-PidAlive $frontendPid } else { $false })"
  Write-Host "  listeners   : $(if ($frontendListeners.Count) { $frontendListeners -join ', ' } else { '-' })"
  Write-Host "  http        : $frontendHealth"
  Write-Host "  logs        : $FrontendOutLog | $FrontendErrLog"
}

function Invoke-Stop {
  Stop-ServiceByPortAndPid -Name "backend" -Port $BackendPort -PidFile $BackendPidFile
  Stop-ServiceByPortAndPid -Name "frontend" -Port $FrontendPort -PidFile $FrontendPidFile
}

function Invoke-Start {
  Start-Backend
  Start-Frontend
  Show-Status
}

function Invoke-Restart {
  Invoke-Stop
  Invoke-Start
}
