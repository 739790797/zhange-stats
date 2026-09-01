import { Alert, Input, Modal, Spin, message } from "antd";
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addTarkovKeyOwn,
  addTarkovRaidRoomMark,
  bringTarkovRaidRoomKey,
  claimTarkovRaidRoomTask,
  claimTarkovRaidRoomTasks,
  clearTarkovRaidRoomMarks,
  fetchTarkovMapDetail,
  fetchTarkovRaidPrep,
  fetchTarkovRaidPrepState,
  fetchTarkovRaidRoom,
  putTarkovRaidPrepState,
  fetchTarkovTaskDones,
  writeTarkovTaskDones,
  joinTarkovRaidRoom,
  leaveTarkovRaidRoom,
  markTarkovRaidRoomObjectivesDone,
  putTarkovRaidRoomTaskProgress,
  removeTarkovRaidRoomMark,
  removeTarkovRaidRoomMember,
  resetTarkovRaidRoom,
  seedTarkovRaidRoomClaimsFromProgress,
  setTarkovRaidRoomMap,
  setTarkovRaidRoomPassword,
  tarkovRaidRoomWsUrl,
  transferTarkovRaidRoomHost,
  removeTarkovKeyOwn,
  unbringTarkovRaidRoomKey,
  unclaimTarkovRaidRoomTask,
  undoTarkovRaidRoomMark,
  type TarkovRaidRoomDetail,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode, useTarkovGameModeControls, parseTarkovGameMode } from "@/lib/tarkovGameMode";
import { TARKOV_RAID_PREP_PATH } from "@/lib/tarkovHomeNav";
import {
  RAID_PREP_MAX_SELECTED,
  buildRaidPrepOverlays,
  colorForTaskIndex,
  colorForUserId,
  filterRaidPrepOverlaysForViewer,
  filterRaidPrepRows,
  groupRaidPrepRowsByProgress,
  hydrateRaidPrepCatalogRows,
  planRaidPrepTaskProgressSync,
  objectiveDonesToSkipMap,
  raidPrepAutoSwitchMapId,
  raidPrepMapOptions,
  raidPrepSkippedIds,
  resolveRaidPrepLocateTargets,
  roomObjectiveMarksForCompletedTasks,
  raidPrepObjectiveDoneLegacyScopes,
  raidPrepObjectiveDoneScope,
  raidPrepSkipMapsEqual,
  raidPrepTaskProgressStatus,
  readRaidPrepObjectiveDoneWithLegacy,
  mergeRaidPrepSkipMaps,
  skipMapToObjectiveDones,
  pinSelectedRaidPrepRows,
  useRaidPrepObjectiveDone,
  selectedTasksFromCatalog,
  settleRaidPrepSelection,
  type RaidPrepTaskProgressStatus,
} from "@/lib/tarkovRaidPrep";
import {
  TARKOV_TASK_PROGRESS_EVENT,
  type TarkovTaskProgressDetail,
} from "@/lib/tarkovLiveWatch";
import { useTarkovLastLogMapId, useTarkovLastLogPhase } from "@/lib/tarkovLiveWatchContext";
import { useRaidPrepGeometry } from "@/lib/useRaidPrepGeometry";
import { useTarkovRaidDockOpen } from "@/lib/tarkovRaidDockPrefs";
import { useRaidRoomLiveStore } from "@/lib/tarkovRaidRoomLiveStore";
import { logMapLabel } from "@/lib/tarkovGameLogs";
import { applyTarkovKeyOwnsCache } from "@/lib/tarkovKeyPacks";
import {
  commitTaskStatus,
  loadTaskDoneIds,
  loadTaskStartedIds,
} from "@/lib/tarkovTaskTree";
import {
  applyRoomWsEvent,
  keepRaidRoomPresence,
  formatRaidRoomLiveStatus,
  formatRaidRoomMemberChipLine,
  raidRoomMemberRegionLabel,
  groupClaimsByTask,
  claimTaskIdsForUser,
  parseRaidRoomLogPhases,
  overlayRaidRoomLocalPhase,
  normalizeRaidRoomRaidId,
  raidRoomCanAutoSwitchMap,
  raidRoomPickDockMapId,
  raidRoomSharedRaidMapId,
  raidRoomLiveStatus,
  patchRaidRoomKeyOwns,
  userBroughtKey,
  userOwnsKey,
  isTypingTarget,
  mergeBoardMarks,
  parsePlayerFixEvent,
  parseStrokePoints,
  playerFixMatchesRoomMap,
  RAID_ROOM_WS_PING_MS,
  raidRoomWsRetryDelayMs,
  withRaidRoomViewerFlags,
  type RaidRoomMarkLike,
  type RaidRoomLogPhase,
  type StrokePoint,
  type TarkovMapDrawMode,
} from "@/lib/tarkovRaidRooms";
import { PanelFallback } from "@/components/RouteFallback";
import { TarkovRaidPrepFilters } from "@/components/guides/tarkov/TarkovRaidPrepFilters";
import { TarkovRaidPrepTaskGroups } from "@/components/guides/tarkov/TarkovRaidPrepTaskGroups";
import { TarkovRaidPrepOcrModal } from "@/components/guides/tarkov/TarkovRaidPrepOcrModal";
import { TarkovRaidPrepSummary } from "@/components/guides/tarkov/TarkovRaidPrepSummary";
import { TarkovRaidPrepGuideOverview } from "@/components/guides/tarkov/TarkovRaidPrepGuideOverview";
import { TarkovRaidPrepTaskCard } from "@/components/guides/tarkov/TarkovRaidPrepTaskCard";
import { TarkovRaidRoomOverlapBoard } from "@/components/guides/tarkov/TarkovRaidRoomOverlapBoard";
import { useTarkovGoonTracker } from "@/lib/tarkovGoonTrackerLive";
import {
  TarkovGoonRoomNotice,
  TarkovGoonSightingHint,
} from "@/components/guides/tarkov/TarkovGoonTrackerBanner";
import type { TarkovMapFocusRequest } from "@/components/guides/tarkov/TarkovMapViewer";
import { useAuthStore } from "@/stores/authStore";
import catalogCss from "./TarkovItemCatalogPanel.module.css";
import styles from "./TarkovRaidPrepPanel.module.css";

const TarkovRaidRoomLiveMap = lazy(() =>
  import("@/components/guides/tarkov/TarkovRaidRoomLiveMap").then((m) => ({
    default: m.TarkovRaidRoomLiveMap,
  })),
);

