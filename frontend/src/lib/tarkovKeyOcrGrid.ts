/** 钥匙箱格子：用投影找规整方阵，不引入检测模型。 */

export type TarkovKeyGridCell = {
  col: number;
  row: number;
  x: number;
  y: number;
  width: number;
  height: number;
};

export type TarkovKeyGrid = {
  cols: number;
  rows: number;
  cellWidth: number;
  cellHeight: number;
  cells: TarkovKeyGridCell[];
};

export type TarkovKeyNameBand = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type TarkovKeyRowSheetLayout = {
  scale: number;
  gap: number;
  pad: number;
  bandWidth: number;
  bandHeight: number;
  columns: number;
  cellXs: number[];
  sheetWidth: number;
  sheetHeight: number;
};

const MIN_PERIOD = 28;
const MAX_PERIOD = 180;
const NAME_BAND_RATIO = 0.38;
const NAME_BAND_MAX_SRC_HEIGHT = 24;
const ROW_GAP = 28;
const ROW_PAD = 8;

/** 送进 Tesseract 的短名条：扁长文本行，避免把图标放得太大。 */
export const KEY_NAME_BAND_TARGET_WIDTH = 280;
export const KEY_NAME_BAND_TARGET_HEIGHT = 112;
export const KEY_NAME_BAND_MIN_SRC_HEIGHT = 10;
export const KEY_NAME_BAND_MIN_SRC_WIDTH = 12;
/** 只为找格缩图；裁切仍回原图。 */
export const KEYBOX_DETECT_MAX_EDGE = 1600;
export const KEY_ROW_SHEET_CHUNK = 5;

export function keyRowSheetChunks(
  columns: number,
  chunk = KEY_ROW_SHEET_CHUNK,
): Array<{ start: number; count: number }> {
  const out: Array<{ start: number; count: number }> = [];
  const size = Math.max(1, chunk);
  for (let start = 0; start < columns; start += size) {
    out.push({ start, count: Math.min(size, columns - start) });
  }
  return out;
}

function grayAt(data: Uint8ClampedArray, width: number, x: number, y: number): number {
  const i = (y * width + x) * 4;
  return 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
}

function smooth(values: number[], radius = 1): number[] {
  const n = values.length;
  const out = new Array<number>(n);
  for (let i = 0; i < n; i += 1) {
    const lo = Math.max(0, i - radius);
    const hi = Math.min(n, i + radius + 1);
    let sum = 0;
    for (let j = lo; j < hi; j += 1) sum += values[j];
    out[i] = sum / (hi - lo);
  }
  return out;
}

function colScore(
  data: Uint8ClampedArray,
  width: number,
  y0: number,
  y1: number,
): number[] {
  const out = new Array<number>(width).fill(0);
  const span = Math.max(1, y1 - y0);
  for (let x = 0; x < width; x += 1) {
    let mean = 0;
    for (let y = y0; y < y1; y += 1) mean += grayAt(data, width, x, y);
    out[x] = mean / span;
  }
  for (let y = y0; y < y1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const g = grayAt(data, width, x, y);
      const left = grayAt(data, width, x - 1, y);
      const right = grayAt(data, width, x + 1, y);
      if (g >= 28 && g >= left && g >= right && g - Math.min(left, right) >= 4) {
        out[x] += 0.4;
      }
    }
  }
  return out;
}

function rowScore(
  data: Uint8ClampedArray,
  width: number,
  height: number,
  x0: number,
  x1: number,
): number[] {
  const out = new Array<number>(height).fill(0);
  const span = Math.max(1, x1 - x0);
  for (let y = 0; y < height; y += 1) {
    let mean = 0;
    for (let x = x0; x < x1; x += 1) mean += grayAt(data, width, x, y);
    out[y] = mean / span;
  }
  for (let y = 1; y < height - 1; y += 1) {
    for (let x = x0; x < x1; x += 1) {
      const g = grayAt(data, width, x, y);
      const above = grayAt(data, width, x, y - 1);
      const below = grayAt(data, width, x, y + 1);
      if (g >= 28 && g >= above && g >= below && g - Math.min(above, below) >= 4) {
        out[y] += 0.15;
      }
    }
  }
  return out;
}

function autocorrPeriod(values: number[], minP: number, maxP: number): number | null {
  const n = values.length;
  if (n < minP * 2) return null;
  let mean = 0;
  for (const value of values) mean += value;
  mean /= n;
  const hi = Math.min(maxP, Math.floor(n / 3));
  if (hi < minP) return null;
  const scores: number[] = [];
  let best = Number.NEGATIVE_INFINITY;
  for (let p = minP; p <= hi; p += 1) {
    let sum = 0;
    const count = n - p;
    for (let i = 0; i < count; i += 1) {
      sum += (values[i] - mean) * (values[i + p] - mean);
    }
    const score = sum / count;
    scores.push(score);
    if (score > best) best = score;
  }
  if (best <= 0) return null;
  const floor = best * 0.62;
  for (let i = 0; i < scores.length; i += 1) {
    const score = scores[i];
    if (score < floor) continue;
    const prev = i > 0 ? scores[i - 1] : Number.NEGATIVE_INFINITY;
    const next = i + 1 < scores.length ? scores[i + 1] : Number.NEGATIVE_INFINITY;
    if (score >= prev && score >= next) return minP + i;
  }
  return minP + scores.indexOf(best);
}

