#!/usr/bin/env bash
# 检查依赖后重启。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ZHANGE_LOG_TAG="${ZHANGE_LOG_TAG:-restart}"
# shellcheck source=./_lib.sh
source "${SCRIPT_DIR}/_lib.sh"

trap fix_tree_owner EXIT
ensure_deps
if has_systemd_unit; then
  ensure_static_assets
fi
restart_app
log "已重启。"
show_setup_token