export function TarkovRaidRoomPanel({ publicId }: { publicId: string }) {
  const gameMode = useTarkovGameMode();
  const { setMode } = useTarkovGameModeControls();
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();
  const me = useAuthStore((s) => s.user);
  const [room, setRoom] = useState<TarkovRaidRoomDetail | null>(null);
  const [keyword, setKeyword] = useState("");
  const [query, setQuery] = useState("");
  const [tool, setTool] = useState<TarkovMapDrawMode>("pan");
  const [progressTick, setProgressTick] = useState(0);
  const meIdRef = useRef(me?.id);
  meIdRef.current = me?.id;
  const [pendingMarks, setPendingMarks] = useState<RaidRoomMarkLike[]>([]);
  const [wsGen, setWsGen] = useState(0);
  const [wsLive, setWsLive] = useState(false);
  const [logPhases, setLogPhases] = useState<RaidRoomLogPhase[]>([]);
  const lastLogMapId = useTarkovLastLogMapId();
  const lastLogPhase = useTarkovLastLogPhase();
  const lastLogPhaseSigRef = useRef("");
  const autoClaimKeyRef = useRef("");
  const [error, setError] = useState("");
  const [guideOpen, setGuideOpen] = useState(false);
  const [guideTaskId, setGuideTaskId] = useState("");
  const [ocrOpen, setOcrOpen] = useState(false);
  const [highlightTaskId, setHighlightTaskId] = useState("");
  const [dockOpen, setDockOpen] = useTarkovRaidDockOpen();
  const [statsOpen, setStatsOpen] = useState(false);
  const [previewMapId, setPreviewMapId] = useState("");
  const [pickingMap, setPickingMap] = useState(false);
  const [manageOpen, setManageOpen] = useState(false);
  const [joinPassword, setJoinPassword] = useState("");
  const [passwordDraft, setPasswordDraft] = useState("");
  const [managePassLocked, setManagePassLocked] = useState(true);
  const [focusRequest, setFocusRequest] = useState<TarkovMapFocusRequest | null>(
    null,
  );
  const objDoneScope = raidPrepObjectiveDoneScope(
    room?.map_slug || "",
    gameMode,
    me?.id,
  );
  const objDoneLegacy = useMemo(
    () => raidPrepObjectiveDoneLegacyScopes(room?.map_slug || "", publicId),
    [publicId, room?.map_slug],
  );
  const [objDone, toggleObjDoneLocal, replaceObjDone] = useRaidPrepObjectiveDone(
    objDoneScope,
    objDoneLegacy,
  );
  const objSeedKeyRef = useRef("");
  const focusSeqRef = useRef(0);
  const locateIndexRef = useRef<Record<string, number>>({});
  const wsRef = useRef<WebSocket | null>(null);
  const lastProgressKeyRef = useRef("");
  const autoMapSigRef = useRef("");

  const roomQuery = useQuery({
    queryKey: ["guides-tarkov-raid-room", publicId],
    queryFn: () => fetchTarkovRaidRoom(publicId),
    retry: 1,
    refetchInterval: (query) =>
      query.state.data?.is_member && !wsLive ? 30_000 : false,
  });
  const refetchRoomRef = useRef(roomQuery.refetch);
  refetchRoomRef.current = roomQuery.refetch;

  useEffect(() => {
    if (roomQuery.data) {
      const next = withRaidRoomViewerFlags(roomQuery.data, meIdRef.current);
      setRoom((current) => {
        if (!current) return next;
        const currentMarks = current.marks?.length || 0;
        const nextMarks = next.marks?.length || 0;
        if (currentMarks > nextMarks) return current;
        return keepRaidRoomPresence(next, current);
      });
    }
  }, [roomQuery.data]);

  const canEdit = Boolean(room?.can_edit);
  const mapId = room?.map_slug || "";
  const mapIdRef = useRef(mapId);
  mapIdRef.current = mapId;
  const showOverlap = !mapId;
  const mapOptions = useMemo(() => raidPrepMapOptions(), []);
  const { status: goonStatus } = useTarkovGoonTracker();
  const overlapSlugs = useMemo(
    () => (room?.map_overlap || []).map((row) => row.map_slug).filter(Boolean),
    [room?.map_overlap],
  );
  const defaultDockMapId = useMemo(
    () =>
      raidRoomPickDockMapId({
        goonMapSlug: goonStatus?.map_slug,
        overlapSlugs,
        mapOptionIds: mapOptions.map((item) => item.id),
        currentMapId: mapId,
      }),
    [goonStatus?.map_slug, mapId, mapOptions, overlapSlugs],
  );
  const dockMapId = showOverlap ? previewMapId || defaultDockMapId : mapId;
  const canClaimOnDock = Boolean(canEdit && mapId && dockMapId === mapId);
  useEffect(() => {
    if (!showOverlap) return;
    if (typeof window === "undefined") return;
    if (window.matchMedia("(min-width: 981px)").matches) {
      setDockOpen(true);
    }
  }, [setDockOpen, showOverlap]);
  const canEditRef = useRef(canEdit);
  canEditRef.current = canEdit;
  const roomObjDonesRef = useRef(room?.objective_dones);
  roomObjDonesRef.current = room?.objective_dones;

  /* 只跟 token / 房间身份重连，快照更新不要拆掉 WS */
  // oxlint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    const isMember = Boolean(roomQuery.data?.is_member || room?.is_member);
    if (!token || !publicId || !isMember) {
      return undefined;
    }
    let stopped = false;
    let retry = 0;
    let ws: WebSocket | null = null;
    let ping = 0;
    let retryTimer = 0;

    const connect = () => {
      if (stopped) return;
      ws = new WebSocket(tarkovRaidRoomWsUrl(publicId));
      wsRef.current = ws;
      ws.onopen = () => {
        retry = 0;
        ws?.send(JSON.stringify({ event: "auth", token }));
      };
      ws.onmessage = (event) => {
        let payload: {
          event?: string;
          snapshot?: TarkovRaidRoomDetail;
          online_user_ids?: number[];
          user_id?: number;
          floor?: string;
          points?: unknown;
          x?: unknown;
          y?: unknown;
          z?: unknown;
          yaw?: unknown;
          map_id?: unknown;
          file_name?: unknown;
          log_phases?: unknown;
          mark?: { author_user_id?: number };
        };
        try {
          payload = JSON.parse(String(event.data || ""));
        } catch {
          return;
        }
        if (payload.event === "snapshot") {
          setWsLive(true);
          setWsGen((n) => n + 1);
          setLogPhases(parseRaidRoomLogPhases(payload.log_phases));
          if (ws?.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ event: "ping" }));
          }
        }
        if (payload.event === "log_phase") {
          setLogPhases(parseRaidRoomLogPhases(payload.log_phases));
        }
        if (payload.event === "player_fix") {
          const parsed = parsePlayerFixEvent(payload);
          if (!parsed || parsed.userId === meIdRef.current) return;
          if (!playerFixMatchesRoomMap(parsed.mapId, mapIdRef.current)) return;
          useRaidRoomLiveStore.getState().upsertFix(parsed);
          return;
        }
        if (payload.event === "presence" && payload.online_user_ids) {
          const online = new Set(payload.online_user_ids);
          useRaidRoomLiveStore.getState().dropFixesNotIn(online);
        }
        if (payload.event === "draw_draft") {
          const uid = Number(payload.user_id);
          if (!uid || uid === meIdRef.current) return;
          const points = parseStrokePoints(payload.points);
          useRaidRoomLiveStore.getState().setDraft(
            points.length
              ? {
                  userId: uid,
                  floor: String(payload.floor || ""),
                  points,
                  color: colorForUserId(uid),
                }
              : null,
            uid,
          );
          return;
        }
        if (payload.event === "mark_add") {
          const uid = Number(payload.mark?.author_user_id);
          if (uid) useRaidRoomLiveStore.getState().setDraft(null, uid);
        }
        if (payload.event === "board_clear") {
          useRaidRoomLiveStore.getState().clearDrafts();
          setPendingMarks([]);
        }
        if (payload.event === "reset") {
          navigate(TARKOV_RAID_PREP_PATH);
          return;
        }
        if (payload.event === "member_leave") {
          const uid = Number(payload.user_id);
          if (uid) useRaidRoomLiveStore.getState().dropFixUser(uid);
          if (uid && uid === meIdRef.current) {
            navigate(TARKOV_RAID_PREP_PATH);
            return;
          }
        }
        setRoom((current) =>
          applyRoomWsEvent(current, payload, meIdRef.current),
        );
      };
      ws.onclose = () => {
        setWsLive(false);
        if (stopped) return;
        void refetchRoomRef.current();
        retryTimer = window.setTimeout(() => {
          connect();
        }, raidRoomWsRetryDelayMs(retry));
        retry += 1;
      };
    };

    connect();
    ping = window.setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ event: "ping" }));
      }
    }, RAID_ROOM_WS_PING_MS);
    const onVisible = () => {
      if (
        document.visibilityState === "visible" &&
        wsRef.current?.readyState === WebSocket.OPEN
      ) {
        wsRef.current.send(JSON.stringify({ event: "ping" }));
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      stopped = true;
      document.removeEventListener("visibilitychange", onVisible);
      window.clearInterval(ping);
      window.clearTimeout(retryTimer);
      setWsLive(false);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [token, publicId, room?.is_member, roomQuery.data?.is_member]);

  useEffect(() => {
    lastLogPhaseSigRef.current = "";
    setLogPhases([]);
  }, [publicId]);

  useEffect(() => {
    const ws = wsRef.current;
    if (
      !room?.is_member ||
      !lastLogPhase ||
      !wsLive ||
      !ws ||
      ws.readyState !== WebSocket.OPEN
    ) {
      return;
    }
    const sig = `${lastLogPhase.kind}:${lastLogPhase.raidId}:${lastLogPhase.at}:${wsGen}`;
    if (lastLogPhaseSigRef.current === sig) return;
    lastLogPhaseSigRef.current = sig;
    ws.send(
      JSON.stringify({
        event: "log_phase",
        kind: lastLogPhase.kind,
        map_id: lastLogPhase.mapId,
        map_label: lastLogPhase.mapLabel,
        raid_id: lastLogPhase.raidId,
        at: lastLogPhase.at,
      }),
    );
  }, [lastLogPhase, room?.is_member, wsGen, wsLive]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setQuery(keyword.trim());
    }, 300);
    return () => window.clearTimeout(handle);
  }, [keyword]);

  const prepQuery = useQuery({
    queryKey: ["guides-tarkov-raid-prep", gameMode, dockMapId],
    queryFn: () => fetchTarkovRaidPrep({ map: dockMapId }),
    enabled: Boolean(dockMapId),
    staleTime: 5 * 60_000,
    retry: 1,
  });
  const taskDonesQuery = useQuery({
    queryKey: ["guides-tarkov-task-dones", gameMode],
    queryFn: fetchTarkovTaskDones,
    staleTime: 30_000,
  });
  const stateQuery = useQuery({
    queryKey: ["guides-tarkov-raid-prep-state", gameMode, mapId],
    queryFn: () => fetchTarkovRaidPrepState(mapId),
    enabled: Boolean(mapId && me),
    staleTime: 30_000,
  });
  const doneTaskIds = taskDonesQuery.data?.task_ids ?? loadTaskDoneIds(gameMode);
  const startedTaskIds = useMemo(
    () => loadTaskStartedIds(gameMode),
    [gameMode, progressTick],
  );

  const mapQuery = useQuery({
    queryKey: ["guides-tarkov-map", gameMode, mapId],
    queryFn: () => fetchTarkovMapDetail(mapId),
    enabled: Boolean(mapId),
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const claimedKey = (room?.claims || [])
    .map((row) => row.task_id)
    .filter(Boolean)
    .sort()
    .join(",");
  const claimedIds = useMemo(
    () => claimedKey.split(",").filter(Boolean),
    [claimedKey],
  );
  const geometry = useRaidPrepGeometry(mapId, claimedIds);

  const applyRoom = useCallback((next: TarkovRaidRoomDetail) => {
    setRoom((current) =>
      withRaidRoomViewerFlags(
        keepRaidRoomPresence(next, current),
        meIdRef.current,
      ),
    );
    setError("");
  }, []);

  const run = useCallback(
    async (action: () => Promise<TarkovRaidRoomDetail>) => {
      try {
        applyRoom(await action());
        return true;
      } catch (exc) {
        setError(apiError(exc, "操作失败"));
        return false;
      }
    },
    [applyRoom],
  );

  useEffect(() => {
    if (!token || !publicId || !room?.is_member) return undefined;
    let cancelled = false;
    const push = () => {
      const started = loadTaskStartedIds(gameMode);
      const done = loadTaskDoneIds(gameMode);
      const key = `${publicId}:${gameMode}:${started.join(",")}|${done.join(",")}`;
      if (key === lastProgressKeyRef.current) return;
      lastProgressKeyRef.current = key;
      void putTarkovRaidRoomTaskProgress(publicId, {
        started_ids: started,
        done_ids: done,
      })
        .then((next) => {
          if (!cancelled) applyRoom(next);
        })
        .catch((exc) => {
          lastProgressKeyRef.current = "";
          if (!cancelled) setError(apiError(exc, "同步进行中任务失败"));
        });
    };
    push();
    const onProgress = (event: Event) => {
      const detail = (event as CustomEvent<TarkovTaskProgressDetail>).detail;
      if (!detail || detail.mode !== gameMode) return;
      setProgressTick((n) => n + 1);
      push();
    };
    window.addEventListener(TARKOV_TASK_PROGRESS_EVENT, onProgress);
    return () => {
      cancelled = true;
      window.removeEventListener(TARKOV_TASK_PROGRESS_EVENT, onProgress);
    };
  }, [applyRoom, gameMode, publicId, room?.is_member, token]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isTypingTarget(event.target)) return;
      if (event.key === "Escape") {
        setTool("pan");
        return;
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        if (canEdit) void run(() => undoTarkovRaidRoomMark(publicId));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [canEdit, publicId, run]);

  const resetMut = useMutation({
    mutationFn: () => resetTarkovRaidRoom(publicId),
    onSuccess: () => navigate(TARKOV_RAID_PREP_PATH),
    onError: (exc) => setError(apiError(exc, "清空房间失败")),
  });
  const kickMut = useMutation({
    mutationFn: (userId: number) =>
      removeTarkovRaidRoomMember(publicId, userId),
    onSuccess: (next) => applyRoom(next),
    onError: (exc) => setError(apiError(exc, "移除失败")),
  });
  const transferMut = useMutation({
    mutationFn: (userId: number) =>
      transferTarkovRaidRoomHost(publicId, userId),
    onSuccess: (next) => {
      applyRoom(next);
      if (!next.is_host) setManageOpen(false);
    },
    onError: (exc) => setError(apiError(exc, "转让房主失败")),
  });
  const leaveMut = useMutation({
    mutationFn: () => leaveTarkovRaidRoom(publicId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["guides-tarkov-raid-rooms"] });
      navigate(TARKOV_RAID_PREP_PATH);
    },
    onError: (exc) => setError(apiError(exc, "离开失败")),
  });
  const joinMut = useMutation({
    mutationFn: () =>
      joinTarkovRaidRoom(publicId, {
        gameMode,
        password: joinPassword.trim() || undefined,
      }),
    onSuccess: (next) => {
      setJoinPassword("");
      applyRoom(next);
    },
    onError: (exc) => setError(apiError(exc, "加入失败")),
  });
  const passwordMut = useMutation({
    mutationFn: (password: string | null) =>
      setTarkovRaidRoomPassword(publicId, password),
    onSuccess: (next) => {
      setPasswordDraft("");
      applyRoom(next);
    },
    onError: (exc) => setError(apiError(exc, "设置密码失败")),
  });

  const claims = room?.claims;
  const myClaimIds = useMemo(
    () => claimTaskIdsForUser(claims, me?.id),
    [claims, me?.id],
  );
  const myClaims = useMemo(() => new Set(myClaimIds), [myClaimIds]);
  const groups = useMemo(() => groupClaimsByTask(claims), [claims]);
  const participantsByTask = useMemo(() => {
    const map = new Map<string, Array<{ name: string; userId: number }>>();
    for (const group of groups) {
      map.set(
        group.taskId,
        group.userIds.map((userId, index) => ({
          userId,
          name: group.names[index],
        })),
      );
    }
    return map;
  }, [groups]);
  const catalog = useMemo(
    () => prepQuery.data?.items ?? [],
    [prepQuery.data],
  );
  const catalogRich = useMemo(
    () => hydrateRaidPrepCatalogRows(catalog, geometry.byId),
    [catalog, geometry.byId],
  );
  const selectedTasks = useMemo(
    () =>
      selectedTasksFromCatalog(
        catalogRich,
        groups.map((row) => row.taskId),
      ),
    [catalogRich, groups],
  );
  const overlayTasks = geometry.items;
  const rows = useMemo(
    () =>
      filterRaidPrepRows(catalogRich, { q: query }),
    [catalogRich, query],
  );
  const statusGroups = useMemo(() => {
    const grouped = groupRaidPrepRowsByProgress(
      rows,
      doneTaskIds,
      startedTaskIds,
    );
    return {
      active: pinSelectedRaidPrepRows(grouped.active, myClaims),
      todo: pinSelectedRaidPrepRows(grouped.todo, myClaims),
      done: pinSelectedRaidPrepRows(grouped.done, myClaims),
    };
  }, [doneTaskIds, myClaims, rows, startedTaskIds]);
  const taskStatusOf = (taskId: string) =>
    raidPrepTaskProgressStatus(taskId, doneTaskIds, startedTaskIds);
  const changeTaskStatus = useCallback(
    (taskId: string, status: RaidPrepTaskProgressStatus) => {
      if (raidPrepTaskProgressStatus(taskId, doneTaskIds, startedTaskIds) === status) {
        return;
      }
      const next = commitTaskStatus(gameMode, taskId, status);
      queryClient.setQueryData(["guides-tarkov-task-dones", gameMode], {
        task_ids: next.done,
      });
      void writeTarkovTaskDones(next.done, { replace: true }).catch(() => {});
    },
    [doneTaskIds, gameMode, queryClient, startedTaskIds],
  );
  const overlayTasksRef = useRef(overlayTasks);
  overlayTasksRef.current = overlayTasks;
  const overlays = useMemo(
    () =>
      filterRaidPrepOverlaysForViewer(
        buildRaidPrepOverlays(overlayTasks, mapId),
        objDone,
      ),
    [overlayTasks, mapId, objDone],
  );
  const markQueueRef = useRef(Promise.resolve());
  const flushCompletedTaskMarks = useCallback(
    (completedIds: readonly string[]) => {
      if (!completedIds.length) return;
      markQueueRef.current = markQueueRef.current.then(async () => {
        if (!canEditRef.current || !mapIdRef.current) return;
        const pending = roomObjectiveMarksForCompletedTasks(
          completedIds,
          overlayTasksRef.current,
          mapIdRef.current,
          roomObjDonesRef.current,
          meIdRef.current,
        );
        if (!pending.length) return;
        const extra = new Map<string, Set<string>>();
        for (const row of pending) {
          const bucket = new Set(extra.get(row.taskId) || []);
          bucket.add(row.objectiveId);
          extra.set(row.taskId, bucket);
        }
        const local = readRaidPrepObjectiveDoneWithLegacy(
          objDoneScope,
          objDoneLegacy,
        );
        const merged = mergeRaidPrepSkipMaps(local, extra);
        if (!raidPrepSkipMapsEqual(local, merged)) replaceObjDone(merged);
        await run(() =>
          markTarkovRaidRoomObjectivesDone(
            publicId,
            pending.map((row) => ({
              task_id: row.taskId,
              objective_id: row.objectiveId,
            })),
          ),
        );
      }).catch(() => {
        /* 单次失败不堵后续日志回填 */
      });
    },
    [objDoneLegacy, objDoneScope, publicId, replaceObjDone, run],
  );

  useEffect(() => {
    const onProgress = (event: Event) => {
      const detail = (event as CustomEvent<TarkovTaskProgressDetail>).detail;
      if (!detail || detail.mode !== gameMode) return;
      setProgressTick((n) => n + 1);
      flushCompletedTaskMarks(detail.completedIds || []);
      if (!canEdit) return;
      const plan = planRaidPrepTaskProgressSync({
        catalogIds: catalog.map((row) => row.id),
        selectedIds: myClaimIds,
        startedIds: detail.started,
        doneIds: detail.done,
        occupiedIds: groups.map((row) => row.taskId),
      });
      if (plan.addedIds.length) {
        void run(() => claimTarkovRaidRoomTasks(publicId, plan.addedIds));
      }
      const settled = settleRaidPrepSelection({
        selectedIds: myClaimIds,
        completedIds: detail.completedIds?.length
          ? detail.completedIds
          : detail.done,
      });
      for (const id of settled.removedIds) {
        void run(() => unclaimTarkovRaidRoomTask(publicId, id));
      }
    };
    window.addEventListener(TARKOV_TASK_PROGRESS_EVENT, onProgress);
    return () =>
      window.removeEventListener(TARKOV_TASK_PROGRESS_EVENT, onProgress);
  }, [
    canEdit,
    catalog,
    flushCompletedTaskMarks,
    gameMode,
    groups,
    myClaimIds,
    publicId,
    run,
  ]);

  useEffect(() => {
    if (!canEdit || !mapId || !claimedKey) return;
    const localDone = new Set(loadTaskDoneIds(gameMode));
    flushCompletedTaskMarks(
      overlayTasksRef.current
        .map((task) => task.id)
        .filter((id) => localDone.has(id)),
    );
  }, [
    canEdit,
    claimedKey,
    flushCompletedTaskMarks,
    gameMode,
    geometry.items,
    mapId,
  ]);
  const colorByTask = useMemo(() => {
    const map = new Map<string, string>();
    groups.forEach((group, index) => {
      map.set(group.taskId, colorForTaskIndex(index));
    });
    return map;
  }, [groups]);
  const currentMap = mapOptions.find((item) => item.id === mapId);
  const dockMapLabel =
    mapOptions.find((item) => item.id === dockMapId)?.label || dockMapId;
  const mapLabel = currentMap?.label || mapId;
  const title = (room?.title || "").trim() || `${publicId}号房`;
  const members =
    room?.occupants?.length
      ? room.occupants
      : (room?.members || []).filter((row) => row.in_room !== false);
  const seatedActing = useMemo(() => {
    const fromMembers = (room?.members || []).filter((row) => row.in_room !== false);
    const rows = fromMembers.length ? fromMembers : members;
    return rows.map((row) =>
      row.user_id === me?.id ? { ...row, online: Boolean(row.online || wsLive) } : row,
    );
  }, [members, me?.id, room?.members, wsLive]);
  const canSwitchMap = raidRoomCanAutoSwitchMap(
    me?.id,
    room?.host_user_id,
    seatedActing,
  );
  const displayLogPhases = useMemo(
    () => overlayRaidRoomLocalPhase(logPhases, me?.id, lastLogPhase),
    [lastLogPhase, logPhases, me?.id],
  );
  const phaseByUser = useMemo(() => {
    const map = new Map<number, RaidRoomLogPhase>();
    for (const row of displayLogPhases) map.set(row.userId, row);
    return map;
  }, [displayLogPhases]);
  const roomLiveStatus = raidRoomLiveStatus(
    members.map((row) => row.user_id),
    displayLogPhases,
  );
  const hideLocalFix = Boolean(
    lastLogMapId && !playerFixMatchesRoomMap(lastLogMapId, mapId),
  );

  const askChangeMap = () => {
    setPreviewMapId(mapId);
    setStatsOpen(true);
  };

  const echoedRaidId =
    me?.id &&
    lastLogPhase?.raidId &&
    normalizeRaidRoomRaidId(
      logPhases.find((row) => row.userId === me.id)?.raidId,
    ) === normalizeRaidRoomRaidId(lastLogPhase.raidId)
      ? lastLogPhase.raidId
      : "";
  const sharedAutoMapId = me?.id && echoedRaidId
    ? raidRoomSharedRaidMapId({
        myUserId: me.id,
        myRaidId: echoedRaidId,
        myMapId: lastLogPhase?.mapId || lastLogMapId,
        myKind: lastLogPhase?.kind,
        currentMapId: mapId,
        phases: logPhases,
        occupantIds: members.map((row) => row.user_id),
      })
    : "";

  const pickMapAndSeed = (nextMap: string, fromLog = false) => {
    if (!nextMap || pickingMap) return;
    if (nextMap === mapId) {
      setStatsOpen(false);
      return;
    }
    const apply = async () => {
      setPickingMap(true);
      try {
        const mapped = await run(() => setTarkovRaidRoomMap(publicId, nextMap));
        if (!mapped) return;
        setStatsOpen(false);
        const seeded = await run(() =>
          seedTarkovRaidRoomClaimsFromProgress(publicId),
        );
        if (seeded) {
          const label = logMapLabel(nextMap);
          message.success(
            fromLog && nextMap === sharedAutoMapId
              ? `已按同一战局切换到${label}，并按进行中任务勾到房间`
              : fromLog
                ? `已按你的游戏日志切换到${label}，并按进行中任务勾到房间`
                : "已选图，并按进行中任务勾到房间",
          );
        }
      } finally {
        setPickingMap(false);
      }
    };
    if (mapId && !fromLog) {
      Modal.confirm({
        title: "切换到该地图？",
        content: "换图会清空当前点位、勾选、钥匙和完成进度。",
        okText: "换图",
        cancelText: "取消",
        zIndex: 1100,
        onOk: () => apply(),
      });
      return;
    }
    void apply();
  };

  const autoMapId =
    sharedAutoMapId ||
    (!mapId && canSwitchMap
      ? raidPrepAutoSwitchMapId({
          currentMapId: "",
          logMapId: lastLogPhase?.mapId || lastLogMapId,
          phaseKind: lastLogPhase?.kind,
          fillEmpty: true,
        })
      : "");
  useEffect(() => {
    autoMapSigRef.current = "";
    autoClaimKeyRef.current = "";
  }, [publicId]);
  useEffect(() => {
    if (!autoMapId || pickingMap) return;
    if (!sharedAutoMapId && !canSwitchMap) return;
    const sig = `${publicId}:${autoMapId}:${lastLogPhase?.raidId || ""}:${sharedAutoMapId ? "raid" : lastLogPhase?.kind || "idle"}`;
    if (autoMapSigRef.current === sig) return;
    autoMapSigRef.current = sig;
    pickMapAndSeed(autoMapId, true);
  }, [
    autoMapId,
    canSwitchMap,
    lastLogPhase?.kind,
    lastLogPhase?.raidId,
    pickingMap,
    publicId,
    sharedAutoMapId,
  ]);

  const toggleClaim = useCallback(
    (taskId: string) => {
      if (!canClaimOnDock) return;
      if (myClaims.has(taskId)) {
        void run(() => unclaimTarkovRaidRoomTask(publicId, taskId));
        return;
      }
      if (
        raidPrepTaskProgressStatus(taskId, doneTaskIds, startedTaskIds) ===
        "done"
      ) {
        return;
      }
      const uniqueClaimed = groups.length;
      if (!groups.some((g) => g.taskId === taskId) && uniqueClaimed >= RAID_PREP_MAX_SELECTED) {
        setError(`最多勾选 ${RAID_PREP_MAX_SELECTED} 个任务`);
        return;
      }
      void run(() => claimTarkovRaidRoomTask(publicId, taskId));
    },
    [canClaimOnDock, doneTaskIds, groups, myClaims, publicId, run, startedTaskIds],
  );

  useEffect(() => {
    if (!canEdit || !mapId || dockMapId !== mapId || !room?.is_member || !prepQuery.isSuccess) return;
    const key = `${publicId}:${mapId}:${gameMode}`;
    if (autoClaimKeyRef.current === key) return;
    autoClaimKeyRef.current = key;
    const plan = planRaidPrepTaskProgressSync({
      catalogIds: catalog.map((row) => row.id),
      selectedIds: myClaimIds,
      startedIds: loadTaskStartedIds(gameMode),
      doneIds: loadTaskDoneIds(gameMode),
      occupiedIds: groups.map((row) => row.taskId),
    });
    if (!plan.addedIds.length) return;
    void run(() => claimTarkovRaidRoomTasks(publicId, plan.addedIds));
  }, [
    canEdit,
    catalog,
    dockMapId,
    gameMode,
    groups,
    mapId,
    myClaimIds,
    prepQuery.isSuccess,
    publicId,
    room?.is_member,
    run,
  ]);

  const syncFromTaskProgress = () => {
    if (!canClaimOnDock) return;
    const plan = planRaidPrepTaskProgressSync({
      catalogIds: catalog.map((row) => row.id),
      selectedIds: myClaimIds,
      startedIds: loadTaskStartedIds(gameMode),
      doneIds: loadTaskDoneIds(gameMode),
      occupiedIds: groups.map((row) => row.taskId),
    });
    if (!plan.addedIds.length) {
      message.info(plan.hint);
      return;
    }
    setDockOpen(true);
    void (async () => {
      const ok = await run(() =>
        claimTarkovRaidRoomTasks(publicId, plan.addedIds),
      );
      if (ok) message.success(plan.hint);
    })();
  };

  const toggleKeyBring = useCallback(
    (itemId: string) => {
      if (!canEdit) return;
      if (userBroughtKey(room?.key_brings, itemId, me?.id)) {
        void run(() => unbringTarkovRaidRoomKey(publicId, itemId));
        return;
      }
      void run(() => bringTarkovRaidRoomKey(publicId, itemId));
    },
    [canEdit, me?.id, publicId, room?.key_brings, run],
  );
  const toggleKeyOwn = useCallback(
    async (itemId: string) => {
      if (!me) return;
      const have = userOwnsKey(room?.key_owns, itemId, me.id);
      const name =
        (me.display_name || me.username || "").trim() || `用户${me.id}`;
      const user = { userId: me.id, name };
      setRoom((current) =>
        current
          ? {
              ...current,
              key_owns: patchRaidRoomKeyOwns(
                current.key_owns,
                itemId,
                user,
                !have,
              ),
            }
          : current,
      );
      try {
        const data = have
          ? await removeTarkovKeyOwn(itemId)
          : await addTarkovKeyOwn(itemId);
        applyTarkovKeyOwnsCache(queryClient, data.item_ids || []);
      } catch (exc) {
        setRoom((current) =>
          current
            ? {
                ...current,
                key_owns: patchRaidRoomKeyOwns(
                  current.key_owns,
                  itemId,
                  user,
                  have,
                ),
              }
            : current,
        );
        setError(apiError(exc, "更新钥匙拥有失败"));
      }
    },
    [me, queryClient, room?.key_owns],
  );

  const toggleObjDone = useCallback(
    (taskId: string, objectiveId: string) => {
      if (!canEdit) return;
      toggleObjDoneLocal(taskId, objectiveId);
    },
    [canEdit, toggleObjDoneLocal],
  );

  const myName =
    (me?.display_name || me?.username || "").trim() ||
    (me ? `用户${me.id}` : "");
  const viewerObjectiveDones = useMemo(() => {
    const others = (room?.objective_dones || []).filter(
      (row) => row.user_id !== me?.id,
    );
    if (!me) return others;
    return [
      ...others,
      ...skipMapToObjectiveDones(objDone, {
        userId: me.id,
        name: myName,
      }),
    ];
  }, [me, myName, objDone, room?.objective_dones]);

  useEffect(() => {
    if (!mapId || !me) return;
    const key = `${publicId}:${gameMode}:${mapId}:${me.id}`;
    if (objSeedKeyRef.current === key) return;
    if (stateQuery.isLoading && !stateQuery.data) return;
    objSeedKeyRef.current = key;
    const fromRoom = objectiveDonesToSkipMap(room?.objective_dones, me.id);
    const fromServer = stateQuery.data
      ? objectiveDonesToSkipMap(
          (stateQuery.data.objective_dones || []).map((row) => ({
            task_id: row.task_id,
            objective_id: row.objective_id,
            user_id: me.id,
          })),
          me.id,
        )
      : new Map();
    const local = readRaidPrepObjectiveDoneWithLegacy(objDoneScope, objDoneLegacy);
    const merged = mergeRaidPrepSkipMaps(local, fromRoom, fromServer);
    if (!raidPrepSkipMapsEqual(local, merged)) replaceObjDone(merged);
  }, [
    gameMode,
    mapId,
    me,
    objDoneLegacy,
    objDoneScope,
    publicId,
    replaceObjDone,
    room?.objective_dones,
    stateQuery.data,
    stateQuery.isLoading,
  ]);

  useEffect(() => {
    if (!mapId || !me || !objDoneScope || !stateQuery.isSuccess) return;
    const handle = window.setTimeout(() => {
      void putTarkovRaidPrepState(mapId, {
        selected: stateQuery.data?.selected ?? [],
        objective_dones: skipMapToObjectiveDones(objDone, {
          userId: me.id,
          name: myName,
        }).map((row) => ({
          task_id: row.task_id,
          objective_id: row.objective_id,
        })),
        key_brings: stateQuery.data?.key_brings ?? [],
      }).catch(() => {
        /* 未登录或网络失败时本机勾选仍可用 */
      });
    }, 700);
    return () => window.clearTimeout(handle);
  }, [
    mapId,
    me,
    myName,
    objDone,
    objDoneScope,
    stateQuery.data?.key_brings,
    stateQuery.data?.selected,
    stateQuery.isSuccess,
  ]);

  const locateTask = useCallback(
    async (row: (typeof rows)[number]) => {
      let points = resolveRaidPrepLocateTargets(
        overlayTasks.find((item) => item.id === row.id) || row,
        mapId,
        raidPrepSkippedIds(objDone, row.id),
      );
      if (!points.length && row.has_map_markers) {
        try {
          const rich = await geometry.ensure(row.id);
          points = rich
            ? resolveRaidPrepLocateTargets(
                rich,
                mapId,
                raidPrepSkippedIds(objDone, row.id),
              )
            : [];
        } catch {
          return;
        }
      }
      if (!points.length) return;
      const index = locateIndexRef.current[row.id] || 0;
      const point = points[index % points.length]!;
      locateIndexRef.current[row.id] = index + 1;
      focusSeqRef.current += 1;
      setHighlightTaskId(row.id);
      setFocusRequest({ ...point, seq: focusSeqRef.current });
      window.setTimeout(() => {
        document
          .querySelector(`[data-raid-prep-task="${row.id}"]`)
          ?.scrollIntoView({ block: "nearest" });
      }, 0);
    },
    [geometry, mapId, objDone, overlayTasks],
  );

  const openGuide = useCallback((taskId: string) => {
    setGuideTaskId(taskId);
    setGuideOpen(true);
  }, []);

  const onQuestLabelClick = useCallback((taskId: string) => {
    setHighlightTaskId(taskId);
    openGuide(taskId);
  }, [openGuide]);

  const onStroke = useCallback((stroke: { floor: string; points: StrokePoint[] }) => {
    if (!canEdit || !stroke.points.length) return;
    const first = stroke.points[0];
    const last = stroke.points[stroke.points.length - 1];
    const tempId = -Date.now();
    setPendingMarks((current) => [
      ...current,
      {
        id: tempId,
        kind: "stroke",
        floor: stroke.floor,
        x: first.x,
        z: first.z,
        x2: last.x,
        z2: last.z,
        points: stroke.points.map((point) => [point.x, point.z]),
        author_user_id: me?.id || 0,
        author_display_name: me?.display_name || "",
      },
    ]);
    void (async () => {
      const ok = await run(() =>
        addTarkovRaidRoomMark(publicId, {
          kind: "stroke",
          floor: stroke.floor,
          x: first.x,
          z: first.z,
          x2: last.x,
          z2: last.z,
          points: stroke.points.map((point) => [point.x, point.z]),
        }),
      );
      void ok;
      setPendingMarks((current) => current.filter((row) => row.id !== tempId));
    })();
  }, [canEdit, me?.display_name, me?.id, publicId, run]);

  const onPin = useCallback(
    (mark: { floor: string; x: number; z: number }) => {
      if (!canEdit) return;
      void run(() =>
        addTarkovRaidRoomMark(publicId, {
          kind: "pin",
          floor: mark.floor,
          x: mark.x,
          z: mark.z,
        }),
      );
    },
    [canEdit, publicId, run],
  );

  const onLine = useCallback(
    (mark: {
      floor: string;
      x: number;
      z: number;
      x2: number;
      z2: number;
    }) => {
      if (!canEdit) return;
      void run(() =>
        addTarkovRaidRoomMark(publicId, {
          kind: "line",
          floor: mark.floor,
          x: mark.x,
          z: mark.z,
          x2: mark.x2,
          z2: mark.z2,
        }),
      );
    },
    [canEdit, publicId, run],
  );

  const onEraseMark = useCallback(
    (markId: number) => {
      if (!canEdit || markId <= 0) return;
      void run(() => removeTarkovRaidRoomMark(publicId, markId));
    },
    [canEdit, publicId, run],
  );

  const boardMarks = useMemo(
    () => mergeBoardMarks(room?.marks || [], pendingMarks),
    [room?.marks, pendingMarks],
  );

  if (roomQuery.isLoading && !room) {
    return (
      <div className={catalogCss.status}>
        <Spin tip="加载房间…" />
      </div>
    );
  }
  if (roomQuery.isError && !room) {
    return (
      <Alert
        type="error"
        showIcon
        message="房间加载失败"
        description={apiError(roomQuery.error, "房间加载失败")}
      />
    );
  }
  if (!room) return null;

  return (
    <div
      className={styles.stage}
      data-dock={dockOpen ? "open" : "closed"}
      data-pick={showOverlap ? "true" : undefined}
    >
      {room.game_mode && room.game_mode !== gameMode ? (
        <Alert
          type="warning"
          showIcon
          message={`房间绑定 ${String(room.game_mode).toUpperCase()}，当前目录是 ${gameMode.toUpperCase()}`}
          description={
            <button
              type="button"
              className={styles.dockChip}
              onClick={() => setMode(parseTarkovGameMode(room.game_mode))}
            >
              顶栏切换到 {String(room.game_mode).toUpperCase()}
            </button>
          }
        />
      ) : null}
      <div className={styles.topBar}>
        <div className={styles.roomId}>
          <h1 className={styles.roomTitle}>{title}</h1>
          <div className={styles.roomMeta}>
            {mapLabel || "未选地图"}
            {mapId ? (
              <TarkovGoonSightingHint mapId={mapId} variant="inline" />
            ) : null}
            {" · "}
            {room.member_count}/{room.max_members}
            {room.has_password ? " · 有密码" : ""}
            {" · "}
            <span
              className={styles.roomLive}
              data-in-raid={roomLiveStatus === "in_raid" ? "true" : "false"}
            >
              {formatRaidRoomLiveStatus(roomLiveStatus)}
            </span>
          </div>
        </div>
        <div className={styles.members} aria-label="房间成员">
          {seatedActing.map((row) => {
            const phase = phaseByUser.get(row.user_id);
            const region = raidRoomMemberRegionLabel({
              kind: phase?.kind,
              mapLabel: phase?.mapLabel,
              mapId: phase?.mapId,
            });
            const chipLine = formatRaidRoomMemberChipLine({
              name: row.display_name,
              isHost: row.is_host,
              online: row.online,
              kind: phase?.kind,
              mapLabel: phase?.mapLabel,
              mapId: phase?.mapId,
            });
            return (
              <span
                key={row.user_id}
                className={styles.memberChip}
                data-online={row.online ? "true" : "false"}
                data-phase={phase?.kind || ""}
                title={chipLine}
              >
                <span className={styles.memberName}>
                  {row.is_host ? "⭐" : ""}
                  {row.display_name}
                </span>
                <span
                  className={styles.memberOnline}
                  data-on={row.online ? "true" : "false"}
                >
                  {row.online ? "在线" : "离线"}
                </span>
                {region ? (
                  <span className={styles.memberRegion}>{region}</span>
                ) : null}
              </span>
            );
          })}
        </div>
        <div className={styles.topActions}>
          {room.is_member && mapId ? (
            <button
              type="button"
              className={styles.dockChip}
              onClick={askChangeMap}
            >
              各图任务
            </button>
          ) : null}
          {room.is_host ? (
            <button
              type="button"
              className={styles.dockChip}
              onClick={() => {
                setManagePassLocked(true);
                setManageOpen(true);
              }}
            >
              房间管理
            </button>
          ) : null}
          {room.is_member ? (
            <button
              type="button"
              className={styles.dockChip}
              onClick={() => leaveMut.mutate()}
            >
              离开
            </button>
          ) : null}
        </div>
      </div>
      {!room.is_member ? (
        <Alert
          type="info"
          showIcon
          message="你还不是房间成员"
          description={
            <div className={styles.joinGate}>
              {room.has_password ? (
                <Input.Password
                  value={joinPassword}
                  onChange={(event) => setJoinPassword(event.target.value)}
                  placeholder="房间密码"
                  maxLength={32}
                  onPressEnter={() => joinMut.mutate()}
                />
              ) : null}
              <button
                type="button"
                className={styles.dockChip}
                disabled={
                  joinMut.isPending ||
                  (Boolean(room.has_password) && !joinPassword.trim())
                }
                onClick={() => joinMut.mutate()}
              >
                {joinMut.isPending ? "加入中…" : "加入房间"}
              </button>
            </div>
          }
        />
      ) : null}
      {error ? <Alert type="error" showIcon message={error} /> : null}

      <div className={styles.workspace}>
        <div className={styles.mapPane}>
          {mapId ? <TarkovGoonRoomNotice mapId={mapId} /> : null}
          {room.is_member ? (
            <button
              type="button"
              className={styles.dockEdge}
              aria-expanded={dockOpen}
              aria-controls="tarkov-raid-dock"
              onClick={() => setDockOpen((open) => !open)}
            >
              <span className={styles.srOnly}>
                {dockOpen ? "收起任务栏" : "展开任务栏"}
              </span>
              <span aria-hidden>{dockOpen ? "›" : "‹"}</span>
            </button>
          ) : null}
          {canEdit && !showOverlap ? (
            <div className={styles.drawDock}>
              {(
                [
                  ["pan", "拖拽", "拖拽移动地图"],
                  ["pen", "画笔", "按住拖拽涂鸦，空格拖地图"],
                  ["pin", "钉点", "单击钉一个点"],
                  ["line", "直线", "点两点连成直线"],
                  ["erase", "橡皮", "点一下擦掉笔画"],
                ] as const
              ).map(([mode, label, hint]) => (
                <button
                  key={mode}
                  type="button"
                  title={hint}
                  className={`${styles.dockChip} ${tool === mode ? styles.dockChipOn : ""}`}
                  onClick={() => setTool(mode)}
                >
                  {label}
                </button>
              ))}
              <button
                type="button"
                className={styles.dockChip}
                onClick={() => void run(() => undoTarkovRaidRoomMark(publicId))}
              >
                撤销
              </button>
              {room.is_host ? (
                <button
                  type="button"
                  className={styles.dockChip}
                  onClick={() =>
                    void (async () => {
                      const ok = await run(() => clearTarkovRaidRoomMarks(publicId));
                      if (ok) setPendingMarks([]);
                    })()
                  }
                >
                  清板
                </button>
              ) : null}
              {tool === "pan" ? (
                <span className={styles.drawHint}>拖拽移动地图</span>
              ) : null}
              {tool === "pen" ? (
                <span className={styles.drawHint}>拖拽涂鸦，按住空格拖地图</span>
              ) : null}
              {tool === "pin" ? (
                <span className={styles.drawHint}>单击钉点</span>
              ) : null}
              {tool === "line" ? (
                <span className={styles.drawHint}>点两个位置连直线</span>
              ) : null}
              {tool === "erase" ? (
                <span className={styles.drawHint}>点一下擦掉笔画</span>
              ) : null}
            </div>
          ) : null}
          <div className={styles.mapFill}>
            {showOverlap ? (
              room.is_member ? (
                <div className={styles.mapPickPane}>
                  <TarkovRaidRoomOverlapBoard
                    rows={room.map_overlap || []}
                    members={members}
                    progress={room.task_progress || []}
                    mapOptions={mapOptions}
                    isHost={canSwitchMap}
                    picking={pickingMap}
                    currentMapSlug={mapId || undefined}
                    previewMapSlug={dockMapId || undefined}
                    onPreviewMap={setPreviewMapId}
                    onPickMap={canSwitchMap ? pickMapAndSeed : undefined}
                  />
                </div>
              ) : (
                <div className={catalogCss.status}>加入后可一起准备</div>
              )
            ) : mapQuery.isLoading ? (
              <div className={catalogCss.status}>
                <Spin tip="加载地图…" />
              </div>
            ) : mapQuery.isError ? (
              <Alert
                type="error"
                showIcon
                message="地图加载失败"
                description={apiError(mapQuery.error, "地图加载失败")}
              />
            ) : (
              <Suspense fallback={<PanelFallback tip="加载地图…" />}>
                <TarkovRaidRoomLiveMap
                  publicId={publicId}
                  mapId={mapId}
                  parentSlug={mapQuery.data?.parent_slug || undefined}
                  extracts={mapQuery.data?.extracts}
                  bosses={mapQuery.data?.bosses}
                  spawns={mapQuery.data?.spawns}
                  questOverlays={overlays}
                  focusRequest={focusRequest}
                  highlightTaskId={highlightTaskId}
                  boardMarks={boardMarks}
                  suppressLocalFix={hideLocalFix}
                  authorUserId={me?.id || 0}
                  authorDisplayName={
                    (me?.display_name || me?.username || "").trim() ||
                    (me ? `用户${me.id}` : "")
                  }
                  drawMode={canEdit ? tool : "pan"}
                  canEdit={canEdit}
                  members={members}
                  wsRef={wsRef}
                  wsGen={wsGen}
                  onStroke={onStroke}
                  onPin={onPin}
                  onLine={onLine}
                  onEraseMark={onEraseMark}
                  onQuestLabelClick={onQuestLabelClick}
                  questParticipantsByTask={participantsByTask}
                  topRight={
                    <div className={styles.summaryStack}>
                      <TarkovRaidPrepSummary
                        tasks={selectedTasks}
                        mapId={mapId}
                        participantsByTask={participantsByTask}
                        keyBrings={room?.key_brings}
                        keyOwns={room?.key_owns}
                        currentUserId={me?.id}
                        canToggleKeyBring={canEdit}
                        onToggleKeyBring={toggleKeyBring}
                        canToggleKeyOwn={Boolean(me)}
                        onToggleKeyOwn={me ? toggleKeyOwn : undefined}
                        skippedByTask={objDone}
                        doneTaskIds={doneTaskIds}
                        objectiveDones={viewerObjectiveDones}
                        onToggleObjective={toggleObjDone}
                        onTitle={openGuide}
                      />
                      <TarkovRaidPrepGuideOverview
                        tasks={selectedTasks}
                        mapId={mapId}
                        participantsByTask={participantsByTask}
                        skippedByTask={objDone}
                        doneTaskIds={doneTaskIds}
                        onToggleObjective={toggleObjDone}
                        open={guideOpen}
                        onOpenChange={setGuideOpen}
                        activeId={guideTaskId}
                        onActiveIdChange={setGuideTaskId}
                      />
                    </div>
                  }
                />
              </Suspense>
            )}
          </div>
        </div>
        {room.is_member ? (
        <aside
          id="tarkov-raid-dock"
          className={styles.dock}
          aria-label="任务列表"
        >
          <TarkovRaidPrepFilters
            keyword={keyword}
            onKeyword={setKeyword}
            leading={
              <div className={styles.dockLeadActions}>
                {showOverlap ? (
                  <p className={styles.dockHint}>
                    {dockMapLabel
                      ? `预览${dockMapLabel}任务`
                      : "点左侧地图预览任务"}
                    {canClaimOnDock
                      ? "；可勾进本房"
                      : "。选好地图后可勾进房间"}
                  </p>
                ) : null}
                {canClaimOnDock ? (
                  <>
                    <button
                      type="button"
                      className={styles.changeMapBtn}
                      onClick={() => setOcrOpen(true)}
                    >
                      截图识别
                    </button>
                    <button
                      type="button"
                      className={styles.changeMapBtn}
                      disabled={!catalog.length}
                      title="按个人中心进行中的任务，勾选本图相关项"
                      onClick={syncFromTaskProgress}
                    >
                      从任务进度同步
                    </button>
                  </>
                ) : null}
              </div>
            }
          />
          <div
            className={styles.taskList}
            onClick={() => setHighlightTaskId("")}
          >
            {prepQuery.isLoading && !prepQuery.data && !rows.length ? (
              <div className={styles.empty}>
                <Spin />
              </div>
            ) : (
              <TarkovRaidPrepTaskGroups
                groups={statusGroups}
                empty={<div className={styles.empty}>当前搜索下无任务</div>}
                renderRow={(row) => (
                  <TarkovRaidPrepTaskCard
                    key={row.id}
                    row={row}
                    mapSlug={dockMapId}
                    compact
                    checked={myClaims.has(row.id)}
                    highlighted={myClaims.has(row.id)}
                    status={taskStatusOf(row.id)}
                    done={taskStatusOf(row.id) === "done"}
                    active={highlightTaskId === row.id}
                    color={
                      myClaims.has(row.id)
                        ? colorByTask.get(row.id) || colorForTaskIndex(0)
                        : undefined
                    }
                    disabled={!canEdit}
                    claimDisabled={!canClaimOnDock}
                    skipped={raidPrepSkippedIds(objDone, row.id)}
                    onToggleObjective={toggleObjDone}
                    onToggle={toggleClaim}
                    onNeedDetail={showOverlap ? undefined : geometry.ensure}
                    onLocate={showOverlap ? undefined : locateTask}
                    onTitle={openGuide}
                    onSetStatus={changeTaskStatus}
                  />
                )}
              />
            )}
          </div>
        </aside>
        ) : null}
      </div>
      <TarkovRaidPrepOcrModal
        open={ocrOpen}
        onClose={() => setOcrOpen(false)}
        catalog={catalog}
        selectedIds={[...myClaims]}
        maxSelected={RAID_PREP_MAX_SELECTED}
        onConfirm={async (ids) => {
          const next = ids.filter((id) => !myClaims.has(id));
          if (!next.length) return;
          await run(() => claimTarkovRaidRoomTasks(publicId, next));
        }}
      />
      <Modal
        title="各图任务"
        open={statsOpen}
        onCancel={() => setStatsOpen(false)}
        footer={null}
        width={960}
        destroyOnClose
        classNames={{ body: styles.entryModalBody }}
      >
        {canSwitchMap ? (
          <p className={styles.mapPickHint}>
            数字是各人进行中的本图任务。点「选这张图」才会换图，并清空当前点位、勾选、钥匙和完成进度。
          </p>
        ) : (
          <p className={styles.mapPickHint}>
            数字是各人进行中的本图任务。
          </p>
        )}
        <TarkovRaidRoomOverlapBoard
          rows={room.map_overlap || []}
          members={members}
          progress={room.task_progress || []}
          mapOptions={mapOptions}
          isHost={canSwitchMap}
          picking={pickingMap}
          currentMapSlug={mapId || undefined}
          previewMapSlug={previewMapId || mapId || undefined}
          onPreviewMap={setPreviewMapId}
          onPickMap={canSwitchMap ? pickMapAndSeed : undefined}
        />
      </Modal>
      <Modal
        title={
          <div className={styles.manageModalHead}>
            <span>房间管理</span>
            <button
              type="button"
              className={styles.manageModalClose}
              aria-label="关闭"
              onClick={() => setManageOpen(false)}
            >
              ×
            </button>
          </div>
        }
        open={manageOpen}
        onCancel={() => setManageOpen(false)}
        footer={null}
        width={460}
        destroyOnClose
        closable={false}
        className={styles.manageModal}
        classNames={{
          content: styles.manageModalContent,
          body: styles.manageModalBody,
        }}
        styles={{
          body: { paddingTop: 24 },
        }}
      >
        <section className={styles.manageSection}>
          <h2 className={styles.manageSectionTitle}>成员</h2>
          <div className={styles.manageList}>
            {members.map((row) => (
              <div key={row.user_id} className={styles.manageRow}>
                <span className={styles.manageName}>
                  <span
                    className={styles.memberDot}
                    style={{ background: colorForUserId(row.user_id) }}
                  />
                  <span className={styles.manageNameText}>{row.display_name}</span>
                  {row.is_host ? (
                    <span className={styles.manageHostTag}>房主</span>
                  ) : null}
                </span>
                {!row.is_host ? (
                  <div className={styles.manageRowActions}>
                    <button
                      type="button"
                      className={styles.dockChip}
                      disabled={transferMut.isPending}
                      onClick={() => {
                        Modal.confirm({
                          title: `将房主转让给 ${row.display_name}？`,
                          content: "对方将成为房主，你可以继续留在房间。",
                          okText: "转让",
                          cancelText: "取消",
                          onOk: () => transferMut.mutateAsync(row.user_id),
                        });
                      }}
                    >
                      转让房主
                    </button>
                    <button
                      type="button"
                      className={styles.dockChip}
                      disabled={kickMut.isPending}
                      onClick={() => {
                        Modal.confirm({
                          title: `移除 ${row.display_name}？`,
                          content: "会请出房间，并去掉此人的任务勾选、钥匙声明和完成进度。",
                          okText: "移除",
                          cancelText: "取消",
                          onOk: () => kickMut.mutateAsync(row.user_id),
                        });
                      }}
                    >
                      移除
                    </button>
                  </div>
                ) : (
                  <span className={styles.manageHostMark}>自己</span>
                )}
              </div>
            ))}
          </div>
        </section>
        <form
          className={styles.manageSection}
          autoComplete="off"
          onSubmit={(event) => {
            event.preventDefault();
            const next = passwordDraft.trim();
            if (!next || passwordMut.isPending) return;
            passwordMut.mutate(next);
          }}
        >
          <h2 className={styles.manageSectionTitle}>房间密码</h2>
          <p className={styles.managePasswordHint}>
            {room.has_password
              ? "已设密码，未入座的人需要输入才能加入"
              : "未设密码，大厅点一下即可加入"}
          </p>
          <div className={styles.managePasswordRow}>
            <Input.Password
              value={passwordDraft}
              onChange={(event) => setPasswordDraft(event.target.value)}
              placeholder={room.has_password ? "输入新密码" : "输入密码"}
              maxLength={32}
              name="tarkov-raid-room-pass"
              autoComplete="new-password"
              autoCorrect="off"
              spellCheck={false}
              readOnly={managePassLocked}
              onFocus={() => setManagePassLocked(false)}
              data-1p-ignore="true"
              data-lpignore="true"
            />
          </div>
          <div className={styles.managePasswordActions}>
            <button
              type="submit"
              className={styles.dockChip}
              disabled={passwordMut.isPending || !passwordDraft.trim()}
            >
              {room.has_password ? "修改密码" : "设置密码"}
            </button>
            {room.has_password ? (
              <button
                type="button"
                className={styles.manageTextBtn}
                disabled={passwordMut.isPending}
                onClick={() => passwordMut.mutate("")}
              >
                清除密码
              </button>
            ) : null}
          </div>
        </form>
        <div className={styles.manageFooter}>
          <button
            type="button"
            className={`${styles.dockChip} ${styles.manageDanger}`}
            disabled={resetMut.isPending}
            onClick={() => {
              Modal.confirm({
                title: "清空房间？",
                content: "会请出所有人，并清空地图、点位、任务勾选、钥匙声明、完成进度和密码。",
                okText: "清空房间",
                cancelText: "取消",
                onOk: () => resetMut.mutateAsync(),
              });
            }}
          >
            清空房间
          </button>
        </div>
      </Modal>
    </div>
  );
}
