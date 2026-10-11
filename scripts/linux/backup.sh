#!/usr/bin/env bash
# 备份：config/ + data/runtime + data/uploads + data/models + manifest.json（VERSION、迁移版本）。
# MySQL 另打 zhange.sql（utf8mb4）；SQLite 用在线备份 API 取一致副本。不打包更新暂存、锁与缓存。
# 默认写入本安装树 data/backups/。覆盖：ZHANGE_BACKUP_DIR  ZHANGE_BACKUP_KEEP_DAYS=14
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BACKUP_ROOT="${ZHANGE_BACKUP_DIR:-${REPO_ROOT}/data/backups}"
KEEP_DAYS="${ZHANGE_BACKUP_KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"

die() { printf '[backup] ERROR: %s\n' "$*" >&2; exit 1; }
log() { printf '[backup] %s\n' "$*"; }

command -v python3 >/dev/null || die "需要 python3"
[[ "${KEEP_DAYS}" =~ ^[0-9]+$ ]] || die "ZHANGE_BACKUP_KEEP_DAYS 须为非负整数"

mkdir -p "${REPO_ROOT}/data/tmp"
umask 077
WORKDIR="$(mktemp -d "${REPO_ROOT}/data/tmp/zhange-backup.XXXXXX")"
trap 'rm -rf "${WORKDIR}"' EXIT

mkdir -p "${BACKUP_ROOT}"
chmod 700 "${BACKUP_ROOT}"

ARCHIVE="${BACKUP_ROOT}/zhange-${STAMP}.tar.gz"
python3 "${REPO_ROOT}/scripts/common/backup_util.py" backup \
  --root "${REPO_ROOT}" --out "${ARCHIVE}" --work "${WORKDIR}"

log "保留 ${KEEP_DAYS} 天"
find "${BACKUP_ROOT}" -maxdepth 1 -name 'zhange-*.tar.gz' -mtime "+${KEEP_DAYS}" -delete || true
log "完成 ${ARCHIVE}"
