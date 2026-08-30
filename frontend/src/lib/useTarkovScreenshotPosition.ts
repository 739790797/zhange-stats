import { useTarkovLiveWatch } from "@/lib/tarkovLiveWatchContext";

export type { TarkovScreenshotFix, LiveWatchPerm as ScreenshotWatchPerm } from "@/lib/tarkovLiveWatchContext";

/** 地图页消费全站截图轮询；授权按钮仍走同一套目录。 */
export function useTarkovScreenshotPosition() {
  const live = useTarkovLiveWatch();
  return {
    supported: live.supported,
    perm: live.shotPerm,
    hasStored: live.hasStoredShots,
    storedLabel: live.shotLabel,
    fix: live.fix,
    lastFileName: live.lastShotName,
    busy: live.shotBusy,
    enable: live.enableShots,
  };
}
