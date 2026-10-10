#!/usr/bin/env bash
# 从 GitHub Release 更新：校验 sha256 → 暂存 → pip → 白名单增删改、frontend 同步 → 迁移 → 切换 static，再重启。
# 不区分生产/开发。管理端无法更新时用本脚本；日常生产仍可用管理端一键更新。
# --static-only：只补当前 VERSION 的预构建前端（全新安装用；不改代码、不重启）。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ZHANGE_LOG_TAG="${ZHANGE_LOG_TAG:-update}"
# shellcheck source=./_lib.sh
source "${SCRIPT_DIR}/_lib.sh"

trap fix_tree_owner EXIT
ensure_deps

CHECK=0
NO_RESTART=0
for arg in "$@"; do
  case "${arg}" in
    --check|-h|--help) CHECK=1 ;;
    --no-restart|--static-only) NO_RESTART=1 ;;
  esac
done

set +e
as_service_user "${VENV_PY}" "${REPO_ROOT}/scripts/common/update.py" "$@"
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

if [[ "${EUID}" -eq 0 ]]; then
  write_systemd_unit
  fix_tree_owner
  chmod 700 "${REPO_ROOT}/config" 2>/dev/null || true
  chmod 700 "${DATA_DIR}" "${UPLOAD_DIR}" 2>/dev/null || true
else
  log "WARN: 非 root，未刷新 systemd 单元；请 sudo bash scripts/linux/install.sh 后 restart"
fi

restart_app
log "更新完成并已重启。"
