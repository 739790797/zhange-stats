import { apiError } from "@/lib/apiError";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  Children,
  type ReactNode,
  type Ref,
} from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { FullscreenExitOutlined, FullscreenOutlined } from "@ant-design/icons";
import { Spin } from "antd";
import {
  TarkovMapFullscreenRootContext,
  exitMapFullscreen,
  mapFullscreenEnabled,
  mapFullscreenTarget,
  mapWrapInFullscreen,
  requestMapFullscreen,
} from "@/lib/tarkovMapFullscreen";
import { useNavigate } from "react-router-dom";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "@/components/guides/tarkov/tarkovFonts.css";
import {
  fetchTarkovMapLoot,
  type TarkovMapBoss,
  type TarkovMapBtrStop,
  type TarkovMapExtract,
  type TarkovMapHazard,
  type TarkovMapLock,
  type TarkovMapLootContainer,
  type TarkovMapLootLoose,
  type TarkovMapSpawn,
  type TarkovMapStationaryWeapon,
  type TarkovMapSwitch,
} from "@/api/guidesApi";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { TarkovMapCanvasMarkerLayer } from "@/lib/tarkovMapCanvasMarkerLayer";
import { isCanvasMarkerEvent } from "@/lib/tarkovMapCanvasMarkers";
import { getBounds, getCRS, getScaledBounds, pos } from "@/lib/tarkovMapCrs";
import {
  isPlaceEditTool,
  placeVisibleOnFloor,
  resolveMapPlaceLabels,
  type TarkovMapPlaceEdit,
  type TarkovMapPlaceLike,
} from "@/lib/tarkovMapPlaceLabels";
import {
  collectRaidPrepQuestFilterPeopleOrSelf,
  colorForTaskId,
  colorForUserId,
  defaultQuestPersonOffKeys,
  filterRaidPrepOverlaysForSelection,
  mapLayerFloorBands,
  nextQuestPeopleParentSelection,
  nextQuestPersonSelection,
  overlayFloorForPoint,
  overlayFloorForSpan,
  raidPrepParticipants,
  raidPrepPersonKey,
  raidPrepQuestPointMenuActions,
  type RaidPrepMapParticipant,
  type RaidPrepObjectiveDoneLike,
  type RaidPrepSkipMap,
  type RaidPrepPoint,
  type TarkovRaidPrepOverlay,
} from "@/lib/tarkovRaidPrep";
import { itemHrefFromTypes } from "@/lib/tarkovItemTypes";
import { attachFallbackImgErrors } from "@/lib/tarkovMapImgFallback";
import { setMarkerOutlineVisible } from "@/lib/tarkovMapMarkerOutlineLayers";
import {
  collectPlayerFixMarks,
  playerFixCameraTarget,
  playerFixFollowSig,
  playerFixMarkerCaption,
  playerFixPulseOpacity,
  type RaidRoomPlayerFixPulseLine,
  type TarkovMapPlayerMark,
  isMapDrawTool,
  isTypingTarget,
  shouldRightButtonPanMap,
  MARK_TEXT_MAX,
  mergeBoardMarks,
  normalizeMarkLabel,
  simplifyStroke,
  strokeFingerprint,
  type RaidRoomDraftStroke,
  type RaidRoomKeyBringLike,
  type RaidRoomMarkLike,
  type StrokePoint,
  type TarkovMapDrawMode,
} from "@/lib/tarkovRaidRooms";
import { MAP_OFF_LEVEL_OPACITY, mapBaseOffLevel } from "@/lib/tarkovMapFloors";
import {
  findInteractiveMap,
  findRasterMap,
  floorLabel,
  type TarkovDevMapLayer,
} from "@/lib/tarkovMapImages";
import {
  pullAccountMapFilters,
  scheduleAccountMapFilters,
} from "@/lib/tarkovMapFilterAccount";
import {
  defaultShownFloorName,
  loadTarkovMapViewerPrefs,
  mapFocusZoom,
  mapLootLayerTogglesVisible,
  overlayFlagsForMode,
  resolveMapFloor,
  resolveMapStyle,
  saveTarkovMapViewerPrefs,
  withExtractKind,
  withHazardKind,
  withLootContainerKind,
  withLootLooseKind,
  withMapFloor,
  withSpawnKind,
  type TarkovMapOverlayMode,
  type TarkovMapViewerPrefs,
} from "@/lib/tarkovMapViewerPrefs";
import {
  allPresentExtractKindsOn,
  anyPresentExtractKindOn,
  extractKindsPresent,
  TARKOV_EXTRACT_KIND_LABELS,
  tarkovExtractIconUrl,
  withExtractKindsForPresent,
} from "@/lib/tarkovMapExtracts";
import {
  filterGroupAllOn,
  filterGroupPartial,
  isFilterGroupCollapsed,
  TARKOV_MAP_FILTER_GROUP_LABELS,
  TARKOV_MAP_FILTER_ITEM_LABELS,
  toggleFilterGroupCollapsed,
  withFilterGroupOn,
  type TarkovMapFilterGroupId,
} from "@/lib/tarkovMapFilterGroups";
import {
  allPresentSpawnKindsOn,
  anyPresentSpawnKindOn,
  spawnKindsPresent,
  TARKOV_SPAWN_KIND_LABELS,
  tarkovSpawnIconUrl,
  withSpawnKindsForPresent,
} from "@/lib/tarkovMapSpawns";
import {
  allPresentKindsOn,
  anyPresentKindOn,
  hazardKindsPresent,
  isHazardKindOn,
  isLootContainerKindOn,
  lootContainerKindLabel,
  lootContainerKindsPresent,
  lootFilterParentOn,
  tarkovBtrIconUrl,
  tarkovContainerIconUrl,
  tarkovHazardIconUrl,
  tarkovHazardKindLabel,
  tarkovLockHref,
  tarkovLockIconUrl,
  tarkovLooseLootIconUrl,
  mapLayerMarkerFloorBands,
  tarkovStationaryIconUrl,
  tarkovSwitchIconUrl,
  withArrivedLootKindsOn,
  withKindsForPresent,
  type TarkovLockKeyMode,
} from "@/lib/tarkovMapMarkers";
import {
  isLootLooseKindOn,
  lootLooseKindLabel,
  lootLooseKindsPresent,
  lootLooseRowVisible,
  tarkovLooseLootKindIconUrl,
} from "@/lib/tarkovMapLootLoose";
import { useTarkovScreenshotPosition } from "@/lib/useTarkovScreenshotPosition";
import floatStyles from "./TarkovMapFloat.module.css";
import styles from "./TarkovMapViewer.module.css";
import {
  type MapRuntime,
  BOARD_PANE,
  PLAYER_PULSE_PANE,
  SVG_BASE_PANE,
} from "./mapViewer/runtime";
import {
  applyBasemapZoomCap,
  attachInteractiveSvg,
  attachInteractiveTiles,
  attachPanPerfGuards,
  attachZoomControl,
  setSvgBakedTextHidden,
  setSvgFloor,
} from "./mapViewer/layers/base";
import {
  addBoardMarks,
  parkLocalStroke,
  renderLocalDraft,
  strokeToMark,
} from "./mapViewer/layers/board";
import {
  addBtrMarkers,
  addExtractMarkers,
  addHazardOutlines,
  collectBossMarkers,
  collectHazardMarkers,
  collectLockMarkers,
  collectLootContainerMarkers,
  collectLootLooseMarkers,
  collectPlayerSpawnMarkers,
  collectStationaryMarkers,
  collectSwitchMarkers,
} from "./mapViewer/layers/markers";
import { addLabelMarkers, addPlaceBoxes } from "./mapViewer/layers/places";
import {
  syncPlayerFixMarkers,
  syncPlayerFixPulseLines,
  syncRemoteDrafts,
} from "./mapViewer/layers/players";
import {
  type QuestClickHandler,
  addQuestLabels,
  isLeafletViewReady,
  addQuestOverlays,
  applyQuestLabelHighlight,
  bindQuestActionPopup,
  leafletLayerMap,
  overlayBubbleHtml,
} from "./mapViewer/layers/quests";

export type TarkovMapFocusRequest = RaidPrepPoint & { seq: number };

type Props = {
  slug: string;
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
  questOverlays?: TarkovRaidPrepOverlay[];
  fill?: boolean;
  /** 左下角放大缩小。联机地图关掉，滚轮仍可缩放。 */
  zoomControl?: boolean;
  className?: string;
  boardMarks?: RaidRoomMarkLike[];
  remoteDrafts?: RaidRoomDraftStroke[];
  remotePlayerFixes?: TarkovMapPlayerMark[];
  playerFixPulseLines?: RaidRoomPlayerFixPulseLine[];
  suppressLocalFix?: boolean;
  drawColor?: string;
  authorUserId?: number;
  authorDisplayName?: string;
  drawMode?: TarkovMapDrawMode;
  onStroke?: (stroke: { floor: string; points: StrokePoint[] }) => void;
  onPin?: (mark: { floor: string; x: number; z: number }) => void;
  onLine?: (mark: {
    floor: string;
    x: number;
    z: number;
    x2: number;
    z2: number;
  }) => void;
  onText?: (mark: { floor: string; x: number; z: number; label: string }) => void;
  onTextMove?: (mark: { id: number; x: number; z: number }) => void;
  /** 文字标记谁能拖；不给 = 都能拖。 */
  canDragTextMark?: (mark: { id: number; author_user_id: number }) => boolean;
  onDraftStroke?: (draft: { floor: string; points: StrokePoint[] } | null) => void;
  onEraseMark?: (markId: number) => void;
  onFloorChange?: (floor: string) => void;
  /** 点击任务点位或名称：打开该任务攻略 */
  onQuestLabelClick?: (taskId: string) => void;
  /** 点击步骤点菜单「已完成该步骤」 */
  onQuestCompleteObjective?: (taskId: string, objectiveId: string) => void;
  /** 任务 id → 参与者，供地图悬浮窗展示 */
  questParticipantsByTask?: ReadonlyMap<string, readonly RaidPrepMapParticipant[]>;
  /** 全员步骤完成；与筛选表勾中的人一起决定还显示哪些点 */
  questObjectiveDones?: readonly RaidPrepObjectiveDoneLike[] | null;
  /** 无人树时回退：当前用户已勾掉的步骤 */
  questSkippedByTask?: RaidPrepSkipMap;
  /** 侧栏任务人：self=默认只勾自己；all=全开（测试房要看到「帮」点） */
  questPeopleStartOn?: "self" | "all";
  highlightTaskId?: string;
  overlayMode?: TarkovMapOverlayMode;
  layerChrome?: "full" | "floors";
  /** 外部请求将地图平移到指定游戏坐标（seq 递增可重复定位同一点） */
  focusRequest?: TarkovMapFocusRequest | null;
  topRight?: ReactNode;
  /** 叠在地图左上角、图层面板下方（房间成员名单等）。 */
  topLeft?: ReactNode;
  /** 叠在地图上的工具条（涂鸦等）；挂在全屏根节点里，全屏时仍可见。 */
  toolbar?: ReactNode;
  /** 收起时隐藏左上角房间卡和图层。 */
  showSidebars?: boolean;
  /** 工具条里已有全屏按钮时，不再画右下角那颗。 */
  hideCornerFullscreen?: boolean;
  /** 库里的自定义地名；有则替换 tarkov.dev / 手写表 */
  places?: TarkovMapPlaceLike[];
  placeEdit?: TarkovMapPlaceEdit;
  lockKeyMode?: TarkovLockKeyMode;
  lockKeyOwns?: readonly RaidRoomKeyBringLike[] | null;
  lockKeyBrings?: readonly RaidRoomKeyBringLike[] | null;
};


const DRAFT_THROTTLE_MS = 48;
const QUEST_LABEL_ZOOM_MS = 80;
/** 列表 props 的缺省值要引用稳定：写成 `= []` 每次渲染都是新数组，依赖它的图层 effect 会每次重建。 */
const EMPTY_LIST = Object.freeze([]) as never[];


function FilterCheckRow({
  checked,
  onChange,
  icon,
  label,
  child,
  inputRef,
}: {
  checked: boolean;
  onChange: () => void;
  icon?: string;
  label: string;
  child?: boolean;
  inputRef?: Ref<HTMLInputElement>;
}) {
  return (
    <label
      className={`${styles.filterRow}${child ? ` ${styles.filterRowChild}` : ""}`}
    >
      <input
        ref={inputRef}
        className={styles.filterCheck}
        type="checkbox"
        checked={checked}
        onChange={onChange}
      />
      {icon ? (
        <img
          className={styles.filterIcon}
          src={icon}
          alt=""
          width={14}
          height={14}
        />
      ) : null}
      <span>{label}</span>
    </label>
  );
}

