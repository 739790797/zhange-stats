#!/bin/sh
# 在 app 镜像内执行：把 MAA 宿主机文件导出到挂载目录（默认 /host）
# 宿主机用法：
#   cd /opt/zhange-stats
#   docker run --rm -v "$PWD:/host" ghcr.io/739790797/zhange-stats:latest \
#     /bin/sh /app/maa-host/scripts/export-to-host.sh
set -eu

DEST="${1:-/host}"
SRC="/app/maa-host"

if [ ! -d "$SRC" ]; then
  echo "镜像内缺少 $SRC，请升级到含 MAA host pack 的 app 版本" >&2
  exit 1
fi

if [ ! -d "$DEST" ]; then
  echo "目标目录不存在: $DEST（请用 -v /opt/zhange-stats:/host 挂载）" >&2
  exit 1
fi

# 只覆盖 MAA 相关文件，不碰用户的 compose.yml / .env / data
mkdir -p "$DEST/scripts" "$DEST/deploy/systemd" "$DEST/docs"
cp -f "$SRC/compose.maa.yml" "$DEST/compose.maa.yml"
cp -f "$SRC/scripts/install-maa-host.sh" "$DEST/scripts/install-maa-host.sh"
cp -f "$SRC/scripts/export-to-host.sh" "$DEST/scripts/export-maa-host-from-image.sh"
cp -f "$SRC/deploy/systemd/maa-binder.service" "$DEST/deploy/systemd/maa-binder.service"
if [ -f "$SRC/docs/maa-ops.md" ]; then
  cp -f "$SRC/docs/maa-ops.md" "$DEST/docs/maa-ops.md"
fi
chmod +x "$DEST/scripts/install-maa-host.sh" "$DEST/scripts/export-maa-host-from-image.sh" 2>/dev/null || true

echo "已导出 MAA 宿主机文件到 $DEST"
echo "下一步（在宿主机）：sudo bash scripts/install-maa-host.sh"
