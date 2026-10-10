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
PYTHON_BIN="${ZHANGE_PYTHON:-python3}"
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

# root 跑脚本时，往安装树里写东西的命令（venv / pip / 配置同步 / npm / 更新器）改由服务用户执行，
# 免得留下 root 属主文件让服务与管理端更新写不进去。
as_service_user() {
  if [[ "${EUID}" -eq 0 ]] && id -u "${SERVICE_USER}" >/dev/null 2>&1 \
    && command -v runuser >/dev/null 2>&1; then
    runuser -u "${SERVICE_USER}" -- "$@"
  else
    "$@"
  fi
}

# 只改属主不对的条目；-h 不跟随符号链接。MariaDB 数据目录归 mysql 用户，跳过。
fix_tree_owner() {
  [[ "${EUID}" -eq 0 ]] || return 0
  id -u "${SERVICE_USER}" >/dev/null 2>&1 || return 0
  local group
  group="$(id -gn "${SERVICE_USER}")"
  find "${REPO_ROOT}" -path "${REPO_ROOT}/data/mariadb" -prune -o \
    \( ! -user "${SERVICE_USER}" -o ! -group "${group}" \) \
    -exec chown -h "${SERVICE_USER}:${group}" {} + \
    || log "WARN: 修正安装树属主（${SERVICE_USER}）时有条目失败"
}

python_is_supported() {
  "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1
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
  if ! (cd "${BACKEND_DIR}" && as_service_user "${VENV_PY}" -m app.core.config_sync); then
    log "WARN: 站点配置同步失败"
  fi
}

ensure_venv() {
  if [[ -x "${VENV_PY}" ]]; then
    python_is_supported "${VENV_PY}" \
      || die "backend/.venv 的 Python 低于 3.11：删掉 backend/.venv 后用 Python 3.11+ 重跑 install"
    return 0
  fi
  need_cmd "${PYTHON_BIN}"
  python_is_supported "${PYTHON_BIN}" \
    || die "需要 Python 3.11+（${PYTHON_BIN} 是 $("${PYTHON_BIN}" -V 2>&1)）。系统自带的太旧时装 python3.11 与 python3.11-venv，再用 ZHANGE_PYTHON=python3.11 重跑"
  log "创建 venv…"
  as_service_user "${PYTHON_BIN}" -m venv "${VENV_DIR}"
}

# 与 app_updator.requirements_stamp 同格式（sha256sum 输出），管理端更新与脚本共用一个戳。
requirements_stamp() {
  local name files=()
  for name in requirements.txt constraints.txt; do
    if [[ -f "${BACKEND_DIR}/${name}" ]]; then
      files+=("${name}")
    fi
  done
  (cd "${BACKEND_DIR}" && sha256sum "${files[@]}")
}

pip_stamp_matches() {
  [[ -f "${PIP_STAMP}" ]] || return 1
  local want have
  want="$(requirements_stamp | tr -s '[:space:]' ' ')"
  have="$(tr -s '[:space:]' ' ' < "${PIP_STAMP}")"
  [[ -n "${want// /}" && "${want% }" == "${have% }" ]]
}

write_pip_stamp() {
  requirements_stamp | as_service_user tee "${PIP_STAMP}" >/dev/null \
    || log "WARN: 写入 ${PIP_STAMP} 失败"
}

pip_is_outdated() {
  local version
  version="$("$1" -m pip --version 2>/dev/null | awk '{print $2}')"
  [[ ! "${version%%.*}" =~ ^[0-9]+$ ]] || (( ${version%%.*} < 23 ))
}

