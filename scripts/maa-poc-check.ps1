# PoC：在已启用 compose.maa profile 的机器上快速检查网络与 poc 容器。
# 用法（宿主机）：powershell -File scripts/maa-poc-check.ps1

$ErrorActionPreference = "Stop"
Write-Host "== docker networks =="
docker network ls | Select-String "maa"
Write-Host "== redroid-poc =="
docker ps -a --filter "label=zhange.maa.poc=1"
Write-Host "== maa-worker =="
docker ps -a --filter "name=maa-worker"
Write-Host "详见 docs/maa-ops.md"
