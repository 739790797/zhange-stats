#!/usr/bin/env bash
# 检查依赖后启动（有 systemd unit 则 systemctl start，否则本机 6130/6131）。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ZHANGE_LOG_TAG="${ZHANGE_LOG_TAG:-run}"
# shellcheck source=./_lib.sh
source "${SCRIPT_DIR}/_lib.sh"

ensure_deps
start_app
log "已启动。"
