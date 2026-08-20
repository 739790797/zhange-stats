/** 对齐 tarkov.dev bitcoin-farm-calculator：GPU 数量缩放产出间隔。 */

export const BITCOIN_ITEM_ID = "59faff1d86f7746c51718c9c";
export const GRAPHIC_CARD_ITEM_ID = "57347ca924597744596b4e71";
export const MIN_GRAPHICS_CARDS = 1;
export const MAX_GRAPHICS_CARDS = 50;

/** 1 张显卡时的基准秒数（Wiki ≈ 20h51m）；有制作数据时用上游 duration。 */
export const DEFAULT_BITCOIN_DURATION_SEC = 75_116;

const GPU_SPEED_FACTOR = 0.041225;

export function bitcoinMsToProduce(
  gpuCount: number,
  durationSec = DEFAULT_BITCOIN_DURATION_SEC,
): number {
  const gpus = Math.min(
    MAX_GRAPHICS_CARDS,
    Math.max(MIN_GRAPHICS_CARDS, Math.round(gpuCount) || 1),
  );
  const seconds = durationSec / (1 + (gpus - 1) * GPU_SPEED_FACTOR);
  return seconds * 1000;
}

export function bitcoinPerDay(
  gpuCount: number,
  durationSec = DEFAULT_BITCOIN_DURATION_SEC,
): number {
  const ms = bitcoinMsToProduce(gpuCount, durationSec);
  if (!ms) return 0;
  return (24 * 60 * 60 * 1000) / ms;
}
