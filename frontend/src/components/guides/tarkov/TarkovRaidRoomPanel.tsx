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
  tarkovRaidRoomWsUrl,
  unclaimTarkovRaidRoomTask,
  undoTarkovRaidRoomMark,
  type TarkovRaidPrepTask,
  type TarkovRaidRoomDetail,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import {
  TARKOV_RAID_PREP_PATH,
  TARKOV_TRADERS,
  tarkovMapHref,
  tarkovTaskHref,
} from "@/lib/tarkovHomeNav";
import { tarkovMapLabel } from "@/lib/tarkovMapLabelsZh";
import {
  RAID_PREP_TYPE_FILTERS,
  buildRaidPrepOverlays,
  colorForTaskId,
  colorForUserId,
  neededKeyNamesForMap,
  objectiveZoneNames,
  raidPrepMapOptions,
} from "@/lib/tarkovRaidPrep";
import {
  applyRoomWsEvent,
  claimedTaskIds,
  formatRoomRemain,
  groupClaimsByTask,
  remainMs,
  roomDisplayTitle,
} from "@/lib/tarkovRaidRooms";
import {
  orderObjectiveTypes,
  tarkovObjectiveTypeLabel,
  tarkovObjectiveTypeTone,
} from "@/lib/tarkovTaskObjective";
import { PanelFallback } from "@/components/RouteFallback";
import { TarkovTraderThumb } from "@/components/guides/tarkov/TarkovTraderThumb";
import { useAuthStore } from "@/stores/authStore";
import catalog from "./TarkovItemCatalogPanel.module.css";
import taskStyles from "./TarkovTasksPanel.module.css";
import styles from "./TarkovRaidPrepPanel.module.css";

const TarkovMapViewer = lazy(() =>
  import("@/components/guides/tarkov/TarkovMapViewer").then((m) => ({
    default: m.TarkovMapViewer,
  })),
);

function traderFilterLabel(slug: string, apiName: string): {
  english: string;
  chinese: string;
} {
  const known = TARKOV_TRADERS.find((item) => item.id === slug);
  if (known) return { english: known.english, chinese: known.chinese };
  const match = apiName.match(/^(.*?)\s*[（(](.+?)[）)]\s*$/);
  if (match) {
    return { english: match[1].trim(), chinese: match[2].trim() };
  }
  return { english: apiName, chinese: "" };
}

