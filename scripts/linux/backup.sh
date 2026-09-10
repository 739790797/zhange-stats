#!/usr/bin/env bash
# 备份：config/ + data/runtime + data/uploads + data/models；MySQL 另打 zhange.sql。
# 默认写入本安装树 data/backups/。覆盖：ZHANGE_BACKUP_DIR  ZHANGE_BACKUP_KEEP_DAYS=14
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BACKUP_ROOT="${ZHANGE_BACKUP_DIR:-${REPO_ROOT}/data/backups}"
KEEP_DAYS="${ZHANGE_BACKUP_KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "${REPO_ROOT}/data/tmp"
WORKDIR="$(mktemp -d "${REPO_ROOT}/data/tmp/zhange-backup.XXXXXX")"
trap 'rm -rf "${WORKDIR}"' EXIT

die() { printf '[backup] ERROR: %s\n' "$*" >&2; exit 1; }
log() { printf '[backup] %s\n' "$*"; }

command -v python3 >/dev/null || die "需要 python3"

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
if not engine:
    if url.startswith("sqlite"):
        engine = "sqlite"
    elif url.startswith("mysql"):
        engine = "mysql"
print("ENGINE=" + json.dumps(engine))
print("DATABASE_URL=" + json.dumps(url))
PY
)"

mkdir -p "${BACKUP_ROOT}" "${REPO_ROOT}/data/tmp"
chmod 700 "${BACKUP_ROOT}"

DUMP=""
if [[ "${ENGINE}" == "mysql" ]]; then
  command -v mysqldump >/dev/null || die "MySQL 备份需要 mysqldump"
  [[ -n "${DATABASE_URL}" ]] || die "没有 MySQL 连接串（config/database.json 或 DATABASE_URL）"
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
  [[ -n "${DB_NAME}" ]] || die "无法从连接串解析库名"
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
elif [[ "${ENGINE}" == "sqlite" ]]; then
  log "SQLite：打包 data/runtime 中的库文件"
else
  log "未识别引擎，只打包 config/ 与 data/"
fi

ARCHIVE="${BACKUP_ROOT}/zhange-${STAMP}.tar.gz"
python3 - <<PY
import tarfile
from pathlib import Path
root = Path(r"${REPO_ROOT}")
archive = Path(r"${ARCHIVE}")
dump = Path(r"${DUMP}") if r"${DUMP}" else None
runtime = root / "data" / "runtime"
if not runtime.is_dir():
    runtime = root / "var" / "data"
uploads = root / "data" / "uploads"
if not uploads.is_dir():
    uploads = root / "var" / "uploads"
models = root / "data" / "models"
config = root / "config"
with tarfile.open(archive, "w:gz") as tf:
    if dump and dump.is_file():
        tf.add(dump, arcname="zhange.sql")
    if config.is_dir():
        tf.add(config, arcname="config")
    env = root / ".env"
    if env.is_file():
        tf.add(env, arcname=".env")
    if runtime.is_dir():
        tf.add(runtime, arcname="data/runtime")
    if uploads.is_dir():
        tf.add(uploads, arcname="data/uploads")
    if models.is_dir():
        tf.add(models, arcname="data/models")
print("wrote", archive, "bytes", archive.stat().st_size)
PY

chmod 600 "${ARCHIVE}"
log "保留 ${KEEP_DAYS} 天"
find "${BACKUP_ROOT}" -maxdepth 1 -name 'zhange-*.tar.gz' -mtime "+${KEEP_DAYS}" -delete || true
log "完成 ${ARCHIVE}"
