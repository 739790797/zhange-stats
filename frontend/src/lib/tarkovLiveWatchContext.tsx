import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchTarkovTaskDonesFor,
  fetchTarkovTasks,
  importTarkovRaidLogs,
  recordTarkovTaskProfile,
  resetTarkovTaskProgress,
  writeTaskProgressLedger,
  type TarkovTaskDones,
  type TarkovTaskListItem,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useAuthStore } from "@/stores/authStore";
import {
  createTarkovLogReadCache,
  forgetTarkovLogDirs,
  isFileSystemAccessSupported,
  isPickerAbort,
  loadStoredLogsDir,
  loadStoredLogsPath,
  loadStoredScreenshotsDir,
  loadStoredScreenshotsPath,
  listScreenshotFileNames,
  observeDirectory,
  peekSessionFingerprint,
  pickLogsDirectory,
  pickScreenshotsDirectory,
  pollLatestScreenshot,
  queryLogsDirPermission,
  queryScreenshotsDirPermission,
  readScreenshotByName,
  removeScreenshotFiles,
  readLogsIndex,
  readSessionApplicationLogs,
  readSessionLogs,
  readStattedSessionLogs,
  requestLogsDirPermission,
  requestScreenshotsDirPermission,
  retainTarkovLogFolders,
  saveLogsDir,
  saveScreenshotsDir,
  screenshotsDirCanWrite,
  statSessionLogs,
  type ReadableDir,
} from "@/lib/tarkovGameLogAccess";
import {
  TARKOV_SCREENSHOT_POLL_MS,
  TARKOV_SCREENSHOT_PRUNE_BATCH,
  TARKOV_SCREENSHOT_PRUNE_EVENT,
  isNewerScreenshot,
  latestLogMapId,
  latestScreenshotName,
  loadScreenshotPrunePref,
  logPhaseFromParsed,
  parseTarkovLogBundle,
  screenshotNamesToPrune,
  takeSessionStubs,
  toRaidLogImportRows,
  identitiesFromParsed,
  sessionStubInBeijing,
  type TarkovLogBundleMemo,
  type TarkovLogIdentity,
  type TarkovLogPhasePayload,
  type TarkovLogQuestDrop,
  type TarkovLogQuestEvent,
  type TarkovRaidLogImportRow,
} from "@/lib/tarkovGameLogs";
import {
  defaultLogSyncRange,
  filterSessionStubsByRange,
  yieldLogSyncQueue,
  type TarkovLogSyncOpts,
} from "@/lib/tarkovLogSyncRange";
import {
  breakpointMatchesGameMode,
  latestIdentityForMode,
  sessionStubMatchesBreakpoint,
} from "@/lib/tarkovLogBreakpoints";
import {
  loadOfflineMapId,
  resolveOfflineLogMapId,
  TARKOV_OFFLINE_MAP_EVENT,
} from "@/lib/tarkovOfflineMap";
import {
  TARKOV_LIVE_DIRS_EVENT,
  addedIdList,
  formatLiveLogBackfillHint,
  logStampFromParsed,
  nextLiveQuestProgress,
  notifyTarkovTaskProgress,
  planLogSessionReads,
  planRaidLogImport,
  planRaidLogImportRows,
  sameIdLists,
  type LogPollCursor,
} from "@/lib/tarkovLiveWatch";
import {
  TarkovLiveFixContext,
  TarkovLiveLogMapContext,
  TarkovLiveLogPhaseContext,
  TarkovLiveShotMetaContext,
  TarkovLiveWatchContext,
  TarkovLogSyncContext,
  type LiveWatchPerm,
  type TarkovLiveShotMeta,
  type TarkovLogSyncValue,
  type TarkovLiveWatchValue,
  type TarkovScreenshotFix,
} from "@/lib/tarkovLiveWatchContexts";
import { parseTarkovScreenshotName } from "@/lib/tarkovScreenshotPos";
import { keepLogPhase } from "@/lib/tarkovStableValues";
import { formatBeijing, laterBeijingClock, nowBeijingStamp } from "@/lib/time";
import { useTarkovGameMode, type TarkovGameMode } from "@/lib/tarkovGameMode";
import {
  adoptQuestBoundary,
  adoptServerTaskLedger,
  applyQuestReplayReset,
  loadTabQuestEpoch,
  questLedgerIsStale,
  saveQuestServerEpoch,
  loadLocalQuestBoundary,
  loadTaskDoneIds,
  loadTaskFailedIds,
  loadTaskObjectivePairs,
  loadTaskStartedIds,
  clearedDoneAfter,
  loadTaskClearedDone,
  loadQuestProfileId,
  loadQuestProfileResetPending,
  loadQuestProgressFloor,
  loadQuestServerEpoch,
  loadQuestSyncFromLatest,
  saveQuestProfileId,
  questLedgerEpochNow,
  clearQuestProfileResetPending,
  saveTaskProgress,
  saveTaskSyncMark,
  taskProgressQueryData,
  unionTaskProgress,
  ledgerIdsToClear,
} from "@/lib/tarkovTaskTree";
import {
  buildQuestLogCatalog,
  buildQuestLogSyncReview,
  emptyQuestLogCatalog,
  collectQuestReplayDrops,
  foldSessionQuests,
  formatQuestLogDropHint,
  mergeQuestProgressFromFolded,
  questProgressDelta,
  questsMatchingReplay,
  type FoldedQuestEntry,
  type QuestLogCatalog,
  type QuestLogSyncReview,
  type QuestReplayFilter,
} from "@/lib/tarkovTaskLogSync";
import {
  clearedMapFromServer,
  combineQuestBoundary,
  planQuestReplay,
  questBoundaryFromServer,
  type QuestBoundary,
  type QuestResetReason,
} from "@/lib/tarkovQuestBoundary";
import {
  TASK_DONES_QUERY_KEY,
  adoptAccountTaskLedger,
  useTarkovTaskAccountSync,
} from "@/lib/useTarkovTaskAccountSync";
import { dropBlockedProgress } from "@/lib/tarkovTaskLineLedger";
import { applyMutexLedger } from "@/lib/tarkovTaskMutex";
import { TarkovLogSyncReviewModal } from "@/components/guides/tarkov/TarkovLogSyncReviewModal";

function sessionHasProfile(
  identities: readonly TarkovLogIdentity[],
  profileId: string,
  gameMode: TarkovGameMode,
): boolean {
  const wanted = profileId.trim();
  if (!wanted) return false;
  return identities.some((row) => {
    if ((row.profileId || "").trim() !== wanted) return false;
    return breakpointMatchesGameMode(row, gameMode);
  });
}

/** 实时轮询里完整同步失败后的重试间隔。 */
const FULL_SYNC_RETRY_MS = 60_000;

