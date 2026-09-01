import {
  useTarkovLiveShotMeta,
  useTarkovScreenshotFix,
} from "@/lib/useTarkovLiveWatch";

export type { TarkovScreenshotFix, LiveWatchPerm as ScreenshotWatchPerm } from "@/lib/tarkovLiveWatchContexts";

/** 地图页消费全站截图轮询；授权按钮仍走同一套目录。 */
export function useTarkovScreenshotPosition() {
  const meta = useTarkovLiveShotMeta();
  const fix = useTarkovScreenshotFix();
  return {
    supported: meta.supported,
    perm: meta.perm,
    hasStored: meta.hasStored,
    storedLabel: meta.storedLabel,
    fix,
    lastFileName: fix?.fileName || "",
    busy: meta.busy,
    enable: meta.enable,
  };
}
