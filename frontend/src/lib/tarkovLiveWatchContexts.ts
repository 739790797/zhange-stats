import { createContext } from "react";
import type { TarkovLogPhasePayload, TarkovLogPreviewRaid, TarkovLogSessionStub } from "@/lib/tarkovGameLogs";
import type { QuestLogSyncReview } from "@/lib/tarkovTaskLogSync";
import type { TarkovLogSyncOpts } from "@/lib/tarkovLogSyncRange";
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
  logSyncBusy: boolean;
  logSyncScan: { done: number; total: number } | null;
  enableShots: () => Promise<void>;
  resume: () => Promise<void>;
  /** 读每次启动的 application.log，带上身份和战局；结束时间可能还空着。 */
  previewLogSessions: () => Promise<{
    ok: boolean;
    hint: string;
    sessions: TarkovLogSessionStub[];
  }>;
  /** 按日期范围排队解析启动文件夹；只上传任务 id。 */
  syncLogs: (opts?: TarkovLogSyncOpts) => Promise<{
    ok: boolean;
    hint: string;
    review?: QuestLogSyncReview;
  }>;
  cancelLogSync: () => void;
  /** 账号上已记下的回放下限；没有则空字符串。 */
  readQuestFloor: () => Promise<string>;
  /** 补读这一次启动的通知日志，取该局结束时间。没有则空字符串。 */
  resolveRaidEndedAt: (
    folder: string,
    raid: Pick<TarkovLogPreviewRaid, "raidId" | "startedAt">,
  ) => Promise<string>;
  /** 取消已写入账号的转生归档。 */
  releaseQuestFloor: () => Promise<void>;
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
  logSyncBusy: false,
  logSyncScan: null,
  enableShots: async () => undefined,
  resume: async () => undefined,
  previewLogSessions: async () => ({ ok: false, hint: "", sessions: [] }),
  syncLogs: async () => ({ ok: false, hint: "" }),
  cancelLogSync: () => undefined,
  readQuestFloor: async () => "",
  resolveRaidEndedAt: async () => "",
  releaseQuestFloor: async () => undefined,
};

/** 日志回填按钮只关心这几项；与总 value 分开，免得 lastLogAt / 截图坐标一变就重绘备战页。 */
export type TarkovLogSyncValue = Pick<
  TarkovLiveWatchValue,
  | "previewLogSessions"
  | "syncLogs"
  | "cancelLogSync"
  | "readQuestFloor"
  | "resolveRaidEndedAt"
  | "releaseQuestFloor"
> & {
  busy: boolean;
  scan: { done: number; total: number } | null;
};

export const EMPTY_LOG_SYNC: TarkovLogSyncValue = {
  busy: false,
  scan: null,
  previewLogSessions: EMPTY_LIVE_WATCH.previewLogSessions,
  syncLogs: EMPTY_LIVE_WATCH.syncLogs,
  cancelLogSync: EMPTY_LIVE_WATCH.cancelLogSync,
  readQuestFloor: async () => "",
  resolveRaidEndedAt: async () => "",
  releaseQuestFloor: async () => undefined,
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
export const TarkovLogSyncContext =
  createContext<TarkovLogSyncValue>(EMPTY_LOG_SYNC);
