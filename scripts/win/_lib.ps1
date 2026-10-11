#Requires -Version 5.1
# Shared by the scripts/win/*.ps1 entry points. Not a public command.

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$DevDir = Join-Path $RepoRoot "data\run"
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"
$VenvDir = Join-Path $BackendDir ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$PipStamp = Join-Path $VenvDir ".zhange-req.stamp"
$StaticDir = Join-Path $RepoRoot "static"
$DataDir = Join-Path $RepoRoot "data\runtime"
$UploadDir = Join-Path $RepoRoot "data\uploads"
$ModelsDir = Join-Path $RepoRoot "data\models"
$CacheDir = Join-Path $RepoRoot "data\cache"
$TmpDir = Join-Path $RepoRoot "data\tmp"
$env:PYTHONPYCACHEPREFIX = Join-Path $CacheDir "pycache"
$env:HF_HOME = Join-Path $CacheDir "huggingface"
$env:TORCH_HOME = Join-Path $CacheDir "torch"
$env:EASYOCR_MODULE_PATH = Join-Path $CacheDir "easyocr"
$env:PIP_CACHE_DIR = Join-Path $CacheDir "pip"
$env:XDG_CACHE_HOME = Join-Path $CacheDir "xdg"
$env:TEMP = $TmpDir
$env:TMP = $TmpDir
$env:TMPDIR = $TmpDir
$env:npm_config_cache = Join-Path $CacheDir "npm"

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

function Ensure-InstallPaths {
  $configDir = Join-Path $RepoRoot "config"
  New-Item -ItemType Directory -Force -Path $DataDir, $UploadDir, $ModelsDir, $StaticDir, $DevDir, (Join-Path $RepoRoot "data\backups"), $CacheDir, $TmpDir, $env:PYTHONPYCACHEPREFIX, $env:HF_HOME, $env:TORCH_HOME, $env:PIP_CACHE_DIR, $configDir | Out-Null
}

# Same format as app_updator.requirements_stamp (sha256sum output): the admin updater and the scripts share one stamp.
function Get-RequirementsStamp {
  $lines = @()
  foreach ($name in @("requirements.txt", "constraints.txt")) {
    $path = Join-Path $BackendDir $name
    if (Test-Path $path) {
      $hash = (Get-FileHash -Algorithm SHA256 -Path $path).Hash.ToLowerInvariant()
      $lines += "$hash  $name"
    }
  }
  return $lines
}

function Test-PipStamp {
  if (-not (Test-Path $PipStamp)) { return $false }
  $want = @(Get-RequirementsStamp) -join " "
  $have = Get-Content -Path $PipStamp -Raw -ErrorAction SilentlyContinue
  if (-not $want.Trim() -or -not $have) { return $false }
  $wantWords = @($want -split '\s+' | Where-Object { $_ }) -join " "
  $haveWords = @("$have" -split '\s+' | Where-Object { $_ }) -join " "
  return ($wantWords -eq $haveWords)
}

function Write-PipStamp {
  try {
    Set-Content -Path $PipStamp -Value @(Get-RequirementsStamp) -Encoding ascii
  } catch {
    Write-Host "[pip] WARN: could not write $PipStamp"
  }
}

function Test-PipOutdated {
  $raw = & $PythonExe -m pip --version
  if ($LASTEXITCODE -ne 0 -or -not $raw) { return $true }
  if ("$raw" -match '^pip (\d+)\.') { return ([int]$Matches[1] -lt 23) }
  return $true
}