pip_install_backend() {
  local python="$1"
  local req="${BACKEND_DIR}/requirements.txt"
  local lock="${BACKEND_DIR}/constraints.txt"
  local index="https://download.pytorch.org/whl/cpu"
  local constraint
  local pinned=()
  [[ -f "${req}" ]] || die "缺少 ${req}"
  if [[ -f "${lock}" ]]; then
    pinned=(-c "${lock}")
  fi
  if pip_is_outdated "${python}"; then
    as_service_user "${python}" -m pip install -U pip
  fi
  as_service_user "${python}" -m pip install torch torchvision --index-url "${index}"
  mkdir -p "${TMP_DIR}"
  constraint="$(mktemp "${TMP_DIR}/zhange-torch.XXXXXX")"
  chmod 0644 "${constraint}"
  as_service_user "${python}" -m pip freeze | grep -E '^(torch|torchvision)==' > "${constraint}" || true
  if [[ -s "${constraint}" ]]; then
    as_service_user "${python}" -m pip install -r "${req}" -c "${constraint}" ${pinned[@]+"${pinned[@]}"}
  else
    as_service_user "${python}" -m pip install -r "${req}" ${pinned[@]+"${pinned[@]}"}
  fi
  rm -f "${constraint}"
  as_service_user "${python}" -m pip uninstall -y opencv-python >/dev/null 2>&1 || true
  as_service_user "${python}" -m pip install -q --force-reinstall --no-deps \
    "opencv-python-headless>=4.8.0" ${pinned[@]+"${pinned[@]}"}
}

ensure_python_deps() {
  ensure_venv
  if [[ "${ZHANGE_FORCE_PIP:-0}" != "1" ]] && pip_stamp_matches; then
    return 0
  fi
  log "安装 Python 依赖（CPU torch）…"
  pip_install_backend "${VENV_PY}"
  write_pip_stamp
}

ensure_frontend_deps() {
  [[ -f "${REPO_ROOT}/frontend/package.json" ]] || return 0
  if [[ -d "${REPO_ROOT}/frontend/node_modules" ]]; then
    return 0
  fi
  command -v npm >/dev/null 2>&1 || return 0
  log "安装前端依赖…"
  (cd "${REPO_ROOT}/frontend" && as_service_user npm ci)
}

# 全新安装（git clone）没有 static/：取当前 VERSION 的 Release 预构建前端并校验 sha256。失败不致命。
ensure_static_assets() {
  [[ -f "${STATIC_DIR}/index.html" ]] && return 0
  [[ -x "${VENV_PY}" ]] || return 0
  log "static/ 里没有前端，下载 v$(tr -d '[:space:]' < "${REPO_ROOT}/VERSION") 的预构建 static…"
  if ! as_service_user "${VENV_PY}" "${REPO_ROOT}/scripts/common/update.py" --static-only; then
    log "WARN: 前端 static 未就绪（做法见上方提示）；后端照常启动，页面在补上 static/ 前打不开"
  fi
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
  fix_tree_owner
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

# systemd 单元监听地址：config/systemd.env 的 UVICORN_HOST / UVICORN_PORT，缺省 0.0.0.0:8000。
service_base_url() {
  local env_file="${REPO_ROOT}/config/systemd.env" host="" port=""
  if [[ -r "${env_file}" ]]; then
    host="$(sed -n 's/^[[:space:]]*UVICORN_HOST=//p' "${env_file}" | tail -n 1 | tr -d "\"' \r")"
    port="$(sed -n 's/^[[:space:]]*UVICORN_PORT=//p' "${env_file}" | tail -n 1 | tr -d "\"' \r")"
  fi
  case "${host}" in
    "" | 0.0.0.0 | :: | "[::]" | localhost) host="127.0.0.1" ;;
  esac
  if [[ "${host}" == *:* && "${host}" != \[* ]]; then
    host="[${host}]"
  fi
  printf 'http://%s:%s' "${host}" "${port:-8000}"
}

# 向导未完成时应用把一次性令牌写进 data/runtime/setup-token；未选库时首次访问向导接口才生成。
show_setup_token() {
  local token_file="${DATA_DIR}/setup-token" base
  if [[ ! -f "${REPO_ROOT}/config/database.json" && ! -e "${token_file}" ]]; then
    if has_systemd_unit; then
      base="$(service_base_url)"
    else
      base="http://127.0.0.1:${BACKEND_PORT}"
    fi
    wait_http "${base}/api/setup/status" 30 || true
  fi
  [[ -e "${token_file}" ]] || return 0
  if [[ -r "${token_file}" ]]; then
    log "安装令牌：$(tr -d '[:space:]' < "${token_file}")"
  else
    log "安装令牌在 ${token_file}（sudo cat 查看）"
  fi
  log "浏览器打开站点走安装向导时填写；向导完成后令牌自动删除。"
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
