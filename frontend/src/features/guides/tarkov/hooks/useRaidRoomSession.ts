import { useEffect, useRef, useState, type RefObject } from "react";
import { useNavigate } from "react-router-dom";
import { tarkovRaidRoomWsUrl, type TarkovRaidRoomDetail } from "@/features/guides/tarkov/api/guidesApi";
import { isAssistantEmbed } from "@/shared/lib/assistantShell";
import { TARKOV_HOME_PATH, TARKOV_RAID_PREP_PATH } from "@/features/guides/tarkov/model/tarkovHomeNav";
import {
  applyRoomWsEvent,
  colorForUserId,
  parsePlayerFixEvent,
  parsePlayerFixEvents,
  parseRaidRoomLogPhases,
  parseStrokePoints,
  playerFixIsFresh,
  RAID_ROOM_WS_PING_MS,
  raidRoomLogPhaseSig,
  raidRoomSocketClient,
  raidRoomWsCloseReason,
  raidRoomWsRetryDelayMs,
  type RaidRoomLogPhase,
  type RaidRoomWsEvent,
} from "@/features/guides/tarkov/model/tarkovRaidRooms";
import { raidPrepMapsEquivalent } from "@/features/guides/tarkov/model/tarkovRaidPrep";
import { useRaidRoomLiveStore } from "@/features/guides/tarkov/model/tarkovRaidRoomLiveStore";

/** 房间 WS 帧：房间快照之外还夹带各人实时状态（相位 / 坐标 / 草图）。 */
type RaidRoomSocketPayload = RaidRoomWsEvent<TarkovRaidRoomDetail> & {
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

type RoomSetter = (
  update: (
    current: TarkovRaidRoomDetail | null,
  ) => TarkovRaidRoomDetail | null,
) => void;

type UseRaidRoomSessionOptions = {
  publicId: string;
  /** 有会话才连；未登录时房间页走登录引导。 */
  token: boolean;
  isMember: boolean;
  meId: number | null | undefined;
  /** 读房间快照的 ref：onopen / 重连时把手上的查看图补推给服务端。 */
  mapIdRef: RefObject<string>;
  setRoom: RoomSetter;
  /** 断开后立刻拉一次 HTTP 快照兜底（不靠 WS 恢复）。 */
  refetch: () => void;
  /** 房主清板 / 换图后要丢掉本机还没提交的记号。 */
  clearPendingMarks: () => void;
};


/**
 * 房间 WebSocket 会话：鉴权、心跳、退避重连，以及各事件到本机状态的分发。
 *
 * 只跟 token / 房间身份重连 —— 快照更新不会拆掉连接（否则每次有人动一下画板，
 * 全房间都要重握手）。断开时先 refetch 一次，再由调用方决定怎么提示。
 */
export function useRaidRoomSession({
  publicId,
  token,
  isMember,
  meId,
  mapIdRef,
  setRoom,
  refetch,
  clearPendingMarks,
}: UseRaidRoomSessionOptions): RaidRoomSession {
  const navigate = useNavigate();
  const [wsGen, setWsGen] = useState(0);
  const [wsLive, setWsLive] = useState(false);
  const [wsStopReason, setWsStopReason] = useState("");
  const [logPhases, setLogPhases] = useState<RaidRoomLogPhase[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const logPhaseRoomRef = useRef("");
  const lastLogPhaseSigRef = useRef("");
  const meIdRef = useRef(meId);
  meIdRef.current = meId;
  const refetchRef = useRef(refetch);
  refetchRef.current = refetch;
  const clearPendingMarksRef = useRef(clearPendingMarks);
  clearPendingMarksRef.current = clearPendingMarks;

  useEffect(() => {
    lastLogPhaseSigRef.current = "";
    logPhaseRoomRef.current = "";
    setLogPhases([]);
  }, [publicId]);

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
        let payload: RaidRoomSocketPayload;
        try {
          payload = JSON.parse(String(event.data || ""));
        } catch {
          return;
        }
        handleMessage(payload);
      };
      ws.onclose = (event) => {
        setWsLive(false);
        if (stopped) return;
        void refetchRef.current();
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

    const handleMessage = (payload: RaidRoomSocketPayload) => {
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
            clearPendingMarksRef.current();
          }
        } else {
          useRaidRoomLiveStore.getState().clearDrafts();
          clearPendingMarksRef.current();
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
      setRoom((current) => applyRoomWsEvent(current, payload, meIdRef.current));
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
  }, [token, publicId, isMember, navigate, mapIdRef, setRoom]);

  /** 本机相位广播：同一相位（kind + 局号 + 时间戳 + 连接代次）只发一次。 */
  const sendLogPhase = (phase: RaidRoomLogPhaseInput) => {
    const ws = wsRef.current;
    if (
      !isMember ||
      !phase ||
      !wsLive ||
      !ws ||
      ws.readyState !== WebSocket.OPEN
    ) {
      return;
    }
    const sig = raidRoomLogPhaseSig(phase, wsGen);
    if (lastLogPhaseSigRef.current === sig) return;
    lastLogPhaseSigRef.current = sig;
    ws.send(
      JSON.stringify({
        event: "log_phase",
        kind: phase.kind,
        map_id: phase.mapId,
        map_label: phase.mapLabel,
        raid_id: phase.raidId,
        at: phase.at,
      }),
    );
  };

  return {
    wsRef,
    wsGen,
    wsLive,
    wsStopReason,
    logPhases,
    logPhaseRoomRef,
    sendLogPhase,
  };
}

export type RaidRoomSession = {
  wsRef: RefObject<WebSocket | null>;
  /** 每条 snapshot 帧 +1：相位去重签名用它区分同一相位的两次快照。 */
  wsGen: number;
  wsLive: boolean;
  /** 服务端终态关闭码的提示；空串表示可退避重连。 */
  wsStopReason: string;
  logPhases: RaidRoomLogPhase[];
  /** 本连接内收到过 log_phase / snapshot 的房间号；跨房后不复用相位。 */
  logPhaseRoomRef: RefObject<string>;
  /** 把本机相位广播给房间（有 WS 且已连上时）。 */
  sendLogPhase: (phase: RaidRoomLogPhaseInput) => void;
};

/** 本机相位载荷：服务端不认 userId（那是广播时补的），本机只带这几项。 */
export type RaidRoomLogPhaseInput = Omit<RaidRoomLogPhase, "userId">;
