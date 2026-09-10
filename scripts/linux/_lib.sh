#!/usr/bin/env bash
# Shared by linux/install.sh, run.sh, restart.sh, update.sh. Not a public command.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"
VENV_DIR="${BACKEND_DIR}/.venv"
VENV_PY="${VENV_DIR}/bin/python"
STATIC_DIR="${REPO_ROOT}/static"
SERVICE_SRC="${SCRIPT_DIR}/zhange-stats.service"
SERVICE_NAME="${ZHANGE_SERVICE:-zhange-stats.service}"
SERVICE_USER="${ZHANGE_USER:-zhange}"
DEV_DIR="${REPO_ROOT}/data/run"
BACKEND_PORT="${ZHANGE_BACKEND_PORT:-6130}"
FRONTEND_PORT="${ZHANGE_FRONTEND_PORT:-6131}"
PIP_STAMP="${VENV_DIR}/.zhange-req.stamp"
ZHANGE_LOG_TAG="${ZHANGE_LOG_TAG:-zhange}"

DATA_DIR="${REPO_ROOT}/data/runtime"
UPLOAD_DIR="${REPO_ROOT}/data/uploads"
MODELS_DIR="${REPO_ROOT}/data/models"
CACHE_DIR="${REPO_ROOT}/data/cache"
TMP_DIR="${REPO_ROOT}/data/tmp"

export PYTHONPYCACHEPREFIX="${CACHE_DIR}/pycache"
export HF_HOME="${CACHE_DIR}/huggingface"
export TORCH_HOME="${CACHE_DIR}/torch"
export EASYOCR_MODULE_PATH="${CACHE_DIR}/easyocr"
export PIP_CACHE_DIR="${CACHE_DIR}/pip"
export XDG_CACHE_HOME="${CACHE_DIR}/xdg"
export TMPDIR="${TMP_DIR}"
export npm_config_cache="${CACHE_DIR}/npm"

log() { printf '[%s] %s\n' "${ZHANGE_LOG_TAG}" "$*"; }
die() { printf '[%s] ERROR: %s\n' "${ZHANGE_LOG_TAG}" "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "缺少命令: $1"
}

ensure_runtime_dirs() {
  mkdir -p "${DATA_DIR}" "${UPLOAD_DIR}" "${MODELS_DIR}" "${STATIC_DIR}" "${DEV_DIR}" \
    "${REPO_ROOT}/data/backups" "${CACHE_DIR}" "${TMP_DIR}" \
    "${PYTHONPYCACHEPREFIX}" "${HF_HOME}" "${TORCH_HOME}" "${PIP_CACHE_DIR}" \
    "${REPO_ROOT}/config"
  chmod 700 "${REPO_ROOT}/config" 2>/dev/null || true
}

sync_site_config() {
  [[ -x "${VENV_PY}" ]] || return 0
  if ! (cd "${BACKEND_DIR}" && "${VENV_PY}" -m app.core.config_sync); then
    log "WARN: 站点配置同步失败"
  fi
}

ensure_venv() {
  if [[ -x "${VENV_PY}" ]]; then
    return 0
  fi
  log "创建 venv…"
  python3 -m venv "${VENV_DIR}"
}

pip_install_backend() {
  local python="$1"
  local req="${BACKEND_DIR}/requirements.txt"
  local index="https://download.pytorch.org/whl/cpu"
  local constraint
  [[ -f "${req}" ]] || die "缺少 ${req}"
  "${python}" -m pip install -U pip
  "${python}" -m pip install torch torchvision --index-url "${index}"
  mkdir -p "${TMP_DIR}"
  constraint="$(mktemp "${TMP_DIR}/zhange-torch.XXXXXX")"
  "${python}" -m pip freeze | grep -E '^(torch|torchvision)==' > "${constraint}" || true
  if [[ -s "${constraint}" ]]; then
    "${python}" -m pip install -r "${req}" -c "${constraint}"
  else
    "${python}" -m pip install -r "${req}"
  fi
  rm -f "${constraint}"
  "${python}" -m pip uninstall -y opencv-python >/dev/null 2>&1 || true
  "${python}" -m pip install -q --force-reinstall --no-deps "opencv-python-headless>=4.8.0"
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "${PIP_STAMP}"
}

ensure_python_deps() {
  ensure_venv
  local force="${ZHANGE_FORCE_PIP:-0}"
  local req="${BACKEND_DIR}/requirements.txt"
  if [[ "${force}" != "1" && -f "${PIP_STAMP}" && -f "${req}" && ! "${req}" -nt "${PIP_STAMP}" ]]; then
    return 0
  fi
  log "安装 Python 依赖（CPU torch）…"
  pip_install_backend "${VENV_PY}"
}