function snapLines(
  score: number[],
  period: number,
  start: number,
  end: number,
): number[] {
  let bestPhase = 0;
  let best = Number.NEGATIVE_INFINITY;
  for (let phase = 0; phase < period; phase += 1) {
    let sum = 0;
    let count = 0;
    for (let x = start + phase; x < end; x += period) {
      const lo = Math.max(0, x - 1);
      const hi = Math.min(score.length - 1, x + 1);
      let peak = score[lo];
      for (let i = lo + 1; i <= hi; i += 1) peak = Math.max(peak, score[i]);
      sum += peak;
      count += 1;
    }
    if (count && sum / count > best) {
      best = sum / count;
      bestPhase = phase;
    }
  }
  const lines: number[] = [];
  for (let x = start + bestPhase; x < end; x += period) {
    const lo = Math.max(0, x - 2);
    const hi = Math.min(score.length - 1, x + 2);
    let peak = lo;
    for (let i = lo + 1; i <= hi; i += 1) {
      if (score[i] > score[peak]) peak = i;
    }
    if (!lines.length || peak - lines[lines.length - 1] >= Math.max(16, period - 8)) {
      lines.push(peak);
    }
  }
  return lines;
}

function median(values: number[]): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function gaps(lines: number[]): number[] {
  const out: number[] = [];
  for (let i = 1; i < lines.length; i += 1) out.push(lines[i] - lines[i - 1]);
  return out;
}

/**
 * 从 RGBA 像素里找钥匙箱 / 仓库那种等宽等高格子。
 * 找不到规整方阵时返回 null，调用方回退整图 OCR。
 */
export function detectInventoryGrid(
  data: Uint8ClampedArray,
  width: number,
  height: number,
): TarkovKeyGrid | null {
  if (width < 200 || height < 160 || data.length < width * height * 4) return null;

  const topSkip = Math.max(12, Math.round(height * 0.04));
  const botSkip = Math.max(4, Math.round(height * 0.015));
  const sideSkip = Math.max(2, Math.round(width * 0.005));
  const y0 = topSkip;
  const y1 = height - botSkip;
  const x0 = sideSkip;
  const x1 = width - sideSkip;

  const cols = smooth(colScore(data, width, y0, y1));
  const rows = smooth(rowScore(data, width, height, x0, x1));
  const colPeriod = autocorrPeriod(cols.slice(x0, x1), MIN_PERIOD, MAX_PERIOD);
  if (!colPeriod) return null;
  const rowMin = Math.max(MIN_PERIOD, Math.round(colPeriod * 0.72));
  const rowMax = Math.min(MAX_PERIOD, Math.round(colPeriod * 1.38));
  let rowPeriod =
    autocorrPeriod(rows.slice(y0, y1), rowMin, rowMax) ||
    autocorrPeriod(rows.slice(y0, y1), MIN_PERIOD, MAX_PERIOD);
  if (!rowPeriod) return null;
  // 钥匙格接近正方形；耐久横条会把行周期吸到搜索窗口下沿（约 0.72×列宽）。
  const atBound =
    Math.abs(rowPeriod - rowMin) <= 2 || Math.abs(rowPeriod - rowMax) <= 2;
  const ratio = colPeriod / rowPeriod;
  if (atBound || ratio < 0.85 || ratio > 1.18) {
    rowPeriod = colPeriod;
  }

  const vlines = snapLines(cols, colPeriod, 0, width);
  const hlines = snapLines(rows, rowPeriod, Math.max(8, topSkip - 8), height);
  if (vlines.length < 5 || hlines.length < 3) return null;

  const colGaps = gaps(vlines);
  const rowGaps = gaps(hlines);
  const cellWidth = median(colGaps);
  const cellHeight = median(rowGaps);
  if (cellWidth < MIN_PERIOD || cellHeight < MIN_PERIOD) return null;
  if (Math.abs(cellWidth - colPeriod) > 10 || Math.abs(cellHeight - rowPeriod) > 12) {
    return null;
  }

  const cells: TarkovKeyGridCell[] = [];
  for (let row = 0; row < hlines.length - 1; row += 1) {
    const heightGap = hlines[row + 1] - hlines[row];
    if (heightGap < cellHeight * 0.72 || heightGap > cellHeight * 1.35) continue;
    for (let col = 0; col < vlines.length - 1; col += 1) {
      const widthGap = vlines[col + 1] - vlines[col];
      if (widthGap < cellWidth * 0.72 || widthGap > cellWidth * 1.35) continue;
      cells.push({
        col,
        row,
        x: vlines[col],
        y: hlines[row],
        width: widthGap,
        height: heightGap,
      });
    }
  }
  if (cells.length < 8) return null;
  const colCount = 1 + Math.max(...cells.map((cell) => cell.col));
  const rowCount = 1 + Math.max(...cells.map((cell) => cell.row));
  if (colCount < 4 || rowCount < 2) return null;

  return {
    cols: colCount,
    rows: rowCount,
    cellWidth,
    cellHeight,
    cells,
  };
}

