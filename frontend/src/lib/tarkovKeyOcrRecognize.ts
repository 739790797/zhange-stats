import { ocrOutputScale } from "@/lib/tarkovOcr";
import {
  INVENTORY_OCR_PROFILE,
  newTarkovOcrCanvas,
  recognizeOcrImage,
  type TarkovOcrProfile,
  type TarkovOcrWord,
} from "@/lib/tarkovOcrEngine";
import {
  detectKeyboxGrid,
  findKeyGridCell,
  groupWordsByRowColumn,
  keyIconBodyRect,
  keyNameBandAdmissible,
  keyNameBandDestRect,
  keyNameBandHasInk,
  keyNameBandRect,
  keyRowSheetChunks,
  keyRowSheetLayout,
  type TarkovKeyGrid,
  type TarkovKeyGridCell,
} from "@/lib/tarkovKeyOcrGrid";
import {
  matchKeysFromOcr,
  type TarkovKeyOcrCatalogKey,
  type TarkovKeyOcrMatch,
} from "@/lib/tarkovKeyOcr";
import { loadKeyIconTemplates } from "@/lib/tarkovKeyIconBank";
import {
  matchKeyIcon,
  sampleIconFromRgba,
} from "@/lib/tarkovKeyIconMatch";
import {
  annotateOverlayCell,
  buildKeyOcrOverlay,
  cloneKeyOcrOverlay,
  type TarkovKeyOcrOverlay,
} from "@/lib/tarkovKeyOcrOverlay";

/** 已对齐到固定短名规格的行条：不再二次拉伸。 */
export const KEY_ROW_OCR_PROFILE: TarkovOcrProfile = {
  psm: "sparse_text",
  dpi: 220,
  scale: 1,
  passes: ["invert", "normal"],
  contrast: "high",
  minWidth: 160,
  minHeight: 36,
  tooSmallMessage: "图片过小，请使用游戏内钥匙格截图",
  maxEdge: 4096,
};

type ProgressFn = (status: string, progress: number) => void;

export type TarkovKeyOcrRecognizeResult = {
  matches: TarkovKeyOcrMatch[];
  overlay: TarkovKeyOcrOverlay;
};

type LoadedKeybox = {
  width: number;
  height: number;
  data: Uint8ClampedArray;
  source: CanvasImageSource;
  release?: () => void;
};

async function loadKeyboxImage(source: Blob): Promise<LoadedKeybox> {
  if (typeof createImageBitmap === "function") {
    const bitmap = await createImageBitmap(source);
    const canvas = newTarkovOcrCanvas();
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) {
      bitmap.close();
      throw new Error("无法创建画布");
    }
    ctx.drawImage(bitmap, 0, 0);
    const image = ctx.getImageData(0, 0, canvas.width, canvas.height);
    return {
      width: canvas.width,
      height: canvas.height,
      data: image.data,
      source: bitmap,
      release: () => bitmap.close(),
    };
  }

  const url = URL.createObjectURL(source);
  try {
    const imageEl = await new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("图片读取失败"));
      img.src = url;
    });
    const width = imageEl.naturalWidth || imageEl.width;
    const height = imageEl.naturalHeight || imageEl.height;
    const canvas = newTarkovOcrCanvas();
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) throw new Error("无法创建画布");
    ctx.drawImage(imageEl, 0, 0);
    const image = ctx.getImageData(0, 0, width, height);
    return { width, height, data: image.data, source: imageEl };
  } finally {
    URL.revokeObjectURL(url);
  }
}

function cellsByRow(grid: TarkovKeyGrid): TarkovKeyGridCell[][] {
  const rows: TarkovKeyGridCell[][] = Array.from({ length: grid.rows }, () => []);
  for (const cell of grid.cells) {
    rows[cell.row]?.push(cell);
  }
  for (const row of rows) row.sort((a, b) => a.col - b.col);
  return rows.filter((row) => row.length >= 3);
}

