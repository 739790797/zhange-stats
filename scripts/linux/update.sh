#!/usr/bin/env bash
# 从 GitHub Release 更新：白名单增删改、frontend 同步、static、pip、迁移，再重启。
# 不区分生产/开发。管理端无法更新时用本脚本；日常生产仍可用管理端一键更新。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ZHANGE_LOG_TAG="${ZHANGE_LOG_TAG:-update}"
# shellcheck source=./_lib.sh
source "${SCRIPT_DIR}/_lib.sh"

ensure_deps

CHECK=0
NO_RESTART=0
for arg in "$@"; do
  case "${arg}" in
    --check|-h|--help) CHECK=1 ;;
    --no-restart) NO_RESTART=1 ;;
  esac
done

set +e
"${VENV_PY}" "${REPO_ROOT}/scripts/common/update.py" "$@"
rc=$?
set -e

if [[ "${CHECK}" -eq 1 || "${NO_RESTART}" -eq 1 ]]; then
  exit "${rc}"
fi
if [[ "${rc}" -eq 2 ]]; then
  log "已是最新版本，未重启。"
  exit 0
fi
if [[ "${rc}" -ne 0 ]]; then
  exit "${rc}"
fi

if [[ "${EUID}" -eq 0 ]] && id -u "${SERVICE_USER}" >/dev/null 2>&1; then
  chown -R "${SERVICE_USER}:${SERVICE_USER}" "${REPO_ROOT}"
  chmod 700 "${REPO_ROOT}/config" 2>/dev/null || true
  chmod 700 "${DATA_DIR}" "${UPLOAD_DIR}" 2>/dev/null || true
fi

restart_app
log "更新完成并已重启。"
