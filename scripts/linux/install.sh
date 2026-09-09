#!/usr/bin/env bash
# 安装本机依赖（系统包、venv、MariaDB、.env 路径）。不写入 APP_ENV。
# 生产机请在本机 .env 自行设 APP_ENV=production。
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
  install -d -m 0755 /etc/systemd/system
  sed \
    -e "s|__REPO_ROOT__|${REPO_ROOT}|g" \
    -e "s|__SERVICE_USER__|${SERVICE_USER}|g" \
    "${SERVICE_SRC}" > "/etc/systemd/system/${SERVICE_NAME}"
  systemctl daemon-reload
  systemctl enable "${SERVICE_NAME}"
  log "已安装并 enable ${SERVICE_NAME}（未自动 start，请执行 scripts/linux/run.sh）"
fi

ensure_deps

chown -R "${SERVICE_USER}:${SERVICE_USER}" "${REPO_ROOT}"
chmod 750 "${REPO_ROOT}"
chmod 640 "${REPO_ROOT}/.env" 2>/dev/null || true
chmod 700 "${DATA_DIR}" "${UPLOAD_DIR}"

chmod a+x "${SCRIPT_DIR}/install.sh" "${SCRIPT_DIR}/run.sh" "${SCRIPT_DIR}/restart.sh" \
  "${SCRIPT_DIR}/backup.sh" "${SCRIPT_DIR}/restore.sh"

log "完成。编辑 .env 后: bash ${SCRIPT_DIR}/run.sh"
