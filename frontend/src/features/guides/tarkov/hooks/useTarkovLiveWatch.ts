import { useContext } from "react";
import type { TarkovLogPhasePayload } from "@/features/guides/tarkov/model/tarkovGameLogs";
import {
  TarkovLiveFixContext,
  TarkovLiveLogMapContext,
  TarkovLiveLogPhaseContext,
  TarkovLiveShotMetaContext,
  TarkovLiveWatchContext,
  TarkovLogSyncContext,
  type TarkovLiveShotMeta,
  type TarkovLogSyncValue,
  type TarkovLiveWatchValue,
  type TarkovScreenshotFix,
} from "@/features/guides/tarkov/providers/tarkovLiveWatchContexts";

export function useTarkovLiveWatch(): TarkovLiveWatchValue {
  return useContext(TarkovLiveWatchContext);
}

export function useTarkovScreenshotFix(): TarkovScreenshotFix | null {
  return useContext(TarkovLiveFixContext);
}

export function useTarkovLastLogMapId(): string {
  return useContext(TarkovLiveLogMapContext);
}

export function useTarkovLastLogPhase(): TarkovLogPhasePayload | null {
  return useContext(TarkovLiveLogPhaseContext);
}

export function useTarkovLiveShotMeta(): TarkovLiveShotMeta {
  return useContext(TarkovLiveShotMetaContext);
}

/** 日志回填专用；不随 lastLogAt / 截图坐标变化。 */
export function useTarkovLogSync(): TarkovLogSyncValue {
  return useContext(TarkovLogSyncContext);
}
