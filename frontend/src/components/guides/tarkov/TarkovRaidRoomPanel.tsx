import { Alert, Modal, Spin } from "antd";
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
  removeTarkovRaidRoomMark,
  resetTarkovRaidRoom,
  setTarkovRaidRoomMap,
  tarkovRaidRoomWsUrl,
  unbringTarkovRaidRoomKey,
  unclaimTarkovRaidRoomTask,
  undoTarkovRaidRoomMark,
  type TarkovRaidRoomDetail,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { TARKOV_RAID_PREP_PATH, tarkovRaidRoomShareUrl } from "@/lib/tarkovHomeNav";
import {
  RAID_PREP_MAX_SELECTED,
  buildRaidPrepOverlays,
  colorForTaskIndex,
  colorForUserId,
  filterRaidPrepRows,
  partitionRaidPrepRows,
  raidPrepMapOptions,
  resolveRaidPrepLocatePoints,
  selectedTasksFromCatalog,
} from "@/lib/tarkovRaidPrep";
import {
  applyRoomWsEvent,
  groupClaimsByTask,
  claimTaskIdsForUser,
  userBroughtKey,
  isTypingTarget,
  mergeBoardMarks,
  parseStrokePoints,
  raidRoomWsRetryDelayMs,
  withRaidRoomViewerFlags,
  type RaidRoomDraftStroke,
  type RaidRoomMarkLike,
  type StrokePoint,
  type TarkovMapDrawMode,
} from "@/lib/tarkovRaidRooms";
import { useTarkovTaskMineMode } from "@/lib/tarkovTaskProgress";
import { PanelFallback } from "@/components/RouteFallback";
import { TarkovTaskProgressSwitch } from "@/components/guides/tarkov/TarkovTaskProgressSwitch";
import { TarkovTrackerBindButton } from "@/components/guides/tarkov/TarkovTrackerBindButton";
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
  const [mine, setMine] = useTarkovTaskMineMode();
  const meIdRef = useRef(me?.id);
  meIdRef.current = me?.id;
  const [pendingMarks, setPendingMarks] = useState<RaidRoomMarkLike[]>([]);
  const [remoteDrafts, setRemoteDrafts] = useState<RaidRoomDraftStroke[]>([]);
  const [error, setError] = useState("");
  const [guideOpen, setGuideOpen] = useState(false);
  const [guideTaskId, setGuideTaskId] = useState("");
  const [ocrOpen, setOcrOpen] = useState(false);
  const [highlightTaskId, setHighlightTaskId] = useState("");
  const [dockOpen, setDockOpen] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);
  const [mapPickOpen, setMapPickOpen] = useState(false);
  const [focusRequest, setFocusRequest] = useState<TarkovMapFocusRequest | null>(
    null,
  );
  const focusSeqRef = useRef(0);
  const locateIndexRef = useRef<Record<string, number>>({});
  const wsRef = useRef<WebSocket | null>(null);

  const roomQuery = useQuery({
    queryKey: ["guides-tarkov-raid-room", publicId],
    queryFn: () => fetchTarkovRaidRoom(publicId),
    retry: 1,
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
          mark?: { author_user_id?: number };
        };
        try {
          payload = JSON.parse(String(event.data || ""));
        } catch {
          return;
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
    const handle = window.setTimeout(() => {
      setQuery(keyword.trim());
    }, 300);
    return () => window.clearTimeout(handle);
  }, [keyword]);

  const prepQuery = useQuery({
    queryKey: ["guides-tarkov-raid-prep", gameMode, mapId, mine],
    queryFn: () => fetchTarkovRaidPrep({ map: mapId, progress: mine }),
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
    onError: (exc) => setError(apiError(exc, "清桌失败")),
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
  const bound = Boolean(prepQuery.data?.progress_bound);
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
  const overlays = useMemo(
    () => buildRaidPrepOverlays(overlayTasks, mapId),
    [overlayTasks, mapId],
  );
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
      content: "换图会清空点位、任务勾选和钥匙声明",
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

  const toggleKeyBring = (itemId: string) => {
    if (!canEdit) return;
    if (userBroughtKey(room?.key_brings, itemId, me?.id)) {
      void run(() => unbringTarkovRaidRoomKey(publicId, itemId));
      return;
    }
    void run(() => bringTarkovRaidRoomKey(publicId, itemId));
  };

  const locateTask = useCallback(
    async (row: (typeof rows)[number]) => {
      let points = resolveRaidPrepLocatePoints(
        overlayTasks.find((item) => item.id === row.id) || row,
        mapId,
      );
      if (!points.length && row.has_map_markers) {
        try {
          const extra = await fetchTarkovRaidPrep({
            map: mapId,
            geometry: true,
            ids: [row.id],
          });
          const rich = extra.items.find((item) => item.id === row.id);
          points = rich ? resolveRaidPrepLocatePoints(rich, mapId) : [];
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
    [mapId, overlayTasks],
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
              onClick={() => {
                Modal.confirm({
                  title: "清桌？",
                  content: "会请出所有人，并清空地图、点位、任务勾选和钥匙声明。",
                  okText: "清桌",
                  cancelText: "取消",
                  onOk: () => resetMut.mutateAsync(),
                });
              }}
            >
              清桌
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
      {mine && prepQuery.data && !bound ? (
        <Alert
          type="info"
          showIcon
          message="还没绑定 Tarkov Tracker"
          description={
            <span className={styles.bindHint}>
              绑定后可按进度灰显已完成任务。
              <TarkovTrackerBindButton />
            </span>
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
                  <p className={styles.mapPickHint}>选择这局地图。之后换图会清空点位、任务勾选和钥匙声明。</p>
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
                        currentUserId={me?.id}
                        canToggleKeyBring={canEdit}
                        onToggleKeyBring={toggleKeyBring}
                      />
                      <TarkovRaidPrepGuideOverview
                        tasks={selectedTasks.map((row) => ({
                          id: row.id,
                          name: row.name,
                          normalized_name: row.normalized_name,
                          trader_slug: row.trader_slug,
                          trader_name: row.trader_name,
                        }))}
                        participantsByTask={participantsByTask}
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
                <TarkovTaskProgressSwitch enabled={mine} onChange={setMine} />
                {canEdit ? (
                  <button
                    type="button"
                    className={styles.changeMapBtn}
                    onClick={() => setOcrOpen(true)}
                  >
                    截图识别
                  </button>
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
                    compact
                    checked={myClaims.has(row.id)}
                    highlighted
                    active={highlightTaskId === row.id}
                    color={colorByTask.get(row.id) || colorForTaskIndex(index)}
                    disabled={!canEdit}
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
                        compact
                        checked={myClaims.has(row.id)}
                        highlighted
                        active={highlightTaskId === row.id}
                        color={colorByTask.get(row.id) || colorForTaskIndex(index)}
                        disabled={!canEdit}
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
                        checked={false}
                        highlighted={false}
                        active={highlightTaskId === row.id}
                        disabled={!canEdit}
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
          换图会清空点位、任务勾选和钥匙声明
        </p>
        <MapPickGrid
          options={mapOptions}
          selectedId={mapId || undefined}
          onPick={pickMap}
        />
      </Modal>
    </div>
  );
}
