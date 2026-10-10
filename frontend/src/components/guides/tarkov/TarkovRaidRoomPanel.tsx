import { Alert, Input, Modal, Spin } from "antd";
import { useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
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
  writeTaskProgressLedger,
  addTarkovTaskObjectiveDone,
  removeTarkovTaskDone,
  removeTarkovTaskObjectiveDone,
  joinTarkovRaidRoom,
  leaveTarkovRaidRoom,
  markTarkovRaidRoomObjectivesDone,
  putTarkovRaidRoomTaskProgress,
  removeTarkovRaidRoomMark,
  moveTarkovRaidRoomMark,
  removeTarkovRaidRoomMember,
  resetTarkovRaidRoom,
  setTarkovRaidRoomMap,
  tarkovRaidRoomWsUrl,
  transferTarkovRaidRoomHost,
  removeTarkovKeyOwn,
  unbringTarkovRaidRoomKey,
  unclaimTarkovRaidRoomTask,
  undoTarkovRaidRoomMark,
  type TarkovRaidRoomDetail,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { isAssistantEmbed } from "@/lib/assistantShell";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { useTarkovPmcFaction } from "@/lib/tarkovPmcFaction";
import { mergeRaidPrepGuideTasks } from "@/lib/eftarkovGuide";
import { TARKOV_HOME_PATH, TARKOV_RAID_PREP_PATH } from "@/lib/tarkovHomeNav";
import {
  RAID_PREP_MAX_SELECTED,
  clipRaidPrepStateObjectiveDones,
  buildRaidPrepOverlays,
  colorForTaskIndex,
  colorForUserId,
  filterRaidPrepRows,
  groupRaidPrepRowsByProgress,
  hydrateRaidPrepCatalogRows,
  planRaidPrepTaskProgressSync,
  raidPrepOnMapTaskIds,
  objectiveDonesToSkipMap,
  isRaidPrepAutoMapKind,
  normalizeRaidPrepMapId,
  raidPrepMapOptions,
  raidPrepMapsEquivalent,
  raidPrepSkippedIds,
  resolveRaidPrepLocateTargets,
  roomObjectiveMarksForCompletedTasks,
  raidPrepObjectiveDoneLegacyScopes,
  raidPrepObjectiveDoneScope,
  raidPrepSkipMapsEqual,
  raidPrepTaskProgressStatus,
  readRaidPrepObjectiveDoneWithLegacy,
  mergeRaidPrepSkipMaps,
  raidPrepSkipMapForViewer,
  planRaidPrepObjectiveToggle,
  skipMapToObjectiveDones,
  pinSelectedRaidPrepRows,
  raidPrepAllObjectiveIds,
  objectivePairsToSkipMap,
  useRaidPrepObjectiveDone,
  selectedTasksFromCatalog,
  settleRaidPrepSelection,
  type RaidPrepTaskProgressStatus,
} from "@/lib/tarkovRaidPrep";
import {
  TARKOV_TASK_PROGRESS_EVENT,
  type TarkovTaskProgressDetail,
} from "@/lib/tarkovLiveWatch";
import { TarkovLogSyncRangeModal } from "@/components/guides/tarkov/TarkovLogSyncRangeModal";
import { useTarkovLogSyncDialog } from "@/lib/useTarkovLogSyncDialog";
import { useTarkovLastLogMapId, useTarkovLastLogPhase } from "@/lib/useTarkovLiveWatch";
import { useRaidPrepGeometry } from "@/lib/useRaidPrepGeometry";
import { useTarkovRaidDockOpen } from "@/lib/tarkovRaidDockPrefs";
import {
  mapFullscreenEnabled,
  TarkovMapFullscreenRootContext,
} from "@/lib/tarkovMapFullscreen";
import { useRaidRoomLiveStore } from "@/lib/tarkovRaidRoomLiveStore";
import { applyTarkovKeyOwnsCache } from "@/lib/tarkovKeyPacks";
import {
  commitTaskObjective,
  commitTaskStatus,
  loadTaskDoneIds,
  loadTaskFailedIds,
  loadTaskStartedIds,
  resolveAccountTaskProgress,
  taskProgressQueryData,
} from "@/lib/tarkovTaskTree";
import {
  applyRoomWsEvent,
  keepRaidRoomPresence,
  mergeLocalPresenceClient,
  raidRoomSocketClient,
  groupClaimsByTask,
  raidRoomTasksCountingTowardMapCap,
  claimTaskIdsForUser,
  parseRaidRoomLogPhases,
  overlayRaidRoomLocalPhase,
  raidRoomPickDockMapId,
  raidRoomViewerMapSlug,
  readRaidRoomViewMap,
  writeRaidRoomViewMap,
  patchRaidRoomKeyOwns,
  userBroughtKey,
  userOwnsKey,
  isTypingTarget,
  mergeBoardMarks,
  normalizeMarkLabel,
  parsePlayerFixEvent,
  parsePlayerFixEvents,
  parseStrokePoints,
  playerFixIsFresh,
  shouldSuppressLocalPlayerFix,
  RAID_ROOM_WS_PING_MS,
  raidRoomWsCloseReason,
  raidRoomWsRetryDelayMs,
  withRaidRoomViewerFlags,
  type RaidRoomMarkLike,
  type RaidRoomWsEvent,
  type RaidRoomLogPhase,
  type StrokePoint,
  type TarkovMapDrawMode,
} from "@/lib/tarkovRaidRooms";
import { useDocumentHidden, visibleRefetchInterval } from "@/lib/visibleRefetchInterval";
import { TarkovRaidPrepFilters, TarkovShotDirButton } from "@/components/guides/tarkov/TarkovRaidPrepFilters";
import { TarkovRaidPrepTaskGroups } from "@/components/guides/tarkov/TarkovRaidPrepTaskGroups";
import { TarkovRaidPrepOcrModal } from "@/components/guides/tarkov/TarkovRaidPrepOcrModal";
import { TarkovRaidPrepSummary } from "@/components/guides/tarkov/TarkovRaidPrepSummary";
import { TarkovRaidPrepGuideOverview } from "@/components/guides/tarkov/TarkovRaidPrepGuideOverview";
import { TarkovRaidPrepTaskCard } from "@/components/guides/tarkov/TarkovRaidPrepTaskCard";
import { TarkovRaidRoomOverlapBoard } from "@/components/guides/tarkov/TarkovRaidRoomOverlapBoard";
import { TarkovRaidRoomChannelRoster } from "@/components/guides/tarkov/TarkovRaidRoomChannelRoster";
import { TarkovRaidSessionMap } from "@/components/guides/tarkov/TarkovRaidSessionMap";
import { TarkovRaidWorkspace } from "@/components/guides/tarkov/TarkovRaidWorkspace";
import { useTarkovGoonTracker } from "@/lib/useTarkovGoonTracker";
import { TarkovGoonSightingHint } from "@/components/guides/tarkov/TarkovGoonTrackerBanner";
import { TarkovLoginPrompt } from "@/components/guides/tarkov/TarkovLoginPrompt";
import type { TarkovMapFocusRequest } from "@/components/guides/tarkov/TarkovMapViewer";
import { useAuthStore } from "@/stores/authStore";
import catalogCss from "./TarkovItemCatalogPanel.module.css";
import styles from "./TarkovRaidPrepPanel.module.css";

type DrawToolIconName =
  | "pan"
  | "pen"
  | "pin"
  | "line"
  | "text"
  | "erase"
  | "undo"
  | "clear"
  | "sidebars"
  | "fullscreen"
  | "fullscreenExit";

function DrawToolIcon({ name }: { name: DrawToolIconName }) {
  const stroke = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.4,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
      {name === "pan" ? (
        <path
          {...stroke}
          d="M8 2v12M2 8h12M8 2 6.2 3.8M8 2l1.8 1.8M8 14l-1.8-1.8M8 14l1.8-1.8M2 8l1.8-1.8M2 8l1.8 1.8M14 8l-1.8-1.8M14 8l-1.8 1.8"
        />
      ) : null}
      {name === "pen" ? (
        <path {...stroke} d="M10.6 2.2 13.8 5.4 5.6 13.6 2.2 14l.4-3.4Z" />
      ) : null}
      {name === "pin" ? (
        <>
          <path
            {...stroke}
            d="M8 14.2s-4.1-4.3-4.1-7.1a4.1 4.1 0 1 1 8.2 0c0 2.8-4.1 7.1-4.1 7.1Z"
          />
          <circle {...stroke} cx="8" cy="7.1" r="1.2" />
        </>
      ) : null}
      {name === "line" ? <path {...stroke} d="M3 13 13 3" /> : null}
      {name === "text" ? (
        <path {...stroke} d="M3 3.2h10M8 3.2v9.6M5.6 12.8h4.8" />
      ) : null}
      {name === "erase" ? (
        <path
          {...stroke}
          d="M6.2 13.2h7M3.4 10.1 9.2 4.3a1.4 1.4 0 0 1 2 0l1.5 1.5a1.4 1.4 0 0 1 0 2L7.2 13.3H3.3l.1-3.2Z"
        />
      ) : null}
      {name === "undo" ? (
        <path {...stroke} d="M3.2 6.4V3.2h3.2M3.5 6.2A5 5 0 1 1 4.9 12" />
      ) : null}
      {name === "clear" ? (
        <path {...stroke} d="M3.2 4.2h9.6M6.2 4.2V2.8h3.6v1.4M4.4 4.2l.6 9h5.9l.6-9" />
      ) : null}
      {name === "sidebars" ? (
        <path fill="currentColor" stroke="none" d="M2.6 3h2.6v10H2.6zM10.8 3H13.4v10h-2.6z" />
      ) : null}
      {name === "fullscreen" ? (
        <path {...stroke} d="M3 6.2V3h3.2M13 6.2V3h-3.2M3 9.8V13h3.2M13 9.8V13h-3.2" />
      ) : null}
      {name === "fullscreenExit" ? (
        <path {...stroke} d="M6.2 3v3.2H3M9.8 3v3.2H13M6.2 13v-3.2H3M9.8 13v-3.2H13" />
      ) : null}
    </svg>
  );
}