export function TarkovLiveWatchProvider({ children }: { children: ReactNode }) {
  useTarkovTaskAccountSync();
  const supported = isFileSystemAccessSupported();
  const gameMode = useTarkovGameMode();
  const queryClient = useQueryClient();
  const shotRef = useRef<ReadableDir | null>(null);
  const shotDirRef = useRef<ReadableDir | null>(null);
  const shotCanWriteRef = useRef(false);
  const shotPruneRef = useRef<string[]>([]);
  const shotWatchingRef = useRef(false);
  const shotNeedListRef = useRef(false);
  // useRef(loadScreenshotPrunePref()) 每次渲染都会读一遍 localStorage；惰性 useState 只在首帧读，之后靠事件刷新 ref
  const [initialPrunePref] = useState(loadScreenshotPrunePref);
  const shotPrunePrefRef = useRef(initialPrunePref);
  const logRef = useRef<ReadableDir | null>(null);
  const seenShotNamesRef = useRef<Set<string>>(new Set());
  const shotStampRef = useRef<{ name: string; lastModified: number } | null>(
    null,
  );
  const logCursorRef = useRef<LogPollCursor | null>(null);
  const lastParsedRef = useRef<Array<{ parsed: ReturnType<typeof parseTarkovLogBundle> }>>(
    [],
  );
  const endedRaidKeysRef = useRef<Set<string>>(new Set());
  const shotTickBusyRef = useRef(false);
  const logTickBusyRef = useRef(false);
  const syncAbortRef = useRef<AbortController | null>(null);
  /** 实时轮询触发的完整同步失败后，到这个时刻（ms）之前不再自动重试；按 模式|ProfileId 记。 */
  const fullSyncRetryAtRef = useRef<Map<string, number>>(new Map());
  const syncLogsRef = useRef<
    (opts?: TarkovLogSyncOpts) => Promise<{ ok: boolean; hint: string }>
  >(async () => ({ ok: false, hint: "" }));
  const gameModeRef = useRef(gameMode);
  const loggedIn = Boolean(useAuthStore((s) => s.user));
  const loggedInRef = useRef(loggedIn);
  loggedInRef.current = loggedIn;
  const catalogRef = useRef<QuestLogCatalog>(emptyQuestLogCatalog());
  const catalogItemsRef = useRef<TarkovTaskListItem[]>([]);
  gameModeRef.current = gameMode;

  const [shotPerm, setShotPerm] = useState<LiveWatchPerm>(
    supported ? "unknown" : "none",
  );
  const [logPerm, setLogPerm] = useState<LiveWatchPerm>(
    supported ? "unknown" : "none",
  );
  const [shotLabel, setShotLabel] = useState("");
  const [logLabel, setLogLabel] = useState("");
  const [lastShotAt, setLastShotAt] = useState<number | string | null>(null);
  const [lastLogAt, setLastLogAt] = useState<number | string | null>(null);
  const [lastShotName, setLastShotName] = useState("");
  const [lastLogMapId, setLastLogMapId] = useState("");
  const [lastLogPhase, setLastLogPhase] = useState<TarkovLogPhasePayload | null>(
    null,
  );
  const [offlineMapId, setOfflineMapId] = useState(loadOfflineMapId);
  const offlineMapIdRef = useRef(offlineMapId);
  offlineMapIdRef.current = offlineMapId;
  const [fix, setFix] = useState<TarkovScreenshotFix | null>(null);
  const [shotBusy, setShotBusy] = useState(false);
  const [logSyncBusy, setLogSyncBusy] = useState(false);
  const [logSyncScan, setLogSyncScan] = useState<{
    done: number;
    total: number;
  } | null>(null);
  const [logSyncReview, setLogSyncReview] = useState<QuestLogSyncReview | null>(
    null,
  );

  const catalogQuery = useQuery({
    queryKey: ["guides-tarkov-task-list", gameMode],
    queryFn: () => fetchTarkovTasks({ layout: "all" }),
    staleTime: 5 * 60_000,
    enabled: supported && logPerm === "granted",
    retry: 1,
  });
  const catalogItems = catalogQuery.data?.items;
  const queryCatalog = useMemo(
    () => (catalogItems ? buildQuestLogCatalog(catalogItems) : emptyQuestLogCatalog()),
    [catalogItems],
  );
  catalogRef.current = queryCatalog;
  if (catalogItems) {
    catalogItemsRef.current = catalogItems;
  }

  const loadQuestBase = useCallback(() => {
    const mode = gameModeRef.current;
    const prevDone = loadTaskDoneIds(mode);
    const prevStarted = loadTaskStartedIds(mode);
    const prevFailed = loadTaskFailedIds(mode);
    if (loadQuestProfileResetPending(mode)) {
      return { done: prevDone, started: prevStarted, failed: prevFailed };
    }
    const cached = queryClient.getQueryData<TarkovTaskDones>([
      TASK_DONES_QUERY_KEY,
      mode,
    ]);
    // 缓存里的账号进度若来自另一个边界版本（别处清空 / 重置过），并进来就是把旧任务带回来。
    // 各面板手写回缓存时只放四个进度字段、不带 reset_epoch：那是本机刚写的，可以并。
    const cachedEpoch = cached?.reset_epoch;
    const localEpoch = loadQuestServerEpoch(mode);
    if (!cached || (typeof cachedEpoch === "number" && localEpoch !== cachedEpoch)) {
      return { done: prevDone, started: prevStarted, failed: prevFailed };
    }
    return unionTaskProgress(
      { done: prevDone, started: prevStarted, failed: prevFailed },
      {
        done: cached.task_ids,
        started: cached.started_ids,
        failed: cached.failed_ids,
      },
    );
  }, [queryClient]);

  /**
   * 当前模式的回放边界：登录时直接回源取账号（各面板改写过的缓存不带边界字段，不能信），访客取本机。
   * 登录却拿不到账号边界时返回 null：宁可不同步，也不能拿本机猜的边界去整表替换账号。
   */
  const loadQuestBoundary = useCallback(
    async (mode: TarkovGameMode): Promise<QuestBoundary | null> => {
      const local = loadLocalQuestBoundary(mode);
      if (!loggedInRef.current) return combineQuestBoundary(null, local);
      let data: TarkovTaskDones;
      try {
        data = await fetchTarkovTaskDonesFor(mode);
      } catch {
        return null;
      }
      const server = questBoundaryFromServer(data);
      // 别处清空 / 重置过：先换成账号那份，再在它上面回放
      if (
        questLedgerIsStale(loadQuestServerEpoch(mode), server.epoch) ||
        questLedgerIsStale(loadTabQuestEpoch(mode), server.epoch)
      ) {
        adoptAccountTaskLedger(mode, data);
      } else {
        adoptQuestBoundary(mode, server);
        saveQuestServerEpoch(mode, server.epoch);
      }
      queryClient.setQueryData([TASK_DONES_QUERY_KEY, mode], data);
      return combineQuestBoundary(server, local);
    },
    [queryClient],
  );

  /**
   * 回放结果整表替换本模式进度，并把下限写进账号（只增不减）。
   * 账号回 409：别处已经清空 / 重置过，本机这份结果作废，交给账号同步重拉。
   */
  const commitQuestReset = useCallback(
    async (
      mode: TarkovGameMode,
      input: {
        profileId: string;
        fromAt: string;
        reason: QuestResetReason;
        epoch: number;
        done: string[];
        started: string[];
        failed: string[];
        base: { done: string[]; started: string[]; failed: string[] };
      },
    ): Promise<{ ok: true } | { ok: false; hint: string }> => {
      const syncedAt = nowBeijingStamp();
      let objectives: Array<{ task_id: string; objective_id: string }> = [];
      if (loggedInRef.current) {
        let data: TarkovTaskDones;
        try {
          data = await resetTarkovTaskProgress(
            {
              reset_at: input.fromAt,
              profile_id: input.profileId,
              reason: input.reason,
              // 用这次同步开头从账号读到的 epoch：中途别处又清空了就会 409
              expect_epoch: input.epoch,
              task_ids: input.done,
              started_ids: input.started,
              failed_ids: input.failed,
              objective_dones: [],
            },
            mode,
          );
        } catch (error) {
          return {
            ok: false,
            hint: apiError(error, "写入账号失败，任务进度没有改动。请稍后再同步。"),
          };
        }
        adoptServerTaskLedger(mode, {
          done: data.task_ids || [],
          started: data.started_ids || [],
          failed: data.failed_ids || [],
          objectives: data.objective_dones || [],
          cleared: clearedMapFromServer(data.cleared),
          boundary: questBoundaryFromServer(data),
        });
        objectives = data.objective_dones || [];
        queryClient.setQueryData([TASK_DONES_QUERY_KEY, mode], data);
      } else {
        applyQuestReplayReset(mode, input);
      }
      saveTaskSyncMark(mode, syncedAt);
      const done = loadTaskDoneIds(mode);
      notifyTarkovTaskProgress({
        mode,
        done,
        started: loadTaskStartedIds(mode),
        failed: loadTaskFailedIds(mode),
        objectives,
        syncedAt,
        changed: true,
        completedIds: addedIdList(input.base.done, done),
        source: "log",
      });
      return { ok: true };
    },
    [queryClient],
  );

  const commitQuestProgress = useCallback(
    (
      base: { done: string[]; started: string[]; failed: string[] },
      next: {
        done: string[];
        started: string[];
        failed: string[];
        changed: boolean;
      },
      opts?: { put?: boolean; replace?: boolean; force?: boolean },
    ) => {
      const mode = gameModeRef.current;
      const epoch = questLedgerEpochNow();
      const syncedAt = nowBeijingStamp();
      const write = next.changed || Boolean(opts?.force);
      saveTaskSyncMark(mode, syncedAt);
      if (next.changed || opts?.replace) {
        saveTaskProgress(
          mode,
          next.done,
          next.started,
          false,
          false,
          opts?.replace ? [] : undefined,
          next.failed,
        );
      }
      notifyTarkovTaskProgress({
        mode,
        done: write ? next.done : base.done,
        started: write ? next.started : base.started,
        failed: write ? next.failed : base.failed,
        objectives: opts?.replace ? [] : loadTaskObjectivePairs(mode),
        syncedAt,
        changed: write,
        completedIds: write ? addedIdList(base.done, next.done) : [],
        source: "log",
      });
      if (!write) return;
      const cached = queryClient.getQueryData([TASK_DONES_QUERY_KEY, mode]);
      if (cached) {
        queryClient.setQueryData(
          [TASK_DONES_QUERY_KEY, mode],
          taskProgressQueryData(
            next.done,
            next.started,
            loadTaskObjectivePairs(mode),
            next.failed,
          ),
        );
      }
      if (opts?.put === false) return;
      void writeTaskProgressLedger(
        {
          done: next.done,
          started: next.started,
          failed: next.failed,
          ...(opts?.replace ? { objectives: [] as Array<{ task_id: string; objective_id: string }> } : {}),
        },
        base,
        opts?.replace ? { replace: true } : undefined,
      )
        .then((data) => {
          if (questLedgerEpochNow() !== epoch) return;
          if (opts?.replace) clearQuestProfileResetPending(mode);
          const objectives = data.objective_dones || loadTaskObjectivePairs(mode);
          const catalog = catalogRef.current;
          let cleaned = applyMutexLedger(
            next.done,
            next.started,
            next.failed,
            catalog.mutexById,
          );
          if (catalog.blockedById.size) {
            cleaned = dropBlockedProgress(
              cleaned.done,
              cleaned.started,
              cleaned.failed,
              catalog.blockedById,
            );
          }
          const extras = ledgerIdsToClear(
            {
              done: data.task_ids,
              started: data.started_ids,
              failed: data.failed_ids,
            },
            cleaned,
          );
          saveTaskProgress(
            mode,
            cleaned.done,
            cleaned.started,
            true,
            true,
            objectives,
            cleaned.failed,
          );
          queryClient.setQueryData(
            [TASK_DONES_QUERY_KEY, mode],
            taskProgressQueryData(
              cleaned.done,
              cleaned.started,
              objectives,
              cleaned.failed,
            ),
          );
          notifyTarkovTaskProgress({
            mode,
            done: cleaned.done,
            started: cleaned.started,
            failed: cleaned.failed,
            objectives,
            syncedAt,
            changed: true,
            completedIds: addedIdList(base.done, cleaned.done),
            source: "log",
          });
          if (!extras.length) return;
          return writeTaskProgressLedger(
            {
              done: cleaned.done,
              started: cleaned.started,
              failed: cleaned.failed,
            },
            {
              done: data.task_ids,
              started: data.started_ids,
              failed: data.failed_ids,
            },
          );
        })
        .catch(() => {
          /* 未登录或网络失败时本机进度仍已写上 */
        });
    },
    [queryClient],
  );

  const applySessions = useCallback(
    (sessions: Array<{ parsed: ReturnType<typeof parseTarkovLogBundle> }>) => {
      const mode = gameModeRef.current;
      if (loadQuestSyncFromLatest(mode)) return;
      lastParsedRef.current = sessions;
      const profileId = latestIdentityForMode(
        sessions.flatMap((row) => identitiesFromParsed(row.parsed)),
        mode,
      )?.profileId;
      const base = loadQuestBase();
      const next = nextLiveQuestProgress(
        base.done,
        base.started,
        sessions,
        mode,
        catalogRef.current,
        base.failed,
        loadTaskClearedDone(mode),
        { profileId, fromAt: loadQuestProgressFloor(mode) },
      );
      commitQuestProgress(base, next);
    },
    [commitQuestProgress, loadQuestBase],
  );

  const applyParsedMap = useCallback(
    (parsed: ReturnType<typeof parseTarkovLogBundle> | null) => {
      const phase = parsed ? logPhaseFromParsed(parsed) : null;
      // 每次日志 tick 都会重解析出新对象；内容没变就留旧引用，免得相位 context 全树重绘
      setLastLogPhase((prev) => keepLogPhase(prev, phase));
      const logMap = latestLogMapId(parsed);
      setLastLogMapId(
        resolveOfflineLogMapId({
          logMapId: logMap,
          offlineMapId: offlineMapIdRef.current,
          raidMode: phase?.raidMode,
          phaseKind: phase?.kind,
        }) || logMap,
      );
    },
    [],
  );

  const hydrate = useCallback(async () => {
    if (!supported) {
      setShotPerm("none");
      setLogPerm("none");
      return;
    }
    const [storedShot, storedLog, shotPath, logPath] = await Promise.all([
      loadStoredScreenshotsDir(),
      loadStoredLogsDir(),
      loadStoredScreenshotsPath(),
      loadStoredLogsPath(),
    ]);
    if (!storedShot) {
      shotRef.current = null;
      shotDirRef.current = null;
      shotCanWriteRef.current = false;
      setShotPerm("none");
      setShotLabel("");
    } else {
      shotRef.current = storedShot;
      shotDirRef.current = null;
      seenShotNamesRef.current = new Set();
      shotStampRef.current = null;
      setShotLabel(shotPath || storedShot.name);
      const current = await queryScreenshotsDirPermission(storedShot);
      setShotPerm(current === "granted" ? "granted" : "prompt");
      shotCanWriteRef.current =
        current === "granted" && (await screenshotsDirCanWrite(storedShot));
      if (shotCanWriteRef.current && shotPrunePrefRef.current.enabled) {
        shotNeedListRef.current = true;
      }
    }
    if (!storedLog) {
      logRef.current = null;
      setLogPerm("none");
      setLogLabel("");
      setLastLogPhase(null);
      endedRaidKeysRef.current = new Set();
    } else {
      logRef.current = storedLog;
      logCursorRef.current = null;
      endedRaidKeysRef.current = new Set();
      setLogLabel(logPath || storedLog.name);
      const current = await queryLogsDirPermission(storedLog);
      setLogPerm(current === "granted" ? "granted" : "prompt");
    }
  }, [supported]);

  useEffect(() => {
    void hydrate();
    const onDirs = () => {
      void hydrate();
    };
    const onPrune = () => {
      shotPrunePrefRef.current = loadScreenshotPrunePref();
      if (!shotPrunePrefRef.current.enabled) {
        shotPruneRef.current = [];
        return;
      }
      shotNeedListRef.current = true;
    };
    window.addEventListener(TARKOV_LIVE_DIRS_EVENT, onDirs);
    window.addEventListener(TARKOV_SCREENSHOT_PRUNE_EVENT, onPrune);
    const onOfflineMap = () => {
      setOfflineMapId(loadOfflineMapId());
    };
    window.addEventListener(TARKOV_OFFLINE_MAP_EVENT, onOfflineMap);
    return () => {
      window.removeEventListener(TARKOV_LIVE_DIRS_EVENT, onDirs);
      window.removeEventListener(TARKOV_SCREENSHOT_PRUNE_EVENT, onPrune);
      window.removeEventListener(TARKOV_OFFLINE_MAP_EVENT, onOfflineMap);
    };
  }, [hydrate]);

  useEffect(() => {
    if (logSyncBusy) return;
    if (!lastParsedRef.current.length) return;
    applySessions(lastParsedRef.current);
  }, [applySessions, gameMode, logSyncBusy]);

  useEffect(() => {
    const newest = lastParsedRef.current[lastParsedRef.current.length - 1]?.parsed;
    if (!newest) return;
    applyParsedMap(newest);
  }, [applyParsedMap, offlineMapId]);

  useEffect(() => {
    if (!supported || shotPerm !== "granted") return;
    seenShotNamesRef.current = new Set();
    shotStampRef.current = null;
    shotDirRef.current = null;
    shotPruneRef.current = [];
    shotWatchingRef.current = false;
    let cancelled = false;
    let stopObserve: (() => void) | null = null;
    const applyLatest = (latest: {
      name: string;
      lastModified: number;
    }) => {
      setLastShotName(latest.name);
      setLastShotAt(latest.lastModified);
      if (!isNewerScreenshot(shotStampRef.current, latest)) return;
      shotStampRef.current = {
        name: latest.name,
        lastModified: latest.lastModified,
      };
      const parsed = parseTarkovScreenshotName(latest.name);
      if (!parsed) return;
      setFix({
        ...parsed,
        fileName: latest.name,
        lastModified: latest.lastModified,
      });
    };

    const queuePrune = (names: readonly string[], keepLatest: string | null) => {
      const pref = shotPrunePrefRef.current;
      if (!pref.enabled) {
        shotPruneRef.current = [];
        return;
      }
      const queued = new Set(shotPruneRef.current);
      for (const name of screenshotNamesToPrune(
        names,
        keepLatest,
        pref.keepMax,
      )) {
        if (queued.has(name)) continue;
        queued.add(name);
        shotPruneRef.current.push(name);
      }
    };

    const drainPrune = async () => {
      const dir = shotDirRef.current;
      if (
        !dir ||
        !shotCanWriteRef.current ||
        !shotPrunePrefRef.current.enabled ||
        !shotPruneRef.current.length
      ) {
        return;
      }
      const batch = shotPruneRef.current.splice(0, TARKOV_SCREENSHOT_PRUNE_BATCH);
      const removed = await removeScreenshotFiles(dir, batch);
      for (const name of removed) seenShotNamesRef.current.delete(name);
    };

    const tick = async (forceList = false, appeared: string[] = []) => {
      if (cancelled || document.hidden || shotTickBusyRef.current) return;
      const handle = shotRef.current;
      if (!handle) return;
      shotTickBusyRef.current = true;
      try {
        if (appeared.length && shotDirRef.current) {
          for (const name of appeared) {
            const row = await readScreenshotByName(shotDirRef.current, name);
            if (!row) continue;
            seenShotNamesRef.current.add(row.name);
            applyLatest(row);
          }
          const names = await listScreenshotFileNames(shotDirRef.current);
          queuePrune(
            names,
            shotStampRef.current?.name || latestScreenshotName(names),
          );
        } else if (forceList || !shotWatchingRef.current) {
          const { names, latest, dir } = await pollLatestScreenshot(
            handle,
            seenShotNamesRef.current,
            shotDirRef.current,
          );
          if (cancelled) return;
          shotDirRef.current = dir;
          for (const name of names) seenShotNamesRef.current.add(name);
          const keepLatest = latest?.name || latestScreenshotName(names);
          if (latest) applyLatest(latest);
          queuePrune(names, keepLatest);
          if (!stopObserve) {
            stopObserve = await observeDirectory(dir, (next) => {
              shotWatchingRef.current = true;
              void tick(next.length === 0, next);
            });
            if (stopObserve) shotWatchingRef.current = true;
          }
        }
        await drainPrune();
      } catch {
        /* 保留上一次定位 */
      } finally {
        shotTickBusyRef.current = false;
      }
    };
    const onVisible = () => {
      if (!document.hidden) void tick(true);
    };
    void tick(true);
    const timer = window.setInterval(() => {
      if (shotNeedListRef.current) {
        shotNeedListRef.current = false;
        void tick(true);
        return;
      }
      if (
        shotWatchingRef.current &&
        !(shotPrunePrefRef.current.enabled && shotCanWriteRef.current)
      ) {
        void drainPrune();
        return;
      }
      void tick(true);
    }, TARKOV_SCREENSHOT_POLL_MS);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      stopObserve?.();
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [shotPerm, supported]);

  useEffect(() => {
    if (!supported || logPerm !== "granted") return;
    logCursorRef.current = null;
    let cancelled = false;
    const readCache = createTarkovLogReadCache();
    const parseMemo: TarkovLogBundleMemo = new WeakMap();
    const tick = async () => {
      if (cancelled || document.hidden || logTickBusyRef.current) return;
      const handle = logRef.current;
      if (!handle) return;
      logTickBusyRef.current = true;
      try {
        const { sessions } = await readLogsIndex(handle, readCache);
        if (cancelled) return;
        const newest = sessions[0] || null;
        if (!newest) return;
        const newestStat = await statSessionLogs(handle, newest.folder, readCache);
        if (cancelled) return;
        const { fingerprint } = newestStat;
        const plan = planLogSessionReads(
          newest.folder,
          fingerprint,
          logCursorRef.current,
        );
        logCursorRef.current = { folder: newest.folder, fingerprint };
        if (plan.skip) return;
        const parsedSessions = [];
        for (const folder of plan.folders) {
          const stat =
            folder === newest.folder
              ? newestStat
              : await statSessionLogs(handle, folder, readCache);
          const read = await readStattedSessionLogs(stat, readCache);
          if (cancelled) return;
          const parsed = parseTarkovLogBundle(read.files, parseMemo);
          parsedSessions.push({ parsed, read });
        }
        retainTarkovLogFolders(readCache, plan.folders);
        const newestRead =
          parsedSessions.find((row) => row.read.folder === newest.folder) ||
          parsedSessions[parsedSessions.length - 1];
        if (newestRead) {
          const stamp = logStampFromParsed(
            newestRead.parsed,
            newestRead.read.files.map((file) => file.lastModified),
          );
          if (stamp != null) setLastLogAt(stamp);
          applyParsedMap(newestRead.parsed);
        }
        const sessionRows = parsedSessions.map((row) => ({
          folder: row.read.folder,
          parsed: row.parsed,
        }));
        const mode = gameModeRef.current;
        const polledProfile = (
          latestIdentityForMode(
            sessionRows.flatMap((row) => identitiesFromParsed(row.parsed, row.folder)),
            mode,
          )?.profileId || ""
        ).trim();
        const knownProfile = loadQuestProfileId(mode);
        // 待兑现的清空，或日志里换了角色 / 头一次见到角色：交给完整同步（读账号边界、识别换角色、写回账号）。
        // 失败就隔一阵再试；等待期间不做增量合并（边界没定下来，合并可能把清空前的任务写回去）。
        const needsFullSync =
          loadQuestSyncFromLatest(mode) ||
          (Boolean(polledProfile) && polledProfile !== knownProfile);
        if (needsFullSync) {
          const key = `${mode}|${polledProfile}`;
          const retryAt = fullSyncRetryAtRef.current.get(key) || 0;
          if (Date.now() < retryAt) return;
          const result = await syncLogsRef.current({
            ...defaultLogSyncRange(),
            duringTick: true,
            quiet: true,
          });
          if (result.ok) fullSyncRetryAtRef.current.delete(key);
          else fullSyncRetryAtRef.current.set(key, Date.now() + FULL_SYNC_RETRY_MS);
          return;
        }
        applySessions(sessionRows);
        const importPlan = planRaidLogImport(endedRaidKeysRef.current, sessionRows);
        endedRaidKeysRef.current = importPlan.nextKeys;
        if (importPlan.rows.length) {
          void importTarkovRaidLogs(importPlan.rows)
            .then(() => {
              void queryClient.invalidateQueries({
                queryKey: ["guides-tarkov-raid-logs"],
              });
            })
            .catch(() => {
              /* 未登录或网络失败时本机相位仍已更新 */
            });
        }
      } catch {
        // 保留上一次任务进度；目录句柄可能已失效，下一轮重新解析。
        forgetTarkovLogDirs(readCache);
      } finally {
        logTickBusyRef.current = false;
      }
    };
    const onVisible = () => {
      if (!document.hidden) void tick();
    };
    void tick();
    const timer = window.setInterval(() => void tick(), TARKOV_SCREENSHOT_POLL_MS);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [applyParsedMap, applySessions, logPerm, queryClient, supported]);

  const resume = useCallback(async () => {
    if (!supported) return;
    const shot = shotRef.current;
    if (shot) {
      const next = await requestScreenshotsDirPermission(shot);
      if (next === "granted") {
        await saveScreenshotsDir(shot);
        shotCanWriteRef.current = await screenshotsDirCanWrite(shot);
        if (shotCanWriteRef.current && shotPrunePrefRef.current.enabled) {
          shotNeedListRef.current = true;
        }
        setShotPerm("granted");
      } else {
        setShotPerm("prompt");
      }
    }
    const logs = logRef.current;
    if (logs) {
      const next = await requestLogsDirPermission(logs);
      if (next === "granted") {
        setLogPerm("granted");
      } else {
        setLogPerm("prompt");
      }
    }
  }, [supported]);

  useEffect(() => {
    if (!supported) return;
    if (shotPerm !== "prompt" && logPerm !== "prompt") return;
    const onDown = () => {
      void resume();
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [logPerm, resume, shotPerm, supported]);

  const enableShots = useCallback(async () => {
    if (!supported) return;
    setShotBusy(true);
    try {
      const existing = shotRef.current;
      if (existing) {
        const next = await requestScreenshotsDirPermission(existing);
        if (next === "granted") {
          await saveScreenshotsDir(existing);
          shotCanWriteRef.current = await screenshotsDirCanWrite(existing);
          if (shotCanWriteRef.current && shotPrunePrefRef.current.enabled) {
            shotNeedListRef.current = true;
          }
          setShotPerm("granted");
          return;
        }
        setShotPerm("prompt");
        return;
      }
      const picked = await pickScreenshotsDirectory(null);
      const next = await requestScreenshotsDirPermission(picked);
      if (next !== "granted") {
        setShotPerm("prompt");
        return;
      }
      shotRef.current = picked;
      shotDirRef.current = null;
      seenShotNamesRef.current = new Set();
      shotStampRef.current = null;
      shotCanWriteRef.current = await screenshotsDirCanWrite(picked);
      if (shotCanWriteRef.current && shotPrunePrefRef.current.enabled) {
        shotNeedListRef.current = true;
      }
      setShotLabel(picked.name);
      await saveScreenshotsDir(picked);
      setShotPerm("granted");
    } catch (error) {
      if (!isPickerAbort(error) && !shotRef.current) setShotPerm("none");
    } finally {
      setShotBusy(false);
    }
  }, [supported]);

  const ensureLogsHandle = useCallback(async (): Promise<
    { ok: true; handle: NonNullable<typeof logRef.current> } | { ok: false; hint: string }
  > => {
    if (!supported) {
      return {
        ok: false,
        hint: "当前浏览器不支持读取本机日志目录，请用 Chrome 或 Edge。",
      };
    }
    let handle = logRef.current;
    if (handle) {
      const next = await requestLogsDirPermission(handle);
      if (next !== "granted") {
        setLogPerm("prompt");
        return { ok: false, hint: "浏览器没有批准读取日志目录。" };
      }
      setLogPerm("granted");
      return { ok: true, handle };
    }
    const picked = await pickLogsDirectory(null);
    const next = await requestLogsDirPermission(picked);
    if (next !== "granted") {
      setLogPerm("prompt");
      return { ok: false, hint: "浏览器没有批准读取日志目录。" };
    }
    logRef.current = picked;
    setLogLabel(picked.name);
    await saveLogsDir(picked);
    setLogPerm("granted");
    return { ok: true, handle: picked };
  }, [supported]);

  const previewLogSessions = useCallback(async (): Promise<{
    ok: boolean;
    hint: string;
    sessions: Awaited<ReturnType<typeof readLogsIndex>>["sessions"];
  }> => {
    try {
      const ready = await ensureLogsHandle();
      if (!ready.ok) return { ok: false, hint: ready.hint, sessions: [] };
      // 一次列目录共用一份读盘缓存：每个启动文件夹不再重新解析日志根（助手模式下每次都过文件桥）
      const historyCache = createTarkovLogReadCache();
      const { sessions } = await readLogsIndex(ready.handle, historyCache);
      const withIdentities = [];
      let scanned = 0;
      for (const stub of sessions) {
        const read = await readSessionApplicationLogs(ready.handle, stub.folder, historyCache);
        const parsed = parseTarkovLogBundle(read.files);
        withIdentities.push({
          ...sessionStubInBeijing(stub, parsed),
          identities: identitiesFromParsed(parsed, stub.folder),
        });
        scanned += 1;
        if (scanned % 8 === 0) await yieldLogSyncQueue();
      }
      return { ok: true, hint: "", sessions: withIdentities };
    } catch (error) {
      if (isPickerAbort(error)) return { ok: false, hint: "", sessions: [] };
      const text =
        error instanceof Error && error.message
          ? error.message
          : "无法列出启动记录";
      return { ok: false, hint: text, sessions: [] };
    }
  }, [ensureLogsHandle]);

  const cancelLogSync = useCallback(() => {
    syncAbortRef.current?.abort();
  }, []);

  const syncLogs = useCallback(
    async (opts?: TarkovLogSyncOpts): Promise<{
      ok: boolean;
      hint: string;
      review?: QuestLogSyncReview;
    }> => {
      if (logTickBusyRef.current && !opts?.duringTick) {
        return { ok: false, hint: "正在读取日志，请稍后再试。" };
      }
      const syncEpoch = questLedgerEpochNow();
      const abort = new AbortController();
      if (opts?.signal) {
        if (opts.signal.aborted) abort.abort();
        else {
          opts.signal.addEventListener("abort", () => abort.abort(), {
            once: true,
          });
        }
      }
      syncAbortRef.current = abort;
      setLogSyncBusy(true);
      if (!opts?.duringTick) logTickBusyRef.current = true;
      if (!opts?.quiet) setLogSyncReview(null);
      const emptyDelta = { done: 0, started: 0, failed: 0, unfinished: 0 };
      try {
        const ready = await ensureLogsHandle();
        if (!ready.ok) return { ok: false, hint: ready.hint };
        if (abort.signal.aborted) return { ok: false, hint: "已取消同步。" };
        const handle = ready.handle;
        if (
          !catalogItemsRef.current.length ||
          (!catalogRef.current.knownIds?.size &&
            !catalogRef.current.mutexById.size)
        ) {
          try {
            const data = await fetchTarkovTasks({ layout: "all" });
            catalogRef.current = buildQuestLogCatalog(data.items || []);
            if (data.items?.length) catalogItemsRef.current = data.items;
          } catch {
            /* 无图鉴时仍回放，失败一律记 failed；没有图鉴也就不猜转生 */
          }
        }
        const mode = gameModeRef.current;
        // 边界以账号为准：登出、换浏览器、战鸽助手读到的都是同一份
        const boundary = await loadQuestBoundary(mode);
        if (!boundary) {
          return { ok: false, hint: "读不到账号上的任务进度，这次没有同步。请检查网络后再试。" };
        }
        const boundaryEpoch = boundary.epoch;
        if (abort.signal.aborted) return { ok: false, hint: "已取消同步。" };
        const historyCache = createTarkovLogReadCache();
        const { sessions } = await readLogsIndex(handle, historyCache);
        // 身份与任务事件一律读全部启动记录：换角色 / 转生 / 清空要整表重置时，必须拿完整历史回放，
        // 只用所选几天的日志重置会把更早的正常进度永远挡在下限之外。所选日期与断点只用来筛增量回放。
        const clearing = Boolean(boundary.pendingClearAt);
        const pickedRange = clearing
          ? defaultLogSyncRange()
          : opts?.from && opts?.to
            ? opts
            : defaultLogSyncRange();
        const breakpoint = clearing ? undefined : pickedRange.breakpoint;
        const ranged = takeSessionStubs(sessions, 0);
        // 先读每次启动的身份，再整段读一遍任务事件：转生识别要看下限之前的完成
        const considered: Array<{
          stub: (typeof ranged)[number];
          identities: TarkovLogIdentity[];
        }> = [];
        for (const stub of ranged) {
          if (abort.signal.aborted) break;
          const app = await readSessionApplicationLogs(handle, stub.folder, historyCache);
          const appParsed = parseTarkovLogBundle(app.files);
          considered.push({
            // 文件夹名是游戏本机墙钟；读过日志就按它的偏移换成北京时间，再按所选日期筛
            stub: sessionStubInBeijing(stub, appParsed),
            identities: identitiesFromParsed(appParsed, stub.folder),
          });
          if (considered.length % 8 === 0) await yieldLogSyncQueue();
        }
        if (abort.signal.aborted) {
          return { ok: false, hint: "已取消同步。" };
        }
        const pickedFolders = new Set(
          filterSessionStubsByRange(
            considered.map((row) => row.stub),
            pickedRange,
          ).map((stub) => stub.folder),
        );
        const seenIdentities = considered.flatMap((row) => row.identities);
        const latestSeen = (
          latestIdentityForMode(seenIdentities, mode)?.profileId || ""
        ).trim();
        if (!latestSeen) {
          return {
            ok: clearing ? false : true,
            hint: clearing
              ? "日志里还没有读到当前角色，任务进度保持清空。"
              : sessions.length
                ? "这些日志里还没有读到当前模式的 ProfileId。"
                : formatLiveLogBackfillHint(0, "backfill", emptyDelta),
          };
        }
        if (breakpoint?.profileId && breakpoint.profileId !== latestSeen) {
          return {
            ok: true,
            hint: "这份启动记录不是当前角色。任务进度仍按当前角色保留，请改选最新的那条启动记录。",
          };
        }
        const targets = considered
          .filter((row) => sessionHasProfile(row.identities, latestSeen, mode))
          .filter((row) =>
            sessionStubMatchesBreakpoint(
              { ...row.stub, identities: row.identities },
              breakpoint,
            ),
          )
          .map((row) => row.stub)
          .sort((a, b) =>
            (a.startedAt || a.folder).localeCompare(b.startedAt || b.folder),
          );

        // 当前角色的全部任务事件（不截下限），用来识别同一 ProfileId 的转生
        const profileFilter: QuestReplayFilter = { gameMode: mode, profileId: latestSeen };
        const parsedTargets: Array<{
          folder: string;
          parsed: ReturnType<typeof parseTarkovLogBundle>;
          fileTimes: number[];
        }> = [];
        const allEvents: TarkovLogQuestEvent[] = [];
        const newestFolder = sessions[0]?.folder || "";
        setLogSyncScan({ done: 0, total: targets.length });
        let processed = 0;
        for (const stub of targets) {
          if (abort.signal.aborted) break;
          const read = await readSessionLogs(handle, stub.folder, { cache: historyCache });
          if (abort.signal.aborted) break;
          const parsed = parseTarkovLogBundle(read.files);
          parsedTargets.push({
            folder: stub.folder,
            parsed,
            fileTimes: read.files.map((file) => file.lastModified),
          });
          allEvents.push(...questsMatchingReplay(parsed, profileFilter));
          processed += 1;
          setLogSyncScan({ done: processed, total: targets.length });
          await yieldLogSyncQueue();
        }
        if (abort.signal.aborted) {
          return { ok: false, hint: processed ? "已取消同步（未写入）。" : "已取消同步。" };
        }
        if (questLedgerEpochNow() !== syncEpoch) {
          return { ok: false, hint: "任务进度已清空，这次同步没有写回。" };
        }
        let plan = planQuestReplay({
          gameMode: mode,
          identities: seenIdentities,
          events: allEvents,
          boundary,
          catalog: catalogRef.current,
        });
        if (!plan) {
          return { ok: false, hint: "日志里还没有读到当前角色，任务进度保持清空。" };
        }
        // 只是推断出来的重置（猜转生 / 账号不知道旧角色），玩家也没点清空：整表重置不可撤销，先问；
        // 轮询（没有 confirmReset）或玩家说不是，就当普通增量同步
        if (plan.reset && plan.confirm && plan.reason && plan.reason !== "clear") {
          const yes = opts?.confirmReset
            ? await opts.confirmReset({
                reason: plan.reason,
                at: plan.fromAt,
                taskCount: plan.prestige?.taskIds.length || 0,
              })
            : false;
          if (abort.signal.aborted) return { ok: false, hint: "已取消同步。" };
          if (!yes) {
            plan = {
              ...plan,
              fromAt: boundary.resetAt,
              reset: false,
              reason: null,
              confirm: false,
            };
          }
        }
        // 整表重置用全部日志；增量合并才按所选日期 / 断点收窄
        const fromAt = plan.reset
          ? plan.fromAt
          : laterBeijingClock(plan.fromAt, breakpoint?.at || "");
        const filter: QuestReplayFilter = { gameMode: mode, profileId: plan.profileId, fromAt };
        const replayRows = plan.reset
          ? parsedTargets
          : parsedTargets.filter((row) => pickedFolders.has(row.folder));
        if (!plan.reset && !replayRows.length) {
          return {
            ok: true,
            hint: breakpoint
              ? "这个范围内没有匹配该角色 / 版本的启动记录。"
              : "这个日期范围内没有启动记录。",
          };
        }

        let folded: Map<string, FoldedQuestEntry> = new Map();
        let questEvents = 0;
        const raidRows: TarkovRaidLogImportRow[] = [];
        const reviewEvents: TarkovLogQuestEvent[] = [];
        const reviewDrops: TarkovLogQuestDrop[] = [];
        let newestParsed: ReturnType<typeof parseTarkovLogBundle> | null = null;
        let newestFileTimes: number[] = [];
        for (const row of replayRows) {
          const step = foldSessionQuests(folded, row.parsed, filter);
          folded = step.next;
          questEvents += step.eventCount;
          reviewEvents.push(...questsMatchingReplay(row.parsed, filter));
          reviewDrops.push(...collectQuestReplayDrops(row.parsed, filter));
          raidRows.push(...toRaidLogImportRows([{ folder: row.folder, parsed: row.parsed }]));
          if (row.folder === newestFolder) {
            newestParsed = row.parsed;
            newestFileTimes = row.fileTimes;
          }
        }
        if (newestFolder) {
          const fingerprint = await peekSessionFingerprint(handle, newestFolder, historyCache);
          logCursorRef.current = { folder: newestFolder, fingerprint };
          if (newestParsed) {
            const stamp = logStampFromParsed(newestParsed, newestFileTimes);
            if (stamp != null) setLastLogAt(stamp);
            applyParsedMap(newestParsed);
            lastParsedRef.current = [{ parsed: newestParsed }];
          }
        }
        const prevDone = loadTaskDoneIds(mode);
        const prevStarted = loadTaskStartedIds(mode);
        const prevFailed = loadTaskFailedIds(mode);
        const base = plan.reset
          ? { done: [] as string[], started: [] as string[], failed: [] as string[] }
          : loadQuestBase();
        const merged = mergeQuestProgressFromFolded(
          base.done,
          base.started,
          folded,
          questEvents,
          catalogRef.current,
          base.failed,
          // 重置也要认晚于下限的手动取消，否则重放会把玩家亲手取消的任务带回来
          plan.reset
            ? clearedDoneAfter(loadTaskClearedDone(mode), fromAt)
            : loadTaskClearedDone(mode),
        );
        let hint = "";
        if (plan.reset && plan.reason) {
          const committed = await commitQuestReset(mode, {
            profileId: plan.profileId,
            fromAt,
            reason: plan.reason,
            epoch: boundaryEpoch,
            done: merged.done,
            started: merged.started,
            failed: merged.failed,
            base: { done: prevDone, started: prevStarted, failed: prevFailed },
          });
          if (!committed.ok) return { ok: false, hint: committed.hint };
        } else {
          saveQuestProfileId(mode, plan.profileId);
          // 让账号记住当前角色：之后新浏览器 / 登出后同步，日志里残留的旧角色就不会被当成「换了角色」
          if (loggedInRef.current && boundary.profileId !== plan.profileId) {
            void recordTarkovTaskProfile(plan.profileId, mode).catch(() => {});
          }
          commitQuestProgress(base, {
            done: merged.done,
            started: merged.started,
            failed: merged.failed,
            changed:
              !sameIdLists(base.done, merged.done) ||
              !sameIdLists(base.started, merged.started) ||
              !sameIdLists(base.failed, merged.failed),
          });
        }
        const importPlan = planRaidLogImportRows(
          endedRaidKeysRef.current,
          raidRows,
          { force: true },
        );
        endedRaidKeysRef.current = importPlan.nextKeys;
        if (importPlan.rows.length) {
          void importTarkovRaidLogs(importPlan.rows)
            .then(() => {
              void queryClient.invalidateQueries({
                queryKey: ["guides-tarkov-raid-logs"],
              });
            })
            .catch(() => {});
        }
        const nextDone = loadTaskDoneIds(mode);
        const nextStarted = loadTaskStartedIds(mode);
        const nextFailed = loadTaskFailedIds(mode);
        hint = formatLiveLogBackfillHint(
          replayRows.length,
          "backfill",
          questProgressDelta(
            prevDone,
            prevStarted,
            nextDone,
            nextStarted,
            prevFailed,
            nextFailed,
          ),
          { questEvents },
        );
        if (plan.reason === "prestige") {
          hint = `日志里识别到转生（${formatBeijing(plan.fromAt)}），已从转生后重新同步。${hint}`;
        } else if (plan.reason === "profile") {
          hint = `日志里换了游戏角色，已从新角色同步。${hint}`;
        } else if (plan.reason === "clear") {
          hint = `已跳过清空前的旧任务。${hint}`;
        }
        const rows = buildQuestLogSyncReview(reviewEvents, base, {
          catalog: catalogRef.current,
          items: catalogItemsRef.current,
          clearedDone: plan.reset
            ? clearedDoneAfter(loadTaskClearedDone(mode), fromAt)
            : loadTaskClearedDone(mode),
        });
        const dropHint = formatQuestLogDropHint(reviewDrops);
        const review: QuestLogSyncReview | undefined =
          rows.length || dropHint
            ? { hint, rows, dropHint, drops: reviewDrops }
            : undefined;
        if (review && !opts?.quiet) setLogSyncReview(review);
        return { ok: true, hint, review };
      } catch (error) {
        if (isPickerAbort(error)) return { ok: false, hint: "" };
        const text =
          error instanceof Error && error.message
            ? error.message
            : "同步日志失败";
        return { ok: false, hint: text };
      } finally {
        if (syncAbortRef.current === abort) syncAbortRef.current = null;
        if (!opts?.duringTick) logTickBusyRef.current = false;
        setLogSyncBusy(false);
        setLogSyncScan(null);
      }
    },
    [
      applyParsedMap,
      commitQuestProgress,
      commitQuestReset,
      ensureLogsHandle,
      loadQuestBase,
      loadQuestBoundary,
      queryClient,
    ],
  );
  syncLogsRef.current = syncLogs;

  const hasStoredShots = Boolean(shotRef.current) || Boolean(shotLabel);
  const hasStoredLogs = Boolean(logRef.current) || Boolean(logLabel);
  const visible =
    supported &&
    (hasStoredShots ||
      hasStoredLogs ||
      shotPerm === "granted" ||
      logPerm === "granted");

  const value = useMemo<TarkovLiveWatchValue>(
    () => ({
      supported,
      visible,
      shotPerm,
      logPerm,
      hasStoredShots,
      hasStoredLogs,
      shotLabel,
      logLabel,
      lastShotAt,
      lastLogAt,
      lastShotName,
      lastLogMapId,
      fix,
      shotBusy,
      logSyncBusy,
      logSyncScan,
      enableShots,
      resume,
      previewLogSessions,
      syncLogs,
      cancelLogSync,
    }),
    [
      cancelLogSync,
      enableShots,
      fix,
      hasStoredLogs,
      hasStoredShots,
      lastLogAt,
      lastShotAt,
      lastLogMapId,
      lastShotName,
      logLabel,
      logPerm,
      logSyncBusy,
      logSyncScan,
      previewLogSessions,
      resume,
      shotBusy,
      shotLabel,
      shotPerm,
      supported,
      syncLogs,
      visible,
    ],
  );

  const shotMeta = useMemo<TarkovLiveShotMeta>(
    () => ({
      supported,
      perm: shotPerm,
      hasStored: hasStoredShots,
      storedLabel: shotLabel,
      busy: shotBusy,
      enable: enableShots,
    }),
    [enableShots, hasStoredShots, shotBusy, shotLabel, shotPerm, supported],
  );

  const logSync = useMemo<TarkovLogSyncValue>(
    () => ({
      busy: logSyncBusy,
      scan: logSyncScan,
      previewLogSessions,
      syncLogs,
      cancelLogSync,
    }),
    [cancelLogSync, logSyncBusy, logSyncScan, previewLogSessions, syncLogs],
  );

  return (
    <TarkovLiveWatchContext.Provider value={value}>
      <TarkovLogSyncContext.Provider value={logSync}>
      <TarkovLiveShotMetaContext.Provider value={shotMeta}>
        <TarkovLiveLogMapContext.Provider value={lastLogMapId}>
          <TarkovLiveLogPhaseContext.Provider value={lastLogPhase}>
            <TarkovLiveFixContext.Provider value={fix}>
              {children}
              <TarkovLogSyncReviewModal
                open={Boolean(logSyncReview)}
                review={logSyncReview}
                onClose={() => setLogSyncReview(null)}
              />
            </TarkovLiveFixContext.Provider>
          </TarkovLiveLogPhaseContext.Provider>
        </TarkovLiveLogMapContext.Provider>
      </TarkovLiveShotMetaContext.Provider>
      </TarkovLogSyncContext.Provider>
    </TarkovLiveWatchContext.Provider>
  );
}
