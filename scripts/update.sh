#!/usr/bin/env bash
# Linux：手工自更新（与管理端一键更新同源逻辑：backend/scripts/self_update.py）
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"
PY="${BACKEND_DIR}/.venv/bin/python"

VERSION_ARG="${1:-latest}"
PROXY_ARG="${2:-}"

if [[ ! -x "${PY}" ]]; then
  echo "[update] 缺少 ${PY}，请先运行 scripts/install.sh" >&2
  exit 1
fi

export APP_INSTALL_DIR="${APP_INSTALL_DIR:-${REPO_ROOT}}"
export APP_ENV="${APP_ENV:-production}"

cd "${BACKEND_DIR}"
ARGS=(scripts/self_update.py --version "${VERSION_ARG}")
if [[ -n "${PROXY_ARG}" ]]; then
  ARGS+=(--proxy "${PROXY_ARG}")
fi
exec "${PY}" "${ARGS[@]}"
