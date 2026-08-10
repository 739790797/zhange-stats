# 可选：为 Windows WSL2 安装带 binder 的自定义内核，以便本机跑 Redroid。
# 风险：可能影响 Docker Desktop / 其他 WSL 发行版。生产请用 Linux（R730XD）。
# 用法（管理员 PowerShell）：
#   powershell -ExecutionPolicy Bypass -File .\scripts\maa-wsl-binder-kernel.ps1
# 启用后需：wsl --shutdown → 重启 Docker Desktop → 再测 binder。
# 若 Docker 起不来：删掉或改名 %USERPROFILE%\.wslconfig 后 wsl --shutdown。

$ErrorActionPreference = "Stop"
$kernelDir = Join-Path $env:USERPROFILE ".zhange-maa\wsl-kernel"
$kernelPath = Join-Path $kernelDir "wsl2-kernel-redroid-natfix"
$url = "https://github.com/akwin1234/damru-wsl2-kernel-redroid-natfix-source/releases/download/v6.6.114.1-damru-redroid-natfix-20260602/wsl2-kernel-redroid-natfix-20260602"
$expectSha = "1c2a5c2c4737a02b8f81dcd82162727cb5644d194bb9cfb2f9162a9862b03c6e"

Write-Host "WARNING: Custom WSL kernel may break Docker Desktop. Prefer Linux host for MAA." -ForegroundColor Yellow
$confirm = Read-Host "Type YES to continue"
if ($confirm -ne "YES") { throw "aborted" }

New-Item -ItemType Directory -Force -Path $kernelDir | Out-Null
if (-not (Test-Path $kernelPath) -or ((Get-FileHash $kernelPath -Algorithm SHA256).Hash.ToLower() -ne $expectSha)) {
  Write-Host "Downloading kernel..."
  curl.exe -L --fail --retry 3 -o $kernelPath $url
  $sha = (Get-FileHash $kernelPath -Algorithm SHA256).Hash.ToLower()
  if ($sha -ne $expectSha) { throw "sha mismatch: $sha" }
}

$wslConfig = Join-Path $env:USERPROFILE ".wslconfig"
$backup = Join-Path $env:USERPROFILE (".wslconfig.bak-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
if (Test-Path $wslConfig) { Copy-Item $wslConfig $backup -Force }

$kernelEsc = $kernelPath -replace "\\", "\\"
@"
[wsl2]
kernel=$kernelEsc
"@ | Set-Content -Path $wslConfig -Encoding ASCII

Write-Host "Wrote $wslConfig"
Write-Host "Next: wsl --shutdown ; restart Docker Desktop ; then check binderfs."
Write-Host "Rollback: remove/rename .wslconfig and wsl --shutdown"
