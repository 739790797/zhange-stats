#!/usr/bin/env bash
# 安装本机依赖（系统包、venv）。不写入 APP_ENV；不自动装 MariaDB。
# 生产机请在管理端「运行环境」或 config/app.json 设 APP_ENV=production。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ZHANGE_LOG_TAG="${ZHANGE_LOG_TAG:-install}"
export ZHANGE_FORCE_PIP=1
# shellcheck source=./_lib.sh
source "${SCRIPT_DIR}/_lib.sh"

if [[ "${EUID}" -ne 0 ]]; then
  die "请用 root 执行: sudo bash ${SCRIPT_DIR}/install.sh"
fi

log "仓库: ${REPO_ROOT}"
need_cmd apt-get
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip curl ca-certificates

if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
  useradd --system --home-dir "${REPO_ROOT}" --shell /usr/sbin/nologin "${SERVICE_USER}"
  log "已创建用户 ${SERVICE_USER}"
fi

if [[ -f "${SERVICE_SRC}" ]]; then
  write_systemd_unit
  log "未自动 start，请执行 scripts/linux/run.sh"
fi
if [[ -f "${SERVICE_SRC}" && -e "${REPO_ROOT}/deploy" ]]; then
  rm -rf "${REPO_ROOT}/deploy"
  log "已移除旧目录 deploy/"
fi

ensure_deps

chown -R "${SERVICE_USER}:${SERVICE_USER}" "${REPO_ROOT}"
chmod 750 "${REPO_ROOT}"
chmod 700 "${REPO_ROOT}/config" 2>/dev/null || true
chmod 700 "${DATA_DIR}" "${UPLOAD_DIR}"

chmod a+x "${SCRIPT_DIR}/install.sh" "${SCRIPT_DIR}/run.sh" "${SCRIPT_DIR}/restart.sh" \
  "${SCRIPT_DIR}/update.sh" "${SCRIPT_DIR}/backup.sh" "${SCRIPT_DIR}/restore.sh"

log "完成。打开站点走安装向导选库：bash ${SCRIPT_DIR}/run.sh"
