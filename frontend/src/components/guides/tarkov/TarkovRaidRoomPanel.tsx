import { Alert, Modal, Spin, message } from "antd";
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import {
  addTarkovRaidRoomMark,
  bringTarkovRaidRoomKey,
  claimTarkovRaidRoomTask,
  claimTarkovRaidRoomTasks,
  clearTarkovRaidRoomMarks,
  fetchTarkovMapDetail,
  fetchTarkovRaidPrep,
  fetchTarkovRaidRoom,
  joinTarkovRaidRoom,
  leaveTarkovRaidRoom,
  markTarkovRaidRoomObjectiveDone,
  removeTarkovRaidRoomMark,
  removeTarkovRaidRoomMember,
  resetTarkovRaidRoom,
  setTarkovRaidRoomMap,
  tarkovRaidRoomWsUrl,
  unbringTarkovRaidRoomKey,
  unmarkTarkovRaidRoomObjectiveDone,
  unclaimTarkovRaidRoomTask,
  undoTarkovRaidRoomMark,
  type TarkovRaidRoomDetail,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  TARKOV_RAID_PREP_PATH,
  tarkovRaidRoomShareUrl,
} from "@/lib/tarkovHomeNav";
import {
  RAID_PREP_MAX_SELECTED,
  buildRaidPrepOverlays,
  colorForTaskIndex,
  colorForUserId,
  filterRaidPrepRows,
  partitionRaidPrepRows,
  planRaidPrepTaskProgressSync,
  objectiveDonesToSkipMap,
  objectiveDonesToSkipMapAny,
  raidPrepMapOptions,
  raidPrepSkippedIds,
  resolveRaidPrepLocatePoints,
  roomObjectiveMarksForCompletedTasks,
  selectedTasksFromCatalog,
  userMarkedObjective,
} from "@/lib/tarkovRaidPrep";
import {
  TARKOV_TASK_PROGRESS_EVENT,
  type TarkovTaskProgressDetail,
} from "@/lib/tarkovLiveWatch";
import { useTarkovLiveWatch } from "@/lib/tarkovLiveWatchContext";
import { loadTaskDoneIds, loadTaskStartedIds } from "@/lib/tarkovTaskTree";
import {
  applyRoomWsEvent,
  dropPlayerFixesNotIn,
  groupClaimsByTask,
  claimTaskIdsForUser,
  userBroughtKey,
  isTypingTarget,
  mergeBoardMarks,
  parsePlayerFixEvent,
  parseStrokePoints,
  playerFixMatchesRoomMap,
  pruneStalePlayerFixes,
  raidRoomWsRetryDelayMs,
  upsertPlayerFix,
  withRaidRoomViewerFlags,
  type RaidRoomDraftStroke,
  type RaidRoomMarkLike,
  type RaidRoomPlayerFix,
  type StrokePoint,
  type TarkovMapDrawMode,
  type TarkovMapPlayerMark,
} from "@/lib/tarkovRaidRooms";
import { PanelFallback } from "@/components/RouteFallback";
import { TarkovRaidPrepFilters } from "@/components/guides/tarkov/TarkovRaidPrepFilters";
import { TarkovRaidPrepOcrModal } from "@/components/guides/tarkov/TarkovRaidPrepOcrModal";
import { TarkovRaidPrepSummary } from "@/components/guides/tarkov/TarkovRaidPrepSummary";
import { TarkovRaidPrepGuideOverview } from "@/components/guides/tarkov/TarkovRaidPrepGuideOverview";
import { TarkovRaidPrepTaskCard } from "@/components/guides/tarkov/TarkovRaidPrepTaskCard";
import { MapPickGrid } from "@/components/guides/tarkov/TarkovRaidPrepEntryModal";
import type { TarkovMapFocusRequest } from "@/components/guides/tarkov/TarkovMapViewer";
import { useAuthStore } from "@/stores/authStore";
import catalogCss from "./TarkovItemCatalogPanel.module.css";
import styles from "./TarkovRaidPrepPanel.module.css";

const TarkovMapViewer = lazy(() =>
  import("@/components/guides/tarkov/TarkovMapViewer").then((m) => ({
    default: m.TarkovMapViewer,
  })),
);

