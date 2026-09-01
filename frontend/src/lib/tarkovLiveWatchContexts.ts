import { createContext } from "react";
import type { TarkovLogPhasePayload } from "@/lib/tarkovGameLogs";
import type { TarkovScreenshotPos } from "@/lib/tarkovScreenshotPos";

export type TarkovScreenshotFix = TarkovScreenshotPos & {
  fileName: string;
  lastModified: number;
};

export type LiveWatchPerm = "unknown" | "none" | "prompt" | "granted";

export type TarkovLiveWatchValue = {
  supported: boolean;
  visible: boolean;
  shotPerm: LiveWatchPerm;
  logPerm: LiveWatchPerm;
  hasStoredShots: boolean;
  hasStoredLogs: boolean;
  shotLabel: string;
  logLabel: string;
  lastShotAt: number | string | null;
  lastLogAt: number | string | null;
  lastShotName: string;
  lastLogMapId: string;
  fix: TarkovScreenshotFix | null;
  shotBusy: boolean;
  enableShots: () => Promise<void>;
  resume: () => Promise<void>;
};

export const EMPTY_LIVE_WATCH: TarkovLiveWatchValue = {
  supported: false,
  visible: false,
  shotPerm: "none",
  logPerm: "none",
  hasStoredShots: false,
  hasStoredLogs: false,
  shotLabel: "",
  logLabel: "",
  lastShotAt: null,
  lastLogAt: null,
  lastShotName: "",
  lastLogMapId: "",
  fix: null,
  shotBusy: false,
  enableShots: async () => undefined,
  resume: async () => undefined,
};

export type TarkovLiveShotMeta = {
  supported: boolean;
  perm: LiveWatchPerm;
  hasStored: boolean;
  storedLabel: string;
  busy: boolean;
  enable: () => Promise<void>;
};

export const EMPTY_SHOT_META: TarkovLiveShotMeta = {
  supported: false,
  perm: "none",
  hasStored: false,
  storedLabel: "",
  busy: false,
  enable: async () => undefined,
};

export const TarkovLiveWatchContext =
  createContext<TarkovLiveWatchValue>(EMPTY_LIVE_WATCH);
export const TarkovLiveFixContext = createContext<TarkovScreenshotFix | null>(
  null,
);
export const TarkovLiveLogMapContext = createContext("");
export const TarkovLiveLogPhaseContext =
  createContext<TarkovLogPhasePayload | null>(null);
export const TarkovLiveShotMetaContext =
  createContext<TarkovLiveShotMeta>(EMPTY_SHOT_META);
