import { Alert, Spin } from "antd";
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import {
  addTarkovRaidRoomMark,
  claimTarkovRaidRoomTask,
  clearTarkovRaidRoomMarks,
  closeTarkovRaidRoom,
  fetchTarkovMapDetail,
  fetchTarkovRaidPrep,
  fetchTarkovRaidRoom,
  joinTarkovRaidRoom,
  leaveTarkovRaidRoom,
  removeTarkovRaidRoomMark,
  tarkovRaidRoomWsUrl,
  unclaimTarkovRaidRoomTask,
  undoTarkovRaidRoomMark,
  type TarkovRaidRoomDetail,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { TARKOV_RAID_PREP_PATH, tarkovMapHref } from "@/lib/tarkovHomeNav";
import {
  buildRaidPrepOverlays,
  colorForUserId,
  partitionRaidPrepRows,
  raidPrepMapOptions,
  selectedTasksFromCatalog,
} from "@/lib/tarkovRaidPrep";
import {
  applyRoomWsEvent,
  formatRoomRemain,
  groupClaimsByTask,
  isTypingTarget,
  mergeBoardMarks,
  parseStrokePoints,
  remainMs,
  roomDisplayTitle,
  type RaidRoomDraftStroke,
  type RaidRoomMarkLike,
  type StrokePoint,
  type TarkovMapDrawMode,
} from "@/lib/tarkovRaidRooms";
import { PanelFallback } from "@/components/RouteFallback";
import { TarkovRaidPrepFilters } from "@/components/guides/tarkov/TarkovRaidPrepFilters";
import { TarkovRaidPrepSummary } from "@/components/guides/tarkov/TarkovRaidPrepSummary";
import { TarkovRaidPrepTaskCard } from "@/components/guides/tarkov/TarkovRaidPrepTaskCard";
import { useAuthStore } from "@/stores/authStore";
import catalog from "./TarkovItemCatalogPanel.module.css";
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
  const [now, setNow] = useState(() => Date.now());
  const [error, setError] = useState("");
  const wsRef = useRef<WebSocket | null>(null);

  const roomQuery = useQuery({
    queryKey: ["guides-tarkov-raid-room", publicId],
    queryFn: async () => {
      try {
        return await joinTarkovRaidRoom(publicId);
      } catch {
        return fetchTarkovRaidRoom(publicId);
      }
    },
    retry: 1,
  });

  useEffect(() => {
    if (roomQuery.data) {
      setRoom((current) => {
        if (!current) return roomQuery.data;
        const currentMarks = current.marks?.length || 0;
        const nextMarks = roomQuery.data.marks?.length || 0;
        if (currentMarks > nextMarks) return current;
        return roomQuery.data;
      });
    }
  }, [roomQuery.data]);

  const archived = room?.status === "archived";
  const canEdit = Boolean(room?.can_edit) && !archived;
  const mapId = room?.map_slug || "";

  /* 只跟 token / publicId / live 状态重连，快照更新不要拆掉 WS */
  // oxlint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!token || !publicId || !room || room.status !== "live") return undefined;
    let stopped = false;
    const ws = new WebSocket(tarkovRaidRoomWsUrl(publicId));
    wsRef.current = ws;
    ws.onopen = () => {
      ws.send(JSON.stringify({ event: "auth", token }));
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
          setRemoteDrafts((current) => current.filter((row) => row.userId !== uid));
        }
      }
      if (payload.event === "board_clear") {
        setRemoteDrafts([]);
        setPendingMarks([]);
      }
      setRoom((current) => applyRoomWsEvent(current, payload));
    };
    const ping = window.setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ event: "ping" }));
      }
    }, 25000);
    const tick = window.setInterval(() => setNow(Date.now()), 30000);
    return () => {
      stopped = true;
      window.clearInterval(ping);
      window.clearInterval(tick);
      ws.close();
      if (!stopped) wsRef.current = null;
    };
  }, [token, publicId, room?.status]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setQuery(keyword.trim());
    }, 300);
    return () => window.clearTimeout(handle);
  }, [keyword]);

  const prepQuery = useQuery({
    queryKey: [
      "guides-tarkov-raid-prep-room",
      mapId,
      trader,
      query,
    ],
    queryFn: () =>
      fetchTarkovRaidPrep({
        map: mapId,
        q: query,
        trader: trader || undefined,
        progress: false,
      }),
    enabled: Boolean(mapId),
    staleTime: 5 * 60_000,
    retry: 1,
    placeholderData: keepPreviousData,
  });

  const overlayPrepQuery = useQuery({
    queryKey: ["guides-tarkov-raid-prep-room-overlay", gameMode, mapId],
    queryFn: () => fetchTarkovRaidPrep({ map: mapId, progress: false }),
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

  const applyRoom = useCallback((next: TarkovRaidRoomDetail) => {
    setRoom(next);
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

  const closeMut = useMutation({
    mutationFn: () => closeTarkovRaidRoom(publicId),
    onSuccess: (next) => applyRoom(next),
    onError: (exc) => setError(apiError(exc, "关闭失败")),
  });
  const leaveMut = useMutation({
    mutationFn: () => leaveTarkovRaidRoom(publicId),
    onSuccess: () => navigate(TARKOV_RAID_PREP_PATH),
    onError: (exc) => setError(apiError(exc, "离开失败")),
  });

  const claims = room?.claims;
  const myClaims = useMemo(
    () =>
      new Set(
        (claims || [])
          .filter((row) => row.user_id === me?.id)
          .map((row) => row.task_id),
      ),
    [claims, me?.id],
  );
  const groups = useMemo(() => groupClaimsByTask(claims), [claims]);
  const namesByTask = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const group of groups) map.set(group.taskId, group.names);
    return map;
  }, [groups]);
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
  const rows = useMemo(
    () => prepQuery.data?.items ?? [],
    [prepQuery.data],
  );
  const selectedTasks = useMemo(() => {
    const catalog = overlayPrepQuery.isSuccess
      ? overlayPrepQuery.data?.items ?? []
      : rows;
    return selectedTasksFromCatalog(
      catalog,
      groups.map((row) => row.taskId),
    );
  }, [overlayPrepQuery.data, overlayPrepQuery.isSuccess, rows, groups]);
  const { picked, rest } = useMemo(
    () => partitionRaidPrepRows(rows, selectedTasks),
    [rows, selectedTasks],
  );
  const overlays = useMemo(
    () => buildRaidPrepOverlays(selectedTasks, mapId),
    [selectedTasks, mapId],
  );
  const mapOptions = useMemo(() => raidPrepMapOptions(), []);
  const currentMap = mapOptions.find((item) => item.id === mapId);
  const mapLabel = currentMap?.label || mapId;
  const title = room ? roomDisplayTitle(room, mapLabel) : "房间";
  const remain = formatRoomRemain(remainMs(room?.expire_at, now));
  const traders = prepQuery.data?.traders ?? [];
  const members = (room?.members || []).filter((row) => row.in_room);

  const toggleClaim = (taskId: string) => {
    if (!canEdit) return;
    if (myClaims.has(taskId)) void run(() => unclaimTarkovRaidRoomTask(publicId, taskId));
    else void run(() => claimTarkovRaidRoomTask(publicId, taskId));
  };

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
      if (ok) {
        setPendingMarks((current) => current.filter((row) => row.id !== tempId));
      }
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
      <div className={catalog.status}>
        <Spin tip="加入房间…" />
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
    <div className={styles.stage}>
      {archived ? <p className={styles.banner}>已留档，仅供查看</p> : null}
      <div className={styles.topBar}>
        <div className={styles.roomId}>
          <h1 className={styles.roomTitle}>{title}</h1>
          <div className={styles.roomMeta}>
            {mapLabel} · {archived ? "已封存" : remain} · {room.member_count}/
            {room.max_members}
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
          <Link className={styles.wiki} to={TARKOV_RAID_PREP_PATH}>
            大厅
          </Link>
          <Link className={styles.wiki} to={tarkovMapHref(mapId)}>
            地图页
          </Link>
          {room.is_host && !archived ? (
            <button
              type="button"
              className={styles.dockChip}
              onClick={() => closeMut.mutate()}
            >
              关闭房间
            </button>
          ) : null}
          {!room.is_host && room.is_member && !archived ? (
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
            {mapQuery.isLoading ? (
              <div className={catalog.status}>
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
                  questOverlays={overlays}
                  boardMarks={boardMarks}
                  remoteDrafts={remoteDrafts}
                  drawColor={colorForUserId(me?.id || 0)}
                  authorUserId={me?.id || 0}
                  drawMode={canEdit ? tool : "pan"}
                  onStroke={onStroke}
                  onDraftStroke={onDraftStroke}
                  onEraseMark={onEraseMark}
                  fill
                  topRight={
                    <TarkovRaidPrepSummary
                      tasks={selectedTasks}
                      mapId={mapId}
                      participantsByTask={participantsByTask}
                    />
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
                已选 {groups.length}
              </button>
            </div>
          </div>
          <div className={styles.taskList}>
            {listScope === "picked" ? (
              picked.length ? (
                picked.map((row) => (
                  <TarkovRaidPrepTaskCard
                    key={row.id}
                    row={row}
                    mapId={mapId}
                    checked={myClaims.has(row.id)}
                    highlighted
                    names={namesByTask.get(row.id) || []}
                    disabled={!canEdit}
                    onToggle={() => toggleClaim(row.id)}
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
                {groups.length > 0 &&
                overlayPrepQuery.isLoading &&
                !picked.length ? (
                  <div className={styles.pickedBlock}>
                    <p className={styles.pickedLabel}>已选 {groups.length}</p>
                    <div className={styles.empty}>
                      <Spin />
                    </div>
                  </div>
                ) : picked.length ? (
                  <div className={styles.pickedBlock}>
                    <p className={styles.pickedLabel}>已选 {picked.length}</p>
                    {picked.map((row) => (
                      <TarkovRaidPrepTaskCard
                        key={row.id}
                        row={row}
                        mapId={mapId}
                        checked={myClaims.has(row.id)}
                        highlighted
                        names={namesByTask.get(row.id) || []}
                        disabled={!canEdit}
                        onToggle={() => toggleClaim(row.id)}
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
                        mapId={mapId}
                        checked={false}
                        highlighted={false}
                        names={namesByTask.get(row.id) || []}
                        disabled={!canEdit}
                        onToggle={() => toggleClaim(row.id)}
                      />
                    ))}
                  </>
                ) : prepQuery.isLoading && !prepQuery.data ? (
                  <div className={styles.empty}>
                    <Spin />
                  </div>
                ) : (
                  <div className={styles.empty}>
                    {picked.length || groups.length
                      ? "当前筛选下无其他任务"
                      : "当前筛选下无任务"}
                  </div>
                )}
              </>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
