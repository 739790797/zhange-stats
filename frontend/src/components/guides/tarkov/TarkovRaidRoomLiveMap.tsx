import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  PLAYER_FIX_PULSE_MS,
  PULSE_DEMO_BOTS,
  PULSE_DEMO_TICK_MS,
  buildPlayerFixPulseLines,
  collectPlayerFixMarks,
  detectPlayerFixPulseUpdaters,
  isPulseDemoSession,
  playerFixMatchesRoomMap,
  playerFixPulseLinesEqual,
  pulseDemoFixAt,
  replacePlayerFixPulseLines,
  retainPlayerFixPulseLines,
  shouldSuppressLocalPlayerFix,
  type RaidRoomKeyBringLike,
  type RaidRoomMarkLike,
  type RaidRoomPlayerFixPulseLine,
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
  toolbar?: ReactNode;
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
  toolbar,
  lockKeyMode = "party",
  lockKeyOwns,
  lockKeyBrings,
}: TarkovRaidRoomLiveMapProps) {
  const drafts = useRaidRoomLiveStore((state) => state.drafts);
  const fixes = useRaidRoomLiveStore((state) => state.fixes);
  const shotFix = useTarkovScreenshotFix();
  const lastLogMapId = useTarkovLastLogMapId();
  const lastLogPhase = useTarkovLastLogPhase();
  const [pulseLines, setPulseLines] = useState<RaidRoomPlayerFixPulseLine[]>([]);
  const pulseSeenRef = useRef<Map<number, string> | null>(null);
  const pulsePrimedRef = useRef(false);

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

  useEffect(() => {
    if (!import.meta.env.DEV || !isPulseDemoSession(publicId)) {
      return undefined;
    }
    const store = useRaidRoomLiveStore.getState();
    store.bind(publicId);
    let step = 0;
    for (const bot of PULSE_DEMO_BOTS) {
      const fix = pulseDemoFixAt({ userId: bot.userId, step: 0, mapId });
      if (fix) store.upsertFix(fix);
    }
    const timer = window.setInterval(() => {
      step += 1;
      const bot = PULSE_DEMO_BOTS[step % PULSE_DEMO_BOTS.length];
      if (!bot) return;
      const fix = pulseDemoFixAt({
        userId: bot.userId,
        step,
        mapId,
      });
      if (fix) store.upsertFix(fix);
    }, PULSE_DEMO_TICK_MS);
    return () => window.clearInterval(timer);
  }, [mapId, publicId]);

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

  const hideLocalPulseFix =
    suppressLocalFix ||
    shouldSuppressLocalPlayerFix({
      viewMapId: mapId,
      logMapId: lastLogPhase?.mapId || lastLogMapId,
      phaseKind: lastLogPhase?.kind,
    });
  const localPlayerMark = useMemo<TarkovMapPlayerMark | null>(() => {
    if (hideLocalPulseFix || !shotFix || !authorUserId) return null;
    return {
      key: `self:${shotFix.fileName}:${shotFix.lastModified}`,
      userId: authorUserId,
      name: selfName,
      color: colorForUserId(authorUserId),
      x: shotFix.x,
      y: shotFix.y,
      z: shotFix.z,
      yaw: shotFix.yaw,
      self: true,
    };
  }, [authorUserId, hideLocalPulseFix, selfName, shotFix]);
  const displayedPlayerMarks = useMemo(
    () => collectPlayerFixMarks(remotePlayerMarks, localPlayerMark),
    [localPlayerMark, remotePlayerMarks],
  );
  const seatedUserIds = useMemo(() => {
    const ids = new Set<number>();
    for (const row of members) {
      if (row.user_id > 0) ids.add(row.user_id);
    }
    return ids;
  }, [members]);
  const seatedKey = [...seatedUserIds].sort((a, b) => a - b).join(",");
  const displayedMarksRef = useRef(displayedPlayerMarks);
  displayedMarksRef.current = displayedPlayerMarks;
  const seatedIdsRef = useRef(seatedUserIds);
  seatedIdsRef.current = seatedUserIds;

  useEffect(() => {
    pulseSeenRef.current = null;
    pulsePrimedRef.current = false;
    setPulseLines([]);
  }, [publicId, mapId]);

  useEffect(() => {
    const now = Date.now();
    const seated = seatedIdsRef.current;
    const seatedCount = seated.size;
    const locatedUserIds = new Set(
      displayedPlayerMarks.map((row) => row.userId).filter((id) => id > 0),
    );
    if (!pulsePrimedRef.current) {
      pulsePrimedRef.current = true;
      pulseSeenRef.current = detectPlayerFixPulseUpdaters(
        null,
        displayedPlayerMarks,
      ).next;
      setPulseLines((prev) => {
        const nextLines = retainPlayerFixPulseLines(prev, {
          now,
          seatedCount,
          seatedUserIds: seated,
          locatedUserIds,
        });
        return playerFixPulseLinesEqual(prev, nextLines) ? prev : nextLines;
      });
      return;
    }
    const { updaterIds, next } = detectPlayerFixPulseUpdaters(
      pulseSeenRef.current,
      displayedPlayerMarks,
    );
    pulseSeenRef.current = next;
    setPulseLines((prev) => {
      let lines = retainPlayerFixPulseLines(prev, {
        now,
        seatedCount,
        seatedUserIds: seated,
        locatedUserIds,
      });
      for (const updaterId of updaterIds) {
        lines = replacePlayerFixPulseLines(
          lines,
          buildPlayerFixPulseLines({
            marks: displayedPlayerMarks,
            updaterId,
            now,
            seatedCount,
          }),
          updaterId,
        );
      }
      return playerFixPulseLinesEqual(prev, lines) ? prev : lines;
    });
  }, [displayedPlayerMarks, mapId, publicId, seatedKey]);

  useEffect(() => {
    if (!pulseLines.length) return undefined;
    const now = Date.now();
    const until = Math.max(
      0,
      Math.min(
        ...pulseLines.map((line) => line.bornAt + PLAYER_FIX_PULSE_MS - now),
      ),
    );
    const timer = window.setTimeout(() => {
      const seated = seatedIdsRef.current;
      setPulseLines((prev) => {
        const nextLines = retainPlayerFixPulseLines(prev, {
          now: Date.now(),
          seatedCount: seated.size,
          seatedUserIds: seated,
          locatedUserIds: new Set(
            displayedMarksRef.current
              .map((row) => row.userId)
              .filter((id) => id > 0),
          ),
        });
        return playerFixPulseLinesEqual(prev, nextLines) ? prev : nextLines;
      });
    }, until + 16);
    return () => window.clearTimeout(timer);
  }, [pulseLines]);

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
        playerFixPulseLines={pulseLines}
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
        toolbar={toolbar}
        lockKeyMode={lockKeyMode}
        lockKeyOwns={lockKeyOwns}
        lockKeyBrings={lockKeyBrings}
      />
    </>
  );
}
