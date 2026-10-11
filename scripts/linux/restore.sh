#!/usr/bin/env bash
# 从 backup.sh 的 tar.gz 恢复：核对版本 → 停服务 → 可选导库 → 换 config/ 与 data/ → 修属主 → 启动
# 用法：ZHANGE_RESTORE_CONFIRM=YES ZHANGE_RESTORE_ARCHIVE=/path/zhange-*.tar.gz ./scripts/linux/restore.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ZHANGE_LOG_TAG="${ZHANGE_LOG_TAG:-restore}"
# shellcheck source=./_lib.sh
source "${SCRIPT_DIR}/_lib.sh"

ARCHIVE="${ZHANGE_RESTORE_ARCHIVE:-}"
BACKUP_UTIL="${REPO_ROOT}/scripts/common/backup_util.py"

[[ -n "${ARCHIVE}" && -f "${ARCHIVE}" ]] || die "设置 ZHANGE_RESTORE_ARCHIVE 为 backup.sh 产出的 tar.gz"
need_cmd python3

if [[ "${ZHANGE_RESTORE_CONFIRM:-}" != "YES" ]]; then
  die "将覆盖当前库与 data/、config/。确认后：ZHANGE_RESTORE_CONFIRM=YES ZHANGE_RESTORE_ARCHIVE=... $0"
fi

mkdir -p "${TMP_DIR}"
umask 077
WORKDIR="$(mktemp -d "${TMP_DIR}/zhange-restore.XXXXXX")"
trap 'rm -rf "${WORKDIR}"; fix_tree_owner' EXIT
python3 "${BACKUP_UTIL}" unpack --archive "${ARCHIVE}" --dest "${WORKDIR}"
python3 "${BACKUP_UTIL}" inspect --root "${REPO_ROOT}" --dir "${WORKDIR}"

log "停止应用"
stop_app

if ! python3 "${BACKUP_UTIL}" load-db --root "${REPO_ROOT}" --dir "${WORKDIR}"; then
  die "导库失败：config/ 与 data/ 未改动，应用保持停止；处理后重跑 restore"
fi

if [[ -d "${WORKDIR}/config" ]]; then
  log "恢复 config/"
  rm -rf "${REPO_ROOT}/config"
  cp -a "${WORKDIR}/config" "${REPO_ROOT}/config"
  chmod 700 "${REPO_ROOT}/config" 2>/dev/null || true
fi
if [[ -f "${WORKDIR}/.env" ]]; then
  cp -a "${WORKDIR}/.env" "${REPO_ROOT}/.env"
  chmod 600 "${REPO_ROOT}/.env"
fi

copy_tree() {
  local src="$1" dest="$2"
  if [[ -d "${src}" ]]; then
    mkdir -p "$(dirname "${dest}")"
    rm -rf "${dest}"
    cp -a "${src}" "${dest}"
  fi
}

mkdir -p "${REPO_ROOT}/data"
copy_tree "${WORKDIR}/data/runtime" "${REPO_ROOT}/data/runtime"
copy_tree "${WORKDIR}/data/uploads" "${REPO_ROOT}/data/uploads"
copy_tree "${WORKDIR}/data/models" "${REPO_ROOT}/data/models"
# 旧归档：var/data、var/uploads（权重仍在 runtime 里，启动时 migrate 会拆到 models/）
if [[ ! -d "${WORKDIR}/data/runtime" ]]; then
  copy_tree "${WORKDIR}/var/data" "${REPO_ROOT}/data/runtime"
fi
if [[ ! -d "${WORKDIR}/data/uploads" ]]; then
  copy_tree "${WORKDIR}/var/uploads" "${REPO_ROOT}/data/uploads"
fi
chmod 700 "${REPO_ROOT}/data/runtime" "${REPO_ROOT}/data/uploads" 2>/dev/null || true
fix_tree_owner

log "启动应用"
start_app
log "恢复完成。请登录验证。"
