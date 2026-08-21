#!/usr/bin/env bash
# 生产应急更新：应用已挂死、无法走管理端「系统更新」时使用。
# 用法（在 LXC / 主机上）：
#   curl -fsSL https://raw.githubusercontent.com/739790797/zhange-stats/main/scripts/emergency_update.sh | sudo bash
# 或指定版本：
#   sudo TARGET_VERSION=v0.2.38 bash emergency_update.sh
set -euo pipefail

REPO_SLUG="${UPDATE_GITHUB_REPO:-739790797/zhange-stats}"
INSTALL_DIR="${APP_INSTALL_DIR:-/opt/zhange-stats}"
SERVICE_NAME="${ZHANGE_SERVICE:-zhange-stats}"
SERVICE_USER="${ZHANGE_USER:-zhange}"
TARGET_VERSION="${TARGET_VERSION:-}"
# 设 SOURCE_REF=main 可在 Release 未出炉时直接拉主干源码（static 仍取最新 Release）
SOURCE_REF="${SOURCE_REF:-}"

log() { printf '[emergency-update] %s\n' "$*"; }
die() { printf '[emergency-update] ERROR: %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "缺少命令: $1"
}

need_cmd curl
need_cmd python3
need_cmd tar
need_cmd unzip

[[ -d "${INSTALL_DIR}" ]] || die "安装目录不存在: ${INSTALL_DIR}"
[[ -f "${INSTALL_DIR}/.env" ]] || die "缺少 ${INSTALL_DIR}/.env"
[[ -x "${INSTALL_DIR}/backend/.venv/bin/python" ]] || die "缺少 venv: ${INSTALL_DIR}/backend/.venv"

resolve_latest_release() {
  curl -fsSL "https://api.github.com/repos/${REPO_SLUG}/releases/latest" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])'
}

if [[ -n "${TARGET_VERSION}" ]]; then
  TAG="${TARGET_VERSION}"
  [[ "${TAG}" == v* ]] || TAG="v${TAG}"
  SOURCE_REF="${SOURCE_REF:-${TAG}}"
elif [[ -n "${SOURCE_REF}" ]]; then
  TAG="$(resolve_latest_release)"
else
  TAG="$(resolve_latest_release)"
  SOURCE_REF="${TAG}"
fi

VER="${TAG#v}"
log "源码 ${SOURCE_REF} / static ${TAG} → 安装根 ${INSTALL_DIR}"

TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

if [[ "${SOURCE_REF}" == v* ]] || [[ "${SOURCE_REF}" =~ ^[0-9]+\.[0-9]+ ]]; then
  REF_TAG="${SOURCE_REF}"
  [[ "${REF_TAG}" == v* ]] || REF_TAG="v${REF_TAG}"
  ZIP_URL="https://github.com/${REPO_SLUG}/archive/refs/tags/${REF_TAG}.zip"
else
  ZIP_URL="https://github.com/${REPO_SLUG}/archive/refs/heads/${SOURCE_REF}.zip"
fi
ASSET="zhange-stats-${VER}-static.tar.gz"
STATIC_URL="https://github.com/${REPO_SLUG}/releases/download/${TAG}/${ASSET}"

log "下载源码 zipball…"
curl -fL --retry 3 -o "${TMP}/src.zip" "${ZIP_URL}"
log "下载 static 资产…"
curl -fL --retry 3 -o "${TMP}/${ASSET}" "${STATIC_URL}"

log "解压源码…"
unzip -q "${TMP}/src.zip" -d "${TMP}/src"
SRC_ROOT="$(find "${TMP}/src" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
[[ -n "${SRC_ROOT}" ]] || die "zipball 无顶层目录"

# 与 app_updator.SOURCE_WHITELIST 对齐（整目录替换，避免残留坏迁移文件）
WHITELIST=(
  VERSION
  backend/app
  backend/alembic
  backend/requirements.txt
  backend/requirements-dev.txt
  backend/scripts
  scripts
  deploy
  AGENTS.md
  README.md
)

log "落盘白名单路径…"
for rel in "${WHITELIST[@]}"; do
  src="${SRC_ROOT}/${rel}"
  dest="${INSTALL_DIR}/${rel}"
  if [[ ! -e "${src}" ]]; then
    log "跳过缺失路径 ${rel}"
    continue
  fi
  if [[ -d "${src}" ]]; then
    rm -rf "${dest}"
    mkdir -p "$(dirname "${dest}")"
    cp -a "${src}" "${dest}"
  else
    mkdir -p "$(dirname "${dest}")"
    cp -a "${src}" "${dest}"
  fi
done

log "更新 static/…"
STATIC_DIR="${INSTALL_DIR}/static"
mkdir -p "${STATIC_DIR}"
find "${STATIC_DIR}" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
tar -xzf "${TMP}/${ASSET}" -C "${STATIC_DIR}"

log "pip install…"
"${INSTALL_DIR}/backend/.venv/bin/python" -m pip install -r "${INSTALL_DIR}/backend/requirements.txt"

if id -u "${SERVICE_USER}" >/dev/null 2>&1; then
  log "校正属主 ${SERVICE_USER}…"
  chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}" || true
fi

if [[ -d /run/systemd/system ]] && command -v systemctl >/dev/null 2>&1; then
  log "重启 ${SERVICE_NAME}…"
  systemctl restart "${SERVICE_NAME}"
  sleep 2
  systemctl --no-pager --full status "${SERVICE_NAME}" || true
  if curl -fsS "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
    log "健康检查通过: $(curl -fsS http://127.0.0.1:8000/health)"
  else
    log "WARN: /health 尚未就绪，请 journalctl -u ${SERVICE_NAME} -n 80 --no-pager"
  fi
else
  log "未检测到 systemd，请手动重启进程"
fi

log "完成 → VERSION=$(tr -d '[:space:]' < "${INSTALL_DIR}/VERSION")"
