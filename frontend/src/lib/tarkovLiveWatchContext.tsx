import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchTarkovTasks, writeTarkovTaskDones } from "@/api/guidesApi";
import {
  isFileSystemAccessSupported,
  isPickerAbort,
  loadStoredLogsDir,
  loadStoredLogsPath,
  loadStoredScreenshotsDir,
  loadStoredScreenshotsPath,
  peekSessionFingerprint,
  pickScreenshotsDirectory,
  pollLatestScreenshot,
  queryLogsDirPermission,
  readLogsIndex,
  readSessionLogs,
  requestLogsDirPermission,
  saveScreenshotsDir,
  type ReadableDir,
} from "@/lib/tarkovGameLogAccess";
import {
  TARKOV_SCREENSHOT_POLL_MS,
  isNewerScreenshot,
  latestLogMapId,
  parseTarkovLogBundle,
} from "@/lib/tarkovGameLogs";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  TARKOV_LIVE_DIRS_EVENT,
  addedIdList,
  logStampFromParsed,
  nextLiveQuestProgress,
  notifyTarkovTaskProgress,
  planLogSessionReads,
  sameIdLists,
  type LogPollCursor,
} from "@/lib/tarkovLiveWatch";
import {
  parseTarkovScreenshotName,
  type TarkovScreenshotPos,
} from "@/lib/tarkovScreenshotPos";
import { nowBeijingStamp } from "@/lib/time";
import {
  loadTaskCursorAt,
  loadTaskDoneIds,
  loadTaskStartedIds,
  saveTaskProgress,
  saveTaskSyncMark,
} from "@/lib/tarkovTaskTree";

export type TarkovScreenshotFix = TarkovScreenshotPos & {
  fileName: string;
  lastModified: number;
};

export type LiveWatchPerm = "unknown" | "none" | "prompt" | "granted";

