#Requires -Version 5.1
<#
.SYNOPSIS
  Local frontend/backend lifecycle: start | stop | restart | status

.EXAMPLE
  .\scripts\dev.ps1 start
  .\scripts\dev.ps1 stop
  .\scripts\dev.ps1 restart
  .\scripts\dev.ps1 status
#>
param(
  [Parameter(Position = 0)]
  [ValidateSet("start", "stop", "restart", "status")]
  [string]$Command = "status"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$DevDir = Join-Path $RepoRoot ".dev"
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"

$BackendPort = 8000
$FrontendPort = 5173
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

switch ($Command) {
  "start" { Invoke-Start }
  "stop" { Invoke-Stop }
  "restart" {
    Invoke-Stop
    Invoke-Start
  }
  "status" { Show-Status }
}
