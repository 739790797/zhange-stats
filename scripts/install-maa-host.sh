#!/usr/bin/env bash
# 在 Linux 宿主机（如 R730XD）一键启用 MAA 执行面：
#   - 安装并启用 binder systemd（开机自动）
#   - 写入 COMPOSE_PROFILES=maa（及可选 token）
#   - pull + up maa-worker
#
# 用法（仓库根目录）：
#   sudo bash scripts/install-maa-host.sh
#   sudo bash scripts/install-maa-host.sh --no-up   # 只装 binder / 改 .env
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

NO_UP=0
for arg in "$@"; do
  case "$arg" in
    --no-up) NO_UP=1 ;;
    -h|--help)
      echo "Usage: sudo bash scripts/install-maa-host.sh [--no-up]"
      exit 0
      ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请用 root 运行：sudo bash scripts/install-maa-host.sh" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "缺少 .env，请先按 README 配置 DATABASE_URL 等" >&2
  exit 1
fi

echo "==> 安装 binder 内核模块依赖（如可用）"
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y "linux-modules-extra-$(uname -r)" || \
    echo "警告: 未能安装 linux-modules-extra，若 modprobe 失败请手动处理" >&2
fi

echo "==> 安装 systemd 单元 maa-binder.service"
install -m 0644 deploy/systemd/maa-binder.service /etc/systemd/system/maa-binder.service
systemctl daemon-reload
systemctl enable --now maa-binder.service
if ! lsmod | grep -q '^binder_linux'; then
  echo "错误: binder_linux 未加载，Redroid 无法启动。请检查内核是否支持 binder。" >&2
  systemctl status maa-binder.service --no-pager || true
  exit 1
fi
echo "binder_linux 已加载"

ensure_env_line() {
  local key="$1"
  local value="$2"
  if grep -qE "^${key}=" .env; then
    # 已有则不覆盖（避免改掉用户显式配置）
    return 0
  fi
  printf '\n%s=%s\n' "$key" "$value" >> .env
  echo "已写入 .env: ${key}=${value}"
}

echo "==> 写入 .env（仅补缺，不覆盖已有项）"
ensure_env_line "COMPOSE_PROFILES" "maa"
# token 可留空：app/worker 会用 SECRET_KEY 派生；若既无 token 也无 SECRET_KEY 再生成显式值
if ! grep -qE '^MAA_WORKER_TOKEN=.+' .env && ! grep -qE '^SECRET_KEY=.+' .env; then
  tok="$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | xxd -p -c 64)"
  ensure_env_line "MAA_WORKER_TOKEN" "$tok"
fi
ensure_env_line "MAA_WORKER_IMAGE" "ghcr.io/739790797/zhange-stats-maa-worker"
ensure_env_line "MAA_WORKER_TAG" "latest"

if [[ "$NO_UP" -eq 1 ]]; then
  echo "已跳过 compose up（--no-up）。之后执行："
  echo "  docker compose -f compose.yml -f compose.maa.yml --profile maa pull"
  echo "  docker compose -f compose.yml -f compose.maa.yml --profile maa up -d"
  exit 0
fi

echo "==> 拉取并启动 maa-worker"
docker compose -f compose.yml -f compose.maa.yml --profile maa pull
docker compose -f compose.yml -f compose.maa.yml --profile maa up -d

echo
echo "完成。后续："
echo "  - 重启后 binder 由 systemd 自动加载"
echo "  - Watchtower 会自动更新 app 与 maa-worker 镜像"
echo "  - 管理端「设置 → MAA 资源」新增槽位即可自动供给 Android"
echo "详见 docs/maa-ops.md"
