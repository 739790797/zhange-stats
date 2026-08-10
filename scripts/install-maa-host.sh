#!/usr/bin/env bash
# 在 Linux 宿主机（如 R730XD）一键启用 MAA 执行面：
#   - 若缺 compose.maa.yml / systemd 单元：从当前 app 镜像导出到本目录
#   - 安装并启用 binder systemd（开机自动）
#   - 写入 COMPOSE_PROFILES=maa（及可选 token）
#   - pull + up maa-worker
#
# 用法（compose 工程目录，如 /opt/zhange-stats）：
#   # 首次若还没有本脚本，先从镜像导出：
#   docker run --rm -v "$PWD:/host" ghcr.io/739790797/zhange-stats:latest \
#     /bin/sh /app/maa-host/scripts/export-to-host.sh
#   sudo bash scripts/install-maa-host.sh
#
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

# 从 .env 读 APP_IMAGE / APP_TAG（若有）
_env_get() {
  local key="$1"
  local line
  line="$(grep -E "^${key}=" .env 2>/dev/null | tail -n1 || true)"
  if [[ -n "$line" ]]; then
    echo "${line#*=}"
  fi
}

sync_maa_host_files_from_image() {
  local need=0
  [[ -f compose.maa.yml ]] || need=1
  [[ -f deploy/systemd/maa-binder.service ]] || need=1
  if [[ "$need" -eq 0 ]]; then
    return 0
  fi

  local image_base tag image
  image_base="$(_env_get APP_IMAGE)"
  tag="$(_env_get APP_TAG)"
  image_base="${image_base:-ghcr.io/739790797/zhange-stats}"
  tag="${tag:-latest}"
  image="${image_base}:${tag}"

  echo "==> 本目录缺少 MAA 宿主机文件，从镜像导出: $image"
  if ! command -v docker >/dev/null 2>&1; then
    echo "错误: 需要 docker 才能从镜像导出 compose.maa.yml / scripts" >&2
    exit 1
  fi
  docker pull "$image" >/dev/null || true
  docker run --rm -v "$ROOT:/host" "$image" \
    /bin/sh /app/maa-host/scripts/export-to-host.sh /host
}

sync_maa_host_files_from_image

if [[ ! -f deploy/systemd/maa-binder.service ]]; then
  echo "错误: 仍缺少 deploy/systemd/maa-binder.service，请确认 app 镜像已含 /app/maa-host" >&2
  exit 1
fi
if [[ ! -f compose.maa.yml ]]; then
  echo "错误: 仍缺少 compose.maa.yml" >&2
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
echo "  - 以后若缺文件：docker compose --profile maa-export run --rm maa-host-export"
echo "详见 docs/maa-ops.md"
