#!/bin/sh
# All-in-one：同容器启动本机 Redis（限流 + 扫码/cred 短时 KV），再 exec 主进程。
set -eu

EMBEDDED_REDIS="${EMBEDDED_REDIS:-1}"

_start_embedded_redis() {
  if [ "$EMBEDDED_REDIS" != "1" ]; then
    return 0
  fi
  # 已指向外部 Redis 时不抢起本机实例
  case "${REDIS_URL:-}" in
    redis://127.0.0.1:*|redis://localhost:*|"")
      ;;
    *)
      echo "docker-entrypoint: REDIS_URL points elsewhere, skip embedded redis"
      return 0
      ;;
  esac

  mkdir -p /app/data/redis
  # 短时缓存为主：关 RDB/AOF，减磁盘与启动复杂度；限流/扫码丢了可重建
  redis-server \
    --daemonize yes \
    --bind 127.0.0.1 \
    --port 6379 \
    --protected-mode yes \
    --dir /app/data/redis \
    --save "" \
    --appendonly no \
    --logfile "" >/dev/null

  i=0
  while [ "$i" -lt 50 ]; do
    if redis-cli -h 127.0.0.1 -p 6379 ping 2>/dev/null | grep -q PONG; then
      export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"
      echo "docker-entrypoint: embedded redis ready ($REDIS_URL)"
      return 0
    fi
    i=$((i + 1))
    sleep 0.1
  done
  echo "docker-entrypoint: embedded redis failed to start; app will fall back to in-memory" >&2
}

_start_embedded_redis
exec "$@"