function FilterCollapsibleGroup({
  groupId,
  label,
  collapsed,
  onToggle,
  header,
  children,
}: {
  groupId: TarkovMapFilterGroupId;
  label: string;
  collapsed: boolean;
  onToggle: (groupId: TarkovMapFilterGroupId) => void;
  header: ReactNode;
  children: ReactNode;
}) {
  const open = !collapsed;
  const childrenId = `tarkov-map-filter-${groupId}`;
  const hasChildren = Children.count(children) > 0;
  return (
    <div className={styles.filterSubgroup}>
      <div className={styles.filterParent}>
        {header}
        {hasChildren ? (
          <button
            type="button"
            className={styles.filterExpand}
            aria-expanded={open}
            aria-controls={childrenId}
            aria-label={open ? `收起${label}` : `展开${label}`}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onToggle(groupId);
            }}
          >
            {open ? "−" : "+"}
          </button>
        ) : null}
      </div>
      {hasChildren && open ? (
        <div id={childrenId} className={styles.filterChildren}>
          {children}
        </div>
      ) : null}
    </div>
  );
}


type MapTextDraft = {
  gen: number;
  floor: string;
  x: number;
  z: number;
  left: number;
  top: number;
};

export function TarkovMapViewer({
  slug,
  parentSlug,
  extracts = EMPTY_LIST,
  bosses = EMPTY_LIST,
  spawns = EMPTY_LIST,
  locks = EMPTY_LIST,
  hazards = EMPTY_LIST,
  switches = EMPTY_LIST,
  stationaryWeapons = EMPTY_LIST,
  btrStops = EMPTY_LIST,
  lootContainers: lootContainersProp = EMPTY_LIST,
  lootLoose: lootLooseProp = EMPTY_LIST,
  questOverlays = EMPTY_LIST,
  fill = false,
  zoomControl = true,
  className = "",
  boardMarks = EMPTY_LIST,
  remoteDrafts = EMPTY_LIST,
  remotePlayerFixes = EMPTY_LIST,
  playerFixPulseLines = EMPTY_LIST,
  suppressLocalFix = false,
  drawColor = "#c8932a",
  authorUserId = 0,
  authorDisplayName = "",
  drawMode = "pan",
  onStroke,
  onPin,
  onLine,
  onText,
  onTextMove,
  canDragTextMark,
  onDraftStroke,
  onEraseMark,
  onFloorChange,
  onQuestLabelClick,
  onQuestCompleteObjective,
  questParticipantsByTask,
  questObjectiveDones,
  questSkippedByTask,
  questPeopleStartOn = "self",
  highlightTaskId = "",
  overlayMode = "all",
  layerChrome = "full",
  focusRequest,
  topRight,
  topLeft,
  toolbar,
  showSidebars = true,
  hideCornerFullscreen = false,
  places = EMPTY_LIST,
  placeEdit,
  lockKeyMode = "neutral",
  lockKeyOwns,
  lockKeyBrings,
}: Props) {
  const interactive = useMemo(
    () => findInteractiveMap(slug, parentSlug),
    [slug, parentSlug],
  );
  const placeLabels = useMemo(
    () => (interactive ? resolveMapPlaceLabels(interactive, places) : []),
    [interactive, places],
  );
  const raster = useMemo(
    () => findRasterMap(slug, parentSlug),
    [slug, parentSlug],
  );
  const mapDivRef = useRef<HTMLDivElement>(null);
  const runtimeRef = useRef<MapRuntime | null>(null);
  const drawModeRef = useRef(drawMode);
  const onStrokeRef = useRef(onStroke);
  const onPinRef = useRef(onPin);
  const onLineRef = useRef(onLine);
  const onTextRef = useRef(onText);
  const onTextMoveRef = useRef(onTextMove);
  const canDragTextMarkRef = useRef(canDragTextMark);
  const textDragGuardRef = useRef(false);
  const lineStartRef = useRef<StrokePoint | null>(null);
  const textInputRef = useRef<HTMLInputElement | null>(null);
  const textDraftRef = useRef<MapTextDraft | null>(null);
  const textDraftGen = useRef(0);
  const commitTextDraftRef = useRef<() => void>(() => {});
  const [textDraft, setTextDraft] = useState<MapTextDraft | null>(null);
  const onDraftStrokeRef = useRef(onDraftStroke);
  const onEraseMarkRef = useRef(onEraseMark);
  const onQuestLabelClickRef = useRef(onQuestLabelClick);
  const onQuestCompleteObjectiveRef = useRef(onQuestCompleteObjective);
  const questSkippedByTaskRef = useRef(questSkippedByTask);
  const placeEditRef = useRef(placeEdit);
  const drawColorRef = useRef(drawColor);
  const authorUserIdRef = useRef(authorUserId);
  const overlaySigRef = useRef("");
  const questLabelSigRef = useRef("");
  const hideBakedTextRef = useRef(false);
  const floorBandsRef = useRef<ReturnType<typeof mapLayerFloorBands>>([]);
  const interactiveKeyRef = useRef("");
  const updatePrefsRef = useRef<
    (
      patch:
        | Partial<TarkovMapViewerPrefs>
        | ((prev: TarkovMapViewerPrefs) => TarkovMapViewerPrefs),
    ) => void
  >(() => {});
  const questsParentRef = useRef<HTMLInputElement>(null);
  const [questPersonOff, setQuestPersonOff] = useState<Set<string>>(
    () => new Set(),
  );
  const questPersonSeededRef = useRef(false);
  const commitStrokeRef = useRef<
    (stroke: { floor: string; points: StrokePoint[] }) => void
  >(() => {});
  const drawingRef = useRef(false);
  const spaceHeldRef = useRef(false);
  const rightPanHeldRef = useRef(false);
  const floorRef = useRef("");
  const styleRef = useRef("");
  const wrapElRef = useRef<HTMLDivElement | null>(null);
  const [overlayRoot, setOverlayRoot] = useState<HTMLElement | null>(null);
  const [mapFullscreen, setMapFullscreen] = useState(false);
  const toggleMapFullscreen = useCallback(() => {
    const wrap = wrapElRef.current;
    if (!wrap) return;
    if (mapWrapInFullscreen(wrap)) void exitMapFullscreen();
    else void requestMapFullscreen(mapFullscreenTarget(wrap));
  }, []);
  const setWrapEl = useCallback((el: HTMLDivElement | null) => {
    wrapElRef.current = el;
    setOverlayRoot(el);
  }, []);
  const shotWatch = useTarkovScreenshotPosition();
  const playerFixSigRef = useRef("");
  const shotResumeOnceRef = useRef(false);
  const [prefs, setPrefs] = useState(loadTarkovMapViewerPrefs);
  const accountFilterEdited = useRef(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(0);
  const [spaceHeld, setSpaceHeld] = useState(false);
  const [rightPanHeld, setRightPanHeld] = useState(false);
  const [optimisticMarks, setOptimisticMarks] = useState<RaidRoomMarkLike[]>([]);
  const prevVisibleKeysRef = useRef<Set<string>>(new Set());
  const prevBoardCountRef = useRef(0);
  const canSvg = Boolean(interactive?.svgPath);
  const canTile = Boolean(interactive?.tilePath);
  const floors = useMemo(
    () =>
      interactive?.layers?.filter((layer) => layer.svgLayer || layer.tilePath) ??
      [],
    [interactive],
  );
  const floorNames = useMemo(
    () => floors.map((layer) => layer.name),
    [floors],
  );
  const style = resolveMapStyle(prefs.style, canSvg, canTile);
  styleRef.current = style;
  const filterPanelOpen = prefs.filterPanelOpen !== false;
  const floor = resolveMapFloor(
    prefs.floorsByMap[interactive?.key || ""],
    floorNames,
    defaultShownFloorName(interactive?.layers),
  );
  const floorBands = useMemo(
    () => mapLayerFloorBands(interactive),
    [interactive],
  );
  const markerFloorBands = useMemo(
    () => (interactive ? mapLayerMarkerFloorBands(interactive) : []),
    [interactive],
  );
  const visiblePlaces = useMemo(
    () =>
      placeLabels.filter((row) =>
        placeVisibleOnFloor(row, floor, floorBands),
      ),
    [placeLabels, floor, floorBands],
  );
  const questPeople = useMemo(
    () =>
      collectRaidPrepQuestFilterPeopleOrSelf(questParticipantsByTask, {
        name: authorDisplayName,
        userId: authorUserId,
      }),
    [questParticipantsByTask, authorDisplayName, authorUserId],
  );
  useEffect(() => {
    if (questPersonSeededRef.current) return;
    if (questPeopleStartOn === "all") {
      questPersonSeededRef.current = true;
      return;
    }
    const off = defaultQuestPersonOffKeys(questPeople, authorUserId);
    if (off == null) return;
    questPersonSeededRef.current = true;
    setQuestPersonOff(new Set(off));
  }, [questPeople, authorUserId, questPeopleStartOn]);
  const questTree = questOverlays.length > 0;
  const selectedQuestKeys = useMemo(() => {
    if (!questTree) return null;
    return new Set(
      questPeople
        .map((person) => raidPrepPersonKey(person))
        .filter((key) => !questPersonOff.has(key)),
    );
  }, [questTree, questPeople, questPersonOff]);
  const displayedQuestOverlays = useMemo(
    () =>
      filterRaidPrepOverlaysForSelection(questOverlays, {
        selectedKeys: selectedQuestKeys,
        participantsByTask: questParticipantsByTask,
        objectiveDones: questObjectiveDones,
        skippedByTask: questSkippedByTask,
        selfUserId: authorUserId,
      }),
    [
      questOverlays,
      questParticipantsByTask,
      questObjectiveDones,
      questSkippedByTask,
      selectedQuestKeys,
      authorUserId,
    ],
  );
  const displayedParticipantsByTask = useMemo(() => {
    if (!questParticipantsByTask || !selectedQuestKeys) {
      return questParticipantsByTask;
    }
    const next = new Map<string, RaidPrepMapParticipant[]>();
    for (const [taskId, people] of questParticipantsByTask) {
      next.set(
        taskId,
        raidPrepParticipants(people).filter((person) =>
          selectedQuestKeys.has(raidPrepPersonKey(person)),
        ),
      );
    }
    return next;
  }, [questParticipantsByTask, selectedQuestKeys]);
  const overlaySig = useMemo(
    () =>
      displayedQuestOverlays
        .map((row) => {
          const people = row.neededBy
            ? raidPrepParticipants(row.neededBy)
            : raidPrepParticipants(
                displayedParticipantsByTask?.get(row.taskId),
              );
          const sig = people
            .map((person) => `${person.userId ?? ""}:${person.name}`)
            .join(",");
          return `${row.key}:${sig}:${row.done ? "1" : "0"}`;
        })
        .join("\0") +
        `\0${floor}\0${onQuestCompleteObjective ? "complete" : ""}`,
    [
      displayedQuestOverlays,
      displayedParticipantsByTask,
      floor,
      onQuestCompleteObjective,
    ],
  );
  const highlightTaskIdRef = useRef(highlightTaskId);
  highlightTaskIdRef.current = highlightTaskId;
  const overlay = overlayFlagsForMode(prefs, overlayMode);
  const {
    extractKinds,
    spawnKinds,
    showLabels,
    showQuests,
    showLocks,
    showHazards,
    showSwitches,
    showStationary,
    showBtrStops,
    showLootContainers,
    showLootLoose,
    hazardKinds,
    lootContainerKinds,
    lootLooseKinds,
  } = overlay;
  const gameMode = useTarkovGameMode();
  const lootQuery = useQuery({
    queryKey: [
      "guides-tarkov-map",
      gameMode,
      slug,
      "loot",
      showLootLoose,
      showLootContainers,
    ],
    queryFn: () =>
      fetchTarkovMapLoot(slug, {
        lootLoose: showLootLoose,
        lootContainers: showLootContainers,
      }),
    enabled:
      Boolean(slug) &&
      overlayMode !== "boss-spawns" &&
      overlayMode !== "locks" &&
      (showLootLoose || showLootContainers),
    staleTime: 60_000,
    placeholderData: keepPreviousData,
    retry: 1,
  });
  const lootContainers = lootQuery.data?.loot_containers ?? lootContainersProp;
  const lootLoose = lootQuery.data?.loot_loose ?? lootLooseProp;
  const navigate = useNavigate();
  const onLockClickRef = useRef<(keyId: string) => void>(() => {});
  onLockClickRef.current = (keyId) => {
    if (isMapDrawTool(drawModeRef.current)) return;
    if (overlayMode === "locks") return;
    navigate(tarkovLockHref(keyId));
  };
  const onLooseClickRef = useRef<(itemId: string, types: string[]) => void>(
    () => {},
  );
  onLooseClickRef.current = (itemId, types) => {
    if (isMapDrawTool(drawModeRef.current)) return;
    navigate(itemHrefFromTypes(itemId, types));
  };
  const showPointLayers = layerChrome !== "floors";
  const extractKindOptions = useMemo(
    () => extractKindsPresent(extracts),
    [extracts],
  );
  const extractsParentOn = allPresentExtractKindsOn(
    extractKinds,
    extractKindOptions,
  );
  const extractsParentPartial =
    !extractsParentOn &&
    anyPresentExtractKindOn(extractKinds, extractKindOptions);
  const extractsParentRef = useRef<HTMLInputElement>(null);
  const spawnKindOptions = useMemo(
    () => spawnKindsPresent({ spawns, bosses }),
    [spawns, bosses],
  );
  const spawnsParentOn = allPresentSpawnKindsOn(spawnKinds, spawnKindOptions);
  const spawnsParentPartial =
    !spawnsParentOn && anyPresentSpawnKindOn(spawnKinds, spawnKindOptions);
  const spawnsParentRef = useRef<HTMLInputElement>(null);
  const hazardKindOptions = useMemo(() => hazardKindsPresent(hazards), [hazards]);
  const hazardsParentOn =
    showHazards && allPresentKindsOn(hazardKinds, hazardKindOptions, true);
  const hazardsParentPartial =
    showHazards &&
    !hazardsParentOn &&
    anyPresentKindOn(hazardKinds, hazardKindOptions, true);
  const hazardsParentRef = useRef<HTMLInputElement>(null);
  const lootKindOptions = useMemo(
    () => lootContainerKindsPresent(lootContainers),
    [lootContainers],
  );
  const lootParentOn = lootFilterParentOn(
    showLootContainers,
    lootKindOptions,
    lootContainerKinds,
  );
  const lootParentPartial =
    lootKindOptions.length > 0 &&
    !lootParentOn &&
    showLootContainers &&
    anyPresentKindOn(lootContainerKinds, lootKindOptions, false);
  const lootParentRef = useRef<HTMLInputElement>(null);
  const looseKindOptions = useMemo(
    () => lootLooseKindsPresent(lootLoose),
    [lootLoose],
  );
  const looseParentOn = lootFilterParentOn(
    showLootLoose,
    looseKindOptions,
    lootLooseKinds,
  );
  const looseParentPartial =
    looseKindOptions.length > 0 &&
    !looseParentOn &&
    showLootLoose &&
    anyPresentKindOn(lootLooseKinds, looseKindOptions, false);
  const looseParentRef = useRef<HTMLInputElement>(null);
  const usableItems = useMemo(() => {
    const items: { key: "showLocks" | "showSwitches" | "showStationary"; on: boolean }[] =
      [];
    if (locks.length) items.push({ key: "showLocks", on: showLocks });
    if (stationaryWeapons.length) {
      items.push({ key: "showStationary", on: showStationary });
    }
    if (switches.length) items.push({ key: "showSwitches", on: showSwitches });
    return items;
  }, [
    locks.length,
    switches.length,
    stationaryWeapons.length,
    showLocks,
    showSwitches,
    showStationary,
  ]);
  const usableParentOn = filterGroupAllOn(usableItems);
  const usableParentPartial = filterGroupPartial(usableItems);
  const usableParentRef = useRef<HTMLInputElement>(null);
  const showLootLayerToggles = mapLootLayerTogglesVisible(overlayMode);
  const hasMapLayerFilters =
    placeLabels.length > 0 ||
    btrStops.length > 0 ||
    extractKindOptions.length > 0 ||
    spawnKindOptions.length > 0 ||
    usableItems.length > 0 ||
    hazardKindOptions.length > 0 ||
    showLootLayerToggles;
  const hasQuestFilters = questOverlays.length > 0;
  const questPeopleOnCount = questTree
    ? questPeople.filter(
        (person) => !questPersonOff.has(raidPrepPersonKey(person)),
      ).length
    : 0;
  const questsParentOn =
    showQuests && (!questTree || questPeopleOnCount === questPeople.length);
  const questsParentPartial =
    Boolean(showQuests && questTree && questPeopleOnCount > 0 && questPeopleOnCount < questPeople.length);
  drawModeRef.current = drawMode;
  onStrokeRef.current = onStroke;
  onPinRef.current = onPin;
  onLineRef.current = onLine;
  onTextRef.current = onText;
  onTextMoveRef.current = onTextMove;
  canDragTextMarkRef.current = canDragTextMark;
  onDraftStrokeRef.current = onDraftStroke;
  const commitTextDraft = () => {
    const draft = textDraftRef.current;
    if (!draft) return;
    const label = normalizeMarkLabel(textInputRef.current?.value || "");
    textDraftGen.current += 1;
    textDraftRef.current = null;
    setTextDraft(null);
    if (!label) return;
    onTextRef.current?.({ floor: draft.floor, x: draft.x, z: draft.z, label });
  };
  commitTextDraftRef.current = commitTextDraft;
  const cancelTextDraft = () => {
    if (!textDraftRef.current) return;
    textDraftGen.current += 1;
    textDraftRef.current = null;
    setTextDraft(null);
  };
  onEraseMarkRef.current = onEraseMark;
  onQuestLabelClickRef.current = onQuestLabelClick;
  onQuestCompleteObjectiveRef.current = onQuestCompleteObjective;
  questSkippedByTaskRef.current = questSkippedByTask;
  placeEditRef.current = placeEdit;
  const placeEditActive = Boolean(placeEdit);
  const placeEditMode = placeEdit?.mode;
  const placeEditSelectedId = placeEdit?.selectedId;
  drawColorRef.current = drawColor;
  authorUserIdRef.current = authorUserId;
  floorRef.current = floor;
  floorBandsRef.current = floorBands;
  interactiveKeyRef.current = interactive?.key || "";
  commitStrokeRef.current = (stroke) => {
    setOptimisticMarks((current) => [
      ...current,
      strokeToMark(stroke, authorUserIdRef.current),
    ]);
    onStrokeRef.current?.(stroke);
  };
  const visibleMarks = useMemo(
    () => mergeBoardMarks(boardMarks, optimisticMarks),
    [boardMarks, optimisticMarks],
  );

  const updatePrefs = useCallback(
    (
      patch:
        | Partial<TarkovMapViewerPrefs>
        | ((prev: TarkovMapViewerPrefs) => TarkovMapViewerPrefs),
    ) => {
      setPrefs((prev) => {
        const next =
          typeof patch === "function" ? patch(prev) : { ...prev, ...patch };
        accountFilterEdited.current = true;
        saveTarkovMapViewerPrefs(next);
        scheduleAccountMapFilters(next);
        return next;
      });
    },
    [],
  );
  updatePrefsRef.current = updatePrefs;
  useEffect(() => {
    let stop = false;
    void pullAccountMapFilters(() => accountFilterEdited.current).then((remote) => {
      if (stop || !remote || accountFilterEdited.current) return;
      setPrefs(remote);
      saveTarkovMapViewerPrefs(remote);
    });
    return () => {
      stop = true;
    };
  }, []);
  const toggleGroupCollapsed = useCallback(
    (key: TarkovMapFilterGroupId) => {
      updatePrefs((prev) => ({
        ...prev,
        filterGroupsCollapsed: toggleFilterGroupCollapsed(
          prev.filterGroupsCollapsed,
          key,
        ),
      }));
    },
    [updatePrefs],
  );
  const groupCollapsed = (key: TarkovMapFilterGroupId) =>
    isFilterGroupCollapsed(prefs.filterGroupsCollapsed, key);

  useEffect(() => {
    const el = extractsParentRef.current;
    if (el) el.indeterminate = extractsParentPartial;
  }, [extractsParentPartial]);

  useEffect(() => {
    const el = spawnsParentRef.current;
    if (el) el.indeterminate = spawnsParentPartial;
  }, [spawnsParentPartial]);

  useEffect(() => {
    const el = questsParentRef.current;
    if (el) el.indeterminate = questsParentPartial;
  }, [questsParentPartial]);

  useEffect(() => {
    const el = hazardsParentRef.current;
    if (el) el.indeterminate = hazardsParentPartial;
  }, [hazardsParentPartial]);

  useEffect(() => {
    const el = lootParentRef.current;
    if (el) el.indeterminate = lootParentPartial;
  }, [lootParentPartial]);

  useEffect(() => {
    const el = looseParentRef.current;
    if (el) el.indeterminate = looseParentPartial;
  }, [looseParentPartial]);

  useEffect(() => {
    if (!prefs.showLootContainers || !lootKindOptions.length) return;
    const next = withArrivedLootKindsOn(
      prefs.lootContainerKinds,
      lootKindOptions,
      true,
    );
    if (next === prefs.lootContainerKinds) return;
    updatePrefs((prev) => ({
      ...prev,
      lootContainerKinds: withArrivedLootKindsOn(
        prev.lootContainerKinds,
        lootKindOptions,
        prev.showLootContainers,
      ),
    }));
  }, [
    lootKindOptions,
    prefs.lootContainerKinds,
    prefs.showLootContainers,
    updatePrefs,
  ]);

  useEffect(() => {
    if (!prefs.showLootLoose || !looseKindOptions.length) return;
    const next = withArrivedLootKindsOn(
      prefs.lootLooseKinds,
      looseKindOptions,
      true,
    );
    if (next === prefs.lootLooseKinds) return;
    updatePrefs((prev) => ({
      ...prev,
      lootLooseKinds: withArrivedLootKindsOn(
        prev.lootLooseKinds,
        looseKindOptions,
        prev.showLootLoose,
      ),
    }));
  }, [
    looseKindOptions,
    prefs.lootLooseKinds,
    prefs.showLootLoose,
    updatePrefs,
  ]);

  useEffect(() => {
    const el = usableParentRef.current;
    if (el) el.indeterminate = usableParentPartial;
  }, [usableParentPartial]);

  useEffect(() => {
    onFloorChange?.(floor);
  }, [floor, onFloorChange]);

  useEffect(() => {
    const el = mapDivRef.current;
    if (!el) return;
    let cancelled = false;
    let detachDraw = () => {};
    const detachImgFallback = attachFallbackImgErrors(el);
    const runtime: MapRuntime = {
      map: null as unknown as L.Map,
      floorTiles: new Map(),
      extracts: L.layerGroup(),
      outlines: L.layerGroup(),
      outlineById: new Map(),
      hoveredOutlineId: null,
      btrStops: L.layerGroup(),
      labels: L.layerGroup(),
      placeBoxes: L.layerGroup(),
      quests: L.layerGroup(),
      questLabels: L.layerGroup(),
      board: L.layerGroup(),
      live: L.layerGroup(),
      mine: L.layerGroup(),
      remote: L.layerGroup(),
      player: L.layerGroup(),
      pulse: L.layerGroup(),
      mineKeys: new Set(),
      strokeLayers: new Map(),
      draftLayers: new Map(),
      playerLayers: new Map(),
      playerIconHtml: new Map(),
      pulseLayers: new Map(),
    };
    runtimeRef.current = runtime;

    const setupInteractive = async (layer: TarkovDevMapLayer) => {
      const bounds = getBounds(layer.bounds);
      if (!bounds) throw new Error("地图缺少 bounds");
      const maxZoom = Math.max(7, layer.maxZoom ?? 5);
      const map = L.map(el, {
        crs: getCRS(layer),
        zoomSnap: 0.1,
        attributionControl: false,
        zoomControl: false,
        minZoom: layer.minZoom ?? 1,
        maxZoom,
      });
      runtime.map = map;
      runtime.tileMaxZoom = maxZoom;
      if (zoomControl) attachZoomControl(map);
      const scaled = getScaledBounds(layer.bounds || [], 1.5);
      if (scaled) map.setMaxBounds(scaled);
      map.createPane(BOARD_PANE);
      const boardPane = map.getPane(BOARD_PANE);
      if (boardPane) {
        boardPane.style.zIndex = "650";
        boardPane.style.pointerEvents = "none";
        runtime.boardPane = boardPane;
      }
      map.createPane(PLAYER_PULSE_PANE);
      const pulsePane = map.getPane(PLAYER_PULSE_PANE);
      if (pulsePane) {
        pulsePane.style.zIndex = "580";
        pulsePane.style.pointerEvents = "none";
      }
      map.createPane(SVG_BASE_PANE);
      const svgPane = map.getPane(SVG_BASE_PANE);
      if (svgPane) {
        svgPane.style.zIndex = "250";
        svgPane.style.pointerEvents = "none";
      }
      const pointers = new Set<number>();
      let strokePoints: StrokePoint[] = [];
      let strokeFloor = "";
      let lastDraftAt = 0;

      const colorOf = () => drawColorRef.current || "#c8932a";
      const emitDraft = (pts: StrokePoint[], force = false) => {
        const now = Date.now();
        if (!force && now - lastDraftAt < DRAFT_THROTTLE_MS) return;
        lastDraftAt = now;
        onDraftStrokeRef.current?.(
          pts.length ? { floor: strokeFloor, points: pts } : null,
        );
      };
      const finishStroke = () => {
        if (!drawingRef.current) return;
        drawingRef.current = false;
        map.dragging.disable();
        const simplified = simplifyStroke(strokePoints);
        strokePoints = [];
        emitDraft([], true);
        if (!simplified.length) {
          runtime.localStroke?.remove();
          runtime.localStroke = undefined;
          return;
        }
        parkLocalStroke(runtime, simplified, colorOf(), strokeFloor);
        commitStrokeRef.current({ floor: strokeFloor, points: simplified });
      };
      const cancelStroke = () => {
        if (!drawingRef.current) return;
        drawingRef.current = false;
        strokePoints = [];
        runtime.localStroke?.remove();
        runtime.localStroke = undefined;
        emitDraft([], true);
      };
      const onPointerDown = (event: PointerEvent) => {
        if (event.pointerType === "mouse" && event.button !== 0) return;
        const target = event.target as HTMLElement | null;
        if (target?.closest(".leaflet-control")) return;
        pointers.add(event.pointerId);
        if (pointers.size > 1) {
          cancelStroke();
          return;
        }
        if (spaceHeldRef.current || rightPanHeldRef.current) return;
        if (drawModeRef.current !== "pen") return;
        if (drawingRef.current) finishStroke();
        if (runtime.localStroke) {
          runtime.live.removeLayer(runtime.localStroke);
          if (!runtime.mine.hasLayer(runtime.localStroke)) {
            runtime.mine.addLayer(runtime.localStroke);
          }
          runtime.localStroke = undefined;
        }
        const latlng = map.mouseEventToLatLng(event as unknown as MouseEvent);
        drawingRef.current = true;
        strokeFloor = floorRef.current;
        strokePoints = [{ x: latlng.lng, z: latlng.lat }];
        map.dragging.disable();
        try {
          map.getContainer().setPointerCapture(event.pointerId);
        } catch {
          /* 部分浏览器对已捕获指针会抛错 */
        }
        renderLocalDraft(runtime, strokePoints, colorOf());
        emitDraft(strokePoints, true);
        event.preventDefault();
        event.stopPropagation();
      };
      const onPointerMove = (event: PointerEvent) => {
        if (!drawingRef.current) return;
        const latlng = map.mouseEventToLatLng(event as unknown as MouseEvent);
        const next = { x: latlng.lng, z: latlng.lat };
        const prev = strokePoints[strokePoints.length - 1];
        if (prev && Math.hypot(next.x - prev.x, next.z - prev.z) < 0.7) return;
        strokePoints.push(next);
        renderLocalDraft(runtime, strokePoints, colorOf());
        emitDraft(strokePoints);
        event.preventDefault();
      };
      const onPointerUp = (event: PointerEvent) => {
        pointers.delete(event.pointerId);
        if (drawingRef.current) finishStroke();
      };
      const container = map.getContainer();
      container.addEventListener("pointerdown", onPointerDown, true);
      container.addEventListener("pointermove", onPointerMove, true);
      window.addEventListener("pointerup", onPointerUp, true);
      window.addEventListener("pointercancel", onPointerUp, true);
      window.addEventListener("lostpointercapture", onPointerUp, true);
      detachDraw = () => {
        container.removeEventListener("pointerdown", onPointerDown, true);
        container.removeEventListener("pointermove", onPointerMove, true);
        window.removeEventListener("pointerup", onPointerUp, true);
        window.removeEventListener("pointercancel", onPointerUp, true);
        window.removeEventListener("lostpointercapture", onPointerUp, true);
      };

      const preferSvg = styleRef.current === "svg";
      if (preferSvg) {
        try {
          await attachInteractiveSvg(runtime, layer, bounds);
        } catch {
          /* 抽象图失败时仍可用瓦片 */
        }
        if (cancelled) return;
        if (!runtime.svgOverlay) attachInteractiveTiles(runtime, layer, bounds, maxZoom);
      } else {
        attachInteractiveTiles(runtime, layer, bounds, maxZoom);
        if (!runtime.tileLayer) {
          try {
            await attachInteractiveSvg(runtime, layer, bounds);
          } catch {
            /* 瓦片失败时再试 SVG */
          }
          if (cancelled) return;
        }
      }
      if (!runtime.tileLayer && !runtime.svgOverlay) {
        throw new Error("没有可用底图");
      }
      if (cancelled) {
        detachDraw();
        return;
      }
      runtime.iconCanvas = new TarkovMapCanvasMarkerLayer({
        tooltipClassName: styles.spawnTooltip,
        onLootItemClick: (itemId, types) => {
          onLooseClickRef.current(itemId, [...types]);
        },
        onHoverId: (id) => {
          const current = runtimeRef.current;
          if (!current) return;
          if (current.hoveredOutlineId) {
            setMarkerOutlineVisible(
              current.outlineById.get(current.hoveredOutlineId),
              false,
            );
          }
          const next = id && current.outlineById.has(id) ? id : null;
          current.hoveredOutlineId = next;
          if (next) {
            setMarkerOutlineVisible(current.outlineById.get(next), true);
          }
        },
      });
      runtime.iconCanvas.addTo(map);
      runtime.outlines.addTo(map);
      runtime.extracts.addTo(map);
      runtime.btrStops.addTo(map);
      runtime.labels.addTo(map);
      runtime.placeBoxes.addTo(map);
      runtime.quests.addTo(map);
      runtime.questLabels.addTo(map);
      runtime.board.addTo(map);
      runtime.mine.addTo(map);
      runtime.live.addTo(map);
      runtime.remote.addTo(map);
      runtime.player.addTo(map);
      runtime.pulse.addTo(map);
      runtime.fitBox = bounds;
      map.fitBounds(bounds, { animate: false });
      const detachPanPerf = attachPanPerfGuards(
        map,
        wrapElRef.current || el.parentElement || el,
      );
      const prevDetachDraw = detachDraw;
      detachDraw = () => {
        detachPanPerf();
        prevDetachDraw();
      };
    };

    const setupRaster = async (url: string) => {
      const img = await new Promise<HTMLImageElement>((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = () => reject(new Error("平面图加载失败"));
        image.src = url;
      });
      if (cancelled) return;
      const map = L.map(el, {
        crs: L.CRS.Simple,
        attributionControl: false,
        zoomControl: false,
        minZoom: -2,
        maxZoom: 3,
      });
      runtime.map = map;
      if (zoomControl) attachZoomControl(map);
      const bounds = L.latLngBounds([0, 0], [img.height, img.width]);
      L.imageOverlay(url, bounds).addTo(map);
      runtime.fitBox = bounds;
      map.fitBounds(bounds, { animate: false });
    };

    setLoading(true);
    setError("");
    const boot = interactive
      ? setupInteractive(interactive)
      : raster
        ? setupRaster(raster.url)
        : Promise.reject(new Error("没有可用底图"));
    boot
      .then(() => {
        if (cancelled) return;
        setLoading(false);
        setReady((value) => value + 1);
      })
      .catch((exc: unknown) => {
        if (cancelled) return;
        setLoading(false);
        setError(apiError(exc, "地图加载失败"));
      });

    return () => {
      cancelled = true;
      detachDraw();
      detachImgFallback();
      runtime.svgRoot?.replaceChildren();
      runtime.svgRoot = undefined;
      runtimeRef.current = null;
      runtime.map?.remove();
    };
  }, [interactive, raster, zoomControl]);

  useEffect(() => {
    const runtime = runtimeRef.current;
    const map = runtime?.map;
    if (!ready || !runtime || !map || !interactive) return undefined;
    const bounds = getBounds(interactive.bounds);
    if (!bounds) return undefined;
    const maxZoom = Math.max(7, interactive.maxZoom ?? 5);
    let cancelled = false;
    const apply = async () => {
      const floorLayer = floors.find((item) => item.name === floor);
      const keepBaseOpaque = floorLayer?.show === true;
      if (style === "svg") {
        if (!runtime.svgOverlay && interactive.svgPath) {
          try {
            await attachInteractiveSvg(runtime, interactive, bounds);
          } catch {
            /* 切到抽象图失败则继续用瓦片 */
          }
          if (cancelled) return;
          setSvgBakedTextHidden(runtime.svgRoot, hideBakedTextRef.current);
        }
        if (runtime.svgOverlay) {
          applyBasemapZoomCap(
            map,
            runtime.svgOverlay.getBounds(),
            runtime.tileMaxZoom ?? maxZoom,
            true,
          );
          runtime.svgOverlay.addTo(map);
          runtime.tileLayer?.remove();
          for (const tile of runtime.floorTiles.values()) tile.remove();
          setSvgFloor(
            runtime.svgRoot,
            interactive.svgLayer || "",
            floorLayer?.svgLayer || "",
            keepBaseOpaque,
          );
          return;
        }
      }
      if (!runtime.tileLayer && interactive.tilePath) {
        attachInteractiveTiles(runtime, interactive, bounds, maxZoom);
      }
      applyBasemapZoomCap(map, bounds, runtime.tileMaxZoom ?? maxZoom, false);
      runtime.svgOverlay?.remove();
      runtime.tileLayer?.addTo(map);
      runtime.tileLayer?.setOpacity(
        mapBaseOffLevel(floor, keepBaseOpaque) ? MAP_OFF_LEVEL_OPACITY : 1,
      );
      for (const [name, tile] of runtime.floorTiles) {
        if (name === floor) tile.addTo(map);
        else tile.remove();
      }
    };
    void apply();
    return () => {
      cancelled = true;
    };
  }, [style, floor, interactive, floors, ready]);

  const handleQuestClick = useCallback<QuestClickHandler>((target) => {
    if (isMapDrawTool(drawModeRef.current)) return false;
    const nextFloor = overlayFloorForSpan(
      target.row.height,
      floorBandsRef.current,
      target.row.at,
    );
    if (nextFloor !== floorRef.current) {
      const mapKey = interactiveKeyRef.current;
      if (mapKey) {
        updatePrefsRef.current((prev) =>
          withMapFloor(prev, mapKey, nextFloor),
        );
      }
      return true;
    }
    const taskId = (target.row.taskId || "").trim();
    if (!taskId) return false;
    const objectiveId = (target.row.objectiveId || "").trim();
    const alreadyDone = Boolean(
      objectiveId &&
        questSkippedByTaskRef.current?.get(taskId)?.has(objectiveId),
    );
    const actions = raidPrepQuestPointMenuActions({
      canOpenGuide: Boolean(onQuestLabelClickRef.current),
      canComplete: Boolean(onQuestCompleteObjectiveRef.current),
      objectiveId: target.row.objectiveId,
      alreadyDone,
    });
    if (!actions.length) return false;
    if (actions.length === 1 && actions[0] === "guide") {
      onQuestLabelClickRef.current?.(taskId);
      return true;
    }
    const map = leafletLayerMap(target.layer);
    if (!map) return false;
    target.layer.closeTooltip();
    bindQuestActionPopup(
      map,
      target.latlng,
      overlayBubbleHtml(target.row, { actions }),
      (action) => {
        if (action === "guide") onQuestLabelClickRef.current?.(taskId);
        if (
          (action === "complete" || action === "uncomplete") &&
          objectiveId
        ) {
          onQuestCompleteObjectiveRef.current?.(taskId, objectiveId);
        }
      },
    );
    return true;
  }, []);

  useEffect(() => {
    const runtime = runtimeRef.current;
    if (!ready || !runtime?.map || !interactive) return;
    runtime.outlines.clearLayers();
    runtime.outlineById.clear();
    runtime.hoveredOutlineId = null;
    if (anyPresentExtractKindOn(extractKinds, extractKindOptions)) {
      addExtractMarkers(
        runtime.extracts,
        extracts,
        extractKinds,
        floor,
        markerFloorBands,
        runtime.outlines,
      );
    } else runtime.extracts.clearLayers();
    if (showHazards) {
      addHazardOutlines(
        runtime.outlines,
        runtime.outlineById,
        hazards,
        (kind) => isHazardKindOn(hazardKinds, kind),
      );
    }
  }, [
    extracts,
    extractKinds,
    extractKindOptions,
    hazards,
    hazardKinds,
    showHazards,
    floor,
    markerFloorBands,
    interactive,
    ready,
  ]);

  const spawnCanvasMarkers = useMemo(
    () =>
      spawnKinds.pmc || spawnKinds.scav || spawnKinds.sniper
        ? collectPlayerSpawnMarkers(spawns, spawnKinds, floor, markerFloorBands)
        : EMPTY_LIST,
    [spawns, spawnKinds, floor, markerFloorBands],
  );
  const bossCanvasMarkers = useMemo(
    () =>
      spawnKinds.boss && interactive
        ? collectBossMarkers(
            bosses,
            floor,
            markerFloorBands,
            interactive.normalizedName || interactive.key,
          )
        : EMPTY_LIST,
    [bosses, spawnKinds.boss, floor, markerFloorBands, interactive],
  );
  const lockCanvasMarkers = useMemo(
    () =>
      showLocks
        ? collectLockMarkers(
            locks,
            floor,
            markerFloorBands,
            (keyId) => onLockClickRef.current(keyId),
            {
              mode: lockKeyMode,
              viewerId: authorUserId || null,
              owns: lockKeyOwns,
              brings: lockKeyBrings,
            },
            overlayMode === "locks",
          )
        : EMPTY_LIST,
    [
      locks,
      showLocks,
      floor,
      markerFloorBands,
      lockKeyMode,
      authorUserId,
      lockKeyOwns,
      lockKeyBrings,
      overlayMode,
    ],
  );
  const hazardCanvasMarkers = useMemo(
    () =>
      showHazards
        ? collectHazardMarkers(
            hazards,
            (kind) => isHazardKindOn(hazardKinds, kind),
            floor,
            markerFloorBands,
          )
        : EMPTY_LIST,
    [hazards, hazardKinds, showHazards, floor, markerFloorBands],
  );
  const switchCanvasMarkers = useMemo(
    () =>
      showSwitches
        ? collectSwitchMarkers(switches, floor, markerFloorBands)
        : EMPTY_LIST,
    [switches, showSwitches, floor, markerFloorBands],
  );
  const stationaryCanvasMarkers = useMemo(
    () =>
      showStationary
        ? collectStationaryMarkers(stationaryWeapons, floor, markerFloorBands)
        : EMPTY_LIST,
    [stationaryWeapons, showStationary, floor, markerFloorBands],
  );
  const lootContainerCanvasMarkers = useMemo(
    () =>
      showLootContainers
        ? collectLootContainerMarkers(
            lootContainers,
            (kind) => isLootContainerKindOn(lootContainerKinds, kind),
            floor,
            markerFloorBands,
          )
        : EMPTY_LIST,
    [
      lootContainers,
      lootContainerKinds,
      showLootContainers,
      floor,
      markerFloorBands,
    ],
  );
  const lootLooseCanvasMarkers = useMemo(
    () =>
      showLootLoose
        ? collectLootLooseMarkers(
            lootLoose,
            floor,
            markerFloorBands,
            (row) => lootLooseRowVisible(row, lootLooseKinds),
            (itemId, types) => onLooseClickRef.current(itemId, types),
          )
        : EMPTY_LIST,
    [lootLoose, lootLooseKinds, showLootLoose, floor, markerFloorBands],
  );

  useEffect(() => {
    const runtime = runtimeRef.current;
    if (!ready || !runtime?.map || !interactive) return;
    runtime.iconCanvas?.setMarkers([
      ...spawnCanvasMarkers,
      ...bossCanvasMarkers,
      ...lockCanvasMarkers,
      ...hazardCanvasMarkers,
      ...switchCanvasMarkers,
      ...stationaryCanvasMarkers,
      ...lootContainerCanvasMarkers,
      ...lootLooseCanvasMarkers,
    ]);
  }, [
    spawnCanvasMarkers,
    bossCanvasMarkers,
    lockCanvasMarkers,
    hazardCanvasMarkers,
    switchCanvasMarkers,
    stationaryCanvasMarkers,
    lootContainerCanvasMarkers,
    lootLooseCanvasMarkers,
    interactive,
    ready,
  ]);

  useEffect(() => {
    const runtime = runtimeRef.current;
    if (!ready || !runtime?.map || !interactive) return;
    if (showBtrStops) {
      addBtrMarkers(runtime.btrStops, btrStops, floor, markerFloorBands);
    } else runtime.btrStops.clearLayers();
  }, [btrStops, showBtrStops, floor, markerFloorBands, interactive, ready]);

  const showPlaceLayer = showLabels || placeEditActive;
  const hideBakedText = showPlaceLayer && visiblePlaces.length > 0;
  hideBakedTextRef.current = hideBakedText;
  useEffect(() => {
    const runtime = runtimeRef.current;
    if (!ready || !runtime?.map || !interactive) return;
    if (showPlaceLayer) {
      const edit = {
        mode: placeEditMode ?? "off",
        selectedId: placeEditSelectedId,
        onSelect: (id: number) => placeEditRef.current?.onSelect?.(id),
        onMove: (id: number, at: { x: number; z: number }) =>
          placeEditRef.current?.onMove?.(id, at),
        onPoint: (pt: { x: number; z: number; floor: string }) =>
          placeEditRef.current?.onPoint?.(pt),
        onBox: (box: {
          x: number;
          z: number;
          x2: number;
          z2: number;
          floor: string;
        }) => placeEditRef.current?.onBox?.(box),
      } satisfies TarkovMapPlaceEdit;
      addLabelMarkers(
        runtime.labels,
        visiblePlaces,
        placeEditActive ? edit : undefined,
      );
      addPlaceBoxes(
        runtime.placeBoxes,
        visiblePlaces,
        placeEditActive ? edit : undefined,
      );
    } else {
      runtime.labels.clearLayers();
      runtime.placeBoxes.clearLayers();
    }
    setSvgBakedTextHidden(runtime.svgRoot, hideBakedText);
  }, [
    showPlaceLayer,
    hideBakedText,
    visiblePlaces,
    placeEditActive,
    placeEditMode,
    placeEditSelectedId,
    interactive,
    ready,
  ]);

  useEffect(() => {
    const runtime = runtimeRef.current;
    if (!ready || !runtime?.map) return;
    if (!showQuests) {
      overlaySigRef.current = "";
      runtime.quests.clearLayers();
      return;
    }
    if (overlaySigRef.current === overlaySig) return;
    overlaySigRef.current = overlaySig;
    addQuestOverlays(
      runtime.quests,
      displayedQuestOverlays,
      displayedParticipantsByTask,
      handleQuestClick,
      floor,
      floorBands,
      Boolean(onQuestCompleteObjective),
    );
  }, [
    overlaySig,
    displayedQuestOverlays,
    displayedParticipantsByTask,
    floor,
    floorBands,
    showQuests,
    ready,
    handleQuestClick,
    onQuestCompleteObjective,
  ]);

  useEffect(() => {
    const runtime = runtimeRef.current;
    const map = runtime?.map;
    if (!ready || !runtime || !map) return undefined;
    if (!showQuests) {
      runtime.questLabels.clearLayers();
      questLabelSigRef.current = "";
      return undefined;
    }
    /* 标签按屏幕投影聚类：只有叠加内容或缩放级别变了才重建，否则每次 WS 推送都全量拆建。 */
    const drawLabels = (): boolean => {
      /* 投影不可用时不画，也不记签名，等 fitBounds 之后再补一次。 */
      if (!isLeafletViewReady(map)) return false;
      addQuestLabels(
        runtime.questLabels,
        displayedQuestOverlays,
        map,
        handleQuestClick,
        displayedParticipantsByTask,
        floor,
        floorBands,
        Boolean(onQuestCompleteObjective),
      );
      applyQuestLabelHighlight(map.getContainer(), highlightTaskIdRef.current);
      return true;
    };
    const labelSig = () => `${overlaySig}\0${map.getZoom().toFixed(3)}`;
    if (questLabelSigRef.current !== labelSig()) {
      if (drawLabels()) questLabelSigRef.current = labelSig();
    }
    let zoomTimer = 0;
    const refreshQuestLabels = () => {
      window.clearTimeout(zoomTimer);
      zoomTimer = window.setTimeout(() => {
        if (questLabelSigRef.current === labelSig()) return;
        if (drawLabels()) questLabelSigRef.current = labelSig();
      }, QUEST_LABEL_ZOOM_MS);
    };
    map.on("zoomend", refreshQuestLabels);
    return () => {
      window.clearTimeout(zoomTimer);
      map.off("zoomend", refreshQuestLabels);
    };
  }, [
    overlaySig,
    displayedQuestOverlays,
    displayedParticipantsByTask,
    floor,
    floorBands,
    showQuests,
    ready,
    handleQuestClick,
    onQuestCompleteObjective,
  ]);

  useEffect(() => {
    const map = runtimeRef.current?.map;
    if (!ready || !map) return;
    applyQuestLabelHighlight(map.getContainer(), highlightTaskId);
  }, [highlightTaskId, ready]);

  useEffect(() => {
    const runtime = runtimeRef.current;
    if (!ready || !runtime) return;
    addBoardMarks(
      runtime,
      visibleMarks,
      floor,
      drawMode === "erase",
      drawMode === "text",
      (markId) => onEraseMarkRef.current?.(markId),
      (mark) => onTextMoveRef.current?.(mark),
      textDragGuardRef,
      (mark) => canDragTextMarkRef.current?.(mark) ?? true,
    );
    // canDragTextMark 变了（换房主）要重建可拖性：放进依赖
  }, [visibleMarks, floor, drawMode, ready, canDragTextMark]);

  useEffect(() => {
    setOptimisticMarks([]);
    prevVisibleKeysRef.current = new Set();
    prevBoardCountRef.current = 0;
  }, [slug]);

  useEffect(() => {
    const count = boardMarks.length;
    if (prevBoardCountRef.current > 0 && count === 0) {
      setOptimisticMarks([]);
      prevBoardCountRef.current = 0;
      return;
    }
    prevBoardCountRef.current = count;
    if (!count) return;
    const keys = new Set(boardMarks.map((mark) => strokeFingerprint(mark)));
    setOptimisticMarks((current) => {
      const next = current.filter((row) => !keys.has(strokeFingerprint(row)));
      return next.length === current.length ? current : next;
    });
  }, [boardMarks]);

  useEffect(() => {
    const runtime = runtimeRef.current;
    const next = new Set(visibleMarks.map((mark) => strokeFingerprint(mark)));
    const prev = prevVisibleKeysRef.current;
    if (runtime) {
      for (const key of prev) {
        if (next.has(key) || !runtime.mineKeys.has(key)) continue;
        const layer = runtime.strokeLayers.get(key);
        if (layer) {
          runtime.mine.removeLayer(layer);
          runtime.board.removeLayer(layer);
        }
        runtime.strokeLayers.delete(key);
        runtime.mineKeys.delete(key);
      }
    }
    prevVisibleKeysRef.current = next;
  }, [visibleMarks, ready]);

  useEffect(() => {
    const runtime = runtimeRef.current;
    if (!runtime?.map || !interactive) return;
    syncRemoteDrafts(runtime, remoteDrafts, floor);
  }, [remoteDrafts, floor, interactive, ready]);

  useEffect(() => {
    if (!ready) return undefined;
    const wrap = wrapElRef.current;
    if (!wrap) return undefined;
    let timer = 0;
    let lastH = 0;
    const refresh = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        const runtime = runtimeRef.current;
        const map = runtime?.map;
        if (!map) return;
        const width = wrap.clientWidth;
        const height = wrap.clientHeight;
        if (width < 2 || height < 2) return;
        const grewFromTiny = lastH < 48 && height >= 48;
        lastH = height;
        map.invalidateSize({ animate: false });
        if (grewFromTiny && runtime.fitBox) {
          map.fitBounds(runtime.fitBox, { animate: false });
        }
      }, 80);
    };
    refresh();
    const ro =
      typeof ResizeObserver === "undefined" ? null : new ResizeObserver(refresh);
    ro?.observe(wrap);
    window.addEventListener("resize", refresh);
    const onFullscreen = () => {
      setMapFullscreen(mapWrapInFullscreen(wrap));
      refresh();
    };
    document.addEventListener("fullscreenchange", onFullscreen);
    document.addEventListener("webkitfullscreenchange", onFullscreen);
    return () => {
      window.clearTimeout(timer);
      ro?.disconnect();
      window.removeEventListener("resize", refresh);
      document.removeEventListener("fullscreenchange", onFullscreen);
      document.removeEventListener("webkitfullscreenchange", onFullscreen);
    };
  }, [ready, fill]);

  useEffect(() => {
    const map = runtimeRef.current?.map;
    if (!ready || !map || !focusRequest) return;
    const mapKey = interactive?.key || "";
    const nextFloor = overlayFloorForPoint(focusRequest.y, floorBands, focusRequest);
    if (mapKey && nextFloor !== floorRef.current) {
      updatePrefs((prev) => withMapFloor(prev, mapKey, nextFloor));
    }
    const latLng = L.latLng(pos(focusRequest));
    const fly = () => {
      const current = runtimeRef.current?.map;
      if (!current) return;
      current.invalidateSize({ animate: false });
      const zoom = mapFocusZoom(
        overlayMode,
        current.getMinZoom(),
        current.getMaxZoom(),
        current.getZoom(),
      );
      current.flyTo(latLng, zoom, { animate: true, duration: 0.35 });
    };
    fly();
    const timer = window.setTimeout(fly, 180);
    return () => window.clearTimeout(timer);
  }, [focusRequest, ready, floorBands, interactive?.key, overlayMode, updatePrefs]);

  useEffect(() => {
    const runtime = runtimeRef.current;
    const map = runtime?.map;
    const fix = suppressLocalFix ? null : shotWatch.fix;
    if (!ready || !runtime || !map) return;
    const local = fix
      ? {
          key: `self:${fix.fileName}`,
          userId: authorUserId,
          name: playerFixMarkerCaption(authorDisplayName),
          color: authorUserId ? colorForUserId(authorUserId) : "#c8932a",
          x: fix.x,
          y: fix.y,
          z: fix.z,
          yaw: fix.yaw,
          self: true as const,
        }
      : null;
    const marks = collectPlayerFixMarks(remotePlayerFixes, local);
    if (!marks.length) {
      runtime.player.clearLayers();
      runtime.playerLayers.clear();
      runtime.playerIconHtml.clear();
      playerFixSigRef.current = "";
      return;
    }
    syncPlayerFixMarkers(
      runtime,
      marks,
      interactive?.coordinateRotation || 0,
      floor,
      floorBands,
    );
    const follow = playerFixCameraTarget(marks, authorUserId);
    if (!follow) return;
    const sig = playerFixFollowSig(follow);
    if (playerFixSigRef.current === sig) return;
    const hadFix = Boolean(playerFixSigRef.current);
    playerFixSigRef.current = sig;
    const mapKey = interactive?.key || "";
    const nextFloor = overlayFloorForPoint(follow.y, floorBands, follow);
    if (mapKey && nextFloor !== floorRef.current) {
      updatePrefs((prev) => withMapFloor(prev, mapKey, nextFloor));
    }
    const latLng = L.latLng(pos({ x: follow.x, z: follow.z }));
    if (hadFix) {
      map.panTo(latLng, { animate: true, duration: 0.2 });
      return;
    }
    const zoom = Math.max(map.getZoom(), map.getMinZoom() + 1);
    map.flyTo(latLng, zoom, { animate: true, duration: 0.35 });
  }, [
    shotWatch.fix,
    remotePlayerFixes,
    suppressLocalFix,
    authorUserId,
    authorDisplayName,
    ready,
    floor,
    floorBands,
    interactive?.coordinateRotation,
    interactive?.key,
    interactive?.normalizedName,
    slug,
    parentSlug,
    updatePrefs,
  ]);

  const pulseLinesRef = useRef(playerFixPulseLines);
  pulseLinesRef.current = playerFixPulseLines;
  useEffect(() => {
    const runtime = runtimeRef.current;
    if (!ready || !runtime?.pulse) return undefined;
    let raf = 0;
    const tick = () => {
      const now = Date.now();
      const lines = pulseLinesRef.current;
      syncPlayerFixPulseLines(runtime, lines, now, floorBands);
      if (lines.some((line) => playerFixPulseOpacity(line.bornAt, now) > 0)) {
        raf = window.requestAnimationFrame(tick);
      }
    };
    tick();
    return () => window.cancelAnimationFrame(raf);
  }, [floorBands, playerFixPulseLines, ready]);

  useEffect(() => {
    const map = runtimeRef.current?.map;
    const pane = runtimeRef.current?.boardPane;
    if (!map) return;
    const drawing =
      ((isMapDrawTool(drawMode) || isPlaceEditTool(placeEdit?.mode)) &&
        !spaceHeld &&
        !rightPanHeld);
    if (drawing) {
      map.dragging.disable();
      map.doubleClickZoom.disable();
      map.boxZoom.disable();
    } else {
      map.dragging.enable();
      map.doubleClickZoom.enable();
      map.boxZoom.enable();
    }
    if (pane) pane.style.pointerEvents = drawMode === "erase" ? "auto" : "none";
    runtimeRef.current?.iconCanvas?.setInteractive(!drawing);
  }, [drawMode, placeEdit?.mode, spaceHeld, rightPanHeld, ready]);

  useEffect(() => {
    if (drawMode !== "line") lineStartRef.current = null;
    const map = runtimeRef.current?.map;
    if (!ready || !map) return undefined;
    const onClick = (event: L.LeafletMouseEvent) => {
      if (isCanvasMarkerEvent(event.originalEvent)) return;
      if (textDragGuardRef.current) return;
      if (isTypingTarget(event.originalEvent?.target ?? null)) return;
      const clickTarget = event.originalEvent?.target;
      if (
        clickTarget instanceof Element &&
        clickTarget.closest(`.${styles.boardTextIcon}`)
      ) {
        return;
      }
      const mode = drawModeRef.current;
      if (mode !== "pin" && mode !== "line" && mode !== "text") return;
      if (spaceHeldRef.current || rightPanHeldRef.current) return;
      const floor = floorRef.current;
      const x = event.latlng.lng;
      const z = event.latlng.lat;
      if (mode === "text") {
        commitTextDraftRef.current();
        const point = map.latLngToContainerPoint(event.latlng);
        const gen = textDraftGen.current + 1;
        textDraftGen.current = gen;
        const next = { gen, floor, x, z, left: point.x, top: point.y };
        textDraftRef.current = next;
        setTextDraft(next);
        return;
      }
      if (mode === "pin") {
        onPinRef.current?.({ floor, x, z });
        return;
      }
      const start = lineStartRef.current;
      if (!start) {
        lineStartRef.current = { x, z };
        return;
      }
      lineStartRef.current = null;
      onLineRef.current?.({ floor, x: start.x, z: start.z, x2: x, z2: z });
    };
    map.on("click", onClick);
    return () => {
      map.off("click", onClick);
    };
  }, [drawMode, ready]);

  useEffect(() => {
    if (drawMode === "text") return;
    textDraftGen.current += 1;
    textDraftRef.current = null;
    setTextDraft(null);
  }, [drawMode]);

  const textAnchor = textDraft
    ? `${textDraft.gen}:${textDraft.x}:${textDraft.z}`
    : "";
  useEffect(() => {
    const map = runtimeRef.current?.map;
    if (!ready || !map || !textAnchor) return undefined;
    const sync = () => {
      const current = textDraftRef.current;
      if (!current) return;
      const point = map.latLngToContainerPoint(pos({ x: current.x, z: current.z }));
      setTextDraft((prev) => {
        if (!prev || prev.gen !== current.gen) return prev;
        if (
          Math.abs(prev.left - point.x) < 0.5 &&
          Math.abs(prev.top - point.y) < 0.5
        ) {
          return prev;
        }
        const next = { ...prev, left: point.x, top: point.y };
        textDraftRef.current = next;
        return next;
      });
    };
    map.on("move", sync);
    map.on("zoom", sync);
    return () => {
      map.off("move", sync);
      map.off("zoom", sync);
    };
  }, [ready, textAnchor]);

  useEffect(() => {
    const map = runtimeRef.current?.map;
    if (!ready || !map) return undefined;
    const onClick = (event: L.LeafletMouseEvent) => {
      if (isCanvasMarkerEvent(event.originalEvent)) return;
      const edit = placeEditRef.current;
      if (edit?.mode !== "point") return;
      if (spaceHeldRef.current || rightPanHeldRef.current) return;
      edit.onPoint?.({
        floor: floorRef.current,
        x: event.latlng.lng,
        z: event.latlng.lat,
      });
    };
    map.on("click", onClick);
    return () => {
      map.off("click", onClick);
    };
  }, [placeEdit?.mode, ready]);

  useEffect(() => {
    const map = runtimeRef.current?.map;
    if (!ready || !map) return undefined;
    let start: { x: number; z: number } | null = null;
    let draft: L.Rectangle | null = null;
    const clearDraft = () => {
      draft?.remove();
      draft = null;
      start = null;
    };
    const onDown = (event: PointerEvent) => {
      if (placeEditRef.current?.mode !== "box") return;
      if (event.pointerType === "mouse" && event.button !== 0) return;
      if (spaceHeldRef.current || rightPanHeldRef.current) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest(".leaflet-control")) return;
      const latlng = map.mouseEventToLatLng(event as unknown as MouseEvent);
      start = { x: latlng.lng, z: latlng.lat };
      map.dragging.disable();
      try {
        map.getContainer().setPointerCapture(event.pointerId);
      } catch {
        /* ignore */
      }
      event.preventDefault();
      event.stopPropagation();
    };
    const onMove = (event: PointerEvent) => {
      if (!start || placeEditRef.current?.mode !== "box") return;
      const latlng = map.mouseEventToLatLng(event as unknown as MouseEvent);
      const bounds = L.latLngBounds(
        pos(start),
        pos({ x: latlng.lng, z: latlng.lat }),
      );
      if (!draft) {
        draft = L.rectangle(bounds, {
          color: "#c8932a",
          weight: 1,
          fillColor: "#c8932a",
          fillOpacity: 0.12,
          interactive: false,
        }).addTo(map);
      } else {
        draft.setBounds(bounds);
      }
    };
    const onUp = (event: PointerEvent) => {
      if (!start || placeEditRef.current?.mode !== "box") {
        clearDraft();
        return;
      }
      const latlng = map.mouseEventToLatLng(event as unknown as MouseEvent);
      const box = {
        x: start.x,
        z: start.z,
        x2: latlng.lng,
        z2: latlng.lat,
        floor: floorRef.current,
      };
      clearDraft();
      if (Math.abs(box.x2 - box.x) < 0.5 || Math.abs(box.z2 - box.z) < 0.5) {
        return;
      }
      placeEditRef.current?.onBox?.(box);
    };
    const container = map.getContainer();
    container.addEventListener("pointerdown", onDown, true);
    container.addEventListener("pointermove", onMove, true);
    window.addEventListener("pointerup", onUp, true);
    window.addEventListener("pointercancel", onUp, true);
    return () => {
      clearDraft();
      container.removeEventListener("pointerdown", onDown, true);
      container.removeEventListener("pointermove", onMove, true);
      window.removeEventListener("pointerup", onUp, true);
      window.removeEventListener("pointercancel", onUp, true);
    };
  }, [placeEdit?.mode, ready]);

  useEffect(() => {
    const clearSpace = () => {
      spaceHeldRef.current = false;
      setSpaceHeld(false);
    };
    const onDown = (event: KeyboardEvent) => {
      if (event.code !== "Space" || event.repeat) return;
      if (isTypingTarget(event.target)) return;
      event.preventDefault();
      spaceHeldRef.current = true;
      setSpaceHeld(true);
    };
    const onUp = (event: KeyboardEvent) => {
      if (event.code !== "Space") return;
      clearSpace();
    };
    window.addEventListener("keydown", onDown);
    window.addEventListener("keyup", onUp);
    window.addEventListener("blur", clearSpace);
    return () => {
      window.removeEventListener("keydown", onDown);
      window.removeEventListener("keyup", onUp);
      window.removeEventListener("blur", clearSpace);
    };
  }, []);

  useEffect(() => {
    const map = runtimeRef.current?.map;
    if (!ready || !map) return undefined;
    const container = map.getContainer();
    let last: { x: number; y: number } | null = null;
    const allowsRightPan = () =>
      shouldRightButtonPanMap(drawModeRef.current) ||
      isPlaceEditTool(placeEditRef.current?.mode);
    const endPan = () => {
      if (!rightPanHeldRef.current) return;
      rightPanHeldRef.current = false;
      setRightPanHeld(false);
      last = null;
    };
    const onDown = (event: PointerEvent) => {
      if (event.pointerType === "mouse" && event.button !== 2) return;
      if (event.pointerType !== "mouse") return;
      if (!allowsRightPan()) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest(".leaflet-control")) return;
      event.preventDefault();
      event.stopPropagation();
      rightPanHeldRef.current = true;
      setRightPanHeld(true);
      last = { x: event.clientX, y: event.clientY };
    };
    const onMove = (event: PointerEvent) => {
      if (!rightPanHeldRef.current || !last) return;
      const dx = event.clientX - last.x;
      const dy = event.clientY - last.y;
      last = { x: event.clientX, y: event.clientY };
      map.panBy([-dx, -dy], { animate: false });
      event.preventDefault();
    };
    const onUp = (event: PointerEvent) => {
      if (!rightPanHeldRef.current) return;
      if (
        event.type === "pointerup" &&
        event.pointerType === "mouse" &&
        event.button !== 2
      ) {
        return;
      }
      endPan();
    };
    const onContextMenu = (event: Event) => {
      if (!allowsRightPan() && !rightPanHeldRef.current) return;
      event.preventDefault();
    };
    container.addEventListener("pointerdown", onDown, true);
    window.addEventListener("pointermove", onMove, true);
    window.addEventListener("pointerup", onUp, true);
    window.addEventListener("pointercancel", onUp, true);
    container.addEventListener("contextmenu", onContextMenu, true);
    return () => {
      endPan();
      container.removeEventListener("pointerdown", onDown, true);
      window.removeEventListener("pointermove", onMove, true);
      window.removeEventListener("pointerup", onUp, true);
      window.removeEventListener("pointercancel", onUp, true);
      container.removeEventListener("contextmenu", onContextMenu, true);
    };
  }, [ready]);

  if (!interactive && !raster) {
    return (
      <div className={styles.status}>这张图还没有可嵌入的底图。</div>
    );
  }

  return (
    <TarkovMapFullscreenRootContext.Provider
      value={{ root: overlayRoot, fullscreen: mapFullscreen, toggle: toggleMapFullscreen }}
    >
    <div
      ref={setWrapEl}
      className={`${styles.wrap} ${fill ? styles.wrapFill : ""} ${isMapDrawTool(drawMode) ? styles.wrapDraw : ""} ${drawMode === "text" ? styles.wrapText : ""} ${drawMode === "erase" ? styles.wrapErase : ""} ${isPlaceEditTool(placeEdit?.mode) ? styles.wrapPlaceEdit : ""} ${placeEdit?.mode === "select" ? styles.wrapPlaceSelect : ""} ${spaceHeld || rightPanHeld ? styles.wrapSpace : ""} ${mapFullscreen ? styles.wrapFullscreen : ""} ${showSidebars ? "" : styles.wrapSidebarsClosed} ${className}`.trim()}
      onPointerDown={() => {
        if (shotResumeOnceRef.current) return;
        if (shotWatch.perm !== "prompt" || !shotWatch.hasStored) return;
        shotResumeOnceRef.current = true;
        void shotWatch.enable();
      }}
    >
      <div className={styles.map} ref={mapDivRef} />
      {topRight ? <div className={styles.topRight}>{topRight}</div> : null}
      {toolbar ? <div className={styles.toolbar}>{toolbar}</div> : null}
      {textDraft ? (
        <form
          className={styles.textDraft}
          style={{ left: textDraft.left, top: textDraft.top }}
          onSubmit={(event) => {
            event.preventDefault();
            commitTextDraft();
          }}
          onPointerDown={(event) => event.stopPropagation()}
        >
          <input
            ref={textInputRef}
            key={textDraft.gen}
            className={styles.textDraftInput}
            // oxlint-disable-next-line jsx-a11y/no-autofocus -- 输入框就是用户刚在地图上点出来的文字位置
            autoFocus
            maxLength={MARK_TEXT_MAX}
            placeholder="输入文字"
            aria-label="地图文字"
            autoComplete="off"
            enterKeyHint="done"
            onKeyDown={(event) => {
              if (event.key !== "Escape") return;
              event.preventDefault();
              event.stopPropagation();
              cancelTextDraft();
            }}
            onBlur={() => {
              if (textDraftRef.current?.gen !== textDraft.gen) return;
              commitTextDraft();
            }}
          />
        </form>
      ) : null}
      {loading ? (
        <div className={`${styles.status} ${styles.overlay}`}>
          <Spin />
        </div>
      ) : null}
      {error ? (
        <div className={`${styles.status} ${styles.overlay}`}>{error}</div>
      ) : null}
      {(canSvg || canTile || floors.length || interactive) || topLeft ? (
        <div className={styles.topLeftStack}>
        {topLeft ? <div className={styles.topLeftExtra}>{topLeft}</div> : null}
      {canSvg || canTile || floors.length || interactive ? (
        <div
          className={`${floatStyles.panel} ${styles.filterPanel}`}
          data-open={filterPanelOpen ? "true" : "false"}
          aria-label="地图筛选"
        >
          <div className={styles.filterPanelHead}>
            {filterPanelOpen ? (
              <span className={`${styles.filterGroupTitle} ${floatStyles.lg}`}>图层</span>
            ) : null}
            <button
              type="button"
              className={styles.filterPanelToggle}
              aria-expanded={filterPanelOpen}
              aria-controls="tarkov-map-filter-body"
              onClick={() =>
                updatePrefs({ filterPanelOpen: !filterPanelOpen })
              }
            >
              {filterPanelOpen ? "收起" : "图层"}
            </button>
          </div>
          <div
            id="tarkov-map-filter-body"
            className={styles.filterPanelBody}
            hidden={!filterPanelOpen}
          >
          {canSvg || canTile ? (
            <div className={styles.filterGroup} role="radiogroup" aria-label={TARKOV_MAP_FILTER_GROUP_LABELS.style}>
              {canTile ? (
                <label className={styles.filterRow}>
                  <input
                    className={styles.filterRadio}
                    type="radio"
                    name={`tarkov-map-style-${interactive?.key || "map"}`}
                    checked={style === "tile"}
                    onChange={() => updatePrefs({ style: "tile" })}
                  />
                  <span>卫星图</span>
                </label>
              ) : null}
              {canSvg ? (
                <label className={styles.filterRow}>
                  <input
                    className={styles.filterRadio}
                    type="radio"
                    name={`tarkov-map-style-${interactive?.key || "map"}`}
                    checked={style === "svg"}
                    onChange={() => updatePrefs({ style: "svg" })}
                  />
                  <span>抽象图</span>
                </label>
              ) : null}
            </div>
          ) : null}
          {floors.length ? (
            <>
              {canSvg || canTile ? (
                <span className={styles.filterSplit} aria-hidden="true" />
              ) : null}
              <div className={styles.filterGroup} role="radiogroup" aria-label={TARKOV_MAP_FILTER_GROUP_LABELS.levels}>
                <FilterCollapsibleGroup
                  groupId="levels"
                  label={TARKOV_MAP_FILTER_GROUP_LABELS.levels}
                  collapsed={groupCollapsed("levels")}
                  onToggle={toggleGroupCollapsed}
                  header={
                    <span className={styles.filterGroupTitle}>
                      {TARKOV_MAP_FILTER_GROUP_LABELS.levels}
                    </span>
                  }
                >
                <label className={`${styles.filterRow} ${styles.filterRowChild}`}>
                  <input
                    className={styles.filterRadio}
                    type="radio"
                    name={`tarkov-map-floor-${interactive?.key || "map"}-${overlayMode}`}
                    checked={!floor}
                    onChange={() =>
                      updatePrefs((prev) =>
                        withMapFloor(prev, interactive?.key || "", ""),
                      )
                    }
                  />
                  <span>地面</span>
                </label>
                {floors.map((item) => (
                  <label key={item.name} className={`${styles.filterRow} ${styles.filterRowChild}`}>
                    <input
                      className={styles.filterRadio}
                      type="radio"
                      name={`tarkov-map-floor-${interactive?.key || "map"}-${overlayMode}`}
                      checked={floor === item.name}
                      onChange={() =>
                        updatePrefs((prev) =>
                          withMapFloor(prev, interactive?.key || "", item.name),
                        )
                      }
                    />
                    <span>{floorLabel(item.name)}</span>
                  </label>
                ))}
                </FilterCollapsibleGroup>
              </div>
            </>
          ) : null}
          {showPointLayers && interactive ? (
            <>
              {(canSvg || canTile || floors.length) &&
              (hasMapLayerFilters || hasQuestFilters) ? (
                <span className={styles.filterSplit} aria-hidden="true" />
              ) : null}
              {hasMapLayerFilters ? (
              <div className={styles.filterGroup} aria-label="展示点位">
                {placeLabels.length && btrStops.length ? (
                  <FilterCollapsibleGroup
                    groupId="landmarks"
                    label={TARKOV_MAP_FILTER_GROUP_LABELS.landmarks}
                    collapsed={groupCollapsed("landmarks")}
                    onToggle={toggleGroupCollapsed}
                    header={
                      <FilterCheckRow
                        checked={showLabels}
                        label={TARKOV_MAP_FILTER_GROUP_LABELS.landmarks}
                        onChange={() =>
                          updatePrefs({ showLabels: !showLabels })
                        }
                      />
                    }
                  >
                    <FilterCheckRow
                      child
                      checked={showBtrStops}
                      icon={tarkovBtrIconUrl()}
                      label={TARKOV_MAP_FILTER_ITEM_LABELS.btrStop}
                      onChange={() =>
                        updatePrefs({ showBtrStops: !showBtrStops })
                      }
                    />
                  </FilterCollapsibleGroup>
                ) : placeLabels.length || btrStops.length ? (
                  <div className={styles.filterSubgroup}>
                    {placeLabels.length ? (
                      <FilterCheckRow
                        checked={showLabels}
                        label={TARKOV_MAP_FILTER_GROUP_LABELS.landmarks}
                        onChange={() =>
                          updatePrefs({ showLabels: !showLabels })
                        }
                      />
                    ) : null}
                    {btrStops.length ? (
                      <FilterCheckRow
                        checked={showBtrStops}
                        icon={tarkovBtrIconUrl()}
                        label={TARKOV_MAP_FILTER_ITEM_LABELS.btrStop}
                        onChange={() =>
                          updatePrefs({ showBtrStops: !showBtrStops })
                        }
                      />
                    ) : null}
                  </div>
                ) : null}
                {extractKindOptions.length ? (
                  <FilterCollapsibleGroup
                    groupId="extracts"
                    label={TARKOV_MAP_FILTER_GROUP_LABELS.extracts}
                    collapsed={groupCollapsed("extracts")}
                    onToggle={toggleGroupCollapsed}
                    header={
                    <FilterCheckRow
                      inputRef={extractsParentRef}
                      checked={extractsParentOn}
                      label={TARKOV_MAP_FILTER_GROUP_LABELS.extracts}
                      onChange={() =>
                        updatePrefs((prev) => ({
                          ...prev,
                          extractKinds: withExtractKindsForPresent(
                            prev.extractKinds,
                            extractKindOptions,
                            !extractsParentOn,
                          ),
                        }))
                      }
                    />
                    }
                  >
                    {extractKindOptions.map((kind) => (
                      <FilterCheckRow
                        key={kind}
                        child
                        checked={extractKinds[kind]}
                        icon={tarkovExtractIconUrl(kind)}
                        label={TARKOV_EXTRACT_KIND_LABELS[kind]}
                        onChange={() =>
                          updatePrefs((prev) =>
                            withExtractKind(
                              prev,
                              kind,
                              !prev.extractKinds[kind],
                            ),
                          )
                        }
                      />
                    ))}
                  </FilterCollapsibleGroup>
                ) : null}
                {spawnKindOptions.length ? (
                  <FilterCollapsibleGroup
                    groupId="spawns"
                    label={TARKOV_MAP_FILTER_GROUP_LABELS.spawns}
                    collapsed={groupCollapsed("spawns")}
                    onToggle={toggleGroupCollapsed}
                    header={
                    <FilterCheckRow
                      inputRef={spawnsParentRef}
                      checked={spawnsParentOn}
                      label={TARKOV_MAP_FILTER_GROUP_LABELS.spawns}
                      onChange={() =>
                        updatePrefs((prev) => ({
                          ...prev,
                          spawnKinds: withSpawnKindsForPresent(
                            prev.spawnKinds,
                            spawnKindOptions,
                            !spawnsParentOn,
                          ),
                        }))
                      }
                    />
                    }
                  >
                    {spawnKindOptions.map((kind) => (
                      <FilterCheckRow
                        key={kind}
                        child
                        checked={spawnKinds[kind]}
                        icon={tarkovSpawnIconUrl(kind)}
                        label={TARKOV_SPAWN_KIND_LABELS[kind]}
                        onChange={() =>
                          updatePrefs((prev) =>
                            withSpawnKind(
                              prev,
                              kind,
                              !prev.spawnKinds[kind],
                            ),
                          )
                        }
                      />
                    ))}
                  </FilterCollapsibleGroup>
                ) : null}
                {usableItems.length ? (
                  <FilterCollapsibleGroup
                    groupId="usable"
                    label={TARKOV_MAP_FILTER_GROUP_LABELS.usable}
                    collapsed={groupCollapsed("usable")}
                    onToggle={toggleGroupCollapsed}
                    header={
                    <FilterCheckRow
                      inputRef={usableParentRef}
                      checked={usableParentOn}
                      label={TARKOV_MAP_FILTER_GROUP_LABELS.usable}
                      onChange={() =>
                        updatePrefs((prev) => ({
                          ...prev,
                          ...withFilterGroupOn(
                            {
                              showLocks: prev.showLocks,
                              showSwitches: prev.showSwitches,
                              showStationary: prev.showStationary,
                            },
                            usableItems.map((item) => item.key),
                            !usableParentOn,
                          ),
                        }))
                      }
                    />
                    }
                  >
                    {locks.length ? (
                      <FilterCheckRow
                        child
                        checked={showLocks}
                        icon={tarkovLockIconUrl()}
                        label={TARKOV_MAP_FILTER_ITEM_LABELS.locks}
                        onChange={() =>
                          updatePrefs({ showLocks: !showLocks })
                        }
                      />
                    ) : null}
                    {stationaryWeapons.length ? (
                      <FilterCheckRow
                        child
                        checked={showStationary}
                        icon={tarkovStationaryIconUrl()}
                        label={TARKOV_MAP_FILTER_ITEM_LABELS.stationary}
                        onChange={() =>
                          updatePrefs({ showStationary: !showStationary })
                        }
                      />
                    ) : null}
                    {switches.length ? (
                      <FilterCheckRow
                        child
                        checked={showSwitches}
                        icon={tarkovSwitchIconUrl()}
                        label={TARKOV_MAP_FILTER_ITEM_LABELS.switches}
                        onChange={() =>
                          updatePrefs({ showSwitches: !showSwitches })
                        }
                      />
                    ) : null}
                  </FilterCollapsibleGroup>
                ) : null}
                {hazardKindOptions.length ? (
                  <FilterCollapsibleGroup
                    groupId="hazards"
                    label={TARKOV_MAP_FILTER_GROUP_LABELS.hazards}
                    collapsed={groupCollapsed("hazards")}
                    onToggle={toggleGroupCollapsed}
                    header={
                    <FilterCheckRow
                      inputRef={hazardsParentRef}
                      checked={hazardsParentOn}
                      icon={tarkovHazardIconUrl("")}
                      label={TARKOV_MAP_FILTER_GROUP_LABELS.hazards}
                      onChange={() =>
                        updatePrefs((prev) => ({
                          ...prev,
                          showHazards: !hazardsParentOn,
                          hazardKinds: withKindsForPresent(
                            prev.hazardKinds,
                            hazardKindOptions,
                            !hazardsParentOn,
                          ),
                        }))
                      }
                    />
                    }
                  >
                    {hazardKindOptions.map((kind) => (
                      <FilterCheckRow
                        key={kind}
                        child
                        checked={
                          showHazards && isHazardKindOn(hazardKinds, kind)
                        }
                        icon={tarkovHazardIconUrl(kind)}
                        label={tarkovHazardKindLabel(
                          kind,
                          hazards.find((row) => row.hazard_type === kind)
                            ?.name || "",
                        )}
                        onChange={() =>
                          updatePrefs((prev) =>
                            withHazardKind(
                              prev,
                              kind,
                              !(
                                prev.showHazards &&
                                isHazardKindOn(prev.hazardKinds, kind)
                              ),
                            ),
                          )
                        }
                      />
                    ))}
                  </FilterCollapsibleGroup>
                ) : null}
                {showLootLayerToggles ? (
                  <FilterCollapsibleGroup
                    groupId="lootable"
                    label={TARKOV_MAP_FILTER_GROUP_LABELS.lootable}
                    collapsed={groupCollapsed("lootable")}
                    onToggle={toggleGroupCollapsed}
                    header={
                    <FilterCheckRow
                      inputRef={lootParentRef}
                      checked={lootParentOn}
                      icon={tarkovContainerIconUrl("")}
                      label={TARKOV_MAP_FILTER_GROUP_LABELS.lootable}
                      onChange={() =>
                        updatePrefs((prev) => {
                          const on = !lootParentOn;
                          return {
                            ...prev,
                            showLootContainers: on,
                            lootContainerKinds: withKindsForPresent(
                              prev.lootContainerKinds,
                              lootKindOptions,
                              on,
                            ),
                          };
                        })
                      }
                    />
                    }
                  >
                    {lootKindOptions.length
                      ? lootKindOptions.map((kind) => (
                          <FilterCheckRow
                            key={kind}
                            child
                            checked={
                              showLootContainers &&
                              isLootContainerKindOn(lootContainerKinds, kind)
                            }
                            icon={tarkovContainerIconUrl(kind)}
                            label={lootContainerKindLabel(kind, lootContainers)}
                            onChange={() =>
                              updatePrefs((prev) =>
                                withLootContainerKind(
                                  prev,
                                  kind,
                                  !(
                                    prev.showLootContainers &&
                                    isLootContainerKindOn(
                                      prev.lootContainerKinds,
                                      kind,
                                    )
                                  ),
                                ),
                              )
                            }
                          />
                        ))
                      : showLootContainers && lootQuery.isFetching
                        ? (
                            <span className={styles.filterHint}>加载中…</span>
                          )
                        : null}
                  </FilterCollapsibleGroup>
                ) : null}
                {showLootLayerToggles ? (
                  <FilterCollapsibleGroup
                    groupId="lootLoose"
                    label={TARKOV_MAP_FILTER_GROUP_LABELS.lootLoose}
                    collapsed={groupCollapsed("lootLoose")}
                    onToggle={toggleGroupCollapsed}
                    header={
                    <FilterCheckRow
                      inputRef={looseParentRef}
                      checked={looseParentOn}
                      icon={tarkovLooseLootIconUrl()}
                      label={TARKOV_MAP_FILTER_GROUP_LABELS.lootLoose}
                      onChange={() =>
                        updatePrefs((prev) => {
                          const on = !looseParentOn;
                          return {
                            ...prev,
                            showLootLoose: on,
                            lootLooseKinds: withKindsForPresent(
                              prev.lootLooseKinds,
                              looseKindOptions,
                              on,
                            ),
                          };
                        })
                      }
                    />
                    }
                  >
                    {looseKindOptions.length
                      ? looseKindOptions.map((kind) => (
                          <FilterCheckRow
                            key={kind}
                            child
                            checked={
                              showLootLoose && isLootLooseKindOn(lootLooseKinds, kind)
                            }
                            icon={tarkovLooseLootKindIconUrl(kind)}
                            label={lootLooseKindLabel(kind)}
                            onChange={() =>
                              updatePrefs((prev) =>
                                withLootLooseKind(
                                  prev,
                                  kind,
                                  !(
                                    prev.showLootLoose &&
                                    isLootLooseKindOn(prev.lootLooseKinds, kind)
                                  ),
                                ),
                              )
                            }
                          />
                        ))
                      : showLootLoose && lootQuery.isFetching
                        ? (
                            <span className={styles.filterHint}>加载中…</span>
                          )
                        : null}
                  </FilterCollapsibleGroup>
                ) : null}
              </div>
              ) : null}
              {lootQuery.isError && (showLootLoose || showLootContainers) ? (
                <p className={styles.filterError} role="alert">
                  <span>
                    {apiError(lootQuery.error, "散落物图层加载失败")}
                  </span>
                  <button
                    type="button"
                    className={styles.filterErrorRetry}
                    onClick={() => void lootQuery.refetch()}
                  >
                    重试
                  </button>
                </p>
              ) : null}
              {hasQuestFilters ? (
                <>
                  {hasMapLayerFilters ? (
                    <span className={styles.filterSplit} aria-hidden="true" />
                  ) : null}
                  <div
                    className={styles.filterGroup}
                    aria-label={TARKOV_MAP_FILTER_GROUP_LABELS.tasks}
                  >
                    <FilterCollapsibleGroup
                      groupId="tasks"
                      label={TARKOV_MAP_FILTER_GROUP_LABELS.tasks}
                      collapsed={groupCollapsed("tasks")}
                      onToggle={toggleGroupCollapsed}
                      header={
                      <FilterCheckRow
                        inputRef={questsParentRef}
                        checked={questsParentOn}
                        label={TARKOV_MAP_FILTER_GROUP_LABELS.tasks}
                        onChange={() => {
                          const next = nextQuestPeopleParentSelection(
                            questPeople.map((person) =>
                              raidPrepPersonKey(person),
                            ),
                            questsParentOn,
                          );
                          updatePrefs({ showQuests: next.showQuests });
                          setQuestPersonOff(new Set(next.offKeys));
                        }}
                      />
                      }
                    >
                      {questPeople.map((person) => {
                        const key = raidPrepPersonKey(person);
                        const on = showQuests && !questPersonOff.has(key);
                        return (
                          <label
                            key={key}
                            className={`${styles.filterRow} ${styles.filterRowChild}`}
                          >
                            <input
                              className={styles.filterCheck}
                              type="checkbox"
                              checked={on}
                              onChange={() => {
                                const next = nextQuestPersonSelection(
                                  questPeople.map((row) =>
                                    raidPrepPersonKey(row),
                                  ),
                                  questPersonOff,
                                  showQuests,
                                  key,
                                );
                                updatePrefs({ showQuests: next.showQuests });
                                setQuestPersonOff(new Set(next.offKeys));
                              }}
                            />
                            <span
                              className={styles.filterDot}
                              style={{
                                background:
                                  person.userId != null
                                    ? colorForUserId(person.userId)
                                    : colorForTaskId(person.name),
                              }}
                            />
                            <span>{person.name}</span>
                          </label>
                        );
                      })}
                    </FilterCollapsibleGroup>
                  </div>
                </>
              ) : null}
            </>
          ) : null}
          </div>
        </div>
      ) : null}
        </div>
      ) : null}
      {mapFullscreenEnabled() && !hideCornerFullscreen ? (
        <div className={styles.meta}>
          <button
            type="button"
            className={styles.fullScreen}
            aria-pressed={mapFullscreen}
            aria-label={mapFullscreen ? "退出全屏" : "全屏"}
            title={mapFullscreen ? "退出全屏" : "全屏"}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              toggleMapFullscreen();
            }}
          >
            {mapFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
          </button>
        </div>
      ) : null}
      {!interactive && raster ? (
        <div className={styles.note}>平面图，坐标标记仅互动图层可用。</div>
      ) : null}
    </div>
    </TarkovMapFullscreenRootContext.Provider>
  );
}
