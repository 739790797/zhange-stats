import { ocrOutputScale } from "@/lib/tarkovOcr";

/** 中英 LSTM；钥匙短码是拉丁文，任务名是中文。模型用 tessdata_fast，与 public/tesseract 对齐。 */
export const TARKOV_OCR_LANGS = "chi_sim+eng";

export type TarkovOcrPass = "normal" | "invert";
export type TarkovOcrPsm = "single_column" | "sparse_text" | "auto";
export type TarkovOcrContrast = "normal" | "high";

export type TarkovOcrCropRect = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type TarkovOcrWord = {
  text: string;
  confidence: number;
  x0?: number;
  y0?: number;
  x1?: number;
  y1?: number;
};

export type TarkovOcrRecognizeResult = {
  width: number;
  height: number;
  rawTexts: string[];
  words: TarkovOcrWord[];
};

export type TarkovOcrProfile = {
  psm: TarkovOcrPsm;
  dpi: number;
  scale: number;
  passes: TarkovOcrPass[];
  contrast: TarkovOcrContrast;
  minWidth: number;
  minHeight: number;
  tooSmallMessage: string;
  maxEdge?: number;
  crop?: (width: number, height: number) => TarkovOcrCropRect;
};

/** 局前任务列表：单列 + 反色，沿用现有裁切。 */
export const RAID_PREP_OCR_PROFILE: TarkovOcrProfile = {
  psm: "single_column",
  dpi: 200,
  scale: 2,
  passes: ["invert"],
  contrast: "normal",
  minWidth: 640,
  minHeight: 360,
  tooSmallMessage: "图片过小，请使用任务页全屏截图",
};

/**
 * 仓库 / 钥匙格：稀疏文本（RatEye shortName、识价 bot 整图 OCR）。
 * 双通道合并，暗色格子反色、浅色检视窗走原图。
 */
export const INVENTORY_OCR_PROFILE: TarkovOcrProfile = {
  psm: "sparse_text",
  dpi: 220,
  scale: 2,
  passes: ["invert", "normal"],
  contrast: "high",
  minWidth: 400,
  minHeight: 280,
  tooSmallMessage: "图片过小，请使用游戏内钥匙格截图",
  maxEdge: 1920,
};

type ImageBitmapLike = {
  width: number;
  height: number;
  close?: () => void;
};

type LoadedImage = {
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
};

const OCR_WORKER_TIMEOUT_MS = 60_000;
const WORD_MIN_CONFIDENCE = 40;

let workerPromise: Promise<import("tesseract.js").Worker> | null = null;

export function tarkovOcrPublicUrl(rel: string): string {
  const base = (import.meta.env.BASE_URL || "/").replace(/\/?$/, "/");
  return `${base}${rel.replace(/^\//, "")}`;
}

export type TarkovOcrWorkerAssets = {
  langPath?: string;
  workerPath?: string;
  corePath?: string;
  cacheMethod?: "none" | "write" | "readOnly" | "refresh";
};

let ocrWorkerAssets: TarkovOcrWorkerAssets = {};

/** 夹具 / Node 跑同一套引擎时改成本地模型路径；浏览器不调用。 */
export function configureTarkovOcrAssets(next: TarkovOcrWorkerAssets): void {
  ocrWorkerAssets = { ...next };
}

type CanvasFactory = () => HTMLCanvasElement;

let createOcrCanvas: CanvasFactory = () => document.createElement("canvas");

/** Node 夹具注入 canvas；浏览器不调用。 */
export function setTarkovOcrCanvasFactory(factory: CanvasFactory | null): void {
  createOcrCanvas = factory || (() => document.createElement("canvas"));
}

export function newTarkovOcrCanvas(): HTMLCanvasElement {
  return createOcrCanvas();
}

function withTimeout<T>(promise: Promise<T>, ms: number, message: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = globalThis.setTimeout(() => reject(new Error(message)), ms);
    promise.then(
      (value) => {
        globalThis.clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        globalThis.clearTimeout(timer);
        reject(error);
      },
    );
  });
}

