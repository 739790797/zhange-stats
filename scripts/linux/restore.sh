#!/usr/bin/env bash
# 从 backup.sh 的 tar.gz 恢复：停服务 → 可选导库 → 解压 config/ 与 data/ → 启动
# 用法：ZHANGE_RESTORE_CONFIRM=YES ZHANGE_RESTORE_ARCHIVE=/path/zhange-*.tar.gz ./scripts/linux/restore.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ZHANGE_LOG_TAG="${ZHANGE_LOG_TAG:-restore}"
# shellcheck source=./_lib.sh
source "${SCRIPT_DIR}/_lib.sh"

ARCHIVE="${ZHANGE_RESTORE_ARCHIVE:-}"

[[ -n "${ARCHIVE}" && -f "${ARCHIVE}" ]] || die "设置 ZHANGE_RESTORE_ARCHIVE 为 backup.sh 产出的 tar.gz"
need_cmd python3
need_cmd tar

if [[ "${ZHANGE_RESTORE_CONFIRM:-}" != "YES" ]]; then
  die "将覆盖当前库与 data/、config/。确认后：ZHANGE_RESTORE_CONFIRM=YES ZHANGE_RESTORE_ARCHIVE=... $0"
fi

mkdir -p "${TMP_DIR}"
WORKDIR="$(mktemp -d "${TMP_DIR}/zhange-restore.XXXXXX")"
trap 'rm -rf "${WORKDIR}"' EXIT
tar -tzf "${ARCHIVE}" >/dev/null
tar -xzf "${ARCHIVE}" -C "${WORKDIR}"

log "停止应用"
stop_app

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

eval "$(python3 - <<PY
import json, os
from pathlib import Path
root = Path(r"${REPO_ROOT}")
url = (os.environ.get("DATABASE_URL") or "").strip()
engine = ""
cfg = root / "config" / "database.json"
if cfg.is_file():
    try:
        data = json.loads(cfg.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        data = {}
    engine = str(data.get("engine") or "").strip().lower()
    url = url or str(data.get("url") or "").strip()
print("ENGINE=" + json.dumps(engine))
print("DATABASE_URL=" + json.dumps(url))
PY
)"

if [[ -f "${WORKDIR}/zhange.sql" ]]; then
  need_cmd mysql
  [[ -n "${DATABASE_URL}" ]] || die "归档含 zhange.sql 但没有 MySQL 连接串"
  export DATABASE_URL
  eval "$(python3 - <<'PY'
import json, os
from urllib.parse import urlparse, unquote
url = (os.environ.get("DATABASE_URL") or "").replace("mysql+pymysql://", "mysql://", 1)
u = urlparse(url)
def q(v):
    return json.dumps("" if v is None else str(v), ensure_ascii=False)
print("DB_USER=" + q(unquote(u.username or "")))
print("DB_PASS=" + q(unquote(u.password or "")))
print("DB_HOST=" + q(u.hostname or "127.0.0.1"))
print("DB_PORT=" + q(u.port or 3306))
print("DB_NAME=" + q((u.path or "").lstrip("/").split("?")[0]))
PY
)"
  log "导入 ${DB_NAME}"
  MYSQL_PWD="${DB_PASS}" mysql -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" "${DB_NAME}" < "${WORKDIR}/zhange.sql"
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

log "启动应用"
start_app
log "恢复完成。请登录验证。"
