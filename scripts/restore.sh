#!/usr/bin/env bash
# 从 backup.sh 的 tar.gz 恢复：停服务 → 导库 → 解压 var/ 与 .env → 启动
# 用法：sudo ZHANGE_RESTORE_ARCHIVE=/var/backups/zhange/zhange-YYYYMMDD-HHMMSS.tar.gz ./scripts/restore.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"
ARCHIVE="${ZHANGE_RESTORE_ARCHIVE:-}"
SERVICE_NAME="${ZHANGE_SERVICE:-zhange-stats.service}"

die() { printf '[restore] ERROR: %s\n' "$*" >&2; exit 1; }
log() { printf '[restore] %s\n' "$*"; }

[[ -n "${ARCHIVE}" && -f "${ARCHIVE}" ]] || die "设置 ZHANGE_RESTORE_ARCHIVE 为 backup.sh 产出的 tar.gz"
command -v python3 >/dev/null || die "需要 python3"
command -v mysql >/dev/null || die "需要 mysql 客户端"
command -v tar >/dev/null || die "需要 tar"

if [[ "${ZHANGE_RESTORE_CONFIRM:-}" != "YES" ]]; then
  die "将覆盖当前库与 var/。确认后：ZHANGE_RESTORE_CONFIRM=YES ZHANGE_RESTORE_ARCHIVE=... $0"
fi

WORKDIR="$(mktemp -d /tmp/zhange-restore.XXXXXX)"
trap 'rm -rf "${WORKDIR}"' EXIT
tar -tzf "${ARCHIVE}" | head >/dev/null
tar -xzf "${ARCHIVE}" -C "${WORKDIR}"
[[ -f "${WORKDIR}/zhange.sql" ]] || die "归档内没有 zhange.sql"

# 停应用，避免写入
if command -v systemctl >/dev/null && systemctl cat "${SERVICE_NAME}" >/dev/null 2>&1; then
  log "停止 ${SERVICE_NAME}"
  systemctl stop "${SERVICE_NAME}" || true
fi

# 优先用归档里的 .env 解析库连接；否则用现网 .env
RESTORE_ENV="${WORKDIR}/.env"
if [[ ! -f "${RESTORE_ENV}" ]]; then
  RESTORE_ENV="${ENV_FILE}"
fi
[[ -f "${RESTORE_ENV}" ]] || die "没有 .env 可解析 DATABASE_URL"

DATABASE_URL="$(python3 - <<PY
from pathlib import Path
for line in Path(r"${RESTORE_ENV}").read_text(encoding="utf-8").splitlines():
    s = line.strip()
    if s.startswith("DATABASE_URL="):
        print(s.split("=", 1)[1].strip().strip('"').strip("'"))
        break
PY
)"
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

log "恢复 .env 与 var/"
if [[ -f "${WORKDIR}/.env" ]]; then
  cp -a "${WORKDIR}/.env" "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
fi
mkdir -p "${REPO_ROOT}/var"
if [[ -d "${WORKDIR}/var/data" ]]; then
  rm -rf "${REPO_ROOT}/var/data"
  mkdir -p "${REPO_ROOT}/var"
  cp -a "${WORKDIR}/var/data" "${REPO_ROOT}/var/data"
fi
if [[ -d "${WORKDIR}/var/uploads" ]]; then
  rm -rf "${REPO_ROOT}/var/uploads"
  mkdir -p "${REPO_ROOT}/var"
  cp -a "${WORKDIR}/var/uploads" "${REPO_ROOT}/var/uploads"
fi

if command -v systemctl >/dev/null && systemctl cat "${SERVICE_NAME}" >/dev/null 2>&1; then
  log "启动 ${SERVICE_NAME}"
  systemctl start "${SERVICE_NAME}"
fi
log "恢复完成。请登录验证。"