function downsampleRgba(
  data: Uint8ClampedArray,
  width: number,
  height: number,
  destWidth: number,
  destHeight: number,
): Uint8ClampedArray {
  const out = new Uint8ClampedArray(destWidth * destHeight * 4);
  const xRatio = width / destWidth;
  const yRatio = height / destHeight;
  for (let y = 0; y < destHeight; y += 1) {
    const sy0 = Math.floor(y * yRatio);
    const sy1 = Math.max(sy0 + 1, Math.min(height, Math.floor((y + 1) * yRatio)));
    for (let x = 0; x < destWidth; x += 1) {
      const sx0 = Math.floor(x * xRatio);
      const sx1 = Math.max(sx0 + 1, Math.min(width, Math.floor((x + 1) * xRatio)));
      let r = 0;
      let g = 0;
      let b = 0;
      let a = 0;
      let n = 0;
      for (let sy = sy0; sy < sy1; sy += 1) {
        for (let sx = sx0; sx < sx1; sx += 1) {
          const i = (sy * width + sx) * 4;
          r += data[i];
          g += data[i + 1];
          b += data[i + 2];
          a += data[i + 3];
          n += 1;
        }
      }
      const o = (y * destWidth + x) * 4;
      out[o] = r / n;
      out[o + 1] = g / n;
      out[o + 2] = b / n;
      out[o + 3] = a / n;
    }
  }
  return out;
}

export function scaleKeyGrid(
  grid: TarkovKeyGrid,
  scaleX: number,
  scaleY: number,
): TarkovKeyGrid {
  return {
    cols: grid.cols,
    rows: grid.rows,
    cellWidth: grid.cellWidth * scaleX,
    cellHeight: grid.cellHeight * scaleY,
    cells: grid.cells.map((cell) => ({
      ...cell,
      x: cell.x * scaleX,
      y: cell.y * scaleY,
      width: cell.width * scaleX,
      height: cell.height * scaleY,
    })),
  };
}

/**
 * 找格入口：图太大时先缩到 KEYBOX_DETECT_MAX_EDGE，再把格子坐标乘回原图。
 */
export function detectKeyboxGrid(
  data: Uint8ClampedArray,
  width: number,
  height: number,
): TarkovKeyGrid | null {
  const edge = Math.max(width, height);
  if (edge <= KEYBOX_DETECT_MAX_EDGE) {
    return detectInventoryGrid(data, width, height);
  }
  const scale = KEYBOX_DETECT_MAX_EDGE / edge;
  const destWidth = Math.max(1, Math.round(width * scale));
  const destHeight = Math.max(1, Math.round(height * scale));
  const small = downsampleRgba(data, width, height, destWidth, destHeight);
  const grid = detectInventoryGrid(small, destWidth, destHeight);
  if (!grid) return null;
  return scaleKeyGrid(grid, width / destWidth, height / destHeight);
}

export function findKeyGridCell(
  grid: TarkovKeyGrid,
  x: number,
  y: number,
): TarkovKeyGridCell | null {
  for (const cell of grid.cells) {
    if (x >= cell.x && x < cell.x + cell.width && y >= cell.y && y < cell.y + cell.height) {
      return cell;
    }
  }
  return null;
}

/** 塔科夫格子短名在上沿，耐久在右下。 */
export function keyNameBandRect(cell: TarkovKeyGridCell): TarkovKeyNameBand {
  const inset = 2;
  const width = Math.max(1, cell.width - inset * 2);
  const height = Math.max(
    1,
    Math.min(NAME_BAND_MAX_SRC_HEIGHT, Math.round(cell.height * NAME_BAND_RATIO)),
  );
  return {
    x: cell.x + inset,
    y: cell.y + 1,
    width,
    height: Math.min(height, Math.max(1, cell.height - 2)),
  };
}