type TarkovLiveWatchValue = {
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

const EMPTY: TarkovLiveWatchValue = {
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

const TarkovLiveWatchContext = createContext<TarkovLiveWatchValue>(EMPTY);

export function TarkovLiveWatchProvider({ children }: { children: ReactNode }) {
  const supported = isFileSystemAccessSupported();
  const gameMode = useTarkovGameMode();
  const queryClient = useQueryClient();
  const shotRef = useRef<ReadableDir | null>(null);
  const logRef = useRef<ReadableDir | null>(null);
  const seenShotNamesRef = useRef<Set<string>>(new Set());
  const shotStampRef = useRef<{ name: string; lastModified: number } | null>(
    null,
  );
  const logCursorRef = useRef<LogPollCursor | null>(null);
  const lastParsedRef = useRef<Array<{ parsed: ReturnType<typeof parseTarkovLogBundle> }>>(
    [],
  );
  const shotTickBusyRef = useRef(false);
  const logTickBusyRef = useRef(false);
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
  const [fix, setFix] = useState<TarkovScreenshotFix | null>(null);
  const [shotBusy, setShotBusy] = useState(false);

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

  const applySessions = useCallback(
    (sessions: Array<{ parsed: ReturnType<typeof parseTarkovLogBundle> }>) => {
      lastParsedRef.current = sessions;
      const mode = gameModeRef.current;
      const prevDone = loadTaskDoneIds(mode);
      const prevStarted = loadTaskStartedIds(mode);
      const afterAt = loadTaskCursorAt(mode);
      const next = nextLiveQuestProgress(
        prevDone,
        prevStarted,
        sessions,
        mode,
        knownIdsRef.current,
        afterAt,
      );
      const syncedAt = nowBeijingStamp();
      saveTaskSyncMark(
        mode,
        syncedAt,
        next.eventCount > 0 ? next.latestEventAt : undefined,
      );
      if (next.changed) {
        saveTaskProgress(mode, next.done, next.started);
      }
      notifyTarkovTaskProgress({
        mode,
        done: next.changed ? next.done : prevDone,
        started: next.changed ? next.started : prevStarted,
        syncedAt,
        changed: next.changed,
        completedIds: next.changed ? addedIdList(prevDone, next.done) : [],
      });
      if (!next.changed || sameIdLists(prevDone, next.done)) return;
      queryClient.setQueryData(["guides-tarkov-task-dones", mode], {
        task_ids: next.done,
      });
      void writeTarkovTaskDones(next.done, { replace: true }).catch(() => {
        /* 未登录或网络失败时本机进度仍已写上 */
      });
    },
    [queryClient],
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
      setShotPerm("none");
      setShotLabel("");
    } else {
      shotRef.current = storedShot;
      seenShotNamesRef.current = new Set();
      shotStampRef.current = null;
      setShotLabel(shotPath || storedShot.name);
      const current = await queryLogsDirPermission(storedShot);
      setShotPerm(current === "granted" ? "granted" : "prompt");
    }
    if (!storedLog) {
      logRef.current = null;
      setLogPerm("none");
      setLogLabel("");
    } else {
      logRef.current = storedLog;
      logCursorRef.current = null;
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
    window.addEventListener(TARKOV_LIVE_DIRS_EVENT, onDirs);
    return () => window.removeEventListener(TARKOV_LIVE_DIRS_EVENT, onDirs);
  }, [hydrate]);

  useEffect(() => {
    if (!lastParsedRef.current.length) return;
    applySessions(lastParsedRef.current);
  }, [applySessions, gameMode]);

  useEffect(() => {
    if (!supported || shotPerm !== "granted") return;
    seenShotNamesRef.current = new Set();
    shotStampRef.current = null;
    let cancelled = false;
    const tick = async () => {
      if (cancelled || document.hidden || shotTickBusyRef.current) return;
      const handle = shotRef.current;
      if (!handle) return;
      shotTickBusyRef.current = true;
      try {
        const { names, latest } = await pollLatestScreenshot(
          handle,
          seenShotNamesRef.current,
        );
        if (cancelled) return;
        for (const name of names) seenShotNamesRef.current.add(name);
        if (!latest) return;
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
      } catch {
        /* 保留上一次定位 */
      } finally {
        shotTickBusyRef.current = false;
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
        const newestRead = parsedSessions[parsedSessions.length - 1];
        if (newestRead) {
          const stamp = logStampFromParsed(
            newestRead.parsed,
            newestRead.read.files.map((file) => file.lastModified),
          );
          if (stamp != null) setLastLogAt(stamp);
          const mapId = latestLogMapId(newestRead.parsed);
          if (mapId) setLastLogMapId(mapId);
        }
        applySessions(parsedSessions.map((row) => ({ parsed: row.parsed })));
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
  }, [applySessions, logPerm, supported]);

  const resume = useCallback(async () => {
    if (!supported) return;
    const shot = shotRef.current;
    if (shot) {
      const next = await requestLogsDirPermission(shot);
      if (next === "granted") {
        await saveScreenshotsDir(shot);
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
        const next = await requestLogsDirPermission(existing);
        if (next === "granted") {
          await saveScreenshotsDir(existing);
          setShotPerm("granted");
          return;
        }
        setShotPerm("prompt");
        return;
      }
      const picked = await pickScreenshotsDirectory(null);
      const next = await requestLogsDirPermission(picked);
      if (next !== "granted") {
        setShotPerm("prompt");
        return;
      }
      shotRef.current = picked;
      seenShotNamesRef.current = new Set();
      shotStampRef.current = null;
      setShotLabel(picked.name);
      await saveScreenshotsDir(picked);
      setShotPerm("granted");
    } catch (error) {
      if (!isPickerAbort(error) && !shotRef.current) setShotPerm("none");
    } finally {
      setShotBusy(false);
    }
  }, [supported]);

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
      enableShots,
      resume,
    }),
    [
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
      resume,
      shotBusy,
      shotLabel,
      shotPerm,
      supported,
      visible,
    ],
  );

  return (
    <TarkovLiveWatchContext.Provider value={value}>
      {children}
    </TarkovLiveWatchContext.Provider>
  );
}

export function useTarkovLiveWatch(): TarkovLiveWatchValue {
  return useContext(TarkovLiveWatchContext);
}
