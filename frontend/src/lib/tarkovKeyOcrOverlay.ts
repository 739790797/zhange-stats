/** 钥匙箱 OCR 覆盖层：把后端框画回本机截图。 */

export type TarkovKeyOcrOverlayBox = {
  x: number;
  y: number;
  width: number;
  height: number;
  label?: string;
  item_id?: string;
  kind?: string;
};

export type TarkovKeyOcrOverlay = {
  width: number;
  height: number;
  boxes?: TarkovKeyOcrOverlayBox[];
};

export function overlayBoxColor(kind?: string): string {
  if (kind === "hit") return "#22c55e";
  if (kind === "fuzzy") return "#eab308";
  return "#9ca3af";
}

export function overlayBoxLabel(box: TarkovKeyOcrOverlayBox): string {
  const raw = (box.label || "").trim();
  if (raw.length <= 16) return raw;
  return `${raw.slice(0, 15)}…`;
}

export function paintKeyOcrOverlay(
  ctx: CanvasRenderingContext2D,
  overlay: TarkovKeyOcrOverlay,
  scale: number,
): void {
  const boxes = overlay.boxes || [];
  if (!boxes.length) return;
  const typical = boxes[0].width * scale;
  const line = Math.max(1.5, Math.min(3, typical / 36 || 2));
  const fontSize = Math.max(10, Math.min(15, typical * 0.18 || 12));
  ctx.save();
  ctx.lineJoin = "round";
  ctx.textBaseline = "top";
  ctx.font = `600 ${fontSize}px "Microsoft YaHei", "PingFang SC", sans-serif`;
  for (const box of boxes) {
    const color = overlayBoxColor(box.kind);
    const x = box.x * scale;
    const y = box.y * scale;
    const w = Math.max(1, box.width * scale);
    const h = Math.max(1, box.height * scale);
    ctx.strokeStyle = color;
    ctx.globalAlpha = box.kind === "miss" ? 0.45 : 0.95;
    ctx.lineWidth = box.kind === "miss" ? line : line + 0.5;
    ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);
    const label = overlayBoxLabel(box);
    if (!label) continue;
    const pad = 2;
    const textW = ctx.measureText(label).width;
    const boxH = fontSize + pad * 2;
    const boxW = textW + pad * 2;
    const labelY = Math.min(overlay.height * scale - boxH - 1, y + h + 1);
    ctx.globalAlpha = 0.82;
    ctx.fillStyle = "#111";
    ctx.fillRect(x + 1, labelY, boxW, boxH);
    ctx.globalAlpha = 1;
    ctx.fillStyle = color;
    ctx.fillText(label, x + 1 + pad, labelY + pad, Math.max(8, boxW - pad * 2));
  }
  ctx.restore();
}
