#!/usr/bin/env bash
# Linux：手工自更新（与管理端一键更新同源逻辑：backend/scripts/self_update.py）
# 成功后默认 systemctl restart（SSH/root 场景）；管理端一键更新仍走进程内 exec。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"
PY="${BACKEND_DIR}/.venv/bin/python"
SERVICE_NAME="${ZHANGE_SERVICE_NAME:-zhange-stats.service}"

VERSION_ARG="latest"
PROXY_ARG=""
NO_REBOOT=0

usage() {
  cat <<EOF
用法: bash scripts/update.sh [版本] [代理URL] [--no-reboot]

  版本       latest（默认）或 vX.Y.Z
  代理URL    可选，GitHub API/下载前缀
  --no-reboot  只落盘/装依赖，不重启服务

环境变量:
  ZHANGE_SERVICE_NAME  systemd unit 名（默认 zhange-stats.service）
  ZHANGE_SERVICE_USER  更新后 chown 目标用户（默认取 unit 的 User，否则 zhange）
  UPDATE_NO_REBOOT=1   同 --no-reboot
EOF
}

POSITIONAL=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --no-reboot)
      NO_REBOOT=1
      shift
      ;;
    --proxy)
      PROXY_ARG="${2:-}"
      if [[ -z "${PROXY_ARG}" ]]; then
        echo "[update] --proxy 需要参数" >&2
        exit 1
      fi
      shift 2
      ;;
    -*)
      echo "[update] 未知选项: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

if [[ ${#POSITIONAL[@]} -ge 1 ]]; then
  VERSION_ARG="${POSITIONAL[0]}"
fi
if [[ ${#POSITIONAL[@]} -ge 2 ]]; then
  PROXY_ARG="${POSITIONAL[1]}"
fi
if [[ "${UPDATE_NO_REBOOT:-0}" == "1" ]]; then
  NO_REBOOT=1
fi

if [[ ! -x "${PY}" ]]; then
  echo "[update] 缺少 ${PY}，请先运行 scripts/install.sh" >&2
  exit 1
fi

export APP_INSTALL_DIR="${APP_INSTALL_DIR:-${REPO_ROOT}}"
export APP_ENV="${APP_ENV:-production}"

cd "${BACKEND_DIR}"
ARGS=(scripts/self_update.py --version "${VERSION_ARG}" --no-reboot)
if [[ -n "${PROXY_ARG}" ]]; then
  ARGS+=(--proxy "${PROXY_ARG}")
fi

"${PY}" "${ARGS[@]}"

# root 跑更新会把白名单文件写成 root 属主，管理端（zhange）随后无法覆盖 → 一键更新失败
ensure_service_ownership() {
  if [[ "$(id -u)" -ne 0 ]]; then
    return 0
  fi
  local unit_user=""
  if command -v systemctl >/dev/null 2>&1 && systemctl cat "${SERVICE_NAME}" >/dev/null 2>&1; then
    unit_user="$(systemctl show -p User --value "${SERVICE_NAME}" 2>/dev/null || true)"
  fi
  local owner="${ZHANGE_SERVICE_USER:-${unit_user:-zhange}}"
  if ! id -u "${owner}" >/dev/null 2>&1; then
    echo "[update] 警告：用户 ${owner} 不存在，跳过 chown" >&2
    return 0
  fi
  echo "[update] 校正属主为 ${owner}（避免 WEB 一键更新无写权限）…"
  local paths=(
    "${REPO_ROOT}/VERSION"
    "${REPO_ROOT}/AGENTS.md"
    "${REPO_ROOT}/README.md"
    "${REPO_ROOT}/backend/app"
    "${REPO_ROOT}/backend/alembic"
    "${REPO_ROOT}/backend/requirements.txt"
    "${REPO_ROOT}/backend/requirements-dev.txt"
    "${REPO_ROOT}/backend/scripts"
    "${REPO_ROOT}/scripts"
    "${REPO_ROOT}/deploy"
    "${REPO_ROOT}/static"
    "${REPO_ROOT}/data/update-tmp"
    "${REPO_ROOT}/data/update.lock"
  )
  local p
  for p in "${paths[@]}"; do
    if [[ -e "${p}" ]]; then
      chown -R "${owner}:${owner}" "${p}" || true
    fi
  done
  if [[ -d "${REPO_ROOT}/data" ]]; then
    chown "${owner}:${owner}" "${REPO_ROOT}/data" || true
  fi
}

ensure_service_ownership

if [[ "${NO_REBOOT}" -eq 1 ]]; then
  echo "[update] 已跳过重启（--no-reboot / UPDATE_NO_REBOOT=1）"
  exit 0
fi

restart_with_systemctl() {
  local unit="$1"
  if [[ "$(id -u)" -eq 0 ]]; then
    systemctl restart "${unit}"
    return
  fi
  if command -v sudo >/dev/null 2>&1; then
    sudo systemctl restart "${unit}"
    return
  fi
  return 1
}

if [[ -d /run/systemd/system ]] && command -v systemctl >/dev/null 2>&1; then
  if systemctl cat "${SERVICE_NAME}" >/dev/null 2>&1; then
    echo "[update] 重启 ${SERVICE_NAME}…"
    if ! restart_with_systemctl "${SERVICE_NAME}"; then
      echo "[update] 无权限重启，请手动执行: sudo systemctl restart ${SERVICE_NAME}" >&2
      exit 1
    fi
    # 给 uvicorn 一点启动时间再查状态
    sleep 1
    systemctl --no-pager --full status "${SERVICE_NAME}" || true
    echo "[update] 完成（请确认 /health 版本已刷新）"
  else
    echo "[update] 未找到 unit ${SERVICE_NAME}，代码已更新，请手动重启进程" >&2
    exit 1
  fi
else
  echo "[update] 未检测到 systemd，代码已更新，请手动重启 uvicorn" >&2
  exit 1
fi
