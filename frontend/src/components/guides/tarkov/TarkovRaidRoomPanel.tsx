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
  fetchTarkovRaidRoom,
  fetchTarkovTaskDones,
  joinTarkovRaidRoom,
  leaveTarkovRaidRoom,
  markTarkovRaidRoomObjectiveDone,
  markTarkovRaidRoomObjectivesDone,
  putTarkovRaidRoomTaskProgress,
  removeTarkovRaidRoomMark,
  removeTarkovRaidRoomMember,
  resetTarkovRaidRoom,
  seedTarkovRaidRoomClaimsFromProgress,
  setTarkovRaidRoomMap,
  setTarkovRaidRoomPassword,
  tarkovRaidRoomWsUrl,
  removeTarkovKeyOwn,
  unbringTarkovRaidRoomKey,
  unmarkTarkovRaidRoomObjectiveDone,
  unclaimTarkovRaidRoomTask,
  undoTarkovRaidRoomMark,
  type TarkovRaidRoomDetail,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode, useTarkovGameModeControls, parseTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  TARKOV_RAID_PREP_PATH,
  tarkovRaidRoomShareUrl,
} from "@/lib/tarkovHomeNav";
import {
  RAID_PREP_MAX_SELECTED,
  buildRaidPrepOverlays,
  colorForTaskIndex,
  colorForUserId,
  filterRaidPrepOverlaysForViewer,
  filterRaidPrepRows,
  hideCompletedRaidPrepRows,
  hydrateRaidPrepCatalogRows,
  partitionRaidPrepRows,
  planRaidPrepTaskProgressSync,
  objectiveDonesToSkipMap,
  raidPrepMapOptions,
  raidPrepSkippedIds,
  resolveRaidPrepLocatePoints,
  roomObjectiveMarksForCompletedTasks,
  selectedTasksFromCatalog,
  settleRaidPrepSelection,
  userMarkedObjective,
} from "@/lib/tarkovRaidPrep";
import {
  TARKOV_TASK_PROGRESS_EVENT,
  type TarkovTaskProgressDetail,
} from "@/lib/tarkovLiveWatch";
import { useTarkovLastLogMapId, useTarkovLastLogPhase } from "@/lib/tarkovLiveWatchContext";
import { useRaidPrepGeometry } from "@/lib/useRaidPrepGeometry";
import { useTarkovRaidDockOpen } from "@/lib/tarkovRaidDockPrefs";
import { useRaidRoomLiveStore } from "@/lib/tarkovRaidRoomLiveStore";
import { applyTarkovKeyOwnsCache } from "@/lib/tarkovKeyPacks";
import { loadTaskDoneIds, loadTaskStartedIds } from "@/lib/tarkovTaskTree";
import {
  applyRoomWsEvent,
  formatRaidRoomLiveStatus,
  formatRaidRoomMemberWsLine,
  groupClaimsByTask,
  claimTaskIdsForUser,
  parseRaidRoomLogPhases,
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
import { TarkovRaidPrepOcrModal } from "@/components/guides/tarkov/TarkovRaidPrepOcrModal";
import { TarkovRaidPrepSummary } from "@/components/guides/tarkov/TarkovRaidPrepSummary";
import { TarkovRaidPrepGuideOverview } from "@/components/guides/tarkov/TarkovRaidPrepGuideOverview";
import { TarkovRaidPrepTaskCard } from "@/components/guides/tarkov/TarkovRaidPrepTaskCard";
import { TarkovRaidPrepRestList } from "@/components/guides/tarkov/TarkovRaidPrepRestList";
import { TarkovRaidRoomOverlapBoard } from "@/components/guides/tarkov/TarkovRaidRoomOverlapBoard";
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
  const [trader, setTrader] = useState("");
  const [tool, setTool] = useState<TarkovMapDrawMode>("pan");
  const [listScope, setListScope] = useState<"all" | "picked">("all");
  const meIdRef = useRef(me?.id);
  meIdRef.current = me?.id;
  const [pendingMarks, setPendingMarks] = useState<RaidRoomMarkLike[]>([]);
  const [wsGen, setWsGen] = useState(0);
  const [wsLive, setWsLive] = useState(false);
  const [logPhases, setLogPhases] = useState<RaidRoomLogPhase[]>([]);
  const lastLogMapId = useTarkovLastLogMapId();
  const lastLogPhase = useTarkovLastLogPhase();
  const lastLogPhaseSigRef = useRef("");
  const [taskListEl, setTaskListEl] = useState<HTMLDivElement | null>(null);
  const [restHeadEl, setRestHeadEl] = useState<HTMLDivElement | null>(null);
  const [error, setError] = useState("");
  const [guideOpen, setGuideOpen] = useState(false);
  const [guideTaskId, setGuideTaskId] = useState("");
  const [ocrOpen, setOcrOpen] = useState(false);
  const [highlightTaskId, setHighlightTaskId] = useState("");
  const [dockOpen, setDockOpen] = useTarkovRaidDockOpen();
  const [copiedLink, setCopiedLink] = useState(false);
  const [mapPickView, setMapPickView] = useState(false);
  const [pickingMap, setPickingMap] = useState(false);
  const [manageOpen, setManageOpen] = useState(false);
  const [joinPassword, setJoinPassword] = useState("");
  const [passwordDraft, setPasswordDraft] = useState("");
  const [focusRequest, setFocusRequest] = useState<TarkovMapFocusRequest | null>(
    null,
  );
  const objDone = useMemo(
    () => objectiveDonesToSkipMap(room?.objective_dones, me?.id),
    [room?.objective_dones, me?.id],
  );
  const focusSeqRef = useRef(0);
  const locateIndexRef = useRef<Record<string, number>>({});
  const wsRef = useRef<WebSocket | null>(null);
  const lastProgressKeyRef = useRef("");

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
        return next;
      });
    }
  }, [roomQuery.data]);

  const canEdit = Boolean(room?.can_edit);
  const mapId = room?.map_slug || "";
  const mapIdRef = useRef(mapId);
  mapIdRef.current = mapId;
  const canEditRef = useRef(canEdit);
  canEditRef.current = canEdit;
  const roomObjDonesRef = useRef(room?.objective_dones);
  roomObjDonesRef.current = room?.objective_dones;

  /* 只跟 token / 房间身份重连，快照更新不要拆掉 WS */
  // oxlint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (
      !token ||
      !publicId ||
      !room ||
      !room.is_member
    ) {
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
  }, [token, publicId, room?.is_member]);

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
    queryKey: ["guides-tarkov-raid-prep", gameMode, mapId],
    queryFn: () => fetchTarkovRaidPrep({ map: mapId }),
    enabled: Boolean(mapId),
    staleTime: 5 * 60_000,
    retry: 1,
  });
  const taskDonesQuery = useQuery({
    queryKey: ["guides-tarkov-task-dones", gameMode],
    queryFn: fetchTarkovTaskDones,
    staleTime: 30_000,
  });
  const doneTaskIds = taskDonesQuery.data?.task_ids ?? loadTaskDoneIds(gameMode);

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
    setRoom(withRaidRoomViewerFlags(next, meIdRef.current));
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
  const mySelectedTasks = useMemo(
    () => selectedTasksFromCatalog(catalogRich, myClaimIds),
    [catalogRich, myClaimIds],
  );
  const overlayTasks = geometry.items;
  const rows = useMemo(
    () =>
      hideCompletedRaidPrepRows(
        filterRaidPrepRows(catalogRich, { trader, q: query }),
        doneTaskIds,
      ),
    [catalogRich, trader, query, doneTaskIds],
  );
  const { picked, rest } = useMemo(
    () => partitionRaidPrepRows(rows, mySelectedTasks),
    [rows, mySelectedTasks],
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
    [publicId, run],
  );

  useEffect(() => {
    const onProgress = (event: Event) => {
      const detail = (event as CustomEvent<TarkovTaskProgressDetail>).detail;
      if (!detail || detail.mode !== gameMode) return;
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
  const mapOptions = useMemo(() => raidPrepMapOptions(), []);
  const currentMap = mapOptions.find((item) => item.id === mapId);
  const mapLabel = currentMap?.label || mapId;
  const title = (room?.title || "").trim() || `${publicId}号房`;
  const traders = prepQuery.data?.traders ?? [];
  const members =
    room?.occupants?.length
      ? room.occupants
      : (room?.members || []).filter((row) => row.in_room !== false);
  const phaseByUser = useMemo(() => {
    const map = new Map<number, RaidRoomLogPhase>();
    for (const row of logPhases) map.set(row.userId, row);
    return map;
  }, [logPhases]);
  const roomLiveStatus = raidRoomLiveStatus(
    members.map((row) => row.user_id),
    logPhases,
  );
  const hideLocalFix = Boolean(
    lastLogMapId && !playerFixMatchesRoomMap(lastLogMapId, mapId),
  );

  const askChangeMap = () => {
    Modal.confirm({
      title: "回到任务统计？",
      content:
        "将回到开房时的地图任务统计。点一张图才会换图，并清空当前点位、勾选、钥匙和完成进度。",
      okText: "回到统计",
      cancelText: "取消",
      onOk: () => {
        setMapPickView(true);
        setDockOpen(false);
      },
    });
  };

  const seedClaims = () => {
    if (!room?.is_host || !mapId) return;
    void (async () => {
      const ok = await run(() => seedTarkovRaidRoomClaimsFromProgress(publicId));
      if (ok) message.success("已按在座进行中任务勾到房间");
    })();
  };

  const pickMapAndSeed = (nextMap: string) => {
    if (!nextMap || pickingMap) return;
    if (nextMap === mapId) {
      setMapPickView(false);
      return;
    }
    const apply = async () => {
      setPickingMap(true);
      try {
        const mapped = await run(() => setTarkovRaidRoomMap(publicId, nextMap));
        if (!mapped) return;
        setMapPickView(false);
        const seeded = await run(() =>
          seedTarkovRaidRoomClaimsFromProgress(publicId),
        );
        if (seeded) message.success("已选图，并按进行中任务勾到房间");
      } finally {
        setPickingMap(false);
      }
    };
    void apply();
  };

  const toggleClaim = useCallback(
    (taskId: string) => {
      if (!canEdit) return;
      if (myClaims.has(taskId)) {
        void run(() => unclaimTarkovRaidRoomTask(publicId, taskId));
        return;
      }
      const uniqueClaimed = groups.length;
      if (!groups.some((g) => g.taskId === taskId) && uniqueClaimed >= RAID_PREP_MAX_SELECTED) {
        setError(`最多勾选 ${RAID_PREP_MAX_SELECTED} 个任务`);
        return;
      }
      void run(() => claimTarkovRaidRoomTask(publicId, taskId));
    },
    [canEdit, groups, myClaims, publicId, run],
  );

  const syncFromTaskProgress = () => {
    if (!canEdit) return;
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
      if (userMarkedObjective(room?.objective_dones, taskId, objectiveId, me?.id)) {
        void run(() =>
          unmarkTarkovRaidRoomObjectiveDone(publicId, taskId, objectiveId),
        );
        return;
      }
      void run(() =>
        markTarkovRaidRoomObjectiveDone(publicId, taskId, objectiveId),
      );
    },
    [canEdit, me?.id, publicId, room?.objective_dones, run],
  );

  const locateTask = useCallback(
    async (row: (typeof rows)[number]) => {
      let points = resolveRaidPrepLocatePoints(
        overlayTasks.find((item) => item.id === row.id) || row,
        mapId,
        raidPrepSkippedIds(objDone, row.id),
      );
      if (!points.length && row.has_map_markers) {
        try {
          const rich = await geometry.ensure(row.id);
          points = rich
            ? resolveRaidPrepLocatePoints(
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

  const showOverlap = !mapId || mapPickView;

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
            {mapLabel || "未选地图"} · {room.member_count}/{room.max_members}
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
          {members.map((row) => {
            const phase = phaseByUser.get(row.user_id);
            const wsLine = formatRaidRoomMemberWsLine({
              online: row.online,
              phaseKind: phase?.kind,
            });
            return (
              <span
                key={row.user_id}
                className={styles.memberChip}
                data-online={row.online ? "true" : "false"}
                data-phase={phase?.kind || ""}
                title={wsLine}
              >
                <span
                  className={styles.memberDot}
                  style={{ background: colorForUserId(row.user_id) }}
                />
                {row.display_name}
                {row.is_host ? " · 房主" : ""}
                <span className={styles.memberWs}>{wsLine}</span>
              </span>
            );
          })}
        </div>
        <div className={styles.topActions}>
          {mapId && !mapPickView ? (
            <button
              type="button"
              className={styles.dockToggle}
              aria-expanded={dockOpen}
              aria-controls="tarkov-raid-dock"
              onClick={() => setDockOpen((open) => !open)}
            >
              {dockOpen ? "收起任务" : "任务列表"}
            </button>
          ) : null}
          <button
            type="button"
            className={styles.dockChip}
            onClick={() => {
              const url = tarkovRaidRoomShareUrl(
                publicId,
                window.location.origin,
              );
              void navigator.clipboard.writeText(url).then(
                () => {
                  setCopiedLink(true);
                  window.setTimeout(() => setCopiedLink(false), 1600);
                },
                () => setCopiedLink(false),
              );
            }}
          >
            {copiedLink ? "已复制" : "复制链接"}
          </button>
          {room.is_host && mapId && !mapPickView ? (
            <button
              type="button"
              className={styles.dockChip}
              onClick={askChangeMap}
            >
              更换地图
            </button>
          ) : null}
          {room.is_host && mapPickView && mapId ? (
            <button
              type="button"
              className={styles.dockChip}
              onClick={() => setMapPickView(false)}
            >
              取消换图
            </button>
          ) : null}
          {room.is_host ? (
            <button
              type="button"
              className={styles.dockChip}
              onClick={() => setManageOpen(true)}
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
          {mapId && !mapPickView ? (
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
                  {mapPickView && mapId ? (
                    <p className={styles.mapPickHint}>
                      点一张图才会换图并清空进度；点当前地图或「取消换图」则返回。
                    </p>
                  ) : null}
                  <TarkovRaidRoomOverlapBoard
                    rows={room.map_overlap || []}
                    members={members}
                    progress={room.task_progress || []}
                    mapOptions={mapOptions}
                    isHost={room.is_host}
                    picking={pickingMap}
                    currentMapSlug={mapId || undefined}
                    onPickMap={room.is_host ? pickMapAndSeed : undefined}
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
                        objectiveDones={room?.objective_dones}
                        onToggleObjective={toggleObjDone}
                        onTitle={openGuide}
                      />
                      <TarkovRaidPrepGuideOverview
                        tasks={selectedTasks}
                        mapId={mapId}
                        participantsByTask={participantsByTask}
                        skippedByTask={objDone}
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
        {mapId && !mapPickView ? (
        <aside
          id="tarkov-raid-dock"
          className={styles.dock}
          aria-label="任务列表"
        >
          <TarkovRaidPrepFilters
            keyword={keyword}
            onKeyword={setKeyword}
            traders={traders}
            trader={trader}
            onTrader={setTrader}
            leading={
              <div className={styles.dockLeadActions}>
                {canEdit ? (
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
                    {room.is_host ? (
                      <button
                        type="button"
                        className={styles.changeMapBtn}
                        title="按在座已上传的进行中任务，把本图相关项勾进房间"
                        onClick={seedClaims}
                      >
                        按全员进行中勾选
                      </button>
                    ) : null}
                  </>
                ) : null}
              </div>
            }
          />
          <div className={styles.sideHead}>
            <div className={styles.scopeBar} role="tablist" aria-label="任务范围">
              <button
                type="button"
                role="tab"
                aria-selected={listScope === "all"}
                className={`${styles.scopeBtn} ${
                  listScope === "all" ? styles.scopeBtnOn : ""
                }`}
                onClick={() => setListScope("all")}
              >
                全部 {picked.length + rest.length}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={listScope === "picked"}
                className={`${styles.scopeBtn} ${
                  listScope === "picked" ? styles.scopeBtnOn : ""
                }`}
                onClick={() => setListScope("picked")}
              >
                我的已选 {myClaims.size}
              </button>
            </div>
          </div>
          <div
            ref={setTaskListEl}
            className={styles.taskList}
            onClick={() => setHighlightTaskId("")}
          >
            {prepQuery.isLoading && !prepQuery.data && !picked.length ? (
              <div className={styles.empty}>
                <Spin />
              </div>
            ) : listScope === "picked" ? (
              picked.length ? (
                picked.map((row, index) => (
                  <TarkovRaidPrepTaskCard
                    key={row.id}
                    row={row}
                    mapSlug={mapId}
                    compact
                    checked={myClaims.has(row.id)}
                    highlighted
                    active={highlightTaskId === row.id}
                    color={colorByTask.get(row.id) || colorForTaskIndex(index)}
                    disabled={!canEdit}
                    skipped={raidPrepSkippedIds(objDone, row.id)}
                    onToggleObjective={toggleObjDone}
                    onToggle={toggleClaim}
                    onNeedDetail={geometry.ensure}
                    onLocate={locateTask}
                    onTitle={openGuide}
                  />
                ))
              ) : (
                <div className={styles.empty}>还没勾选任务</div>
              )
            ) : (
              <>
                <div ref={setRestHeadEl}>
                  {myClaims.size > 0 &&
                  prepQuery.isLoading &&
                  !picked.length ? (
                    <div className={styles.pickedBlock}>
                      <p className={styles.pickedLabel}>我的已选 {myClaims.size}</p>
                      <div className={styles.empty}>
                        <Spin />
                      </div>
                    </div>
                  ) : picked.length ? (
                    <div className={styles.pickedBlock}>
                      <p className={styles.pickedLabel}>我的已选 {picked.length}</p>
                      {picked.map((row, index) => (
                        <TarkovRaidPrepTaskCard
                          key={row.id}
                          row={row}
                          mapSlug={mapId}
                          compact
                          checked={myClaims.has(row.id)}
                          highlighted
                          active={highlightTaskId === row.id}
                          color={colorByTask.get(row.id) || colorForTaskIndex(index)}
                          disabled={!canEdit}
                          skipped={raidPrepSkippedIds(objDone, row.id)}
                          onToggleObjective={toggleObjDone}
                          onToggle={toggleClaim}
                          onNeedDetail={geometry.ensure}
                          onLocate={locateTask}
                          onTitle={openGuide}
                        />
                      ))}
                    </div>
                  ) : null}
                  {rest.length && picked.length ? (
                    <p className={styles.restLabel}>筛选结果</p>
                  ) : null}
                </div>
                {rest.length ? (
                  <TarkovRaidPrepRestList
                    items={rest}
                    scrollParent={taskListEl}
                    head={restHeadEl}
                    renderRow={(row) => (
                      <TarkovRaidPrepTaskCard
                        key={row.id}
                        row={row}
                        mapSlug={mapId}
                        checked={false}
                        highlighted={false}
                        active={highlightTaskId === row.id}
                        disabled={!canEdit}
                        skipped={raidPrepSkippedIds(objDone, row.id)}
                        onToggleObjective={toggleObjDone}
                        onToggle={toggleClaim}
                        onNeedDetail={geometry.ensure}
                        onLocate={locateTask}
                        onTitle={openGuide}
                      />
                    )}
                  />
                ) : prepQuery.isLoading && !prepQuery.data ? (
                  <div className={styles.empty}>
                    <Spin />
                  </div>
                ) : (
                  <div className={styles.empty}>
                    {picked.length || myClaims.size
                      ? "当前筛选下无其他任务"
                      : "当前筛选下无任务"}
                  </div>
                )}
              </>
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
        title="房间管理"
        open={manageOpen}
        onCancel={() => setManageOpen(false)}
        footer={null}
        width={420}
        destroyOnClose
      >
        <div className={styles.manageList}>
          {members.map((row) => (
            <div key={row.user_id} className={styles.manageRow}>
              <span className={styles.manageName}>
                <span
                  className={styles.memberDot}
                  style={{ background: colorForUserId(row.user_id) }}
                />
                {row.display_name}
                {row.is_host ? " · 房主" : ""}
              </span>
              {!row.is_host ? (
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
              ) : (
                <span className={styles.manageHostMark}>自己</span>
              )}
            </div>
          ))}
        </div>
        <div className={styles.managePassword}>
          <p className={styles.managePasswordHint}>
            {room.has_password
              ? "已设密码，未入座的人需要输入才能加入"
              : "未设密码，大厅点一下即可加入"}
          </p>
          <Input.Password
            value={passwordDraft}
            onChange={(event) => setPasswordDraft(event.target.value)}
            placeholder={room.has_password ? "输入新密码" : "设置密码"}
            maxLength={32}
          />
          <div className={styles.managePasswordActions}>
            <button
              type="button"
              className={styles.dockChip}
              disabled={passwordMut.isPending || !passwordDraft.trim()}
              onClick={() => passwordMut.mutate(passwordDraft.trim())}
            >
              {room.has_password ? "修改密码" : "设置密码"}
            </button>
            {room.has_password ? (
              <button
                type="button"
                className={styles.dockChip}
                disabled={passwordMut.isPending}
                onClick={() => passwordMut.mutate("")}
              >
                清除密码
              </button>
            ) : null}
          </div>
        </div>
        <div className={styles.manageFooter}>
          <button
            type="button"
            className={styles.dockChip}
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
