import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchTarkovTasks, importTarkovRaidLogs, writeTaskProgressLedger, type TarkovTaskListItem } from "@/api/guidesApi";
import {
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
  requestLogsDirPermission,
  requestScreenshotsDirPermission,
  saveLogsDir,
  saveScreenshotsDir,
  screenshotsDirCanWrite,
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
  type LiveWatchPerm,
  type TarkovLiveShotMeta,
  type TarkovLiveWatchValue,
  type TarkovScreenshotFix,
} from "@/lib/tarkovLiveWatchContexts";
import { parseTarkovScreenshotName } from "@/lib/tarkovScreenshotPos";
import { nowBeijingStamp } from "@/lib/time";
import { useTarkovGameMode, type TarkovGameMode } from "@/lib/tarkovGameMode";
import {
  loadTaskDoneIds,
  loadTaskFailedIds,
  loadTaskObjectivePairs,
  loadTaskStartedIds,
  loadTaskClearedDone,
  loadQuestProfileId,
  loadQuestProfileResetPending,
  loadQuestSyncFromLatest,
  saveQuestProfileId,
  clearQuestProfileResetPending,
  clearQuestSyncFromLatest,
  releaseClearedTasks,
  resetTaskProgressForProfile,
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
  planLatestProfileReplay,
  questProfileResetPlan,
  questProgressDelta,
  questsMatchingReplay,
  type FoldedQuestEntry,
  type QuestLogCatalog,
  type QuestLogSyncReview,
  type QuestReplayFilter,
} from "@/lib/tarkovTaskLogSync";
import { useTarkovTaskAccountSync } from "@/lib/useTarkovTaskAccountSync";
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

