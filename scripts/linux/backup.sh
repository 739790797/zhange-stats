#!/usr/bin/env bash
# 备份：MySQL dump + var/data + var/uploads + .env
# 默认写入本安装树 var/backups/。覆盖：ZHANGE_BACKUP_DIR  ZHANGE_BACKUP_KEEP_DAYS=14
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"
BACKUP_ROOT="${ZHANGE_BACKUP_DIR:-${REPO_ROOT}/var/backups}"
KEEP_DAYS="${ZHANGE_BACKUP_KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"
WORKDIR="$(mktemp -d /tmp/zhange-backup.XXXXXX)"
trap 'rm -rf "${WORKDIR}"' EXIT

die() { printf '[backup] ERROR: %s\n' "$*" >&2; exit 1; }
log() { printf '[backup] %s\n' "$*"; }

[[ -f "${ENV_FILE}" ]] || die "缺少 ${ENV_FILE}"
command -v python3 >/dev/null || die "需要 python3"
command -v mysqldump >/dev/null || die "需要 mysqldump（MariaDB/MySQL 客户端）"

DATABASE_URL="$(python3 - <<PY
from pathlib import Path
for line in Path(r"${ENV_FILE}").read_text(encoding="utf-8").splitlines():
    s = line.strip()
    if not s or s.startswith("#"):
        continue
    if s.startswith("DATABASE_URL="):
        print(s.split("=", 1)[1].strip().strip('"').strip("'"))
        break
PY
)"
[[ -n "${DATABASE_URL}" ]] || die ".env 中没有 DATABASE_URL"
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
[[ -n "${DB_NAME}" ]] || die "无法从 DATABASE_URL 解析库名"

mkdir -p "${BACKUP_ROOT}"
chmod 700 "${BACKUP_ROOT}"

DUMP="${WORKDIR}/zhange.sql"
log "mysqldump ${DB_NAME} @ ${DB_HOST}:${DB_PORT}"
MYSQL_PWD="${DB_PASS}" mysqldump \
  --single-transaction \
  --routines \
  --events \
  -h "${DB_HOST}" \
  -P "${DB_PORT}" \
  -u "${DB_USER}" \
  "${DB_NAME}" > "${DUMP}"

DATA_DIR="${REPO_ROOT}/var/data"
UPLOAD_DIR="${REPO_ROOT}/var/uploads"
if [[ -d "${REPO_ROOT}/data" && ! -e "${REPO_ROOT}/var/data/.secret_key" ]]; then
  DATA_DIR="${REPO_ROOT}/data"
  UPLOAD_DIR="${REPO_ROOT}/uploads"
fi

ARCHIVE="${BACKUP_ROOT}/zhange-${STAMP}.tar.gz"
python3 - <<PY
import tarfile
from pathlib import Path
root = Path(r"${REPO_ROOT}")
archive = Path(r"${ARCHIVE}")
dump = Path(r"${DUMP}")
data = Path(r"${DATA_DIR}")
uploads = Path(r"${UPLOAD_DIR}")
with tarfile.open(archive, "w:gz") as tf:
    tf.add(dump, arcname="zhange.sql")
    env = root / ".env"
    if env.is_file():
        tf.add(env, arcname=".env")
    if data.is_dir():
        tf.add(data, arcname="var/data")
    if uploads.is_dir():
        tf.add(uploads, arcname="var/uploads")
print("wrote", archive, "bytes", archive.stat().st_size)
PY

chmod 600 "${ARCHIVE}"
log "保留 ${KEEP_DAYS} 天"
find "${BACKUP_ROOT}" -maxdepth 1 -name 'zhange-*.tar.gz' -mtime "+${KEEP_DAYS}" -delete || true
log "完成 ${ARCHIVE}"
