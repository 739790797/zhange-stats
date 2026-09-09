#!/usr/bin/env bash
# Shared by linux/install.sh, run.sh, restart.sh. Not a public command.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"
VENV_DIR="${BACKEND_DIR}/.venv"
VENV_PY="${VENV_DIR}/bin/python"
STATIC_DIR="${REPO_ROOT}/static"
SERVICE_SRC="${REPO_ROOT}/deploy/systemd/zhange-stats.service"
SERVICE_NAME="${ZHANGE_SERVICE:-zhange-stats.service}"
SERVICE_USER="${ZHANGE_USER:-zhange}"
DEV_DIR="${REPO_ROOT}/var/dev"
BACKEND_PORT="${ZHANGE_BACKEND_PORT:-6130}"
FRONTEND_PORT="${ZHANGE_FRONTEND_PORT:-6131}"
PIP_STAMP="${VENV_DIR}/.zhange-req.stamp"
ZHANGE_LOG_TAG="${ZHANGE_LOG_TAG:-zhange}"

if [[ -d "${REPO_ROOT}/data" && ! -e "${REPO_ROOT}/var/data/.secret_key" ]]; then
  DATA_DIR="${REPO_ROOT}/data"
  UPLOAD_DIR="${REPO_ROOT}/uploads"
else
  DATA_DIR="${REPO_ROOT}/var/data"
  UPLOAD_DIR="${REPO_ROOT}/var/uploads"
fi

log() { printf '[%s] %s\n' "${ZHANGE_LOG_TAG}" "$*"; }
die() { printf '[%s] ERROR: %s\n' "${ZHANGE_LOG_TAG}" "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "缺少命令: $1"
}

ensure_env_key() {
  local key="$1" value="$2"
  local env_file="${REPO_ROOT}/.env"
  if grep -qE "^[[:space:]]*${key}=" "${env_file}" 2>/dev/null; then
    return 0
  fi
  printf '\n%s=%s\n' "${key}" "${value}" >> "${env_file}"
  log "已追加 ${key}"
}

ensure_env_file() {
  if [[ -f "${REPO_ROOT}/.env" ]]; then
    return 0
  fi
  [[ -f "${REPO_ROOT}/.env.example" ]] || die "缺少 .env 与 .env.example"
  cp "${REPO_ROOT}/.env.example" "${REPO_ROOT}/.env"
  log "已复制 .env.example → .env"
}

ensure_runtime_dirs() {
  mkdir -p "${DATA_DIR}" "${UPLOAD_DIR}" "${STATIC_DIR}" "${DEV_DIR}" "${REPO_ROOT}/var/backups"
}

ensure_install_paths() {
  ensure_env_key "APP_INSTALL_DIR" "${REPO_ROOT}"
  ensure_env_key "STATIC_DIR" "${STATIC_DIR}"
  ensure_env_key "DATA_DIR" "${DATA_DIR}"
  ensure_env_key "UPLOAD_DIR" "${UPLOAD_DIR}"
}

ensure_mariadb() {
  log "检查 MariaDB…"
  python3 "${REPO_ROOT}/scripts/common/provision_mariadb.py" --root "${REPO_ROOT}" \
    || die "MariaDB 不可用。可自备库并填写 DATABASE_URL，或 ZHANGE_SKIP_MARIADB=1"
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
  constraint="$(mktemp)"
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

ensure_deps() {
  [[ -f "${REPO_ROOT}/VERSION" ]] || die "未找到 VERSION"
  need_cmd python3
  ensure_runtime_dirs
  ensure_env_file
  ensure_install_paths
  ensure_mariadb
  ensure_python_deps
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