export function TarkovRaidRoomPanel({ publicId }: { publicId: string }) {
  const gameMode = useTarkovGameMode();
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
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
  const [remoteDrafts, setRemoteDrafts] = useState<RaidRoomDraftStroke[]>([]);
  const [remoteFixes, setRemoteFixes] = useState<RaidRoomPlayerFix[]>([]);
  const [wsGen, setWsGen] = useState(0);
  const live = useTarkovLiveWatch();
  const lastSentFixRef = useRef("");
  const [error, setError] = useState("");
  const [guideOpen, setGuideOpen] = useState(false);
  const [guideTaskId, setGuideTaskId] = useState("");
  const [ocrOpen, setOcrOpen] = useState(false);
  const [highlightTaskId, setHighlightTaskId] = useState("");
  const [dockOpen, setDockOpen] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);
  const [mapPickOpen, setMapPickOpen] = useState(false);
  const [manageOpen, setManageOpen] = useState(false);
  const [focusRequest, setFocusRequest] = useState<TarkovMapFocusRequest | null>(
    null,
  );
  const objDone = useMemo(
    () => objectiveDonesToSkipMap(room?.objective_dones, me?.id),
    [room?.objective_dones, me?.id],
  );
  const mapObjDone = useMemo(
    () => objectiveDonesToSkipMapAny(room?.objective_dones),
    [room?.objective_dones],
  );
  const focusSeqRef = useRef(0);
  const locateIndexRef = useRef<Record<string, number>>({});
  const wsRef = useRef<WebSocket | null>(null);

  const roomQuery = useQuery({
    queryKey: ["guides-tarkov-raid-room", publicId],
    queryFn: () => fetchTarkovRaidRoom(publicId),
    retry: 1,
    refetchInterval: (query) =>
      query.state.data?.is_member ? 30_000 : false,
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
          mark?: { author_user_id?: number };
        };
        try {
          payload = JSON.parse(String(event.data || ""));
        } catch {
          return;
        }
        if (payload.event === "snapshot") {
          setWsGen((n) => n + 1);
        }
        if (payload.event === "player_fix") {
          const parsed = parsePlayerFixEvent(payload);
          if (!parsed || parsed.userId === meIdRef.current) return;
          if (!playerFixMatchesRoomMap(parsed.mapId, mapIdRef.current)) return;
          setRemoteFixes((current) => upsertPlayerFix(current, parsed));
          return;
        }
        if (payload.event === "presence" && payload.online_user_ids) {
          const online = new Set(payload.online_user_ids);
          setRemoteFixes((current) => dropPlayerFixesNotIn(current, online));
        }
        if (payload.event === "draw_draft") {
          const uid = Number(payload.user_id);
          if (!uid || uid === meIdRef.current) return;
          const points = parseStrokePoints(payload.points);
          setRemoteDrafts((current) => {
            const rest = current.filter((row) => row.userId !== uid);
            if (!points.length) return rest;
            return [
              ...rest,
              {
                userId: uid,
                floor: String(payload.floor || ""),
                points,
                color: colorForUserId(uid),
              },
            ];
          });
          return;
        }
        if (payload.event === "mark_add") {
          const uid = Number(payload.mark?.author_user_id);
          if (uid) {
            setRemoteDrafts((current) =>
              current.filter((row) => row.userId !== uid),
            );
          }
        }
        if (payload.event === "board_clear") {
          setRemoteDrafts([]);
          setPendingMarks([]);
        }
        if (payload.event === "reset") {
          navigate(TARKOV_RAID_PREP_PATH);
          return;
        }
        if (payload.event === "member_leave") {
          const uid = Number(payload.user_id);
          if (uid) {
            setRemoteFixes((current) =>
              current.filter((row) => row.userId !== uid),
            );
          }
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
    }, 25000);
    return () => {
      stopped = true;
      window.clearInterval(ping);
      window.clearTimeout(retryTimer);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [token, publicId, room?.is_member]);

  useEffect(() => {
    setRemoteFixes((current) =>
      current.filter((row) => playerFixMatchesRoomMap(row.mapId, mapId)),
    );
  }, [mapId]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setRemoteFixes((current) => pruneStalePlayerFixes(current));
    }, 15_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    lastSentFixRef.current = "";
  }, [wsGen]);

  useEffect(() => {
    const ws = wsRef.current;
    const fix = live.fix;
    if (!canEdit || !fix || !ws || ws.readyState !== WebSocket.OPEN) return;
    if (
      live.lastLogMapId &&
      !playerFixMatchesRoomMap(live.lastLogMapId, mapId)
    ) {
      return;
    }
    const sig = `${fix.fileName}:${fix.lastModified}:${mapId}:${wsGen}`;
    if (lastSentFixRef.current === sig) return;
    lastSentFixRef.current = sig;
    ws.send(
      JSON.stringify({
        event: "player_fix",
        x: fix.x,
        y: fix.y,
        z: fix.z,
        yaw: fix.yaw,
        map_id: live.lastLogMapId || mapId,
        file_name: fix.fileName,
      }),
    );
  }, [canEdit, live.fix, live.lastLogMapId, mapId, wsGen]);

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
  const geometryQuery = useQuery({
    queryKey: ["guides-tarkov-raid-prep-geometry", gameMode, mapId, claimedKey],
    queryFn: () =>
      fetchTarkovRaidPrep({
        map: mapId,
        geometry: true,
        ids: claimedKey.split(",").filter(Boolean),
      }),
    enabled: Boolean(mapId) && Boolean(claimedKey),
    staleTime: 5 * 60_000,
    retry: 1,
    placeholderData: keepPreviousData,
  });

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
    onSuccess: () => navigate(TARKOV_RAID_PREP_PATH),
    onError: (exc) => setError(apiError(exc, "离开失败")),
  });
  const joinMut = useMutation({
    mutationFn: () => joinTarkovRaidRoom(publicId),
    onSuccess: (next) => applyRoom(next),
    onError: (exc) => setError(apiError(exc, "加入失败")),
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
  const selectedTasks = useMemo(
    () =>
      selectedTasksFromCatalog(
        catalog,
        groups.map((row) => row.taskId),
      ),
    [catalog, groups],
  );
  const mySelectedTasks = useMemo(
    () => selectedTasksFromCatalog(catalog, myClaimIds),
    [catalog, myClaimIds],
  );
  const overlayTasks = useMemo(
    () =>
      selectedTasksFromCatalog(
        geometryQuery.data?.items ?? [],
        groups.map((row) => row.taskId),
      ),
    [geometryQuery.data, groups],
  );
  const rows = useMemo(
    () => filterRaidPrepRows(catalog, { trader, q: query }),
    [catalog, trader, query],
  );
  const { picked, rest } = useMemo(
    () => partitionRaidPrepRows(rows, mySelectedTasks),
    [rows, mySelectedTasks],
  );
  const overlayTasksRef = useRef(overlayTasks);
  overlayTasksRef.current = overlayTasks;
  const overlays = useMemo(
    () => buildRaidPrepOverlays(overlayTasks, mapId, mapObjDone),
    [overlayTasks, mapId, mapObjDone],
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
        for (const row of pending) {
          const ok = await run(() =>
            markTarkovRaidRoomObjectiveDone(
              publicId,
              row.taskId,
              row.objectiveId,
            ),
          );
          if (!ok) break;
        }
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
    };
    window.addEventListener(TARKOV_TASK_PROGRESS_EVENT, onProgress);
    return () =>
      window.removeEventListener(TARKOV_TASK_PROGRESS_EVENT, onProgress);
  }, [flushCompletedTaskMarks, gameMode]);

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
    geometryQuery.dataUpdatedAt,
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
  const remotePlayerMarks = useMemo<TarkovMapPlayerMark[]>(() => {
    const names = new Map<number, string>();
    for (const row of members) {
      names.set(row.user_id, row.display_name);
    }
    return remoteFixes
      .filter((row) => playerFixMatchesRoomMap(row.mapId, mapId))
      .map((row) => ({
        key: `u:${row.userId}:${row.fileName || row.at}`,
        userId: row.userId,
        name: names.get(row.userId) || "",
        color: colorForUserId(row.userId),
        x: row.x,
        y: row.y,
        z: row.z,
        yaw: row.yaw,
      }));
  }, [mapId, members, remoteFixes]);
  const hideLocalFix = Boolean(
    live.lastLogMapId && !playerFixMatchesRoomMap(live.lastLogMapId, mapId),
  );

  const pickMap = (nextMap: string) => {
    if (!nextMap || nextMap === mapId) {
      setMapPickOpen(false);
      return;
    }
    const apply = () => {
      setMapPickOpen(false);
      void run(() => setTarkovRaidRoomMap(publicId, nextMap));
    };
    if (!mapId) {
      apply();
      return;
    }
    Modal.confirm({
      title: "更换地图？",
      content: "换图会清空点位、任务勾选、钥匙声明和完成进度",
      okText: "换图",
      cancelText: "取消",
      onOk: () => apply(),
    });
  };

  const toggleClaim = (taskId: string) => {
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
  };

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

  const toggleKeyBring = (itemId: string) => {
    if (!canEdit) return;
    if (userBroughtKey(room?.key_brings, itemId, me?.id)) {
      void run(() => unbringTarkovRaidRoomKey(publicId, itemId));
      return;
    }
    void run(() => bringTarkovRaidRoomKey(publicId, itemId));
  };

  const toggleObjDone = (taskId: string, objectiveId: string) => {
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
  };

  const locateTask = useCallback(
    async (row: (typeof rows)[number]) => {
      let points = resolveRaidPrepLocatePoints(
        overlayTasks.find((item) => item.id === row.id) || row,
        mapId,
        raidPrepSkippedIds(mapObjDone, row.id),
      );
      if (!points.length && row.has_map_markers) {
        try {
          const extra = await fetchTarkovRaidPrep({
            map: mapId,
            geometry: true,
            ids: [row.id],
          });
          const rich = extra.items.find((item) => item.id === row.id);
          points = rich
            ? resolveRaidPrepLocatePoints(
                rich,
                mapId,
                raidPrepSkippedIds(mapObjDone, row.id),
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
    [mapId, overlayTasks, mapObjDone],
  );

  const taskLocateHandler = useCallback(
    (row: (typeof rows)[number]) =>
      row.has_map_markers ? () => locateTask(row) : undefined,
    [locateTask],
  );

  const openGuide = useCallback((taskId: string) => {
    setGuideTaskId(taskId);
    setGuideOpen(true);
  }, []);

  const onStroke = (stroke: { floor: string; points: StrokePoint[] }) => {
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
  };

  const onDraftStroke = (draft: { floor: string; points: StrokePoint[] } | null) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(
      JSON.stringify({
        event: "draw_draft",
        floor: draft?.floor || "",
        points: (draft?.points || []).map((point) => [point.x, point.z]),
      }),
    );
  };

  const onEraseMark = (markId: number) => {
    if (!canEdit || markId <= 0) return;
    void run(() => removeTarkovRaidRoomMark(publicId, markId));
  };

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
    <div className={styles.stage} data-dock={dockOpen ? "open" : "closed"}>
      {room.is_host && !mapId ? (
        <p className={styles.banner}>选好地图后才能勾任务、画点和声明钥匙</p>
      ) : null}
      {room.is_member && !room.is_host && !mapId ? (
        <p className={styles.banner}>等待房主选择地图</p>
      ) : null}
      <div className={styles.topBar}>
        <div className={styles.roomId}>
          <h1 className={styles.roomTitle}>{title}</h1>
          <div className={styles.roomMeta}>
            {mapLabel || "未选地图"} · {room.member_count}/{room.max_members}
          </div>
        </div>
        <div className={styles.members} aria-label="房间成员">
          {members.map((row) => (
            <span
              key={row.user_id}
              className={styles.memberChip}
              data-online={row.online ? "true" : "false"}
              title={row.online ? "在线" : "离线"}
            >
              <span
                className={styles.memberDot}
                style={{ background: colorForUserId(row.user_id) }}
              />
              {row.display_name}
              {row.is_host ? " · 房主" : ""}
            </span>
          ))}
        </div>
        <div className={styles.topActions}>
          <button
            type="button"
            className={styles.dockToggle}
            onClick={() => setDockOpen((open) => !open)}
          >
            {dockOpen ? "收起任务" : "任务列表"}
          </button>
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
          {room.is_host && mapId ? (
            <button
              type="button"
              className={styles.dockChip}
              onClick={() => setMapPickOpen(true)}
            >
              更换地图
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
            <button
              type="button"
              className={styles.dockChip}
              disabled={joinMut.isPending}
              onClick={() => joinMut.mutate()}
            >
              {joinMut.isPending ? "加入中…" : "加入房间"}
            </button>
          }
        />
      ) : null}
      {error ? <Alert type="error" showIcon message={error} /> : null}

      <div className={styles.workspace}>
        <div className={styles.mapPane}>
          {canEdit ? (
            <div className={styles.drawDock}>
              {(
                [
                  ["pan", "拖拽", "拖拽移动地图"],
                  ["pen", "画笔", "按住拖拽涂鸦，空格拖地图"],
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
              {tool === "erase" ? (
                <span className={styles.drawHint}>点一下擦掉笔画</span>
              ) : null}
            </div>
          ) : null}
          <div className={styles.mapFill}>
            {!mapId ? (
              room.is_host ? (
                <div className={styles.mapPickPane}>
                  <p className={styles.mapPickHint}>选择这局地图。之后换图会清空点位、任务勾选、钥匙声明和完成进度。</p>
                  <MapPickGrid
                    options={mapOptions}
                    onPick={pickMap}
                  />
                </div>
              ) : (
                <div className={catalogCss.status}>
                  {room.is_member ? "等待房主选择地图" : "加入后可一起准备"}
                </div>
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
                <TarkovMapViewer
                  slug={mapId}
                  parentSlug={mapQuery.data?.parent_slug || undefined}
                  extracts={mapQuery.data?.extracts}
                  bosses={mapQuery.data?.bosses}
                  spawns={mapQuery.data?.spawns}
                  questOverlays={overlays}
                  focusRequest={focusRequest}
                  highlightTaskId={highlightTaskId}
                  boardMarks={boardMarks}
                  remoteDrafts={remoteDrafts}
                  remotePlayerFixes={remotePlayerMarks}
                  suppressLocalFix={hideLocalFix}
                  drawColor={colorForUserId(me?.id || 0)}
                  authorUserId={me?.id || 0}
                  drawMode={canEdit ? tool : "pan"}
                  onStroke={onStroke}
                  onDraftStroke={onDraftStroke}
                  onEraseMark={onEraseMark}
                  fill
                  onQuestLabelClick={(taskId) => {
                    setHighlightTaskId(taskId);
                    openGuide(taskId);
                  }}
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
                        objectiveDones={room?.objective_dones}
                        currentUserId={me?.id}
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
        <aside className={styles.dock} aria-label="任务列表">
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
            className={styles.taskList}
            onClick={() => setHighlightTaskId("")}
          >
            {listScope === "picked" ? (
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
                    objectiveDones={room?.objective_dones}
                    currentUserId={me?.id}
                    onToggleObjective={(objectiveId) =>
                      toggleObjDone(row.id, objectiveId)
                    }
                    onToggle={() => toggleClaim(row.id)}
                    onLocate={taskLocateHandler(row)}
                    onTitle={() => openGuide(row.id)}
                  />
                ))
              ) : (
                <div className={styles.empty}>还没勾选任务</div>
              )
            ) : prepQuery.isLoading && !prepQuery.data && !picked.length ? (
              <div className={styles.empty}>
                <Spin />
              </div>
            ) : (
              <>
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
                        objectiveDones={room?.objective_dones}
                        currentUserId={me?.id}
                        onToggleObjective={(objectiveId) =>
                          toggleObjDone(row.id, objectiveId)
                        }
                        onToggle={() => toggleClaim(row.id)}
                        onLocate={taskLocateHandler(row)}
                        onTitle={() => openGuide(row.id)}
                      />
                    ))}
                  </div>
                ) : null}
                {rest.length ? (
                  <>
                    {picked.length ? (
                      <p className={styles.restLabel}>筛选结果</p>
                    ) : null}
                    {rest.map((row) => (
                      <TarkovRaidPrepTaskCard
                        key={row.id}
                        row={row}
                        mapSlug={mapId}
                        checked={false}
                        highlighted={false}
                        active={highlightTaskId === row.id}
                        disabled={!canEdit}
                        skipped={raidPrepSkippedIds(objDone, row.id)}
                        objectiveDones={room?.objective_dones}
                        currentUserId={me?.id}
                        onToggleObjective={(objectiveId) =>
                          toggleObjDone(row.id, objectiveId)
                        }
                        onToggle={() => toggleClaim(row.id)}
                        onLocate={taskLocateHandler(row)}
                        onTitle={() => openGuide(row.id)}
                      />
                    ))}
                  </>
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
        title="更换地图"
        open={mapPickOpen}
        onCancel={() => setMapPickOpen(false)}
        footer={null}
        width={960}
        destroyOnClose
        classNames={{ body: styles.entryModalBody }}
      >
        <p className={styles.mapPickHint}>
          换图会清空点位、任务勾选、钥匙声明和完成进度
        </p>
        <MapPickGrid
          options={mapOptions}
          selectedId={mapId || undefined}
          onPick={pickMap}
        />
      </Modal>
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
        <div className={styles.manageFooter}>
          <button
            type="button"
            className={styles.dockChip}
            disabled={resetMut.isPending}
            onClick={() => {
              Modal.confirm({
                title: "清空房间？",
                content: "会请出所有人，并清空地图、点位、任务勾选、钥匙声明和完成进度。",
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