function paintRowSheet(
  source: CanvasImageSource,
  pixels: Uint8ClampedArray,
  srcWidth: number,
  srcHeight: number,
  row: TarkovKeyGridCell[],
  colStart: number,
  colCount: number,
): HTMLCanvasElement | null {
  const layout = keyRowSheetLayout(colCount);
  const canvas = newTarkovOcrCanvas();
  canvas.width = layout.sheetWidth;
  canvas.height = layout.sheetHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  for (const cell of row) {
    const local = cell.col - colStart;
    if (local < 0 || local >= colCount) continue;
    const band = keyNameBandRect(cell);
    if (!keyNameBandAdmissible(band)) continue;
    if (!keyNameBandHasInk(pixels, srcWidth, srcHeight, band)) continue;
    const dx = layout.cellXs[local];
    if (dx === undefined) continue;
    const dest = keyNameBandDestRect(band);
    ctx.drawImage(
      source,
      band.x,
      band.y,
      band.width,
      band.height,
      dx + dest.offsetX,
      layout.pad + dest.offsetY,
      dest.width,
      dest.height,
    );
  }
  return canvas;
}

function wordSourcePoint(
  word: TarkovOcrWord,
  srcWidth: number,
  srcHeight: number,
): { x: number; y: number } | null {
  const x0 = Number(word.x0);
  const x1 = Number(word.x1);
  const y0 = Number(word.y0);
  const y1 = Number(word.y1);
  if (![x0, x1, y0, y1].every(Number.isFinite)) return null;
  const scale = ocrOutputScale(
    srcWidth,
    srcHeight,
    INVENTORY_OCR_PROFILE.scale,
    INVENTORY_OCR_PROFILE.maxEdge ?? 1920,
  );
  if (scale <= 0) return null;
  return { x: (x0 + x1) / 2 / scale, y: (y0 + y1) / 2 / scale };
}

function mergeMatches(parts: TarkovKeyOcrMatch[][]): TarkovKeyOcrMatch[] {
  const seen = new Set<string>();
  const out: TarkovKeyOcrMatch[] = [];
  for (const batch of parts) {
    for (const hit of batch) {
      if (seen.has(hit.id)) continue;
      seen.add(hit.id);
      out.push(hit);
    }
  }
  return out;
}

function catalogMatch(
  id: string,
  catalog: TarkovKeyOcrCatalogKey[],
): TarkovKeyOcrMatch | null {
  const key = catalog.find((row) => row.id === id);
  if (!key) return null;
  return {
    id: key.id,
    name: key.name || key.short_name || key.id,
    short_name: key.short_name || key.name || key.id,
    icon_link: key.icon_link || undefined,
    ocrText: "",
    confidence: "exact",
  };
}

/**
 * 钥匙箱识别：RatEye 路径——切格后先对图标，撞图再读短名。
 * 切格失败时才整张 OCR。
 */