function isCanvasLike(
  source: unknown,
): source is HTMLCanvasElement & { toBuffer?: (mime?: string) => Buffer } {
  return Boolean(
    source &&
      typeof source === "object" &&
      typeof (source as { getContext?: unknown }).getContext === "function" &&
      "width" in source &&
      "height" in source,
  );
}

function sourceForWorker(canvas: HTMLCanvasElement): HTMLCanvasElement | Buffer {
  const nodeCanvas = canvas as HTMLCanvasElement & {
    toBuffer?: (mime?: string) => Buffer;
  };
  if (typeof nodeCanvas.toBuffer === "function") {
    return nodeCanvas.toBuffer("image/png");
  }
  return canvas;
}

type OcrProgressFn = (status: string, progress: number) => void;

export async function loadOcrImageSource(
  source: Blob | ImageBitmap | HTMLImageElement | HTMLCanvasElement,
): Promise<LoadedImage> {
  if (typeof ImageBitmap !== "undefined" && source instanceof ImageBitmap) {
    return {
      width: source.width,
      height: source.height,
      drawCrop: (ctx, sx, sy, sw, sh, dw, dh) =>
        ctx.drawImage(source, sx, sy, sw, sh, 0, 0, dw, dh),
      release: () => source.close(),
    };
  }
  if (isCanvasLike(source)) {
    return {
      width: source.width,
      height: source.height,
      drawCrop: (ctx, sx, sy, sw, sh, dw, dh) =>
        ctx.drawImage(source, sx, sy, sw, sh, 0, 0, dw, dh),
    };
  }
  if (typeof HTMLImageElement !== "undefined" && source instanceof HTMLImageElement) {
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

export async function prepareOcrCanvas(
  source: Blob | ImageBitmap | HTMLImageElement | HTMLCanvasElement,
  opts: {
    invert?: boolean;
    contrast?: TarkovOcrContrast;
    scale?: number;
    maxEdge?: number;
    crop?: (width: number, height: number) => TarkovOcrCropRect;
    minWidth?: number;
    minHeight?: number;
    tooSmallMessage?: string;
  } = {},
): Promise<{ canvas: HTMLCanvasElement; width: number; height: number }> {
  const invert = Boolean(opts.invert);
  const high = opts.contrast === "high";
  const loaded = await loadOcrImageSource(source);
  try {
    const { width, height } = loaded;
    const minW = opts.minWidth ?? 400;
    const minH = opts.minHeight ?? 280;
    if (width < minW || height < minH) {
      throw new Error(opts.tooSmallMessage || "图片过小，请使用更清晰的截图");
    }
    const crop = opts.crop?.(width, height) ?? {
      x: 0,
      y: 0,
      width,
      height,
    };
    const scale = ocrOutputScale(
      crop.width,
      crop.height,
      opts.scale ?? 2,
      opts.maxEdge ?? 2560,
    );
    const canvas = newTarkovOcrCanvas();
    canvas.width = Math.max(1, Math.round(crop.width * scale));
    canvas.height = Math.max(1, Math.round(crop.height * scale));
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
      let gray = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
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

async function psmValue(
  mode: TarkovOcrPsm,
): Promise<import("tesseract.js").PSM> {
  const { PSM } = await import("tesseract.js");
  if (mode === "sparse_text") return PSM.SPARSE_TEXT;
  if (mode === "auto") return PSM.AUTO;
  return PSM.SINGLE_COLUMN;
}

async function getOcrWorker(
  onProgress?: OcrProgressFn,
): Promise<import("tesseract.js").Worker> {
  if (!workerPromise) {
    workerPromise = (async () => {
      const { createWorker, PSM } = await import("tesseract.js");
      const worker = await withTimeout(
        createWorker(TARKOV_OCR_LANGS, 1, {
          langPath: ocrWorkerAssets.langPath ?? tarkovOcrPublicUrl("tesseract"),
          gzip: false,
          workerBlobURL: false,
          ...(ocrWorkerAssets.workerPath
            ? { workerPath: ocrWorkerAssets.workerPath }
            : typeof document === "object"
              ? { workerPath: tarkovOcrPublicUrl("tesseract/worker.min.js") }
              : {}),
          ...(ocrWorkerAssets.corePath
            ? { corePath: ocrWorkerAssets.corePath }
            : typeof document === "object"
              ? { corePath: tarkovOcrPublicUrl("tesseract/core") }
              : {}),
          ...(ocrWorkerAssets.cacheMethod
            ? { cacheMethod: ocrWorkerAssets.cacheMethod }
            : {}),
          logger: (message) => {
            onProgress?.(message.status || "", message.progress || 0);
          },
        }),
        OCR_WORKER_TIMEOUT_MS,
        "识别引擎加载超时，请刷新页面后重试",
      );
      await worker.setParameters({
        tessedit_pageseg_mode: PSM.SINGLE_COLUMN,
        preserve_interword_spaces: "1",
      });
      return worker;
    })().catch((error) => {
      workerPromise = null;
      throw error;
    });
  }
  return workerPromise;
}

export function preloadTarkovOcrWorker(): void {
  void getOcrWorker();
}

function collectWords(raw: unknown): TarkovOcrWord[] {
  if (!Array.isArray(raw)) return [];
  const out: TarkovOcrWord[] = [];
  for (const row of raw) {
    if (!row || typeof row !== "object") continue;
    const text = String((row as { text?: unknown }).text || "").trim();
    const confidence = Number((row as { confidence?: unknown }).confidence);
    if (!text || !Number.isFinite(confidence) || confidence < WORD_MIN_CONFIDENCE) {
      continue;
    }
    const bbox = (row as { bbox?: { x0?: unknown; y0?: unknown; x1?: unknown; y1?: unknown } }).bbox;
    const x0 = Number(bbox?.x0);
    const y0 = Number(bbox?.y0);
    const x1 = Number(bbox?.x1);
    const y1 = Number(bbox?.y1);
    out.push({
      text,
      confidence,
      ...(Number.isFinite(x0) ? { x0 } : {}),
      ...(Number.isFinite(y0) ? { y0 } : {}),
      ...(Number.isFinite(x1) ? { x1 } : {}),
      ...(Number.isFinite(y1) ? { y1 } : {}),
    });
  }
  return out;
}

export async function recognizeOcrImage(
  source: Blob | ImageBitmap | HTMLImageElement | HTMLCanvasElement,
  profile: TarkovOcrProfile,
  opts?: { onProgress?: OcrProgressFn },
): Promise<TarkovOcrRecognizeResult> {
  const worker = await getOcrWorker(opts?.onProgress);
  const psm = await psmValue(profile.psm);
  const passes = profile.passes.length ? profile.passes : (["invert"] as TarkovOcrPass[]);
  const rawTexts: string[] = [];
  const words: TarkovOcrWord[] = [];
  let width = 0;
  let height = 0;

  for (let i = 0; i < passes.length; i += 1) {
    const pass = passes[i];
    opts?.onProgress?.(
      "recognizing text",
      passes.length > 1 ? i / passes.length : 0,
    );
    const prepared = await prepareOcrCanvas(source, {
      invert: pass === "invert",
      contrast: profile.contrast,
      scale: profile.scale,
      maxEdge: profile.maxEdge,
      crop: profile.crop,
      minWidth: profile.minWidth,
      minHeight: profile.minHeight,
      tooSmallMessage: profile.tooSmallMessage,
    });
    width = prepared.width;
    height = prepared.height;
    await worker.setParameters({
      tessedit_pageseg_mode: psm,
      preserve_interword_spaces: "1",
      user_defined_dpi: String(profile.dpi),
    });
    const recognized = await worker.recognize(sourceForWorker(prepared.canvas));
    rawTexts.push(recognized.data.text || "");
    words.push(...collectWords((recognized.data as { words?: unknown }).words));
  }
  opts?.onProgress?.("recognizing text", 1);

  return { width, height, rawTexts, words };
}

export async function terminateTarkovOcrWorker(): Promise<void> {
  if (!workerPromise) return;
  const pending = workerPromise;
  workerPromise = null;
  try {
    const worker = await Promise.race([
      pending,
      new Promise<null>((resolve) => {
        globalThis.setTimeout(() => resolve(null), 2000);
      }),
    ]);
    if (worker) await worker.terminate();
  } catch {
    /* ignore */
  }
}
