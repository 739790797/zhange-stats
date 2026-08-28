import {
  isNearWidescreen,
  mergeOcrRawTexts,
  RAID_PREP_OCR_DPI,
  RAID_PREP_OCR_SCALE,
  raidPrepOcrListCropRect,
} from "@/lib/tarkovRaidPrepOcr";

export type RaidPrepOcrRecognizeResult = {
  width: number;
  height: number;
  preferredSize: boolean;
  widescreen: boolean;
  lines: string[];
  rawText: string;
};

type ImageBitmapLike = {
  width: number;
  height: number;
  close?: () => void;
};

async function loadImageSource(
  source: Blob | ImageBitmap | HTMLImageElement | HTMLCanvasElement,
): Promise<{
  width: number;
  height: number;
  drawCrop: (
    ctx: CanvasRenderingContext2D,
    sx: number,
    sy: number,
    sw: number,
    sh: number,
    dw: number,
    dh: number,
  ) => void;
  release?: () => void;
}> {
  if (typeof ImageBitmap !== "undefined" && source instanceof ImageBitmap) {
    return {
      width: source.width,
      height: source.height,
      drawCrop: (ctx, sx, sy, sw, sh, dw, dh) =>
        ctx.drawImage(source, sx, sy, sw, sh, 0, 0, dw, dh),
      release: () => source.close(),
    };
  }
  if (source instanceof HTMLCanvasElement) {
    return {
      width: source.width,
      height: source.height,
      drawCrop: (ctx, sx, sy, sw, sh, dw, dh) =>
        ctx.drawImage(source, sx, sy, sw, sh, 0, 0, dw, dh),
    };
  }
  if (source instanceof HTMLImageElement) {
    const width = source.naturalWidth || source.width;
    const height = source.naturalHeight || source.height;
    return {
      width,
      height,
      drawCrop: (ctx, sx, sy, sw, sh, dw, dh) =>
        ctx.drawImage(source, sx, sy, sw, sh, 0, 0, dw, dh),
    };
  }

  const blob = source as Blob;
  if (typeof createImageBitmap === "function") {
    const bitmap = (await createImageBitmap(blob)) as ImageBitmapLike;
    return {
      width: bitmap.width,
      height: bitmap.height,
      drawCrop: (ctx, sx, sy, sw, sh, dw, dh) =>
        ctx.drawImage(bitmap as ImageBitmap, sx, sy, sw, sh, 0, 0, dw, dh),
      release: () => bitmap.close?.(),
    };
  }

  const url = URL.createObjectURL(blob);
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("图片读取失败"));
      img.src = url;
    });
    return {
      width: image.naturalWidth || image.width,
      height: image.naturalHeight || image.height,
      drawCrop: (ctx, sx, sy, sw, sh, dw, dh) =>
        ctx.drawImage(image, sx, sy, sw, sh, 0, 0, dw, dh),
    };
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** 裁切任务列表区并做对比度增强，供 OCR。 */
export async function prepareRaidPrepOcrCanvas(
  source: Blob | ImageBitmap | HTMLImageElement | HTMLCanvasElement,
  opts: { invert?: boolean; contrast?: "normal" | "high" } = {},
): Promise<{ canvas: HTMLCanvasElement; width: number; height: number }> {
  const invert = Boolean(opts.invert);
  const high = opts.contrast === "high";
  const loaded = await loadImageSource(source);
  try {
    const { width, height } = loaded;
    if (width < 640 || height < 360) {
      throw new Error("图片过小，请使用任务页全屏截图");
    }
    const crop = raidPrepOcrListCropRect(width, height);
    const scale = RAID_PREP_OCR_SCALE;
    const canvas = document.createElement("canvas");
    canvas.width = crop.width * scale;
    canvas.height = crop.height * scale;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) throw new Error("无法创建画布");
    ctx.imageSmoothingEnabled = true;
    loaded.drawCrop(
      ctx,
      crop.x,
      crop.y,
      crop.width,
      crop.height,
      canvas.width,
      canvas.height,
    );

    const image = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const data = image.data;
    const offset = invert ? 35 : high ? 28 : 40;
    const boost = invert ? 1.35 : high ? 1.75 : 1.35;
    for (let i = 0; i < data.length; i += 4) {
      let gray =
        0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
      if (invert) gray = 255 - gray;
      const boosted = Math.min(255, Math.max(0, (gray - offset) * boost));
      data[i] = boosted;
      data[i + 1] = boosted;
      data[i + 2] = boosted;
    }
    ctx.putImageData(image, 0, 0);
    return { canvas, width, height };
  } finally {
    loaded.release?.();
  }
}

let workerPromise: Promise<import("tesseract.js").Worker> | null = null;

function raidPrepOcrLangPath(): string {
  const base = (import.meta.env.BASE_URL || "/").replace(/\/?$/, "/");
  return `${base}tesseract`;
}

async function getOcrWorker(): Promise<import("tesseract.js").Worker> {
  if (!workerPromise) {
    workerPromise = (async () => {
      const { createWorker, PSM } = await import("tesseract.js");
      const worker = await createWorker("chi_sim", 1, {
        langPath: raidPrepOcrLangPath(),
        logger: () => undefined,
      });
      await worker.setParameters({
        tessedit_pageseg_mode: PSM.SINGLE_COLUMN,
        preserve_interword_spaces: "1",
        user_defined_dpi: String(RAID_PREP_OCR_DPI),
      });
      return worker;
    })().catch((error) => {
      workerPromise = null;
      throw error;
    });
  }
  return workerPromise;
}

export async function recognizeRaidPrepTaskScreenshot(
  source: Blob | ImageBitmap | HTMLImageElement | HTMLCanvasElement,
): Promise<RaidPrepOcrRecognizeResult> {
  const worker = await getOcrWorker();
  const inverted = await prepareRaidPrepOcrCanvas(source, { invert: true });
  const invertedResult = await worker.recognize(inverted.canvas);
  const text = invertedResult.data.text || "";
  return {
    width: inverted.width,
    height: inverted.height,
    preferredSize:
      (inverted.width === 1920 && inverted.height === 1080) ||
      (inverted.width === 2560 && inverted.height === 1440),
    widescreen: isNearWidescreen(inverted.width, inverted.height),
    lines: mergeOcrRawTexts(text),
    rawText: text,
  };
}

export async function terminateRaidPrepOcrWorker(): Promise<void> {
  if (!workerPromise) return;
  const pending = workerPromise;
  workerPromise = null;
  try {
    const worker = await pending;
    await worker.terminate();
  } catch {
    /* ignore */
  }
}