ensure_frontend_deps() {
  [[ -f "${REPO_ROOT}/frontend/package.json" ]] || return 0
  if [[ -d "${REPO_ROOT}/frontend/node_modules" ]]; then
    return 0
  fi
  command -v npm >/dev/null 2>&1 || return 0
  log "安装前端依赖…"
  (cd "${REPO_ROOT}/frontend" && npm install --legacy-peer-deps)
}

has_systemd_unit() {
  [[ -d /run/systemd/system ]] && command -v systemctl >/dev/null 2>&1 \
    && systemctl cat "${SERVICE_NAME}" >/dev/null 2>&1
}

write_systemd_unit() {
  [[ -f "${SERVICE_SRC}" ]] || return 0
  install -d -m 0755 /etc/systemd/system
  sed \
    -e "s|__REPO_ROOT__|${REPO_ROOT}|g" \
    -e "s|__SERVICE_USER__|${SERVICE_USER}|g" \
    "${SERVICE_SRC}" > "/etc/systemd/system/${SERVICE_NAME}"
  if command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]; then
    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}"
    log "已写入并 enable /etc/systemd/system/${SERVICE_NAME}"
  else
    log "已写入 /etc/systemd/system/${SERVICE_NAME}（当前无 systemd，未 enable）"
  fi
}

ensure_deps() {
  [[ -f "${REPO_ROOT}/VERSION" ]] || die "未找到 VERSION"
  need_cmd python3
  ensure_runtime_dirs
  ensure_python_deps
  sync_site_config
  if ! has_systemd_unit; then
    ensure_frontend_deps
  fi
}

wait_http() {
  local url="$1"
  local n="${2:-45}"
  local i
  for ((i = 0; i < n; i++)); do
    if python3 -c 'import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=2)' "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

stop_pidfile() {
  local name="$1" pidfile="$2" port="$3"
  local pid=""
  if [[ -f "${pidfile}" ]]; then
    pid="$(tr -d '[:space:]' < "${pidfile}" || true)"
  fi
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    log "停止 ${name} pid=${pid}"
    kill "${pid}" 2>/dev/null || true
    sleep 1
    kill -9 "${pid}" 2>/dev/null || true
  fi
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" >/dev/null 2>&1 || true
  fi
  rm -f "${pidfile}"
}

start_dev_stack() {
  local py="${VENV_PY}"
  mkdir -p "${DEV_DIR}"
  if ! python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', ${BACKEND_PORT}))" 2>/dev/null; then
    log "backend 已在 :${BACKEND_PORT}"
  else
    log "启动 backend :${BACKEND_PORT}"
    (
      cd "${BACKEND_DIR}"
      nohup "${py}" -m uvicorn app.main:app --reload --reload-dir app \
        --host 127.0.0.1 --port "${BACKEND_PORT}" \
        >>"${DEV_DIR}/backend.out.log" 2>>"${DEV_DIR}/backend.err.log" &
      echo $! >"${DEV_DIR}/backend.pid"
    )
    wait_http "http://127.0.0.1:${BACKEND_PORT}/health" 60 || die "backend /health 未就绪（见 ${DEV_DIR}/backend.err.log）"
  fi
  if [[ -f "${REPO_ROOT}/frontend/package.json" ]] && command -v npm >/dev/null 2>&1; then
    if ! python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', ${FRONTEND_PORT}))" 2>/dev/null; then
      log "frontend 已在 :${FRONTEND_PORT}"
    else
      log "启动 frontend :${FRONTEND_PORT}"
      (
        cd "${REPO_ROOT}/frontend"
        export VITE_DEV_PORT="${FRONTEND_PORT}"
        export VITE_API_PROXY="http://127.0.0.1:${BACKEND_PORT}"
        nohup npm run dev >>"${DEV_DIR}/frontend.out.log" 2>>"${DEV_DIR}/frontend.err.log" &
        echo $! >"${DEV_DIR}/frontend.pid"
      )
      wait_http "http://127.0.0.1:${FRONTEND_PORT}/" 45 || log "WARN: frontend 未在超时内就绪"
    fi
  fi
}

stop_dev_stack() {
  stop_pidfile "frontend" "${DEV_DIR}/frontend.pid" "${FRONTEND_PORT}"
  stop_pidfile "backend" "${DEV_DIR}/backend.pid" "${BACKEND_PORT}"
}

start_app() {
  if has_systemd_unit; then
    log "systemctl start ${SERVICE_NAME}"
    systemctl start "${SERVICE_NAME}"
    return 0
  fi
  start_dev_stack
}

stop_app() {
  if has_systemd_unit; then
    log "systemctl stop ${SERVICE_NAME}"
    systemctl stop "${SERVICE_NAME}" || true
    return 0
  fi
  stop_dev_stack
}

restart_app() {
  if has_systemd_unit; then
    log "systemctl restart ${SERVICE_NAME}"
    systemctl restart "${SERVICE_NAME}"
    return 0
  fi
  stop_dev_stack
  start_dev_stack
}
