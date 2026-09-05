import { useCallback, useEffect, useMemo, useRef } from "react";
import {
  TarkovMapViewer,
  type TarkovMapFocusRequest,
} from "@/components/guides/tarkov/TarkovMapViewer";
import {
  colorForUserId,
  type RaidPrepObjectiveDoneLike,
  type RaidPrepSkipMap,
  type TarkovRaidPrepOverlay,
} from "@/lib/tarkovRaidPrep";
import {
  useTarkovLastLogMapId,
  useTarkovLastLogPhase,
  useTarkovScreenshotFix,
} from "@/lib/useTarkovLiveWatch";
import { useRaidRoomLiveStore } from "@/lib/tarkovRaidRoomLiveStore";
import type { TarkovLockKeyMode } from "@/lib/tarkovMapMarkers";
import {
  playerFixMatchesRoomMap,
  shouldSuppressLocalPlayerFix,
  type RaidRoomKeyBringLike,
  type RaidRoomMarkLike,
  type StrokePoint,
  type TarkovMapDrawMode,
  type TarkovMapPlayerMark,
} from "@/lib/tarkovRaidRooms";
import type { RaidPrepMapParticipant } from "@/lib/tarkovRaidPrep";
import type {
  TarkovMapBoss,
  TarkovMapBtrStop,
  TarkovMapExtract,
  TarkovMapHazard,
  TarkovMapLock,
  TarkovMapLootContainer,
  TarkovMapLootLoose,
  TarkovMapPlace,
  TarkovMapSpawn,
  TarkovMapStationaryWeapon,
  TarkovMapSwitch,
} from "@/api/guidesApi";
import { type ReactNode, type RefObject } from "react";

type MemberLike = {
  user_id: number;
  display_name: string;
};

export type TarkovRaidRoomLiveMapProps = {
  publicId: string;
  mapId: string;
  parentSlug?: string;
  extracts?: TarkovMapExtract[];
  bosses?: TarkovMapBoss[];
  spawns?: TarkovMapSpawn[];
  locks?: TarkovMapLock[];
  hazards?: TarkovMapHazard[];
  switches?: TarkovMapSwitch[];
  stationaryWeapons?: TarkovMapStationaryWeapon[];
  btrStops?: TarkovMapBtrStop[];
  lootContainers?: TarkovMapLootContainer[];
  lootLoose?: TarkovMapLootLoose[];
  places?: TarkovMapPlace[];
  questOverlays: TarkovRaidPrepOverlay[];
  questObjectiveDones?: readonly RaidPrepObjectiveDoneLike[] | null;
  questSkippedByTask?: RaidPrepSkipMap;
  focusRequest: TarkovMapFocusRequest | null;
  highlightTaskId: string;
  boardMarks?: RaidRoomMarkLike[];
  suppressLocalFix: boolean;
  authorUserId: number;
  authorDisplayName?: string;
  drawMode?: TarkovMapDrawMode;
  canEdit?: boolean;
  members?: readonly MemberLike[];
  wsRef?: RefObject<WebSocket | null>;
  wsGen?: number;
  onStroke?: (stroke: { floor: string; points: StrokePoint[] }) => void;
  onPin?: (mark: { floor: string; x: number; z: number }) => void;
  onLine?: (mark: {
    floor: string;
    x: number;
    z: number;
    x2: number;
    z2: number;
  }) => void;
  onEraseMark?: (markId: number) => void;
  onQuestLabelClick: (taskId: string) => void;
  onQuestCompleteObjective?: (taskId: string, objectiveId: string) => void;
  questParticipantsByTask: ReadonlyMap<
    string,
    readonly RaidPrepMapParticipant[]
  >;
  topRight?: ReactNode;
  lockKeyMode?: TarkovLockKeyMode;
  lockKeyOwns?: readonly RaidRoomKeyBringLike[] | null;
  lockKeyBrings?: readonly RaidRoomKeyBringLike[] | null;
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
  const lastLogPhase = useTarkovLastLogPhase();
  const lastSentRef = useRef("");

  useEffect(() => {
    lastSentRef.current = "";
  }, [wsGen]);

  useEffect(() => {
    const ws = wsRef.current;
    if (!canEdit || !fix || !ws || ws.readyState !== WebSocket.OPEN) return;
    if (
      shouldSuppressLocalPlayerFix({
        viewMapId: mapId,
        logMapId: lastLogPhase?.mapId || lastLogMapId,
        phaseKind: lastLogPhase?.kind,
      })
    ) {
      return;
    }
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
        map_id: mapId,
        file_name: fix.fileName,
      }),
    );
  }, [canEdit, fix, lastLogMapId, lastLogPhase, mapId, wsGen, wsRef]);

  return null;
}

export function TarkovRaidRoomLiveMap({
  publicId,
  mapId,
  parentSlug,
  extracts,
  bosses,
  spawns,
  locks,
  hazards,
  switches,
  stationaryWeapons,
  btrStops,
  lootContainers,
  lootLoose,
  places,
  questOverlays,
  questObjectiveDones,
  questSkippedByTask,
  focusRequest,
  highlightTaskId,
  boardMarks = [],
  suppressLocalFix,
  authorUserId,
  authorDisplayName = "",
  drawMode = "pan",
  canEdit = false,
  members = [],
  wsRef,
  wsGen = 0,
  onStroke,
  onPin,
  onLine,
  onEraseMark,
  onQuestLabelClick,
  onQuestCompleteObjective,
  questParticipantsByTask,
  topRight,
  lockKeyMode = "party",
  lockKeyOwns,
  lockKeyBrings,
}: TarkovRaidRoomLiveMapProps) {
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
      const ws = wsRef?.current;
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
      {canEdit && wsRef ? (
        <RaidRoomFixRelay
          canEdit={canEdit}
          mapId={mapId}
          wsRef={wsRef}
          wsGen={wsGen}
        />
      ) : null}
      <TarkovMapViewer
        key={mapId}
        slug={mapId}
        parentSlug={parentSlug}
        extracts={extracts}
        bosses={bosses}
        spawns={spawns}
        locks={locks}
        hazards={hazards}
        switches={switches}
        stationaryWeapons={stationaryWeapons}
        btrStops={btrStops}
        lootContainers={lootContainers}
        lootLoose={lootLoose}
        places={places}
        questOverlays={questOverlays}
        questObjectiveDones={questObjectiveDones}
        questSkippedByTask={questSkippedByTask}
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
        onQuestCompleteObjective={onQuestCompleteObjective}
        questParticipantsByTask={questParticipantsByTask}
        topRight={topRight}
        lockKeyMode={lockKeyMode}
        lockKeyOwns={lockKeyOwns}
        lockKeyBrings={lockKeyBrings}
      />
    </>
  );
}
