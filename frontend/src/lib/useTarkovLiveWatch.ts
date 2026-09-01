import { useContext } from "react";
import type { TarkovLogPhasePayload } from "@/lib/tarkovGameLogs";
import {
  TarkovLiveFixContext,
  TarkovLiveLogMapContext,
  TarkovLiveLogPhaseContext,
  TarkovLiveShotMetaContext,
  TarkovLiveWatchContext,
  type TarkovLiveShotMeta,
  type TarkovLiveWatchValue,
  type TarkovScreenshotFix,
} from "@/lib/tarkovLiveWatchContexts";

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
