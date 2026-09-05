import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchTarkovTasks, importTarkovRaidLogs, writeTarkovTaskDones } from "@/api/guidesApi";
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
  type TarkovLogPhasePayload,
  type TarkovRaidLogImportRow,
} from "@/lib/tarkovGameLogs";
import {
  defaultLogSyncRange,
  filterSessionStubsByRange,
  yieldLogSyncQueue,
  type TarkovLogSyncOpts,
} from "@/lib/tarkovLogSyncRange";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
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
import {
  loadTaskDoneIds,
  loadTaskObjectivePairs,
  loadTaskStartedIds,
  loadTaskSyncAt,
  saveTaskProgress,
  saveTaskSyncMark,
  taskProgressQueryData,
  unionTaskProgress,
} from "@/lib/tarkovTaskTree";
import {
  foldSessionQuests,
  mergeQuestProgressFromFolded,
  questProgressDelta,
  type FoldedQuestEntry,
} from "@/lib/tarkovTaskLogSync";
import { useTarkovTaskAccountSync } from "@/lib/useTarkovTaskAccountSync";

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
  const gameModeRef = useRef(gameMode);
  const knownIdsRef = useRef<Set<string> | undefined>(undefined);
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
  const [fix, setFix] = useState<TarkovScreenshotFix | null>(null);
  const [shotBusy, setShotBusy] = useState(false);
  const [logSyncBusy, setLogSyncBusy] = useState(false);
  const [logSyncScan, setLogSyncScan] = useState<{
    done: number;
    total: number;
  } | null>(null);

  const catalogQuery = useQuery({
    queryKey: ["guides-tarkov-task-list", gameMode],
    queryFn: () => fetchTarkovTasks({ layout: "all" }),
    staleTime: 5 * 60_000,
    enabled: supported && logPerm === "granted",
    retry: 1,
  });
  knownIdsRef.current = catalogQuery.data?.items
    ? new Set(catalogQuery.data.items.map((item) => item.id))
    : undefined;

  const loadQuestBase = useCallback(() => {
    const mode = gameModeRef.current;
    const prevDone = loadTaskDoneIds(mode);
    const prevStarted = loadTaskStartedIds(mode);
    const cached = queryClient.getQueryData<{
      task_ids?: string[];
      started_ids?: string[];
      objective_dones?: Array<{ task_id: string; objective_id: string }>;
    }>(["guides-tarkov-task-dones", mode]);
    return unionTaskProgress(
      { done: prevDone, started: prevStarted },
      {
        done: cached?.task_ids,
        started: cached?.started_ids,
      },
    );
  }, [queryClient]);

  const commitQuestProgress = useCallback(
    (
      base: { done: string[]; started: string[] },
      next: { done: string[]; started: string[]; changed: boolean },
      opts?: { put?: boolean },
    ) => {
      const mode = gameModeRef.current;
      const syncedAt = nowBeijingStamp();
      saveTaskSyncMark(mode, syncedAt);
      if (next.changed) {
        saveTaskProgress(mode, next.done, next.started);
      }
      notifyTarkovTaskProgress({
        mode,
        done: next.changed ? next.done : base.done,
        started: next.changed ? next.started : base.started,
        objectives: loadTaskObjectivePairs(mode),
        syncedAt,
        changed: next.changed,
        completedIds: next.changed ? addedIdList(base.done, next.done) : [],
        source: "log",
      });
      if (!next.changed) return;
      const cached = queryClient.getQueryData(["guides-tarkov-task-dones", mode]);
      if (cached) {
        queryClient.setQueryData(
          ["guides-tarkov-task-dones", mode],
          taskProgressQueryData(
            next.done,
            next.started,
            loadTaskObjectivePairs(mode),
          ),
        );
      }
      if (opts?.put === false) return;
      void writeTarkovTaskDones(next.done, {
        startedIds: next.started,
      })
        .then((data) => {
          const objectives = data.objective_dones || loadTaskObjectivePairs(mode);
          saveTaskProgress(
            mode,
            data.task_ids || next.done,
            data.started_ids || next.started,
            true,
            true,
            objectives,
          );
          queryClient.setQueryData(
            ["guides-tarkov-task-dones", mode],
            taskProgressQueryData(
              data.task_ids || next.done,
              data.started_ids || next.started,
              objectives,
            ),
          );
          notifyTarkovTaskProgress({
            mode,
            done: data.task_ids || next.done,
            started: data.started_ids || next.started,
            objectives,
            syncedAt,
            changed: true,
            completedIds: addedIdList(base.done, data.task_ids || next.done),
            source: "log",
          });
        })
        .catch(() => {
          /* 未登录或网络失败时本机进度仍已写上 */
        });
    },
    [queryClient],
  );

  const applySessions = useCallback(
    (sessions: Array<{ parsed: ReturnType<typeof parseTarkovLogBundle> }>) => {
      lastParsedRef.current = sessions;
      const base = loadQuestBase();
      const next = nextLiveQuestProgress(
        base.done,
        base.started,
        sessions,
        gameModeRef.current,
        knownIdsRef.current,
      );
      commitQuestProgress(base, next);
    },
    [commitQuestProgress, loadQuestBase],
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
    return () => {
      window.removeEventListener(TARKOV_LIVE_DIRS_EVENT, onDirs);
      window.removeEventListener(TARKOV_SCREENSHOT_PRUNE_EVENT, onPrune);
    };
  }, [hydrate]);

  useEffect(() => {
    if (logSyncBusy) return;
    if (!lastParsedRef.current.length) return;
    applySessions(lastParsedRef.current);
  }, [applySessions, gameMode, logSyncBusy]);

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
          sessions.map((row) => row.folder),
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
          const mapId = latestLogMapId(newestRead.parsed);
          if (mapId) setLastLogMapId(mapId);
          setLastLogPhase(logPhaseFromParsed(newestRead.parsed));
        }
        const sessionRows = parsedSessions.map((row) => ({
          folder: row.read.folder,
          parsed: row.parsed,
        }));
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
  }, [applySessions, logPerm, queryClient, supported]);

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
      return { ok: true, hint: "", sessions };
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
    async (opts?: TarkovLogSyncOpts): Promise<{ ok: boolean; hint: string }> => {
      if (logTickBusyRef.current) {
        return { ok: false, hint: "正在读取日志，请稍后再试。" };
      }
      const range = opts?.from && opts?.to ? opts : defaultLogSyncRange();
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
      logTickBusyRef.current = true;
      const emptyDelta = { done: 0, started: 0, unfinished: 0 };
      try {
        const ready = await ensureLogsHandle();
        if (!ready.ok) return { ok: false, hint: ready.hint };
        if (abort.signal.aborted) return { ok: false, hint: "已取消同步。" };
        const handle = ready.handle;
        const { sessions } = await readLogsIndex(handle);
        const targets = filterSessionStubsByRange(
          takeSessionStubs(sessions, 0),
          range,
        );
        if (!targets.length) {
          return {
            ok: true,
            hint: sessions.length
              ? "这个日期范围内没有启动记录。"
              : formatLiveLogBackfillHint(0, "backfill", emptyDelta),
          };
        }
        const mode = gameModeRef.current;
        const prevDone = loadTaskDoneIds(mode);
        const prevStarted = loadTaskStartedIds(mode);
        const hadSync = Boolean(loadTaskSyncAt(mode));
        const base = loadQuestBase();
        let folded: Map<string, FoldedQuestEntry> = new Map();
        let questEvents = 0;
        let skipped = 0;
        const raidRows: TarkovRaidLogImportRow[] = [];
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
          skipped += read.skipped.length;
          const foldedStep = foldSessionQuests(folded, parsed, mode);
          folded = foldedStep.next;
          questEvents += foldedStep.eventCount;
          raidRows.push(...toRaidLogImportRows([{ folder: stub.folder, parsed }]));
          if (stub.folder === newestFolder) {
            newestParsed = parsed;
            newestFileTimes = read.files.map((file) => file.lastModified);
          }
          processed += 1;
          setLogSyncScan({ done: processed, total: oldestFirst.length });
          if (processed % 8 === 0) {
            const mid = mergeQuestProgressFromFolded(
              base.done,
              base.started,
              folded,
              questEvents,
              knownIdsRef.current,
            );
            commitQuestProgress(
              base,
              {
                done: mid.done,
                started: mid.started,
                changed:
                  !sameIdLists(base.done, mid.done) ||
                  !sameIdLists(base.started, mid.started),
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
            const mapId = latestLogMapId(newestParsed);
            if (mapId) setLastLogMapId(mapId);
            setLastLogPhase(logPhaseFromParsed(newestParsed));
          }
        }
        if (processed > 0) {
          const merged = mergeQuestProgressFromFolded(
            base.done,
            base.started,
            folded,
            questEvents,
            knownIdsRef.current,
          );
          const changed =
            !sameIdLists(base.done, merged.done) ||
            !sameIdLists(base.started, merged.started);
          commitQuestProgress(
            base,
            { done: merged.done, started: merged.started, changed },
          );
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
        let hint = formatLiveLogBackfillHint(
          processed,
          hadSync ? "incremental" : "backfill",
          questProgressDelta(prevDone, prevStarted, nextDone, nextStarted),
          { questEvents, skipped },
        );
        if (abort.signal.aborted) {
          hint = processed
            ? `${hint}（已取消）`
            : "已取消同步。";
        }
        return {
          ok: Boolean(processed) || !abort.signal.aborted,
          hint,
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
        logTickBusyRef.current = false;
        setLogSyncBusy(false);
        setLogSyncScan(null);
      }
    },
    [commitQuestProgress, ensureLogsHandle, loadQuestBase, queryClient],
  );

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
            </TarkovLiveFixContext.Provider>
          </TarkovLiveLogPhaseContext.Provider>
        </TarkovLiveLogMapContext.Provider>
      </TarkovLiveShotMetaContext.Provider>
    </TarkovLiveWatchContext.Provider>
  );
}