export async function recognizeKeyboxScreenshot(
  source: Blob,
  catalog: TarkovKeyOcrCatalogKey[],
  opts?: {
    onProgress?: ProgressFn;
    onOverlay?: (overlay: TarkovKeyOcrOverlay) => void;
  },
): Promise<TarkovKeyOcrRecognizeResult> {
  const loaded = await loadKeyboxImage(source);
  try {
    const grid = detectKeyboxGrid(loaded.data, loaded.width, loaded.height);
    const overlay = buildKeyOcrOverlay(grid, loaded.data, loaded.width, loaded.height);
    opts?.onOverlay?.(cloneKeyOcrOverlay(overlay));

    const batches: TarkovKeyOcrMatch[][] = [];
    if (!grid) {
      opts?.onProgress?.("recognizing text", 0.1);
      const whole = await recognizeOcrImage(source, INVENTORY_OCR_PROFILE, {
        onProgress: opts?.onProgress,
      });
      batches.push(
        matchKeysFromOcr({
          texts: whole.rawTexts,
          words: whole.words,
          catalog,
        }),
      );
      opts?.onOverlay?.(cloneKeyOcrOverlay(overlay));
      return { matches: mergeMatches(batches), overlay };
    }

    opts?.onProgress?.("matching icons", 0.08);
    const templates = loadKeyIconTemplates(catalog);
    const ocrCells = new Map<string, string[]>();
    const iconMatched = new Set<string>();
    const total = Math.max(1, grid.cells.length);
    grid.cells.forEach((cell, index) => {
      if (index % 8 === 0) {
        opts?.onProgress?.("matching icons", 0.08 + (0.52 * index) / total);
      }
      const body = keyIconBodyRect(cell);
      if (!keyNameBandHasInk(loaded.data, loaded.width, loaded.height, body)) return;
      const sample = sampleIconFromRgba(loaded.data, loaded.width, loaded.height, body);
      const hit = matchKeyIcon(sample, templates);
      const key = `${cell.row},${cell.col}`;
      if (hit.kind === "unique") {
        const matched = catalogMatch(hit.hit.id, catalog);
        if (!matched) return;
        iconMatched.add(key);
        batches.push([matched]);
        annotateOverlayCell(overlay, cell.row, cell.col, {
          matchShort: matched.short_name,
          fromIcon: true,
        });
        return;
      }
      if (hit.kind === "cluster") {
        ocrCells.set(key, hit.hits.map((row) => row.id));
        return;
      }
      if (hit.kind === "none") {
        ocrCells.set(key, catalog.map((row) => row.id));
      }
    });

    if (ocrCells.size) {
      const rows = cellsByRow(grid);
      const chunks = keyRowSheetChunks(grid.cols);
      const rowWork = Math.max(rows.length * chunks.length, 1);
      let done = 0;
      for (let i = 0; i < rows.length; i += 1) {
        const row = rows[i].filter((cell) => ocrCells.has(`${cell.row},${cell.col}`));
        if (!row.length) continue;
        for (const chunk of chunks) {
          opts?.onProgress?.("recognizing text", 0.62 + (0.35 * done) / rowWork);
          done += 1;
          const slice = row.filter(
            (cell) => cell.col >= chunk.start && cell.col < chunk.start + chunk.count,
          );
          if (!slice.length) continue;
          const sheet = paintRowSheet(
            loaded.source,
            loaded.data,
            loaded.width,
            loaded.height,
            slice,
            chunk.start,
            chunk.count,
          );
          if (!sheet) continue;
          const layout = keyRowSheetLayout(chunk.count);
          const recognized = await recognizeOcrImage(sheet, KEY_ROW_OCR_PROFILE);
          const cellTexts = groupWordsByRowColumn(recognized.words as TarkovOcrWord[], layout);
          const cellHits = cellTexts.flatMap((text, local) => {
            if (!text) return [];
            const col = chunk.start + local;
            const rowIndex = slice[0]?.row ?? i;
            const allowIds = ocrCells.get(`${rowIndex},${col}`);
            if (!allowIds) return [];
            const hits = matchKeysFromOcr({ tokens: [text], catalog, allowIds });
            annotateOverlayCell(overlay, rowIndex, col, {
              ocrText: text,
              matchShort: hits[0]?.short_name,
            });
            return hits;
          });
          if (cellHits.length) batches.push(cellHits);
        }
      }
    }

    opts?.onProgress?.("recognizing text", 0.78);
    const whole = await recognizeOcrImage(source, INVENTORY_OCR_PROFILE, {
      onProgress: (status, progress) => {
        opts?.onProgress?.(status, 0.78 + progress * 0.2);
      },
    });
    for (const word of whole.words) {
      const point = wordSourcePoint(word, loaded.width, loaded.height);
      if (!point) continue;
      const cell = findKeyGridCell(grid, point.x, point.y);
      if (!cell) continue;
      const key = `${cell.row},${cell.col}`;
      if (iconMatched.has(key)) continue;
      const allowIds = ocrCells.get(key);
      if (!allowIds) continue;
      const hits = matchKeysFromOcr({
        tokens: [word.text],
        catalog,
        allowIds,
      });
      if (hits.length) batches.push(hits);
      annotateOverlayCell(overlay, cell.row, cell.col, {
        ocrText: word.text,
        matchShort: hits[0]?.short_name,
        fromWhole: true,
      });
    }

    opts?.onOverlay?.(cloneKeyOcrOverlay(overlay));
    return { matches: mergeMatches(batches), overlay };
  } finally {
    loaded.release?.();
  }
}