function Install-PythonDeps {
  $req = Join-Path $BackendDir "requirements.txt"
  if (-not (Test-Path $req)) {
    throw "Missing $req"
  }
  $lock = Join-Path $BackendDir "constraints.txt"
  $lockArgs = @()
  if (Test-Path $lock) { $lockArgs = @("-c", $lock) }
  New-Item -ItemType Directory -Force -Path $TmpDir | Out-Null
  Write-Host "[pip] installing CPU torch + requirements..."
  if (Test-PipOutdated) {
    & $PythonExe -m pip install -U pip
    if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
  }
  & $PythonExe -m pip install torch torchvision --index-url "https://download.pytorch.org/whl/cpu"
  if ($LASTEXITCODE -ne 0) { throw "CPU torch install failed" }
  $constraint = Join-Path $TmpDir ("zhange-torch-" + [guid]::NewGuid().ToString() + ".txt")
  try {
    $pinned = & $PythonExe -m pip freeze | Select-String -Pattern '^(torch|torchvision)=='
    $pinned | ForEach-Object { $_.Line } | Set-Content -Path $constraint -Encoding ascii
    if ((Get-Item $constraint).Length -gt 0) {
      & $PythonExe -m pip install -r $req -c $constraint @lockArgs
    } else {
      & $PythonExe -m pip install -r $req @lockArgs
    }
    if ($LASTEXITCODE -ne 0) { throw "pip install -r requirements.txt failed" }
  } finally {
    Remove-Item $constraint -ErrorAction SilentlyContinue
  }
  & $PythonExe -m pip uninstall -y opencv-python | Out-Null
  & $PythonExe -m pip install -q --force-reinstall --no-deps "opencv-python-headless>=4.8.0" @lockArgs
  if ($LASTEXITCODE -ne 0) { throw "opencv-python-headless install failed" }
}

function Ensure-Venv {
  if (Test-Path $PythonExe) {
    & $PythonExe -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
    if ($LASTEXITCODE -ne 0) {
      throw "backend\.venv is broken or older than Python 3.11: delete backend\.venv and re-run install.ps1 with Python 3.11+"
    }
    return
  }
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
  $force = [bool]$ForcePip -or ($env:ZHANGE_FORCE_PIP -eq "1")
  if (-not $force -and (Test-PipStamp)) { return }
  Install-PythonDeps
  Write-PipStamp
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
    & $npmCmd.Source ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
  } finally {
    Pop-Location
  }
}

function Sync-SiteConfig {
  if (-not (Test-Path $PythonExe)) { return }
  Push-Location $BackendDir
  try {
    & $PythonExe -m app.core.config_sync
    if ($LASTEXITCODE -ne 0) {
      Write-Host "[config] WARN: site config sync failed"
    }
  } finally {
    Pop-Location
  }
}

function Ensure-ZhangeDeps {
  param([switch]$ForcePip)
  if (-not (Test-Path (Join-Path $RepoRoot "VERSION"))) {
    throw "VERSION not found; not an install root"
  }
  Ensure-InstallPaths
  Ensure-PythonDeps -ForcePip:$ForcePip
  Ensure-FrontendDeps
  Sync-SiteConfig
}

# A git clone has no static/: fetch the checksum-verified prebuilt static of the local VERSION.
# Not fatal: the dev stack (run.ps1) serves the frontend through Vite; static/ is only served when STATIC_DIR is set.
function Ensure-StaticAssets {
  if (Test-Path (Join-Path $StaticDir "index.html")) { return }
  if (-not (Test-Path $PythonExe)) { return }
  Write-Host "[static] static\ has no frontend; fetching the prebuilt static of the local VERSION..."
  & $PythonExe (Join-Path $RepoRoot "scripts\common\update.py") --static-only
  if ($LASTEXITCODE -ne 0) {
    Write-Host "[static] WARN: prebuilt static not installed (options above). run.ps1 still works through Vite."
  }
}

# The app writes a one-time token to data\runtime\setup-token until the setup wizard is done;
# with no database chosen yet it is created on the first wizard request.
function Show-SetupToken {
  $tokenFile = Join-Path $DataDir "setup-token"
  if (-not (Test-Path (Join-Path $RepoRoot "config\database.json")) -and -not (Test-Path $tokenFile)) {
    Wait-HttpReady -Url "http://${BackendHost}:${BackendPort}/api/setup/status" -OkCodes @(200) -TimeoutSeconds 30 | Out-Null
  }
  if (-not (Test-Path $tokenFile)) { return }
  $token = "$(Get-Content -Path $tokenFile -Raw -ErrorAction SilentlyContinue)".Trim()
  if ($token) {
    Write-Host "[setup] install token: $token"
  } else {
    Write-Host "[setup] install token file: $tokenFile"
  }
  Write-Host "[setup] Enter it in the setup wizard in the browser; it is deleted once setup completes."
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
    "--port", "$BackendPort",
    "--ws-max-size", "4194304"
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
