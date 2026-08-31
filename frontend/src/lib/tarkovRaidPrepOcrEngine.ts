import {
  isNearWidescreen,
  mergeOcrRawTexts,
  raidPrepOcrListCropRect,
} from "@/lib/tarkovRaidPrepOcr";
import {
  RAID_PREP_OCR_PROFILE,
  prepareOcrCanvas,
  preloadTarkovOcrWorker,
  recognizeOcrImage,
  terminateTarkovOcrWorker,
} from "@/lib/tarkovOcrEngine";

export type RaidPrepOcrRecognizeResult = {
  width: number;
  height: number;
  preferredSize: boolean;
  widescreen: boolean;
  lines: string[];
  rawText: string;
};

/** 裁切任务列表区并做对比度增强，供 OCR。 */
export async function prepareRaidPrepOcrCanvas(
  source: Blob | ImageBitmap | HTMLImageElement | HTMLCanvasElement,
  opts: { invert?: boolean; contrast?: "normal" | "high" } = {},
): Promise<{ canvas: HTMLCanvasElement; width: number; height: number }> {
  return prepareOcrCanvas(source, {
    invert: opts.invert,
    contrast: opts.contrast,
    scale: RAID_PREP_OCR_PROFILE.scale,
    crop: raidPrepOcrListCropRect,
    minWidth: RAID_PREP_OCR_PROFILE.minWidth,
    minHeight: RAID_PREP_OCR_PROFILE.minHeight,
    tooSmallMessage: RAID_PREP_OCR_PROFILE.tooSmallMessage,
  });
}

export function preloadRaidPrepOcrWorker(): void {
  preloadTarkovOcrWorker();
}

export async function recognizeRaidPrepTaskScreenshot(
  source: Blob | ImageBitmap | HTMLImageElement | HTMLCanvasElement,
  opts?: { onProgress?: (status: string, progress: number) => void },
): Promise<RaidPrepOcrRecognizeResult> {
  const result = await recognizeOcrImage(
    source,
    {
      ...RAID_PREP_OCR_PROFILE,
      crop: raidPrepOcrListCropRect,
    },
    opts,
  );
  return {
    width: result.width,
    height: result.height,
    preferredSize:
      (result.width === 1920 && result.height === 1080) ||
      (result.width === 2560 && result.height === 1440),
    widescreen: isNearWidescreen(result.width, result.height),
    lines: mergeOcrRawTexts(...result.rawTexts),
    rawText: result.rawTexts.filter(Boolean).join("\n"),
  };
}

export async function terminateRaidPrepOcrWorker(): Promise<void> {
  await terminateTarkovOcrWorker();
}
