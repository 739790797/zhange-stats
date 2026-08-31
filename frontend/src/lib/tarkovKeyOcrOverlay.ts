import {
  keyNameBandAdmissible,
  keyNameBandHasInk,
  keyNameBandRect,
  type TarkovKeyGrid,
  type TarkovKeyGridCell,
  type TarkovKeyNameBand,
} from "@/lib/tarkovKeyOcrGrid";

export type TarkovKeyOcrOverlaySkip = "small" | "empty";

export type TarkovKeyOcrOverlayCell = {
  col: number;
  row: number;
  x: number;
  y: number;
  width: number;
  height: number;
  band: TarkovKeyNameBand;
  skip?: TarkovKeyOcrOverlaySkip;
  ocrText?: string;
  matchShort?: string;
  fromWhole?: boolean;
  fromIcon?: boolean;
};

export type TarkovKeyOcrOverlay = {
  width: number;
  height: number;
  cols: number;
  rows: number;
  cells: TarkovKeyOcrOverlayCell[];
};

export function describeKeyOcrCell(
  cell: TarkovKeyGridCell,
  data: Uint8ClampedArray,
  width: number,
  height: number,
): TarkovKeyOcrOverlayCell {
  const band = keyNameBandRect(cell);
  let skip: TarkovKeyOcrOverlaySkip | undefined;
  if (!keyNameBandAdmissible(band)) skip = "small";
  else if (!keyNameBandHasInk(data, width, height, band)) skip = "empty";
  return {
    col: cell.col,
    row: cell.row,
    x: cell.x,
    y: cell.y,
    width: cell.width,
    height: cell.height,
    band,
    skip,
  };
}

export function buildKeyOcrOverlay(
  grid: TarkovKeyGrid | null,
  data: Uint8ClampedArray,
  width: number,
  height: number,
): TarkovKeyOcrOverlay {
  if (!grid) {
    return { width, height, cols: 0, rows: 0, cells: [] };
  }
  return {
    width,
    height,
    cols: grid.cols,
    rows: grid.rows,
    cells: grid.cells.map((cell) => describeKeyOcrCell(cell, data, width, height)),
  };
}

export function cloneKeyOcrOverlay(overlay: TarkovKeyOcrOverlay): TarkovKeyOcrOverlay {
  return {
    ...overlay,
    cells: overlay.cells.map((cell) => ({ ...cell, band: { ...cell.band } })),
  };
}

/** 只展示会勾选的目录短名，不写引擎残字。 */
export function overlayCellLabel(cell: TarkovKeyOcrOverlayCell): string {
  return cell.matchShort || "";
}

/** 写在短名条（识别范围）正下方，不挡原图上的名字。 */
export function overlayLabelTop(cell: TarkovKeyOcrOverlayCell): number {
  return cell.band.y + cell.band.height + 1;
}

export function overlayCellColor(cell: TarkovKeyOcrOverlayCell): string {
  if (cell.matchShort) {
    if (cell.fromIcon) return "#22c55e";
    return cell.fromWhole ? "#38bdf8" : "#eab308";
  }
  if (cell.skip) return "#4b5563";
  return "#3f3f2e";
}

function findOverlayCell(
  overlay: TarkovKeyOcrOverlay,
  row: number,
  col: number,
): TarkovKeyOcrOverlayCell | undefined {
  return overlay.cells.find((cell) => cell.row === row && cell.col === col);
}

export function annotateOverlayCell(
  overlay: TarkovKeyOcrOverlay,
  row: number,
  col: number,
  patch: Pick<TarkovKeyOcrOverlayCell, "ocrText" | "matchShort" | "fromWhole" | "fromIcon">,
): void {
  const cell = findOverlayCell(overlay, row, col);
  if (!cell) return;
  if (patch.ocrText) cell.ocrText = patch.ocrText;
  if (patch.matchShort) cell.matchShort = patch.matchShort;
  if (patch.fromWhole) cell.fromWhole = true;
  if (patch.fromIcon) cell.fromIcon = true;
}

export function paintKeyOcrOverlay(
  ctx: CanvasRenderingContext2D,
  overlay: TarkovKeyOcrOverlay,
  scale: number,
): void {
  const line = Math.max(1.5, Math.min(3, overlay.cells[0]?.width ? (overlay.cells[0].width * scale) / 36 : 2));
  ctx.save();
  ctx.lineJoin = "round";
  ctx.textBaseline = "top";
  const fontSize = Math.max(10, Math.min(15, (overlay.cells[0]?.width || 48) * scale * 0.18));
  ctx.font = `600 ${fontSize}px "Microsoft YaHei", "PingFang SC", sans-serif`;
  for (const cell of overlay.cells) {
    const color = overlayCellColor(cell);
    const x = cell.x * scale;
    const y = cell.y * scale;
    const w = cell.width * scale;
    const h = cell.height * scale;
    ctx.strokeStyle = color;
    ctx.globalAlpha = cell.matchShort ? 0.95 : 0.35;
    ctx.lineWidth = cell.matchShort ? line + 0.5 : line;
    ctx.strokeRect(x + 0.5, y + 0.5, Math.max(1, w - 1), Math.max(1, h - 1));
    if (cell.matchShort && !cell.fromIcon) {
      ctx.strokeStyle = "#facc15";
      ctx.globalAlpha = 0.95;
      ctx.lineWidth = line + 0.5;
      ctx.strokeRect(
        cell.band.x * scale + 0.5,
        cell.band.y * scale + 0.5,
        Math.max(1, cell.band.width * scale - 1),
        Math.max(1, cell.band.height * scale - 1),
      );
    }
    const label = overlayCellLabel(cell);
    if (!label) continue;
    const pad = 2;
    const textW = ctx.measureText(label).width;
    const boxH = fontSize + pad * 2;
    const boxW = Math.min(w - 2, textW + pad * 2);
    const labelY = Math.min(
      overlay.height * scale - boxH - 1,
      overlayLabelTop(cell) * scale,
    );
    ctx.globalAlpha = 0.82;
    ctx.fillStyle = "#111";
    ctx.fillRect(x + 1, labelY, boxW, boxH);
    ctx.globalAlpha = 1;
    ctx.fillStyle = color;
    ctx.fillText(label, x + 1 + pad, labelY + pad, Math.max(8, w - 4));
  }
  ctx.restore();
}