/** 图标本体：躲开上沿短名和右下耐久。 */
export function keyIconBodyRect(cell: TarkovKeyGridCell): TarkovKeyNameBand {
  const insetX = Math.max(3, Math.round(cell.width * 0.14));
  const top = Math.max(4, Math.round(cell.height * 0.26));
  const bottom = Math.max(4, Math.round(cell.height * 0.2));
  return {
    x: cell.x + insetX,
    y: cell.y + top,
    width: Math.max(1, cell.width - insetX * 2),
    height: Math.max(1, cell.height - top - bottom),
  };
}

export function keyNameBandAdmissible(band: TarkovKeyNameBand): boolean {
  return (
    band.width >= KEY_NAME_BAND_MIN_SRC_WIDTH &&
    band.height >= KEY_NAME_BAND_MIN_SRC_HEIGHT
  );
}

/** 暗底上几乎没有字/图标，空格不送引擎。 */
export function keyNameBandHasInk(
  data: Uint8ClampedArray,
  width: number,
  height: number,
  band: TarkovKeyNameBand,
): boolean {
  const x0 = Math.max(0, Math.floor(band.x));
  const y0 = Math.max(0, Math.floor(band.y));
  const x1 = Math.min(width, Math.ceil(band.x + band.width));
  const y1 = Math.min(height, Math.ceil(band.y + band.height));
  if (x1 - x0 < 4 || y1 - y0 < 4) return false;
  let count = 0;
  let bright = 0;
  let sum = 0;
  let sum2 = 0;
  for (let y = y0; y < y1; y += 1) {
    for (let x = x0; x < x1; x += 1) {
      const g = grayAt(data, width, x, y);
      count += 1;
      sum += g;
      sum2 += g * g;
      if (g >= 55) bright += 1;
    }
  }
  if (count < 16) return false;
  const mean = sum / count;
  const variance = sum2 / count - mean * mean;
  return bright >= 10 || bright / count >= 0.012 || variance >= 90;
}

export function keyNameBandDestRect(band: TarkovKeyNameBand): {
  width: number;
  height: number;
  offsetX: number;
  offsetY: number;
} {
  const scale = Math.min(
    KEY_NAME_BAND_TARGET_WIDTH / Math.max(1, band.width),
    KEY_NAME_BAND_TARGET_HEIGHT / Math.max(1, band.height),
  );
  const width = Math.max(1, Math.round(band.width * scale));
  const height = Math.max(1, Math.round(band.height * scale));
  return {
    width,
    height,
    offsetX: Math.floor((KEY_NAME_BAND_TARGET_WIDTH - width) / 2),
    offsetY: Math.floor((KEY_NAME_BAND_TARGET_HEIGHT - height) / 2),
  };
}

export function keyRowSheetLayout(columns: number): TarkovKeyRowSheetLayout {
  const bandWidth = KEY_NAME_BAND_TARGET_WIDTH;
  const bandHeight = KEY_NAME_BAND_TARGET_HEIGHT;
  const scale = 1;
  const gap = ROW_GAP;
  const pad = ROW_PAD;
  const cellXs: number[] = [];
  for (let i = 0; i < columns; i += 1) {
    cellXs.push(pad + i * (bandWidth * scale + gap));
  }
  const sheetWidth = pad * 2 + columns * bandWidth * scale + Math.max(0, columns - 1) * gap;
  const sheetHeight = pad * 2 + bandHeight * scale;
  return {
    scale,
    gap,
    pad,
    bandWidth,
    bandHeight,
    columns,
    cellXs,
    sheetWidth,
    sheetHeight,
  };
}

export function keyRowSheetColumnAt(
  xCenter: number,
  layout: TarkovKeyRowSheetLayout,
): number | null {
  let best = -1;
  let bestDist = Number.POSITIVE_INFINITY;
  const half = (layout.bandWidth * layout.scale) / 2;
  for (let i = 0; i < layout.columns; i += 1) {
    const mid = layout.cellXs[i] + half;
    const dist = Math.abs(xCenter - mid);
    if (dist < bestDist) {
      bestDist = dist;
      best = i;
    }
  }
  if (best < 0 || bestDist > half + layout.gap) return null;
  return best;
}

export function groupWordsByRowColumn(
  words: Array<{ text: string; x0?: number; x1?: number }>,
  layout: TarkovKeyRowSheetLayout,
): string[] {
  const buckets = Array.from({ length: layout.columns }, () => [] as string[]);
  for (const word of words) {
    const text = (word.text || "").trim();
    if (!text) continue;
    const x0 = Number(word.x0);
    const x1 = Number(word.x1);
    const center = Number.isFinite(x0) && Number.isFinite(x1) ? (x0 + x1) / 2 : Number.NaN;
    if (!Number.isFinite(center)) continue;
    const col = keyRowSheetColumnAt(center, layout);
    if (col === null) continue;
    buckets[col].push(text);
  }
  return buckets.map((parts) => parts.join(" ").trim());
}
