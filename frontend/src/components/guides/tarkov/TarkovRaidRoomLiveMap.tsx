import { useCallback, useEffect, useMemo, useRef } from "react";
import {
  TarkovMapViewer,
  type TarkovMapFocusRequest,
} from "@/components/guides/tarkov/TarkovMapViewer";
import type { TarkovRaidPrepOverlay } from "@/lib/tarkovRaidPrep";
import { colorForUserId } from "@/lib/tarkovRaidPrep";
import {
  useTarkovLastLogMapId,
  useTarkovScreenshotFix,
} from "@/lib/tarkovLiveWatchContext";
import { useRaidRoomLiveStore } from "@/lib/tarkovRaidRoomLiveStore";
import {
  playerFixMatchesRoomMap,
  type RaidRoomMarkLike,
  type StrokePoint,
  type TarkovMapDrawMode,
  type TarkovMapPlayerMark,
} from "@/lib/tarkovRaidRooms";
import type { RaidPrepMapParticipant } from "@/lib/tarkovRaidPrep";
import type { TarkovMapBoss, TarkovMapExtract, TarkovMapSpawn } from "@/api/guidesApi";
import { type ReactNode, type RefObject } from "react";

type MemberLike = {
  user_id: number;
  display_name: string;
};

type Props = {
  publicId: string;
  mapId: string;
  parentSlug?: string;
  extracts?: TarkovMapExtract[];
  bosses?: TarkovMapBoss[];
  spawns?: TarkovMapSpawn[];
  questOverlays: TarkovRaidPrepOverlay[];
  focusRequest: TarkovMapFocusRequest | null;
  highlightTaskId: string;
  boardMarks: RaidRoomMarkLike[];
  suppressLocalFix: boolean;
  authorUserId: number;
  authorDisplayName?: string;
  drawMode: TarkovMapDrawMode;
  canEdit: boolean;
  members: readonly MemberLike[];
  wsRef: RefObject<WebSocket | null>;
  wsGen: number;
  onStroke: (stroke: { floor: string; points: StrokePoint[] }) => void;
  onPin: (mark: { floor: string; x: number; z: number }) => void;
  onLine: (mark: {
    floor: string;
    x: number;
    z: number;
    x2: number;
    z2: number;
  }) => void;
  onEraseMark: (markId: number) => void;
  onQuestLabelClick: (taskId: string) => void;
  questParticipantsByTask: ReadonlyMap<
    string,
    readonly RaidPrepMapParticipant[]
  >;
  topRight?: ReactNode;
};

function RaidRoomFixRelay({
  canEdit,
  mapId,
  wsRef,
  wsGen,
}: {
  canEdit: boolean;
  mapId: string;
  wsRef: RefObject<WebSocket | null>;
  wsGen: number;
}) {
  const fix = useTarkovScreenshotFix();
  const lastLogMapId = useTarkovLastLogMapId();
  const lastSentRef = useRef("");

  useEffect(() => {
    lastSentRef.current = "";
  }, [wsGen]);

  useEffect(() => {
    const ws = wsRef.current;
    if (!canEdit || !fix || !ws || ws.readyState !== WebSocket.OPEN) return;
    if (lastLogMapId && !playerFixMatchesRoomMap(lastLogMapId, mapId)) return;
    const sig = `${fix.fileName}:${fix.lastModified}:${mapId}:${wsGen}`;
    if (lastSentRef.current === sig) return;
    lastSentRef.current = sig;
    ws.send(
      JSON.stringify({
        event: "player_fix",
        x: fix.x,
        y: fix.y,
        z: fix.z,
        yaw: fix.yaw,
        map_id: lastLogMapId || mapId,
        file_name: fix.fileName,
      }),
    );
  }, [canEdit, fix, lastLogMapId, mapId, wsGen, wsRef]);

  return null;
}

export function TarkovRaidRoomLiveMap({
  publicId,
  mapId,
  parentSlug,
  extracts,
  bosses,
  spawns,
  questOverlays,
  focusRequest,
  highlightTaskId,
  boardMarks,
  suppressLocalFix,
  authorUserId,
  authorDisplayName = "",
  drawMode,
  canEdit,
  members,
  wsRef,
  wsGen,
  onStroke,
  onPin,
  onLine,
  onEraseMark,
  onQuestLabelClick,
  questParticipantsByTask,
  topRight,
}: Props) {
  const drafts = useRaidRoomLiveStore((state) => state.drafts);
  const fixes = useRaidRoomLiveStore((state) => state.fixes);

  useEffect(() => {
    useRaidRoomLiveStore.getState().bind(publicId);
  }, [publicId]);

  useEffect(() => {
    useRaidRoomLiveStore.getState().filterMap(mapId);
  }, [mapId]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      useRaidRoomLiveStore.getState().pruneFixes();
    }, 15_000);
    return () => window.clearInterval(timer);
  }, []);

  const selfName = useMemo(() => {
    const fromProp = (authorDisplayName || "").trim();
    if (fromProp) return fromProp;
    const fromMembers = members.find((row) => row.user_id === authorUserId);
    return (fromMembers?.display_name || "").trim();
  }, [authorDisplayName, authorUserId, members]);
  const remotePlayerMarks = useMemo<TarkovMapPlayerMark[]>(() => {
    const names = new Map<number, string>();
    for (const row of members) {
      names.set(row.user_id, row.display_name);
    }
    return fixes
      .filter((row) => playerFixMatchesRoomMap(row.mapId, mapId))
      .map((row) => ({
        key: `u:${row.userId}:${row.fileName || row.at}`,
        userId: row.userId,
        name:
          (row.userId === authorUserId ? selfName : "") ||
          names.get(row.userId) ||
          "",
        color: colorForUserId(row.userId),
        x: row.x,
        y: row.y,
        z: row.z,
        yaw: row.yaw,
      }));
  }, [authorUserId, fixes, mapId, members, selfName]);

  const onDraftStroke = useCallback(
    (draft: { floor: string; points: StrokePoint[] } | null) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      ws.send(
        JSON.stringify({
          event: "draw_draft",
          floor: draft?.floor || "",
          points: (draft?.points || []).map((point) => [point.x, point.z]),
        }),
      );
    },
    [wsRef],
  );

  return (
    <>
      <RaidRoomFixRelay
        canEdit={canEdit}
        mapId={mapId}
        wsRef={wsRef}
        wsGen={wsGen}
      />
      <TarkovMapViewer
        slug={mapId}
        parentSlug={parentSlug}
        extracts={extracts}
        bosses={bosses}
        spawns={spawns}
        questOverlays={questOverlays}
        focusRequest={focusRequest}
        highlightTaskId={highlightTaskId}
        boardMarks={boardMarks}
        remoteDrafts={drafts}
        remotePlayerFixes={remotePlayerMarks}
        suppressLocalFix={suppressLocalFix}
        drawColor={colorForUserId(authorUserId)}
        authorUserId={authorUserId}
        authorDisplayName={selfName}
        drawMode={drawMode}
        onStroke={onStroke}
        onPin={onPin}
        onLine={onLine}
        onDraftStroke={onDraftStroke}
        onEraseMark={onEraseMark}
        fill
        onQuestLabelClick={onQuestLabelClick}
        questParticipantsByTask={questParticipantsByTask}
        topRight={topRight}
      />
    </>
  );
}