function RaidMapFullscreenButton() {
  const { fullscreen, toggle } = useContext(TarkovMapFullscreenRootContext);
  if (!mapFullscreenEnabled()) return null;
  return (
    <button
      type="button"
      className={styles.dockIcon}
      aria-pressed={fullscreen}
      aria-label={fullscreen ? "退出全屏" : "全屏"}
      title={fullscreen ? "退出全屏" : "全屏"}
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        toggle();
      }}
    >
      <DrawToolIcon name={fullscreen ? "fullscreenExit" : "fullscreen"} />
    </button>
  );
}

export function TarkovRaidRoomPanel({ publicId }: { publicId: string }) {
  const gameMode = useTarkovGameMode();
  const { faction } = useTarkovPmcFaction();
  const navigate = useNavigate();
  const token = Boolean(useAuthStore((s) => s.user));
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
  const [wsStopReason, setWsStopReason] = useState("");
  const hidden = useDocumentHidden();
  const [logPhases, setLogPhases] = useState<RaidRoomLogPhase[]>([]);
  const lastLogMapId = useTarkovLastLogMapId();
  const lastLogPhase = useTarkovLastLogPhase();
  const logSync = useTarkovLogSyncDialog();
  const lastLogPhaseSigRef = useRef("");
  const autoClaimKeyRef = useRef("");
  const [error, setError] = useState("");
  const [guideOpen, setGuideOpen] = useState(false);
  const [guideTaskId, setGuideTaskId] = useState("");
  const [ocrOpen, setOcrOpen] = useState(false);
  const [highlightTaskId, setHighlightTaskId] = useState("");
  const [dockOpen, setDockOpen] = useTarkovRaidDockOpen();
  const [sidebarsOpen, setSidebarsOpen] = useState(true);
  const [statsOpen, setStatsOpen] = useState(false);
  const [viewMapId, setViewMapId] = useState(() => readRaidRoomViewMap(publicId));
  const [pickingMap, setPickingMap] = useState(false);
  const [manageOpen, setManageOpen] = useState(false);
  const [joinPassword, setJoinPassword] = useState("");
  const [focusRequest, setFocusRequest] = useState<TarkovMapFocusRequest | null>(
    null,
  );
  const objDoneScope = raidPrepObjectiveDoneScope(viewMapId, gameMode, me?.id);
  const objDoneLegacy = useMemo(
    () => raidPrepObjectiveDoneLegacyScopes(viewMapId, publicId),
    [publicId, viewMapId],
  );
  const [objDone, toggleObjDoneLocal, replaceObjDone] = useRaidPrepObjectiveDone(
    objDoneScope,
    objDoneLegacy,
  );
  const objToggleSeqRef = useRef(0);
  const objSeedKeyRef = useRef("");
  const focusSeqRef = useRef(0);
  const locateIndexRef = useRef<Record<string, number>>({});
  const wsRef = useRef<WebSocket | null>(null);
  const lastProgressKeyRef = useRef("");
  const autoMapSigRef = useRef("");
  const accountPhaseSigRef = useRef("");
  const accountPhaseReadyRef = useRef(false);
  const logPhaseRoomRef = useRef("");
  const publishViewSigRef = useRef("");

  const roomQuery = useQuery({
    queryKey: ["guides-tarkov-raid-room", publicId],
    queryFn: () => fetchTarkovRaidRoom(publicId),
    retry: 1,
    refetchInterval: (query) =>
      query.state.data?.is_member && !wsLive
        ? visibleRefetchInterval(30_000, hidden)
        : false,
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

  const mapId = viewMapId;
  const canEdit = Boolean(room?.is_member && mapId);
  const mapIdRef = useRef(mapId);
  mapIdRef.current = mapId;
  useEffect(() => {
    setViewMapId(readRaidRoomViewMap(publicId));
    setPendingMarks([]);
  }, [publicId]);
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
  const dockMapId = showOverlap ? defaultDockMapId : mapId;
  const canClaimOnDock = Boolean(canEdit && mapId && dockMapId === mapId);
  const canEditRef = useRef(canEdit);
  canEditRef.current = canEdit;
  const roomObjDonesRef = useRef(room?.objective_dones);
  roomObjDonesRef.current = room?.objective_dones;

  /* 只跟 token / 房间身份重连，快照更新不要拆掉 WS */
  const isMember = Boolean(roomQuery.data?.is_member || room?.is_member);
  useEffect(() => {
    if (!token || !publicId || !isMember) {
      return undefined;
    }
    let stopped = false;
    let retry = 0;
    let ws: WebSocket | null = null;
    let ping = 0;
    let retryTimer = 0;

    useRaidRoomLiveStore.getState().bind(publicId);

    const connect = () => {
      if (stopped) return;
      ws = new WebSocket(tarkovRaidRoomWsUrl(publicId));
      wsRef.current = ws;
      ws.onopen = () => {
        retry = 0;
        ws?.send(
          JSON.stringify({
            event: "auth",
            client: raidRoomSocketClient(isAssistantEmbed()),
          }),
        );
      };
      ws.onmessage = (event) => {
        let payload: RaidRoomWsEvent<TarkovRaidRoomDetail> & {
          user_id?: number;
          floor?: string;
          points?: unknown;
          x?: unknown;
          y?: unknown;
          z?: unknown;
          yaw?: unknown;
          map_id?: unknown;
          map_slug?: unknown;
          file_name?: unknown;
          at?: unknown;
          log_phases?: unknown;
          player_fixes?: unknown;
        };
        try {
          payload = JSON.parse(String(event.data || ""));
        } catch {
          return;
        }
        if (payload.event === "snapshot") {
          setWsLive(true);
          setWsGen((n) => n + 1);
          logPhaseRoomRef.current = publicId;
          setLogPhases(parseRaidRoomLogPhases(payload.log_phases));
          const store = useRaidRoomLiveStore.getState();
          store.bind(publicId);
          for (const fix of parsePlayerFixEvents(payload.player_fixes)) {
            if (playerFixIsFresh(fix.at)) store.upsertFix(fix);
          }
          if (payload.online_user_ids) {
            store.dropFixesNotIn(new Set(payload.online_user_ids));
          }
          if (ws?.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ event: "ping" }));
            const mine = mapIdRef.current;
            if (mine) {
              ws.send(JSON.stringify({ event: "view_map", map_id: mine }));
            }
          }
        }
        if (payload.event === "log_phase") {
          logPhaseRoomRef.current = publicId;
          setLogPhases(parseRaidRoomLogPhases(payload.log_phases));
        }
        if (payload.event === "player_fix") {
          const parsed = parsePlayerFixEvent(payload);
          if (!parsed || !playerFixIsFresh(parsed.at)) return;
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
                  mapId: String(payload.map_id || ""),
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
          const cleared = String(payload.map_slug || "");
          if (cleared) {
            useRaidRoomLiveStore.getState().dropDraftsOnMap(cleared);
            if (
              mapIdRef.current &&
              raidPrepMapsEquivalent(cleared, mapIdRef.current)
            ) {
              setPendingMarks([]);
            }
          } else {
            useRaidRoomLiveStore.getState().clearDrafts();
            setPendingMarks([]);
          }
        }
        if (payload.event === "reset") {
          navigate(TARKOV_HOME_PATH);
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
      ws.onclose = (event) => {
        setWsLive(false);
        if (stopped) return;
        void refetchRoomRef.current();
        const reason = raidRoomWsCloseReason(event.code);
        if (reason) {
          setWsStopReason(reason);
          return;
        }
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
      setWsStopReason("");
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [token, publicId, isMember, navigate]);

  useEffect(() => {
    lastLogPhaseSigRef.current = "";
    accountPhaseSigRef.current = "";
    accountPhaseReadyRef.current = false;
    logPhaseRoomRef.current = "";
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
    enabled: Boolean(me),
  });
  const stateQuery = useQuery({
    queryKey: ["guides-tarkov-raid-prep-state", gameMode, mapId],
    queryFn: () => fetchTarkovRaidPrepState(mapId),
    enabled: Boolean(mapId && me),
    staleTime: 30_000,
  });
  const doneTaskIds = useMemo(() => {
    void progressTick;
    return resolveAccountTaskProgress(taskDonesQuery.data, gameMode).done;
  }, [gameMode, progressTick, taskDonesQuery.data]);
  const startedTaskIds = useMemo(() => {
    void progressTick;
    return resolveAccountTaskProgress(taskDonesQuery.data, gameMode).started;
  }, [gameMode, progressTick, taskDonesQuery.data]);
  const objDoneView = useMemo(() => {
    void progressTick;
    return raidPrepSkipMapForViewer(
      objDone,
      resolveAccountTaskProgress(taskDonesQuery.data, gameMode).objectives,
    );
  }, [gameMode, objDone, progressTick, taskDonesQuery.data]);

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
  const runQuiet = useCallback(
    async (action: () => Promise<TarkovRaidRoomDetail>) => {
      try {
        applyRoom(await action());
        return true;
      } catch {
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
    onSuccess: () => navigate(TARKOV_HOME_PATH),
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
  const onMapTaskIds = useMemo(
    () => (prepQuery.isSuccess ? raidPrepOnMapTaskIds(catalog) : null),
    [catalog, prepQuery.isSuccess],
  );
  const mapCapTaskIds = useMemo(
    () =>
      raidRoomTasksCountingTowardMapCap(
        groups.map((row) => row.taskId),
        onMapTaskIds,
      ),
    [groups, onMapTaskIds],
  );
  const myMapClaimIds = useMemo(
    () => raidRoomTasksCountingTowardMapCap(myClaimIds, onMapTaskIds),
    [myClaimIds, onMapTaskIds],
  );
  const catalogRich = useMemo(
    () => hydrateRaidPrepCatalogRows(catalog, geometry.byId),
    [catalog, geometry.byId],
  );
  const selectedTasks = useMemo(
    () =>
      filterRaidPrepRows(
        selectedTasksFromCatalog(
          catalogRich,
          groups.map((row) => row.taskId),
        ),
        { faction },
      ),
    [catalogRich, faction, groups],
  );
  const guideTasks = useMemo(
    () => mergeRaidPrepGuideTasks(selectedTasks, catalogRich, guideTaskId),
    [catalogRich, guideTaskId, selectedTasks],
  );
  const overlayTasks = geometry.items;
  const rows = useMemo(
    () =>
      filterRaidPrepRows(catalogRich, { q: query, faction }),
    [catalogRich, faction, query],
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
      const task = catalogRich.find((row) => row.id === taskId);
      const fillIds =
        status === "done" && task ? raidPrepAllObjectiveIds(task) : undefined;
      const prev = {
        done: loadTaskDoneIds(gameMode),
        started: loadTaskStartedIds(gameMode),
        failed: loadTaskFailedIds(gameMode),
      };
      const next = commitTaskStatus(
        gameMode,
        taskId,
        status,
        fillIds,
        task?.mutex_ids,
        catalogRich,
      );
      queryClient.setQueryData(
        ["guides-tarkov-task-dones", gameMode],
        taskProgressQueryData(
          next.done,
          next.started,
          next.objectives,
          next.failed,
        ),
      );
      void writeTaskProgressLedger(
        {
          done: next.done,
          started: next.started,
          failed: next.failed,
          objectives: next.objectives,
        },
        prev,
      ).catch(() => {});
    },
    [catalogRich, doneTaskIds, gameMode, queryClient, startedTaskIds],
  );
  const overlayTasksRef = useRef(overlayTasks);
  overlayTasksRef.current = overlayTasks;
  const overlays = useMemo(
    () => buildRaidPrepOverlays(overlayTasks, mapId),
    [overlayTasks, mapId],
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
      if (detail.objectives?.length) {
        const local = readRaidPrepObjectiveDoneWithLegacy(
          objDoneScope,
          objDoneLegacy,
        );
        const merged = mergeRaidPrepSkipMaps(
          local,
          objectivePairsToSkipMap(detail.objectives),
        );
        if (!raidPrepSkipMapsEqual(local, merged)) replaceObjDone(merged);
      }
      if (!canEdit) return;
      const settled = settleRaidPrepSelection({
        selectedIds: myClaimIds,
        completedIds: detail.completedIds?.length
          ? detail.completedIds
          : detail.done,
      });
      for (const id of settled.removedIds) {
        void runQuiet(() => unclaimTarkovRaidRoomTask(publicId, id));
      }
    };
    window.addEventListener(TARKOV_TASK_PROGRESS_EVENT, onProgress);
    return () =>
      window.removeEventListener(TARKOV_TASK_PROGRESS_EVENT, onProgress);
  }, [
    canEdit,
    flushCompletedTaskMarks,
    gameMode,
    myClaimIds,
    objDoneLegacy,
    objDoneScope,
    publicId,
    replaceObjDone,
    runQuiet,
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
  const title =
    (room?.title || "").trim() ||
    (room?.host_display_name || "").trim() ||
    "房间";
  const members = useMemo(
    () =>
      room?.occupants?.length
        ? room.occupants
        : (room?.members || []).filter((row) => row.in_room !== false),
    [room?.occupants, room?.members],
  );
  const seatedActing = useMemo(() => {
    const fromMembers = (room?.members || []).filter((row) => row.in_room !== false);
    const rows = fromMembers.length ? fromMembers : members;
    return rows.map((row) => {
      if (row.user_id !== me?.id) return row;
      return {
        ...row,
        online: Boolean(row.online || wsLive),
        clients: mergeLocalPresenceClient(
          row.clients,
          wsLive,
          raidRoomSocketClient(isAssistantEmbed()),
        ),
      };
    });
  }, [members, me?.id, room?.members, wsLive]);
  const displayLogPhases = useMemo(
    () => overlayRaidRoomLocalPhase(logPhases, me?.id, lastLogPhase),
    [lastLogPhase, logPhases, me?.id],
  );
  const phaseByUser = useMemo(() => {
    const map = new Map<number, RaidRoomLogPhase>();
    for (const row of displayLogPhases) map.set(row.userId, row);
    return map;
  }, [displayLogPhases]);
  const hideLocalFix = shouldSuppressLocalPlayerFix({
    viewMapId: mapId,
    logMapId: lastLogPhase?.mapId || lastLogMapId,
    phaseKind: lastLogPhase?.kind,
  });

  const askChangeMap = () => {
    setStatsOpen(true);
  };

  const pickOwnMap = useCallback((nextMap: string) => {
    const slug = normalizeRaidPrepMapId(nextMap);
    if (!slug || pickingMap) return;
    if (mapId && raidPrepMapsEquivalent(slug, mapId)) {
      setStatsOpen(false);
      return;
    }
    setPickingMap(true);
    writeRaidRoomViewMap(publicId, slug);
    setViewMapId(slug);
    setPendingMarks([]);
    void run(() => setTarkovRaidRoomMap(publicId, slug)).finally(() => {
      setPickingMap(false);
      setStatsOpen(false);
    });
  }, [mapId, pickingMap, publicId, run]);

  const serverViewMap = raidRoomViewerMapSlug(room?.view_maps, me?.id);
  useEffect(() => {
    if (!room?.is_member) return;
    if (!serverViewMap) {
      if (!mapId) return;
      const sig = `publish:${publicId}:${mapId}`;
      if (publishViewSigRef.current === sig) return;
      publishViewSigRef.current = sig;
      void run(() => setTarkovRaidRoomMap(publicId, mapId));
      return;
    }
    if (!mapId || raidPrepMapsEquivalent(serverViewMap, mapId)) return;
    const slug = normalizeRaidPrepMapId(serverViewMap) || serverViewMap;
    writeRaidRoomViewMap(publicId, slug);
    setViewMapId(slug);
  }, [mapId, publicId, room?.is_member, run, serverViewMap]);
  useEffect(() => {
    if (!room?.is_member || !me?.id || logPhaseRoomRef.current !== publicId) return;
    const mine = logPhases.find((row) => row.userId === me.id);
    if (!mine) return;
    const kind = (mine.kind || "").trim();
    const mapSlug = normalizeRaidPrepMapId(mine.mapId || "");
    const sig = `${publicId}:${kind}:${mapSlug}:${mine.raidId || ""}`;
    const changed = accountPhaseReadyRef.current && accountPhaseSigRef.current !== sig;
    const first = !accountPhaseReadyRef.current;
    accountPhaseSigRef.current = sig;
    accountPhaseReadyRef.current = true;
    const entered = kind === "match_found" || kind === "raid_starting" || kind === "raid_started";
    const leaving = kind === "raid_exited" || kind === "matching_aborted";
    if ((changed || first) && entered && mapSlug) {
      if (mapIdRef.current && raidPrepMapsEquivalent(mapSlug, mapIdRef.current)) return;
      writeRaidRoomViewMap(publicId, mapSlug);
      setViewMapId(mapSlug);
      return;
    }
    if (changed && leaving && mapIdRef.current) {
      writeRaidRoomViewMap(publicId, "");
      setViewMapId("");
    }
  }, [logPhases, me?.id, publicId, room?.is_member]);

  useEffect(() => {
    autoMapSigRef.current = "";
    autoClaimKeyRef.current = "";
  }, [publicId]);
  useEffect(() => {
    if (!room?.is_member || !isRaidPrepAutoMapKind(lastLogPhase?.kind)) return;
    const next = normalizeRaidPrepMapId(lastLogPhase?.mapId || lastLogMapId || "");
    if (!next || pickingMap) return;
    if (mapIdRef.current && raidPrepMapsEquivalent(next, mapIdRef.current)) return;
    const sig = `${publicId}:${next}:${lastLogPhase?.kind || ""}:${lastLogPhase?.raidId || ""}`;
    if (autoMapSigRef.current === sig) return;
    autoMapSigRef.current = sig;
    pickOwnMap(next);
  }, [
    lastLogMapId,
    lastLogPhase?.kind,
    lastLogPhase?.mapId,
    lastLogPhase?.raidId,
    pickOwnMap,
    pickingMap,
    publicId,
    room?.is_member,
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
      if (
        !mapCapTaskIds.includes(taskId) &&
        mapCapTaskIds.length >= RAID_PREP_MAX_SELECTED
      ) {
        setError(`最多勾选 ${RAID_PREP_MAX_SELECTED} 个任务`);
        return;
      }
      void run(() => claimTarkovRaidRoomTask(publicId, taskId));
    },
    [canClaimOnDock, doneTaskIds, mapCapTaskIds, myClaims, publicId, run, startedTaskIds],
  );

  useEffect(() => {
    if (!canEdit || !mapId || dockMapId !== mapId || !room?.is_member || !prepQuery.isSuccess) return;
    const key = `${publicId}:${mapId}:${gameMode}`;
    if (autoClaimKeyRef.current === key) return;
    // 进房（或换到这张图）只勾一次。之后取消勾选不再按进行中补回。
    autoClaimKeyRef.current = key;
    const plan = planRaidPrepTaskProgressSync({
      catalogIds: raidPrepOnMapTaskIds(catalog),
      selectedIds: myClaimIds,
      startedIds: loadTaskStartedIds(gameMode),
      doneIds: loadTaskDoneIds(gameMode),
      occupiedIds: mapCapTaskIds,
    });
    if (!plan.addedIds.length) return;
    void runQuiet(() => claimTarkovRaidRoomTasks(publicId, plan.addedIds));
  }, [
    canEdit,
    catalog,
    dockMapId,
    gameMode,
    mapCapTaskIds,
    mapId,
    myClaimIds,
    prepQuery.isSuccess,
    publicId,
    room?.is_member,
    runQuiet,
  ]);

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
      const seq = ++objToggleSeqRef.current;
      const plan = planRaidPrepObjectiveToggle({
        localHas: raidPrepSkippedIds(objDone, taskId).has(objectiveId),
        viewHas: raidPrepSkippedIds(objDoneView, taskId).has(objectiveId),
        taskDone: doneTaskIds.includes(taskId),
      });
      if (plan.toggleLocal) toggleObjDoneLocal(taskId, objectiveId);
      const pairs = commitTaskObjective(
        gameMode,
        taskId,
        objectiveId,
        plan.nextChecked,
      );
      const progress = plan.reopenTask
        ? commitTaskStatus(gameMode, taskId, "active", undefined, undefined, catalogRich)
        : {
            done: loadTaskDoneIds(gameMode),
            started: loadTaskStartedIds(gameMode),
            failed: loadTaskFailedIds(gameMode),
            objectives: pairs,
          };
      queryClient.setQueryData(
        ["guides-tarkov-task-dones", gameMode],
        taskProgressQueryData(
          progress.done,
          progress.started,
          progress.objectives,
          progress.failed,
        ),
      );
      const applyServer = (data: {
        task_ids?: string[];
        started_ids?: string[];
        failed_ids?: string[];
        objective_dones?: typeof pairs;
      }) => {
        if (seq !== objToggleSeqRef.current) return;
        queryClient.setQueryData(
          ["guides-tarkov-task-dones", gameMode],
          taskProgressQueryData(
            data.task_ids || loadTaskDoneIds(gameMode),
            data.started_ids || loadTaskStartedIds(gameMode),
            data.objective_dones || pairs,
            data.failed_ids || loadTaskFailedIds(gameMode),
          ),
        );
      };
      void (
        plan.reopenTask
          ? removeTarkovTaskDone(taskId)
              .catch(() => null)
              .then(() => removeTarkovTaskObjectiveDone(taskId, objectiveId))
              .then(applyServer)
          : (plan.nextChecked
              ? addTarkovTaskObjectiveDone(taskId, objectiveId)
              : removeTarkovTaskObjectiveDone(taskId, objectiveId)
            ).then(applyServer)
      ).catch(() => {});
    },
    [
      canEdit,
      catalogRich,
      doneTaskIds,
      gameMode,
      objDone,
      objDoneView,
      queryClient,
      toggleObjDoneLocal,
    ],
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
      ...skipMapToObjectiveDones(objDoneView, {
        userId: me.id,
        name: myName,
      }),
    ];
  }, [me, myName, objDoneView, room?.objective_dones]);

  useEffect(() => {
    if (!mapId || !me) return;
    if (stateQuery.isLoading && !stateQuery.data) return;
    if (taskDonesQuery.isLoading && !taskDonesQuery.data) return;
    const key = `${publicId}:${gameMode}:${mapId}:${me.id}:${taskDonesQuery.dataUpdatedAt}`;
    if (objSeedKeyRef.current === key) return;
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
    taskDonesQuery.data,
    taskDonesQuery.dataUpdatedAt,
    taskDonesQuery.isLoading,
  ]);

  useEffect(() => {
    if (
      !mapId ||
      !me ||
      !objDoneScope ||
      !stateQuery.isSuccess ||
      !prepQuery.isSuccess
    ) {
      return;
    }
    const handle = window.setTimeout(() => {
      void putTarkovRaidPrepState(mapId, {
        selected: stateQuery.data?.selected ?? [],
        objective_dones: clipRaidPrepStateObjectiveDones(
          skipMapToObjectiveDones(objDone, {
            userId: me.id,
            name: myName,
          }).map((row) => ({
            task_id: row.task_id,
            objective_id: row.objective_id,
          })),
          catalog.map((row) => row.id),
        ),
        key_brings: stateQuery.data?.key_brings ?? [],
      }).catch(() => {
        /* 未登录或网络失败时本机勾选仍可用 */
      });
    }, 700);
    return () => window.clearTimeout(handle);
  }, [
    catalog,
    mapId,
    me,
    myName,
    objDone,
    objDoneScope,
    prepQuery.isSuccess,
    stateQuery.data?.key_brings,
    stateQuery.data?.selected,
    stateQuery.isSuccess,
  ]);

  const locateTask = useCallback(
    async (row: (typeof rows)[number]) => {
      let points = resolveRaidPrepLocateTargets(
        overlayTasks.find((item) => item.id === row.id) || row,
        mapId,
        raidPrepSkippedIds(objDoneView, row.id),
      );
      if (!points.length && row.has_map_markers) {
        try {
          const rich = await geometry.ensure(row.id);
          points = rich
            ? resolveRaidPrepLocateTargets(
                rich,
                mapId,
                raidPrepSkippedIds(objDoneView, row.id),
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
    [geometry, mapId, objDoneView, overlayTasks],
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

  const onText = useCallback(
    (mark: { floor: string; x: number; z: number; label: string }) => {
      if (!canEdit) return;
      const label = normalizeMarkLabel(mark.label);
      if (!label) return;
      const tempId = -Date.now();
      setPendingMarks((current) => [
        ...current,
        {
          id: tempId,
          kind: "text",
          floor: mark.floor,
          x: mark.x,
          z: mark.z,
          label,
          author_user_id: me?.id || 0,
          author_display_name: me?.display_name || "",
        },
      ]);
      void (async () => {
        await run(() =>
          addTarkovRaidRoomMark(publicId, {
            kind: "text",
            floor: mark.floor,
            x: mark.x,
            z: mark.z,
            label,
          }),
        );
        setPendingMarks((current) => current.filter((row) => row.id !== tempId));
      })();
    },
    [canEdit, me?.display_name, me?.id, publicId, run],
  );

  const onTextMove = useCallback(
    (mark: { id: number; x: number; z: number }) => {
      if (!canEdit || mark.id <= 0) return;
      const prev = room?.marks?.find((row) => row.id === mark.id);
      if (!prev || prev.kind !== "text") return;
      const back = { x: prev.x, z: prev.z };
      setRoom((current) => {
        if (!current?.marks) return current;
        return {
          ...current,
          marks: current.marks.map((row) =>
            row.id === mark.id ? { ...row, x: mark.x, z: mark.z } : row,
          ),
        };
      });
      void (async () => {
        const ok = await run(() =>
          moveTarkovRaidRoomMark(publicId, mark.id, { x: mark.x, z: mark.z }),
        );
        if (ok) return;
        setRoom((current) => {
          if (!current?.marks) return current;
          return {
            ...current,
            marks: current.marks.map((row) =>
              row.id === mark.id ? { ...row, x: back.x, z: back.z } : row,
            ),
          };
        });
      })();
    },
    [canEdit, publicId, room?.marks, run],
  );

  const onEraseMark = useCallback(
    (markId: number) => {
      if (!canEdit || markId <= 0) return;
      void run(() => removeTarkovRaidRoomMark(publicId, markId));
    },
    [canEdit, publicId, run],
  );

  const boardMarks = useMemo(
    () =>
      mergeBoardMarks(room?.marks || [], pendingMarks).filter((mark) => {
        const slug = (mark.map_slug || "").trim();
        if (!slug || !mapId) return !slug;
        return raidPrepMapsEquivalent(slug, mapId);
      }),
    [mapId, pendingMarks, room?.marks],
  );
  const memberPhases = useMemo(() => {
    const map = new Map<number, { kind?: string | null; online?: boolean }>();
    for (const row of seatedActing) {
      map.set(row.user_id, {
        online: Boolean(row.online),
        kind: phaseByUser.get(row.user_id)?.kind,
      });
    }
    return map;
  }, [phaseByUser, seatedActing]);

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

  const mapPickHint =
    "点一张图，只切换你自己看的地图。方块下面是正在这张图里的人，匹配中会另外标出。";
  const mapBoard = (
    <TarkovRaidRoomOverlapBoard
      members={seatedActing}
      phaseByUser={phaseByUser}
      mapOptions={mapOptions}
      picking={pickingMap}
      currentMapSlug={mapId || undefined}
      onPickMap={room.is_member ? pickOwnMap : undefined}
    />
  );

  return (
    <TarkovRaidWorkspace
      dockOpen={dockOpen}
      sidebarsOpen={sidebarsOpen}
      onToggleDock={
        room.is_member ? () => setDockOpen((open) => !open) : undefined
      }
      picking={showOverlap}
      showDock={room.is_member && !showOverlap}
      belowBar={
        <>
          {!room.is_member ? (
            <Alert
              type="info"
              showIcon
              message="你还不是房间成员"
              description={
                token ? (
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
                ) : (
                  <TarkovLoginPrompt feature="加入房间后才能看棋盘、认领任务和标点" />
                )
              }
            />
          ) : null}
          {error ? <Alert type="error" showIcon message={error} /> : null}
          {room.is_member && wsStopReason ? (
            <Alert type="warning" showIcon message={wsStopReason} />
          ) : null}
        </>
      }
      goonMapId={mapId || undefined}
      map={
        showOverlap ? (
          room.is_member ? (
            <div className={styles.mapPickPane}>
              <p className={styles.mapPickHint}>{mapPickHint}</p>
              {mapBoard}
            </div>
          ) : (
            <div className={catalogCss.status}>加入后可一起准备</div>
          )
        ) : (
          <TarkovRaidSessionMap
            publicId={publicId}
            mapId={mapId}
            detail={mapQuery.data}
            loading={mapQuery.isLoading}
            error={mapQuery.isError ? mapQuery.error : undefined}
            questOverlays={overlays}
            questObjectiveDones={viewerObjectiveDones}
            questSkippedByTask={objDoneView}
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
            showSidebars={sidebarsOpen}
            members={members}
            memberPhases={memberPhases}
            topLeft={
              <TarkovRaidRoomChannelRoster
                title={title}
                meta={
                  <>
                    {mapLabel || "未选地图"}
                    {mapId ? (
                      <TarkovGoonSightingHint mapId={mapId} variant="inline" />
                    ) : null}
                    {" · "}
                    {room.member_count}/{room.max_members}
                  </>
                }
                actions={
                  room.is_member ? (
                    <>
                      <button type="button" onClick={askChangeMap}>
                        更换地图
                      </button>
                      <button
                        type="button"
                        disabled={leaveMut.isPending}
                        onClick={() => leaveMut.mutate()}
                      >
                        {leaveMut.isPending ? "离开中…" : "离开房间"}
                      </button>
                    </>
                  ) : null
                }
                members={seatedActing}
                viewMaps={
                  me?.id && mapId
                    ? [
                        ...(room.view_maps || []).filter(
                          (row) => row.user_id !== me.id,
                        ),
                        { user_id: me.id, map_slug: mapId },
                      ]
                    : room.view_maps
                }
                phaseByUser={phaseByUser}
              />
            }
            wsRef={wsRef}
            wsGen={wsGen}
            onStroke={onStroke}
            onPin={onPin}
            onLine={onLine}
            onText={onText}
            onTextMove={onTextMove}
            onEraseMark={onEraseMark}
            onQuestLabelClick={onQuestLabelClick}
            onQuestCompleteObjective={canEdit ? toggleObjDone : undefined}
            questParticipantsByTask={participantsByTask}
            lockKeyOwns={room?.key_owns}
            lockKeyBrings={room?.key_brings}
            toolbar={
              canEdit ? (
                <div className={styles.drawDock} role="toolbar" aria-label="地图标注">
                  {(
                    [
                      ["pan", "拖拽", "拖拽移动地图"],
                      ["pen", "画笔", "按住拖拽涂鸦，右键或空格拖地图"],
                      ["pin", "钉点", "单击钉一个点，右键拖地图"],
                      ["line", "直线", "点两点连成直线，右键拖地图"],
                      ["text", "文字", "单击输入文字，拖拽已有文字移动，右键拖地图"],
                      ["erase", "橡皮", "点一下擦掉记号，右键拖地图"],
                    ] as const
                  ).map(([mode, label, hint]) => (
                    <button
                      key={mode}
                      type="button"
                      title={hint}
                      aria-label={label}
                      aria-pressed={tool === mode}
                      className={`${styles.dockIcon} ${tool === mode ? styles.dockIconOn : ""}`}
                      onClick={() => setTool(mode)}
                    >
                      <DrawToolIcon name={mode} />
                    </button>
                  ))}
                  <span className={styles.dockDivider} aria-hidden="true" />
                  <button
                    type="button"
                    className={styles.dockIcon}
                    title="撤销自己的上一笔"
                    aria-label="撤销"
                    onClick={() => void run(() => undoTarkovRaidRoomMark(publicId))}
                  >
                    <DrawToolIcon name="undo" />
                  </button>
                  {room.is_host ? (
                    <button
                      type="button"
                      className={styles.dockIcon}
                      title="清掉这张图上的全部记号"
                      aria-label="清板"
                      onClick={() =>
                        void (async () => {
                          const ok = await run(() =>
                            clearTarkovRaidRoomMarks(publicId),
                          );
                          if (ok) setPendingMarks([]);
                        })()
                      }
                    >
                      <DrawToolIcon name="clear" />
                    </button>
                  ) : null}
                  <span className={styles.dockDivider} aria-hidden="true" />
                  <button
                    type="button"
                    className={styles.dockIcon}
                    aria-pressed={sidebarsOpen}
                    aria-label={sidebarsOpen ? "收起侧边栏" : "展开侧边栏"}
                    title={sidebarsOpen ? "收起侧边栏" : "展开侧边栏"}
                    onClick={() => {
                      setSidebarsOpen((open) => {
                        const next = !open;
                        setDockOpen(next);
                        return next;
                      });
                    }}
                  >
                    <DrawToolIcon name="sidebars" />
                  </button>
                  <RaidMapFullscreenButton />
                </div>
              ) : null
            }
          />
        )
      }
      dock={
        <>
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
                <TarkovShotDirButton />
                <TarkovRaidPrepSummary
                  variant="dock"
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
                  skippedByTask={objDoneView}
                  doneTaskIds={doneTaskIds}
                  objectiveDones={viewerObjectiveDones}
                  onToggleObjective={toggleObjDone}
                  onTitle={openGuide}
                />
                <button
                  type="button"
                  className={styles.changeMapBtn}
                  disabled={logSync.listing}
                  title={logSync.title}
                  onClick={() => void logSync.openDialog()}
                >
                  {logSync.label}
                </button>
                {canClaimOnDock ? (
                  <button
                    type="button"
                    className={styles.changeMapBtn}
                    onClick={() => setOcrOpen(true)}
                  >
                    截图识别
                  </button>
                ) : null}
                <TarkovRaidPrepGuideOverview
                  tasks={guideTasks}
                  mapId={mapId}
                  participantsByTask={participantsByTask}
                  skippedByTask={objDoneView}
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
          {/* oxlint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions -- 点列表空白处清高亮只是鼠标便捷操作，行内控件各自可键盘操作 */}
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
                    skipped={raidPrepSkippedIds(objDoneView, row.id)}
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
        </>
      }
    >
      <TarkovRaidPrepOcrModal
        open={ocrOpen}
        onClose={() => setOcrOpen(false)}
        mapSlug={mapId}
        selectedIds={myMapClaimIds}
        maxSelected={
          RAID_PREP_MAX_SELECTED - (mapCapTaskIds.length - myMapClaimIds.length)
        }
        onConfirm={async (ids) => {
          const next = ids.filter((id) => !myClaims.has(id));
          if (!next.length) return;
          await run(() => claimTarkovRaidRoomTasks(publicId, next));
        }}
      />
      <TarkovLogSyncRangeModal
        open={logSync.open}
        sessions={logSync.sessions}
        onCancel={logSync.closeDialog}
        onConfirm={logSync.confirm}
      />
      <Modal
        title="更换地图"
        open={statsOpen}
        onCancel={() => setStatsOpen(false)}
        footer={null}
        width={960}
        destroyOnClose
        classNames={{ body: styles.entryModalBody }}
      >
        <p className={styles.mapPickHint}>{mapPickHint}</p>
        {mapBoard}
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
    </TarkovRaidWorkspace>
  );
}