/** 启动记录从新到旧。读到两个角色就可以判断转生，不必扫完整个 Logs。 */
async function readModeProfileIdentities(
  handle: ReadableDir,
  gameMode: TarkovGameMode,
): Promise<TarkovLogIdentity[]> {
  const { sessions } = await readLogsIndex(handle);
  const out: TarkovLogIdentity[] = [];
  const seen = new Set<string>();
  let scanned = 0;
  for (const stub of sessions) {
    const read = await readSessionApplicationLogs(handle, stub.folder);
    const rows = identitiesFromParsed(
      parseTarkovLogBundle(read.files),
      stub.folder,
    );
    out.push(...rows);
    for (const row of rows) {
      if (!breakpointMatchesGameMode(row, gameMode)) continue;
      const id = (row.profileId || "").trim();
      if (id) seen.add(id);
    }
    scanned += 1;
    if (seen.size >= 2) break;
    if (scanned % 8 === 0) await yieldLogSyncQueue();
  }
  return out;
}

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
  const shotPrunePrefRef = useRef(loadScreenshotPrunePref());
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
  const profileScanRef = useRef(false);
  const syncLogsRef = useRef<
    (opts?: TarkovLogSyncOpts) => Promise<{ ok: boolean; hint: string }>
  >(async () => ({ ok: false, hint: "" }));
  const gameModeRef = useRef(gameMode);
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
  catalogRef.current = catalogQuery.data?.items
    ? buildQuestLogCatalog(catalogQuery.data.items)
    : emptyQuestLogCatalog();
  if (catalogQuery.data?.items) {
    catalogItemsRef.current = catalogQuery.data.items;
  }

  const loadQuestBase = useCallback(() => {
    const mode = gameModeRef.current;
    const prevDone = loadTaskDoneIds(mode);
    const prevStarted = loadTaskStartedIds(mode);
    const prevFailed = loadTaskFailedIds(mode);
    if (loadQuestProfileResetPending(mode)) {
      return { done: prevDone, started: prevStarted, failed: prevFailed };
    }
    const cached = queryClient.getQueryData<{
      task_ids?: string[];
      started_ids?: string[];
      failed_ids?: string[];
      objective_dones?: Array<{ task_id: string; objective_id: string }>;
    }>(["guides-tarkov-task-dones", mode]);
    return unionTaskProgress(
      { done: prevDone, started: prevStarted, failed: prevFailed },
      {
        done: cached?.task_ids,
        started: cached?.started_ids,
        failed: cached?.failed_ids,
      },
    );
  }, [queryClient]);

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
      const cached = queryClient.getQueryData(["guides-tarkov-task-dones", mode]);
      if (cached) {
        queryClient.setQueryData(
          ["guides-tarkov-task-dones", mode],
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
            ["guides-tarkov-task-dones", mode],
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
        { profileId },
      );
      commitQuestProgress(base, next);
    },
    [commitQuestProgress, loadQuestBase],
  );

  const applyParsedMap = useCallback(
    (parsed: ReturnType<typeof parseTarkovLogBundle> | null) => {
      const phase = parsed ? logPhaseFromParsed(parsed) : null;
      setLastLogPhase(phase);
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
    const tick = async () => {
      if (cancelled || document.hidden || logTickBusyRef.current) return;
      const handle = logRef.current;
      if (!handle) return;
      logTickBusyRef.current = true;
      try {
        const { sessions } = await readLogsIndex(handle);
        if (cancelled) return;
        const newest = sessions[0] || null;
        if (!newest) return;
        const fingerprint = await peekSessionFingerprint(handle, newest.folder);
        if (cancelled) return;
        const plan = planLogSessionReads(
          newest.folder,
          fingerprint,
          logCursorRef.current,
        );
        logCursorRef.current = { folder: newest.folder, fingerprint };
        if (plan.skip) return;
        const parsedSessions = [];
        for (const folder of plan.folders) {
          const read = await readSessionLogs(handle, folder);
          if (cancelled) return;
          const parsed = parseTarkovLogBundle(read.files);
          parsedSessions.push({ parsed, read });
        }
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
        let identities = sessionRows.flatMap((row) =>
          identitiesFromParsed(row.parsed, row.folder),
        );
        const storedProfile = loadQuestProfileId(mode);
        const polledProfile = (
          latestIdentityForMode(identities, mode)?.profileId || ""
        ).trim();
        let scannedHistory = false;
        if (!storedProfile && !profileScanRef.current) {
          try {
            const scanned = await readModeProfileIdentities(handle, mode);
            if (cancelled) return;
            const sawProfile = scanned.some(
              (row) => breakpointMatchesGameMode(row, mode) && row.profileId,
            );
            if (sawProfile) {
              profileScanRef.current = true;
              scannedHistory = true;
              identities = scanned;
            }
          } catch {
            profileScanRef.current = false;
          }
        }
        const latest = latestIdentityForMode(identities, mode);
        const decision = questProfileResetPlan({
          gameMode: mode,
          storedProfileId: storedProfile,
          identities,
          replayProfileId: (latest?.profileId || polledProfile).trim(),
        });
        if (decision?.reset) {
          const result = await syncLogsRef.current({
            ...defaultLogSyncRange(),
            breakpoint: {
              version: latest?.version || "",
              profileId: decision.profileId,
              sessionMode: latest?.sessionMode || "",
              at: decision.at,
            },
            duringTick: true,
            quiet: true,
          });
          if (!result.ok) profileScanRef.current = false;
          return;
        }
        if (
          decision &&
          !decision.reset &&
          decision.profileId &&
          !storedProfile &&
          scannedHistory
        ) {
          saveQuestProfileId(mode, decision.profileId);
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
        /* 保留上一次任务进度 */
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
      const { sessions } = await readLogsIndex(ready.handle);
      const withIdentities = [];
      let scanned = 0;
      for (const stub of sessions) {
        const read = await readSessionApplicationLogs(ready.handle, stub.folder);
        const parsed = parseTarkovLogBundle(read.files);
        withIdentities.push({
          ...stub,
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
      const forceLatest = loadQuestSyncFromLatest(gameModeRef.current);
      const range = forceLatest
        ? defaultLogSyncRange()
        : opts?.from && opts?.to
          ? opts
          : defaultLogSyncRange();
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
            /* 无图鉴时仍回放，失败一律记 failed */
          }
        }
        const { sessions } = await readLogsIndex(handle);
        const ranged = filterSessionStubsByRange(
          takeSessionStubs(sessions, 0),
          range,
        );
        const mode = gameModeRef.current;
        const breakpoint = forceLatest ? undefined : range.breakpoint;
        let filter: QuestReplayFilter = {
          gameMode: mode,
          profileId: breakpoint?.profileId,
          fromAt: breakpoint?.at,
        };
        const considered: Array<{
          stub: (typeof ranged)[number];
          identities: TarkovLogIdentity[];
        }> = [];
        let targets: Array<(typeof ranged)[number] & { identities?: TarkovLogIdentity[] }> =
          [];
        for (const stub of ranged) {
          if (abort.signal.aborted) break;
          if (!breakpoint && !forceLatest) {
            targets.push(stub);
            continue;
          }
          const app = await readSessionApplicationLogs(handle, stub.folder);
          const identities = identitiesFromParsed(
            parseTarkovLogBundle(app.files),
            stub.folder,
          );
          considered.push({ stub, identities });
          const next = { ...stub, identities };
          if (sessionStubMatchesBreakpoint(next, breakpoint)) targets.push(next);
          if (considered.length % 8 === 0) await yieldLogSyncQueue();
        }
        const seenIdentities = considered.flatMap((row) => row.identities);
        if (abort.signal.aborted) {
          return { ok: false, hint: "已取消同步。" };
        }
        const latestSeen = (
          latestIdentityForMode(seenIdentities, mode)?.profileId || ""
        ).trim();
        const latestReplay = forceLatest
          ? planLatestProfileReplay(seenIdentities, mode)
          : null;
        if (forceLatest && !latestReplay) {
          return {
            ok: false,
            hint: "日志里还没有读到当前角色，任务进度保持清空。",
          };
        }
        const replayId = (latestReplay?.profileId || breakpoint?.profileId || "").trim();
        if (!forceLatest && replayId && latestSeen && replayId !== latestSeen) {
          return {
            ok: true,
            hint: "这份启动记录不是当前角色。任务进度仍按当前角色保留，请改选最新的那条启动记录。",
          };
        }
        const prevDone = loadTaskDoneIds(mode);
        const prevStarted = loadTaskStartedIds(mode);
        const prevFailed = loadTaskFailedIds(mode);
        const decision = replayId
          ? questProfileResetPlan({
              gameMode: mode,
              storedProfileId: loadQuestProfileId(mode),
              identities: seenIdentities,
              replayProfileId: replayId,
            })
          : null;
        const replayLatest = Boolean(latestReplay);
        const resetLedger = replayLatest || Boolean(decision?.reset);
        if (replayLatest && latestReplay) {
          filter = {
            gameMode: mode,
            profileId: latestReplay.profileId,
            fromAt: latestReplay.at,
          };
          targets = considered
            .filter((row) =>
              sessionHasProfile(row.identities, latestReplay.profileId, mode),
            )
            .map((row) => ({ ...row.stub, identities: row.identities }));
        } else if (resetLedger && decision) {
          filter = { ...filter, fromAt: decision.at || filter.fromAt };
          targets = considered
            .filter((row) =>
              sessionHasProfile(row.identities, decision.profileId, mode),
            )
            .map((row) => ({ ...row.stub, identities: row.identities }));
        } else if (
          decision &&
          !decision.reset &&
          decision.profileId &&
          (latestIdentityForMode(seenIdentities, mode)?.profileId || "") ===
            decision.profileId &&
          loadQuestProfileId(mode) !== decision.profileId
        ) {
          saveQuestProfileId(mode, decision.profileId);
        }
        if (!targets.length && !resetLedger) {
          return {
            ok: true,
            hint: sessions.length
              ? breakpoint
                ? "这个范围内没有匹配该角色 / 版本的启动记录。"
                : "这个日期范围内没有启动记录。"
              : formatLiveLogBackfillHint(0, "backfill", emptyDelta),
          };
        }
        let folded: Map<string, FoldedQuestEntry> = new Map();
        let questEvents = 0;
        const raidRows: TarkovRaidLogImportRow[] = [];
        const reviewEvents: TarkovLogQuestEvent[] = [];
        const reviewDrops: TarkovLogQuestDrop[] = [];
        let newestParsed: ReturnType<typeof parseTarkovLogBundle> | null = null;
        let newestFileTimes: number[] = [];
        const newestFolder = sessions[0]?.folder || "";
        const oldestFirst = [...targets].sort((a, b) => {
          const ta = a.startedAt || a.folder;
          const tb = b.startedAt || b.folder;
          return ta.localeCompare(tb);
        });
        setLogSyncScan({ done: 0, total: oldestFirst.length });
        let processed = 0;
        for (const stub of oldestFirst) {
          if (abort.signal.aborted) break;
          const read = await readSessionLogs(handle, stub.folder);
          if (abort.signal.aborted) break;
          const parsed = parseTarkovLogBundle(read.files);
          const foldedStep = foldSessionQuests(folded, parsed, filter);
          folded = foldedStep.next;
          questEvents += foldedStep.eventCount;
          reviewEvents.push(...questsMatchingReplay(parsed, filter));
          reviewDrops.push(...collectQuestReplayDrops(parsed, filter));
          raidRows.push(...toRaidLogImportRows([{ folder: stub.folder, parsed }]));
          if (stub.folder === newestFolder) {
            newestParsed = parsed;
            newestFileTimes = read.files.map((file) => file.lastModified);
          }
          processed += 1;
          setLogSyncScan({ done: processed, total: oldestFirst.length });
          if (!resetLedger && processed % 8 === 0) {
            const base = loadQuestBase();
            const mid = mergeQuestProgressFromFolded(
              base.done,
              base.started,
              folded,
              questEvents,
              catalogRef.current,
              base.failed,
            );
            commitQuestProgress(
              base,
              {
                done: mid.done,
                started: mid.started,
                failed: mid.failed,
                changed:
                  !sameIdLists(base.done, mid.done) ||
                  !sameIdLists(base.started, mid.started) ||
                  !sameIdLists(base.failed, mid.failed),
              },
              { put: false },
            );
          }
          await yieldLogSyncQueue();
        }
        if (newestFolder) {
          const fingerprint = await peekSessionFingerprint(handle, newestFolder);
          logCursorRef.current = { folder: newestFolder, fingerprint };
          if (newestParsed) {
            const stamp = logStampFromParsed(newestParsed, newestFileTimes);
            if (stamp != null) setLastLogAt(stamp);
            applyParsedMap(newestParsed);
            lastParsedRef.current = [{ parsed: newestParsed }];
          }
        }
        if (abort.signal.aborted && resetLedger) {
          return { ok: false, hint: "已取消同步。" };
        }
        if (resetLedger && decision && !replayLatest) {
          resetTaskProgressForProfile(mode, decision.profileId, decision.at);
        }
        const base = resetLedger
          ? { done: [] as string[], started: [] as string[], failed: [] as string[] }
          : loadQuestBase();
        if (processed > 0 || resetLedger) {
          const merged = mergeQuestProgressFromFolded(
            base.done,
            base.started,
            folded,
            questEvents,
            catalogRef.current,
            base.failed,
            replayLatest ? new Map() : resetLedger ? loadTaskClearedDone(mode) : undefined,
          );
          const changed =
            !sameIdLists(base.done, merged.done) ||
            !sameIdLists(base.started, merged.started) ||
            !sameIdLists(base.failed, merged.failed);
          commitQuestProgress(
            base,
            {
              done: merged.done,
              started: merged.started,
              failed: merged.failed,
              changed,
            },
            resetLedger ? { replace: true, force: true } : undefined,
          );
          if (replayLatest && latestReplay) {
            releaseClearedTasks(mode, [
              ...merged.done,
              ...merged.started,
              ...merged.failed,
            ]);
            clearQuestSyncFromLatest(mode);
            saveQuestProfileId(mode, latestReplay.profileId);
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
        }
        const nextDone = loadTaskDoneIds(mode);
        const nextStarted = loadTaskStartedIds(mode);
        const nextFailed = loadTaskFailedIds(mode);
        let hint = formatLiveLogBackfillHint(
          processed,
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
        if (replayLatest) hint = `已从当前角色同步。${hint}`;
        else if (resetLedger) hint = `转生后已重置任务进度。${hint}`;
        if (abort.signal.aborted) {
          hint = processed
            ? `${hint}（已取消）`
            : "已取消同步。";
        }
        const rows = buildQuestLogSyncReview(reviewEvents, base, {
          catalog: catalogRef.current,
          items: catalogItemsRef.current,
          clearedDone: loadTaskClearedDone(mode),
        });
        const dropHint = formatQuestLogDropHint(reviewDrops);
        const review: QuestLogSyncReview | undefined =
          rows.length || dropHint
            ? { hint, rows, dropHint, drops: reviewDrops }
            : undefined;
        if (review && !opts?.quiet) setLogSyncReview(review);
        return {
          ok: Boolean(processed) || !abort.signal.aborted,
          hint,
          review,
        };
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
    [applyParsedMap, commitQuestProgress, ensureLogsHandle, loadQuestBase, queryClient],
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

  return (
    <TarkovLiveWatchContext.Provider value={value}>
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
    </TarkovLiveWatchContext.Provider>
  );
}
