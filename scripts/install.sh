#!/usr/bin/env bash
# Linux LXC / 裸机：首次安装战鸽（clone 后执行）。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"
VENV_DIR="${BACKEND_DIR}/.venv"
STATIC_DIR="${REPO_ROOT}/static"
DATA_DIR="${REPO_ROOT}/data"
UPLOAD_DIR="${REPO_ROOT}/uploads"
SERVICE_SRC="${REPO_ROOT}/deploy/systemd/zhange-stats.service"
SERVICE_NAME="zhange-stats.service"
SERVICE_USER="${ZHANGE_USER:-zhange}"

log() { printf '[install] %s\n' "$*"; }
die() { printf '[install] ERROR: %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "缺少命令: $1"
}

need_cmd python3
need_cmd curl

if [[ ! -f "${REPO_ROOT}/VERSION" ]]; then
  die "未找到 VERSION，请在仓库根目录执行"
fi

VERSION="$(tr -d '[:space:]' < "${REPO_ROOT}/VERSION")"
log "安装根: ${REPO_ROOT} (VERSION=${VERSION})"

mkdir -p "${DATA_DIR}" "${UPLOAD_DIR}" "${STATIC_DIR}"

if [[ ! -f "${REPO_ROOT}/.env" ]]; then
  if [[ -f "${REPO_ROOT}/.env.example" ]]; then
    cp "${REPO_ROOT}/.env.example" "${REPO_ROOT}/.env"
    log "已复制 .env.example → .env，请编辑 DATABASE_URL 等"
  else
    die "缺少 .env 与 .env.example"
  fi
fi

# 写入生产常用键（不覆盖已有值）
ensure_env() {
  local key="$1" value="$2"
  if grep -qE "^[[:space:]]*${key}=" "${REPO_ROOT}/.env" 2>/dev/null; then
    return 0
  fi
  printf '\n%s=%s\n' "${key}" "${value}" >> "${REPO_ROOT}/.env"
  log "已追加 ${key}=${value}"
}

ensure_env "APP_ENV" "production"
ensure_env "APP_INSTALL_DIR" "${REPO_ROOT}"
ensure_env "STATIC_DIR" "${STATIC_DIR}"
ensure_env "DATA_DIR" "${DATA_DIR}"
ensure_env "UPLOAD_DIR" "${UPLOAD_DIR}"

if [[ ! -d "${VENV_DIR}" ]]; then
  log "创建 venv..."
  python3 -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
pip install -U pip
pip install -r "${BACKEND_DIR}/requirements.txt"
deactivate

# 若本地已有 frontend/dist 则拷贝；否则尝试从 GitHub Release 拉 static
if [[ -d "${REPO_ROOT}/frontend/dist" ]] && [[ -f "${REPO_ROOT}/frontend/dist/index.html" ]]; then
  log "使用本地 frontend/dist → static/"
  rm -rf "${STATIC_DIR:?}/"*
  cp -a "${REPO_ROOT}/frontend/dist/." "${STATIC_DIR}/"
elif command -v tar >/dev/null 2>&1; then
  REPO_SLUG="${UPDATE_GITHUB_REPO:-739790797/zhange-stats}"
  ASSET="zhange-stats-${VERSION}-static.tar.gz"
  URL="https://github.com/${REPO_SLUG}/releases/download/v${VERSION}/${ASSET}"
  TMP="$(mktemp -d)"
  log "下载预构建 static: ${URL}"
  if curl -fL --retry 3 -o "${TMP}/${ASSET}" "${URL}"; then
    rm -rf "${STATIC_DIR:?}/"*
    tar -xzf "${TMP}/${ASSET}" -C "${STATIC_DIR}"
    log "static 已解压到 ${STATIC_DIR}"
  else
    log "WARN: 无法下载 ${ASSET}。可稍后 npm run build 后拷贝到 static/，或运行 scripts/update.sh"
  fi
  rm -rf "${TMP}"
fi

ensure_service_user() {
  if id -u "${SERVICE_USER}" >/dev/null 2>&1; then
    return 0
  fi
  if command -v useradd >/dev/null 2>&1; then
    useradd --system --home "${REPO_ROOT}" --shell /usr/sbin/nologin "${SERVICE_USER}" \
      || useradd --system --home "${REPO_ROOT}" --shell /bin/false "${SERVICE_USER}"
    log "已创建系统用户 ${SERVICE_USER}"
  else
    die "无法创建用户 ${SERVICE_USER}（缺少 useradd）"
  fi
}

if [[ -d /run/systemd/system ]] && command -v systemctl >/dev/null 2>&1; then
  log "检测到 systemd，安装 ${SERVICE_NAME}（User=${SERVICE_USER}）"
  UNIT_TMP="$(mktemp)"
  sed \
    -e "s|/opt/zhange-stats|${REPO_ROOT}|g" \
    -e "s|^User=zhange|User=${SERVICE_USER}|g" \
    -e "s|^Group=zhange|Group=${SERVICE_USER}|g" \
    "${SERVICE_SRC}" > "${UNIT_TMP}"
  if [[ "$(id -u)" -eq 0 ]]; then
    ensure_service_user
    chown -R "${SERVICE_USER}:${SERVICE_USER}" \
      "${REPO_ROOT}/data" "${REPO_ROOT}/uploads" "${REPO_ROOT}/static" \
      "${REPO_ROOT}/backend/.venv" || true
    # 代码树需可读；更新时服务用户要能写白名单路径
    chown -R "${SERVICE_USER}:${SERVICE_USER}" "${REPO_ROOT}"
    install -m 644 "${UNIT_TMP}" "/etc/systemd/system/${SERVICE_NAME}"
    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}"
    rm -f "${UNIT_TMP}"
    log "已 enable ${SERVICE_NAME}。编辑 .env 后: systemctl start ${SERVICE_NAME}"
    log "一键更新默认用进程内 exec（无需 systemctl 权限）；勿依赖 APP_RESTART_CMD=systemctl 除非已配 sudoers"
  else
    log "非 root：请手动创建用户并安装 unit："
    log "  sudo useradd --system --home ${REPO_ROOT} --shell /usr/sbin/nologin ${SERVICE_USER}"
    log "  sudo chown -R ${SERVICE_USER}:${SERVICE_USER} ${REPO_ROOT}"
    log "  sudo install -m 644 ${UNIT_TMP} /etc/systemd/system/${SERVICE_NAME}"
    log "  sudo systemctl daemon-reload && sudo systemctl enable --now ${SERVICE_NAME}"
  fi
else
  log "未检测到 systemd。可用："
  log "  cd ${BACKEND_DIR} && ${VENV_DIR}/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000"
  log "一键更新将使用进程内 exec 重启。"
fi

log "完成。浏览器打开站点走安装向导；管理端 → 系统更新 可一键升级。"
