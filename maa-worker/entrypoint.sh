#!/bin/sh
set -eu

maa_core_ready() {
  lib="$(maa dir library 2>/dev/null || true)/libMaaCore.so"
  if [ -f "$lib" ] && maa version >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

ensure_maa_core() {
  export LD_LIBRARY_PATH="/var/lib/maa/xdg-data/maa/lib:${LD_LIBRARY_PATH:-}"
  if maa_core_ready; then
    echo "maa-worker: MaaCore already present"
    maa version || true
    return 0
  fi
  if [ -f /var/lib/maa/xdg-data/maa/lib/libMaaCore.so ]; then
    echo "maa-worker: MaaCore libs present; checking load..."
    if maa version >/dev/null 2>&1; then
      echo "maa-worker: MaaCore load ok"
      return 0
    fi
    echo "maa-worker: MaaCore present but failed to load; try update"
    maa update --test-time 0 || true
    if maa version >/dev/null 2>&1; then
      return 0
    fi
  fi
  echo "maa-worker: installing MaaCore + resources (first boot)..."
  i=1
  while [ "$i" -le 3 ]; do
    if maa install --test-time 0 || maa install --force --test-time 0; then
      if maa version >/dev/null 2>&1; then
        echo "maa-worker: MaaCore install ok"
        maa version || true
        return 0
      fi
    fi
    echo "maa-worker: maa install failed (attempt $i/3), retry in 5s..."
    i=$((i + 1))
    sleep 5
  done
  echo "maa-worker: WARNING MaaCore not usable; daily jobs may fail"
  return 0
}

ensure_maa_core
exec "$@"