export function TarkovRaidRoomPanel({ publicId }: { publicId: string }) {
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
  const me = useAuthStore((s) => s.user);
  const [room, setRoom] = useState<TarkovRaidRoomDetail | null>(null);
  const [keyword, setKeyword] = useState("");
  const [trader, setTrader] = useState("");
  const [kappa, setKappa] = useState(false);
  const [pinsOnly, setPinsOnly] = useState(false);
  const [types, setTypes] = useState<string[]>([]);
  const [tool, setTool] = useState<"pan" | "pin" | "line">("pan");
  const toolRef = useRef(tool);
  toolRef.current = tool;
  const [draft, setDraft] = useState<{ x: number; z: number; floor: string } | null>(
    null,
  );
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
    if (roomQuery.data) setRoom(roomQuery.data);
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
      };
      try {
        payload = JSON.parse(String(event.data || ""));
      } catch {
        return;
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
  }, [token, publicId, room?.status]); // status 变化才重连，避免每次快照拆掉 WS

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setTool("pan");
      setDraft(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const prepQuery = useQuery({
    queryKey: ["guides-tarkov-raid-prep-room", mapId, trader, keyword, kappa, types.join(",")],
    queryFn: () =>
      fetchTarkovRaidPrep({
        map: mapId,
        q: keyword,
        trader: trader || undefined,
        kappa: kappa || undefined,
        types,
        progress: false,
      }),
    enabled: Boolean(mapId),
    staleTime: 5 * 60_000,
    retry: 1,
    placeholderData: keepPreviousData,
  });

  const overlayPrepQuery = useQuery({
    queryKey: ["guides-tarkov-raid-prep-room-overlay", mapId],
    queryFn: () => fetchTarkovRaidPrep({ map: mapId, progress: false }),
    enabled: Boolean(mapId),
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const mapQuery = useQuery({
    queryKey: ["guides-tarkov-map", mapId],
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
  const selectedIds = useMemo(() => claimedTaskIds(claims), [claims]);
  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const myClaims = useMemo(
    () => new Set((claims || []).filter((row) => row.user_id === me?.id).map((row) => row.task_id)),
    [claims, me?.id],
  );
  const groups = useMemo(() => groupClaimsByTask(claims), [claims]);
  const rows = useMemo(() => {
    const items = prepQuery.data?.items ?? [];
    if (!pinsOnly) return items;
    return items.filter((row) => row.has_map_markers);
  }, [prepQuery.data, pinsOnly]);
  const selectedTasks = useMemo(() => {
    const items = overlayPrepQuery.data?.items ?? [];
    return items.filter((row) => selectedSet.has(row.id));
  }, [overlayPrepQuery.data, selectedSet]);
  const overlays = useMemo(
    () => buildRaidPrepOverlays(selectedTasks, mapId),
    [selectedTasks, mapId],
  );
  const typeOptions = useMemo(() => {
    const seen = new Set<string>(RAID_PREP_TYPE_FILTERS);
    for (const type of types) seen.add(type);
    for (const row of prepQuery.data?.items || []) {
      for (const type of row.objective_types || []) {
        if (type) seen.add(type);
      }
    }
    return orderObjectiveTypes([...seen]);
  }, [prepQuery.data, types]);
  const mapOptions = useMemo(() => raidPrepMapOptions(), []);
  const currentMap = mapOptions.find((item) => item.id === mapId);
  const mapLabel = currentMap?.label || mapId;
  const title = room ? roomDisplayTitle(room, mapLabel) : "房间";
  const remain = formatRoomRemain(remainMs(room?.expire_at, now));
  const traders = prepQuery.data?.traders ?? [];

  const toggleClaim = (taskId: string) => {
    if (!canEdit) return;
    if (myClaims.has(taskId)) void run(() => unclaimTarkovRaidRoomTask(publicId, taskId));
    else void run(() => claimTarkovRaidRoomTask(publicId, taskId));
  };

  const onMapPoint = (point: { x: number; z: number; floor: string }) => {
    if (!canEdit) return;
    const mode = toolRef.current;
    if (mode === "pin") {
      void run(() =>
        addTarkovRaidRoomMark(publicId, {
          kind: "pin",
          floor: point.floor,
          x: point.x,
          z: point.z,
        }),
      );
      return;
    }
    if (mode !== "line") return;
    if (!draft || draft.floor !== point.floor) {
      setDraft(point);
      return;
    }
    void (async () => {
      const ok = await run(() =>
        addTarkovRaidRoomMark(publicId, {
          kind: "line",
          floor: point.floor,
          x: draft.x,
          z: draft.z,
          x2: point.x,
          z2: point.z,
        }),
      );
      if (ok) setDraft(null);
    })();
  };

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
    <div className={styles.stack}>
      {archived ? (
        <p className={styles.banner}>已留档，仅供查看</p>
      ) : null}
      <div className={styles.lobbyHead}>
        <div>
          <div className={styles.lobbyTitle}>{title}</div>
          <div className={styles.lobbySub}>
            {mapLabel} · {room.host_display_name} · {room.member_count}/
            {room.max_members} · {archived ? "已封存" : remain}
            {(room.members || [])
              .filter((row) => row.in_room)
              .map((row) => (
                <span key={row.user_id}>
                  {" "}
                  · {row.display_name}
                  {row.online ? "●" : ""}
                </span>
              ))}
          </div>
        </div>
        <div className={styles.actions}>
          <Link className={styles.wiki} to={TARKOV_RAID_PREP_PATH}>
            大厅
          </Link>
          <Link className={styles.wiki} to={tarkovMapHref(mapId)}>
            地图页
          </Link>
          {room.is_host && !archived ? (
            <button
              type="button"
              className={taskStyles.chip}
              onClick={() => closeMut.mutate()}
            >
              关闭房间
            </button>
          ) : null}
          {!room.is_host && room.is_member && !archived ? (
            <button
              type="button"
              className={taskStyles.chip}
              onClick={() => leaveMut.mutate()}
            >
              离开
            </button>
          ) : null}
        </div>
      </div>
      {error ? (
        <Alert type="error" showIcon message={error} />
      ) : null}

      <div className={taskStyles.toolbar}>
        <div className={taskStyles.queryRow}>
          <input
            className={taskStyles.search}
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="按任务名称筛选"
            aria-label="搜索任务"
          />
          <button
            type="button"
            aria-pressed={kappa}
            className={`${taskStyles.chip} ${kappa ? taskStyles.chipOn : ""}`}
            onClick={() => setKappa((value) => !value)}
          >
            Kappa
          </button>
          <button
            type="button"
            aria-pressed={pinsOnly}
            className={`${taskStyles.chip} ${pinsOnly ? taskStyles.chipOn : ""}`}
            onClick={() => setPinsOnly((value) => !value)}
          >
            仅有点位
          </button>
        </div>
        <div className={taskStyles.filterRow}>
          <span className={taskStyles.filterLabel}>商人</span>
          <div className={taskStyles.traderBar} role="radiogroup" aria-label="按商人筛选">
            <button
              type="button"
              role="radio"
              aria-checked={!trader}
              className={`${taskStyles.traderBtn} ${taskStyles.traderBtnAll} ${
                !trader ? taskStyles.traderBtnOn : ""
              }`}
              onClick={() => setTrader("")}
            >
              全部
            </button>
            {traders.map((item) => {
              const { english, chinese } = traderFilterLabel(item.slug, item.name);
              const on = trader === item.slug;
              return (
                <button
                  key={item.slug || item.id}
                  type="button"
                  role="radio"
                  aria-checked={on}
                  title={chinese ? `${english}（${chinese}）` : english}
                  className={`${taskStyles.traderBtn} ${on ? taskStyles.traderBtnOn : ""}`}
                  onClick={() => setTrader(item.slug)}
                >
                  <TarkovTraderThumb slug={item.slug} size={40} />
                </button>
              );
            })}
          </div>
        </div>
        <div className={taskStyles.filterRow}>
          <span className={taskStyles.filterLabel}>目标</span>
          <div className={taskStyles.chipBar}>
            {typeOptions.map((type) => (
              <button
                key={type}
                type="button"
                aria-pressed={types.includes(type)}
                className={`${taskStyles.chip} ${types.includes(type) ? taskStyles.chipOn : ""}`}
                onClick={() =>
                  setTypes((current) =>
                    current.includes(type)
                      ? current.filter((item) => item !== type)
                      : [...current, type],
                  )
                }
              >
                {tarkovObjectiveTypeLabel(type)}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className={styles.workspace}>
        <div className={styles.mapPane}>
          {canEdit ? (
            <div className={styles.drawBar}>
              {(["pan", "pin", "line"] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  className={`${taskStyles.chip} ${tool === mode ? taskStyles.chipOn : ""}`}
                  onClick={() => {
                    setTool(mode);
                    setDraft(null);
                  }}
                >
                  {mode === "pan" ? "浏览" : mode === "pin" ? "钉点" : "直线"}
                </button>
              ))}
              <button
                type="button"
                className={taskStyles.chip}
                onClick={() => void run(() => undoTarkovRaidRoomMark(publicId))}
              >
                撤销
              </button>
              {room.is_host ? (
                <button
                  type="button"
                  className={taskStyles.chip}
                  onClick={() => void run(() => clearTarkovRaidRoomMarks(publicId))}
                >
                  清板
                </button>
              ) : null}
              {tool === "line" ? (
                <span className={styles.meta}>
                  {draft ? "再点一下终点" : "先点起点"}
                </span>
              ) : null}
            </div>
          ) : null}
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
                boardMarks={room.marks || []}
                draftLine={
                  draft
                    ? {
                        x: draft.x,
                        z: draft.z,
                        x2: draft.x,
                        z2: draft.z,
                        floor: draft.floor,
                        color: colorForUserId(me?.id || 0),
                      }
                    : null
                }
                drawMode={canEdit ? tool : "pan"}
                onMapPoint={onMapPoint}
                fill
              />
            </Suspense>
          )}
        </div>
        <aside className={styles.side}>
          <div className={styles.sideHead}>
            <span className={styles.count}>
              {rows.length} / {prepQuery.data?.task_count ?? 0}
            </span>
          </div>
          <div className={styles.taskList}>
            {prepQuery.isLoading && !prepQuery.data ? (
              <div className={styles.empty}>
                <Spin />
              </div>
            ) : rows.length ? (
              rows.map((row) => (
                <RoomTaskRow
                  key={row.id}
                  row={row}
                  mapId={mapId}
                  signed={myClaims.has(row.id)}
                  claimed={selectedSet.has(row.id)}
                  names={
                    groups.find((item) => item.taskId === row.id)?.names || []
                  }
                  onToggle={() => toggleClaim(row.id)}
                />
              ))
            ) : (
              <div className={styles.empty}>当前筛选下无任务</div>
            )}
          </div>
        </aside>
      </div>

      <div className={styles.bottomBar} aria-label="已选任务">
        {groups.length ? (
          groups.map((group) => {
            const task = selectedTasks.find((row) => row.id === group.taskId);
            return (
              <span key={group.taskId} className={styles.bottomChip}>
                <span
                  className={styles.dot}
                  style={{ background: colorForTaskId(group.taskId) }}
                />
                {task?.name || group.taskId}
                <span className={styles.bottomNames}>
                  {group.names.join("、")}
                </span>
              </span>
            );
          })
        ) : (
          <span className={styles.meta}>勾选任务后会出现在这里，并带上署名</span>
        )}
      </div>
    </div>
  );
}

function RoomTaskRow({
  row,
  mapId,
  signed,
  claimed,
  names,
  onToggle,
}: {
  row: TarkovRaidPrepTask;
  mapId: string;
  signed: boolean;
  claimed: boolean;
  names: string[];
  onToggle: () => void;
}) {
  const types = orderObjectiveTypes(row.objective_types);
  const zones = objectiveZoneNames(row);
  const keys = neededKeyNamesForMap(row, mapId);
  return (
    <div
      className={`${styles.taskRow} ${claimed ? styles.taskRowOn : ""}`}
      role="button"
      tabIndex={0}
      onClick={onToggle}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onToggle();
        }
      }}
    >
      <input
        className={styles.check}
        type="checkbox"
        checked={signed}
        readOnly
        tabIndex={-1}
        aria-label={row.name || row.id}
      />
      {claimed ? (
        <span
          className={styles.swatch}
          style={{ background: colorForTaskId(row.id) }}
        />
      ) : null}
      {row.trader_slug ? (
        <TarkovTraderThumb
          slug={row.trader_slug}
          size={32}
          title={row.trader_name || row.trader_slug}
        />
      ) : null}
      <div className={styles.taskBody}>
        <div className={styles.taskTitle}>
          <Link
            className={styles.taskName}
            to={tarkovTaskHref(row.id)}
            onClick={(event) => event.stopPropagation()}
          >
            {row.name || row.normalized_name || row.id}
          </Link>
          {row.has_map_markers ? <span className={styles.mark}>有点位</span> : null}
        </div>
        {names.length ? (
          <div className={styles.meta}>{names.join("、")}</div>
        ) : null}
        {types.length ? (
          <span className={taskStyles.typeList}>
            {types.map((type) => (
              <span
                key={type}
                className={taskStyles.typeChip}
                data-tone={tarkovObjectiveTypeTone(type)}
                title={type}
              >
                {tarkovObjectiveTypeLabel(type)}
              </span>
            ))}
          </span>
        ) : null}
        {zones.length ? (
          <div className={styles.tags}>
            {zones.map((name) => (
              <span key={name} className={styles.zoneTag}>
                {tarkovMapLabel(name)}
              </span>
            ))}
          </div>
        ) : null}
        {keys.length ? (
          <div className={styles.tags}>
            {keys.map((name) => (
              <span key={name} className={styles.keyTag}>
                {name}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
