import { apiError } from "@/lib/apiError";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Spin } from "antd";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "@/components/guides/tarkov/tarkovFonts.css";
import type {
  TarkovMapBoss,
  TarkovMapExtract,
  TarkovMapSpawn,
} from "@/api/guidesApi";
import { getBounds, getCRS, getScaledBounds, pos } from "@/lib/tarkovMapCrs";
import { tarkovBossMapLabel, tarkovMapLabel } from "@/lib/tarkovMapLabelsZh";
import {
  isPlaceEditTool,
  PLACE_LABEL_FONT_PX,
  placeLabelIconSize,
  placeNameLines,
  placeVisibleOnFloor,
  resolveMapPlaceLabels,
  type ResolvedMapPlace,
  type TarkovMapPlaceEdit,
  type TarkovMapPlaceLike,
} from "@/lib/tarkovMapPlaceLabels";
import {
  clusterRaidPrepOverlayLabels,
  collectRaidPrepQuestFilterPeople,
  colorForTaskId,
  colorForUserId,
  defaultQuestPersonOffKeys,
  formatRaidPrepOverlayKeyLabel,
  mapLayerFloorBands,
  nextQuestPeopleParentSelection,
  nextQuestPersonSelection,
  overlayFloorForPoint,
  overlayFloorForSpan,
  overlayVisibleOnFloor,
  RAID_PREP_LABEL_CLUSTER_PX,
  raidPrepParticipants,
  raidPrepPersonKey,
  raidPrepQuestOverlayVisible,
  type RaidPrepHeightSpan,
  type RaidPrepMapParticipant,
  type RaidPrepOverlayLabelItem,
  type RaidPrepOverlayStep,
  type RaidPrepPoint,
  type TarkovRaidPrepOverlay,
} from "@/lib/tarkovRaidPrep";
import { traderIconUrl, traderPortraitUrl } from "@/lib/tarkovHomeNav";
import {
  RAID_ROOM_OTHER_FLOOR_OPACITY,
  collectPlayerFixMarks,
  playerFixMarkerCaption,
  type TarkovMapPlayerMark,
  isMapDrawTool,
  isTypingTarget,
  markMatchesFloor,
  markStrokePoints,
  mergeBoardMarks,
  simplifyStroke,
  strokeFingerprint,
  type RaidRoomDraftStroke,
  type RaidRoomMarkLike,
  type StrokePoint,
  type TarkovMapDrawMode,
} from "@/lib/tarkovRaidRooms";
import {
  MAP_OFF_LEVEL_OPACITY,
  mapBaseOffLevel,
  svgFloorGroupClasses,
} from "@/lib/tarkovMapFloors";
import {
  findInteractiveMap,
  findRasterMap,
  floorLabel,
  svgFallbackUrl,
  type TarkovDevMapLayer,
} from "@/lib/tarkovMapImages";
import {
  loadTarkovMapViewerPrefs,
  overlayFlagsForMode,
  resolveMapFloor,
  resolveMapStyle,
  saveTarkovMapViewerPrefs,
  withExtractKind,
  withMapFloor,
  withSpawnKind,
  type TarkovMapOverlayMode,
  type TarkovMapViewerPrefs,
} from "@/lib/tarkovMapViewerPrefs";
import {
  allPresentExtractKindsOn,
  anyPresentExtractKindOn,
  isExtractKindVisible,
  TARKOV_EXTRACT_KIND_LABELS,
  TARKOV_EXTRACT_KINDS,
  tarkovExtractIconUrl,
  tarkovExtractStyle,
  withExtractKindsForPresent,
  type TarkovExtractKindFlags,
} from "@/lib/tarkovMapExtracts";
import {
  allPresentSpawnKindsOn,
  anyPresentSpawnKindOn,
  spawnKindsPresent,
  TARKOV_SPAWN_KIND_LABELS,
  tarkovSpawnIconAnchor,
  tarkovSpawnIconUrl,
  tarkovSpawnTooltipAnchor,
  withSpawnKindsForPresent,
  type TarkovSpawnKind,
} from "@/lib/tarkovMapSpawns";
import {
  gameForwardXZ,
  gameYawToCssDeg,
  screenDeltaToCssDeg,
} from "@/lib/tarkovScreenshotPos";
import { useTarkovScreenshotPosition } from "@/lib/useTarkovScreenshotPosition";
import styles from "./TarkovMapViewer.module.css";

export type TarkovMapFocusRequest = RaidPrepPoint & { seq: number };

type Props = {
  slug: string;
  parentSlug?: string;
  extracts?: TarkovMapExtract[];
  bosses?: TarkovMapBoss[];
  spawns?: TarkovMapSpawn[];
  questOverlays?: TarkovRaidPrepOverlay[];
  fill?: boolean;
  className?: string;
  boardMarks?: RaidRoomMarkLike[];
  remoteDrafts?: RaidRoomDraftStroke[];
  remotePlayerFixes?: TarkovMapPlayerMark[];
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
  onDraftStroke?: (draft: { floor: string; points: StrokePoint[] } | null) => void;
  onEraseMark?: (markId: number) => void;
  onFloorChange?: (floor: string) => void;
  /** 点击任务点位或名称：打开该任务攻略 */
  onQuestLabelClick?: (taskId: string) => void;
  /** 任务 id → 参与者，供地图悬浮窗展示 */
  questParticipantsByTask?: ReadonlyMap<string, readonly RaidPrepMapParticipant[]>;
  highlightTaskId?: string;
  overlayMode?: TarkovMapOverlayMode;
  layerChrome?: "full" | "floors";
  /** 外部请求将地图平移到指定游戏坐标（seq 递增可重复定位同一点） */
  focusRequest?: TarkovMapFocusRequest | null;
  topRight?: ReactNode;
  /** 库里的自定义地名；有则替换 tarkov.dev / 手写表 */
  places?: TarkovMapPlaceLike[];
  placeEdit?: TarkovMapPlaceEdit;
};

type MapRuntime = {
  map: L.Map;
  svgOverlay?: L.SVGOverlay;
  tileLayer?: L.TileLayer;
  floorTiles: Map<string, L.TileLayer>;
  extracts: L.LayerGroup;
  spawns: L.LayerGroup;
  bosses: L.LayerGroup;
  labels: L.LayerGroup;
  placeBoxes: L.LayerGroup;
  quests: L.LayerGroup;
  questLabels: L.LayerGroup;
  board: L.LayerGroup;
  live: L.LayerGroup;
  mine: L.LayerGroup;
  remote: L.LayerGroup;
  player: L.LayerGroup;
  localStroke?: L.Polyline;
  mineKeys: Set<string>;
  strokeLayers: Map<string, L.Layer>;
  draftLayers: Map<number, L.Layer>;
  playerLayers: Map<string, L.Marker>;
  boardPane?: HTMLElement;
  svgRoot?: SVGSVGElement;
};

const BOARD_PANE = "boardPane";
const SVG_BASE_PANE = "svgBasePane";
const DRAFT_THROTTLE_MS = 48;
const QUEST_LABEL_ZOOM_MS = 80;

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function setSvgFloor(
  root: SVGSVGElement | undefined,
  baseId: string,
  floorId: string,
  keepBaseOpaque = false,
) {
  const inner = root?.children[0];
  if (!root || !inner) return;
  root.classList.toggle(
    "off-level",
    mapBaseOffLevel(floorId, keepBaseOpaque),
  );
  for (const child of Array.from(inner.children)) {
    if (child.nodeName.toLowerCase() !== "g") continue;
    const group = child as SVGGElement;
    if (!group.id) continue;
    const flags = svgFloorGroupClasses(
      { id: group.id, keepWithGroup: group.dataset.keepWithGroup },
      baseId,
      floorId,
    );
    group.classList.toggle("base-layer", flags["base-layer"]);
    group.classList.toggle("overlay-layer", flags["overlay-layer"]);
    group.classList.toggle("hidden-layer", flags["hidden-layer"]);
  }
}

function attachInteractiveTiles(
  runtime: MapRuntime,
  layer: TarkovDevMapLayer,
  bounds: L.LatLngBounds,
  maxZoom: number,
) {
  const tileSize = layer.tileSize || 256;
  if (!runtime.tileLayer && layer.tilePath) {
    runtime.tileLayer = L.tileLayer(layer.tilePath, {
      tileSize,
      bounds,
      maxZoom,
      maxNativeZoom: layer.maxZoom ?? 5,
    });
  }
  for (const floorLayer of layer.layers || []) {
    if (!floorLayer.tilePath || runtime.floorTiles.has(floorLayer.name)) continue;
    runtime.floorTiles.set(
      floorLayer.name,
      L.tileLayer(floorLayer.tilePath, {
        tileSize,
        bounds,
        maxZoom,
        maxNativeZoom: layer.maxZoom ?? 5,
      }),
    );
  }
}

async function attachInteractiveSvg(
  runtime: MapRuntime,
  layer: TarkovDevMapLayer,
  bounds: L.LatLngBounds,
) {
  if (runtime.svgOverlay || !layer.svgPath) return;
  const svg = await loadSvgElement(layer.svgPath);
  runtime.svgRoot = svg;
  setSvgFloor(svg, layer.svgLayer || "", "");
  const svgBounds = getBounds(layer.svgBounds) || bounds;
  runtime.svgOverlay = L.svgOverlay(svg, svgBounds, {
    pane: SVG_BASE_PANE,
    interactive: false,
  });
}

async function loadSvgElement(svgPath: string): Promise<SVGSVGElement> {
  const urls = [svgPath, svgFallbackUrl(svgPath)];
  let lastError: unknown;
  for (const url of urls) {
    try {
      const res = await fetch(url);
      if (!res.ok) continue;
      const text = await res.text();
      const holder = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      holder.setAttribute("xmlns", "http://www.w3.org/2000/svg");
      holder.innerHTML = text;
      const inner = holder.children[0];
      if (inner?.getAttribute("viewBox")) {
        holder.setAttribute("viewBox", inner.getAttribute("viewBox") || "");
      }
      return holder;
    } catch (exc) {
      lastError = exc;
    }
  }
  throw lastError instanceof Error ? lastError : new Error("无法加载 SVG 地图");
}

function addExtractMarkers(
  group: L.LayerGroup,
  extracts: TarkovMapExtract[],
  kindFlags: TarkovExtractKindFlags,
) {
  group.clearLayers();
  for (const row of extracts) {
    if (row.x == null || row.z == null) continue;
    if (!isExtractKindVisible(kindFlags, row.faction)) continue;
    const style = tarkovExtractStyle(row.faction);
    const marker = L.marker(pos({ x: row.x, z: row.z }), {
      icon: L.divIcon({
        className: styles.extractIcon,
        html: `<span class="${styles.extractRow}"><img class="${styles.extractBadge}" src="${escapeHtml(style.iconUrl)}" alt="" width="24" height="24"/><span class="${styles.extractName}" style="color:${style.color}">${escapeHtml(row.name)}</span></span>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      }),
      title: `${row.name}（${row.faction || "撤离"}）`,
      zIndexOffset: style.zIndex,
      riseOnHover: true,
    });
    marker.bindPopup(
      `<div class="${styles.extractPopup}"><img src="${escapeHtml(style.iconUrl)}" alt="" width="18" height="18"/><strong style="color:${style.color}">${escapeHtml(row.name)}</strong><span>${escapeHtml(row.faction || "撤离")}</span></div>`,
    );
    marker.addTo(group);
  }
}

function spawnLeafletIcon(kind: TarkovSpawnKind): L.Icon {
  return L.icon({
    iconUrl: tarkovSpawnIconUrl(kind),
    iconSize: [24, 24],
    iconAnchor: tarkovSpawnIconAnchor(kind),
    tooltipAnchor: tarkovSpawnTooltipAnchor(kind),
    className: styles.spawnIcon,
  });
}

function bindSpawnBubble(marker: L.Marker, html: string) {
  marker.bindTooltip(html, {
    direction: "top",
    opacity: 0.96,
    className: styles.spawnTooltip,
  });
  marker.bindPopup(html);
}

function addPlayerSpawnMarkers(
  group: L.LayerGroup,
  spawns: TarkovMapSpawn[],
  kindFlags: { pmc: boolean; scav: boolean },
) {
  group.clearLayers();
  for (const row of spawns) {
    const kind = String(row.kind || "").trim().toLowerCase();
    if (kind !== "pmc" && kind !== "scav") continue;
    if (!kindFlags[kind]) continue;
    if (row.x == null || row.z == null) continue;
    const label = TARKOV_SPAWN_KIND_LABELS[kind];
    const marker = L.marker(pos({ x: row.x, z: row.z }), {
      icon: spawnLeafletIcon(kind),
      title: label,
      riseOnHover: true,
    });
    const zone = (row.zone_name || "").trim();
    const tip = zone
      ? `<strong>${escapeHtml(label)}</strong><div>${escapeHtml(zone)}</div>`
      : `<strong>${escapeHtml(label)}</strong>`;
    bindSpawnBubble(marker, tip);
    marker.addTo(group);
  }
}

function addBossMarkers(
  group: L.LayerGroup,
  bosses: TarkovMapBoss[],
  mapKey?: string,
) {
  group.clearLayers();
  const icon = spawnLeafletIcon("boss");
  for (const boss of bosses) {
    const label = tarkovBossMapLabel(boss.name);
    const chance =
      boss.spawn_chance != null && boss.spawn_chance > 0
        ? `${boss.spawn_chance}%`
        : "";
    for (const loc of boss.locations || []) {
      for (const point of loc.positions || []) {
        const locLabel = loc.name ? tarkovMapLabel(loc.name, mapKey) : "";
        const parts = [label];
        if (chance) parts.push(chance);
        if (locLabel && locLabel !== label) parts.push(locLabel);
        const marker = L.marker(pos({ x: point.x, z: point.z }), {
          icon,
          title: parts.join(" · "),
          riseOnHover: true,
        });
        const tip = [
          `<strong>${escapeHtml(label)}</strong>`,
          chance ? `<div>出生率 ${escapeHtml(chance)}</div>` : "",
          locLabel && locLabel !== label
            ? `<div>${escapeHtml(locLabel)}</div>`
            : "",
        ]
          .filter(Boolean)
          .join("");
        bindSpawnBubble(marker, tip);
        marker.addTo(group);
      }
    }
  }
}

function setSvgBakedTextHidden(
  root: SVGSVGElement | undefined,
  hidden: boolean,
) {
  if (!root) return;
  if (hidden) root.setAttribute("data-hide-baked-text", "1");
  else root.removeAttribute("data-hide-baked-text");
}

function addLabelMarkers(
  group: L.LayerGroup,
  labels: ResolvedMapPlace[],
  edit?: TarkovMapPlaceEdit,
) {
  group.clearLayers();
  const selecting = edit?.mode === "select";
  for (const label of labels) {
    if (!label.position || label.position.length < 2) continue;
    const rotation = label.rotation || 0;
    const lines = placeNameLines(label.text || "");
    if (!lines.length) continue;
    const box = placeLabelIconSize(lines.join("\n"), PLACE_LABEL_FONT_PX);
    const canEdit = selecting && label.id != null;
    const selected = canEdit && edit?.selectedId === label.id;
    const body = lines
      .map((line) => `<span class="${styles.labelLine}">${escapeHtml(line)}</span>`)
      .join("");
    const rotate = rotation ? `transform:rotate(${rotation}deg)` : "";
    const marker = L.marker(pos({ x: label.position[0], z: label.position[1] }), {
      icon: L.divIcon({
        className: `${styles.labelIcon}${selected ? ` ${styles.labelIconOn}` : ""}`,
        html: `<span class="${styles.labelText}"${rotate ? ` style="${rotate}"` : ""}>${body}</span>`,
        iconSize: [box.w, box.h],
        iconAnchor: [box.w / 2, box.h / 2],
      }),
      interactive: canEdit,
      draggable: canEdit,
      autoPan: false,
    });
    if (canEdit && label.id != null) {
      const id = label.id;
      let dragging = false;
      marker.on("dragstart", () => {
        dragging = true;
      });
      marker.on("click", (event) => {
        L.DomEvent.stopPropagation(event);
        if (dragging) return;
        edit?.onSelect?.(id);
      });
      marker.on("dragend", () => {
        const latlng = marker.getLatLng();
        edit?.onMove?.(id, { x: latlng.lng, z: latlng.lat });
        window.setTimeout(() => {
          dragging = false;
        }, 0);
      });
    }
    marker.addTo(group);
  }
}

function addPlaceBoxes(
  group: L.LayerGroup,
  places: ResolvedMapPlace[],
  edit?: TarkovMapPlaceEdit,
) {
  group.clearLayers();
  const selecting = edit?.mode === "select";
  for (const place of places) {
    if (place.kind !== "box" || place.x == null || place.z == null) continue;
    if (place.x2 == null || place.z2 == null) continue;
    const selected = selecting && place.id != null && edit?.selectedId === place.id;
    const rect = L.rectangle(
      L.latLngBounds(pos({ x: place.x, z: place.z }), pos({ x: place.x2, z: place.z2 })),
      {
        color: selected ? "#e8b84a" : "#c8932a",
        weight: selected ? 2 : 1,
        fillColor: "#c8932a",
        fillOpacity: selected ? 0.18 : 0.08,
        interactive: selecting && place.id != null,
        className: styles.placeBox,
      },
    );
    if (selecting && place.id != null) {
      const id = place.id;
      rect.on("click", (event) => {
        L.DomEvent.stopPropagation(event);
        edit?.onSelect?.(id);
      });
    }
    rect.addTo(group);
  }
}

type QuestBubbleRow = {
  taskId?: string;
  title: string;
  subtitle: string;
  steps?: RaidPrepOverlayStep[];
  color: string;
  traderSlug: string;
  keyNames?: string[];
  showNoKey?: boolean;
  optional?: boolean;
  kind?: "zone" | "spawn";
  height?: RaidPrepHeightSpan | null;
  at?: RaidPrepPoint;
  participants?: readonly RaidPrepMapParticipant[];
};

function questParticipantChipsHtml(
  people: readonly RaidPrepMapParticipant[] | undefined,
): string {
  const list = raidPrepParticipants(people);
  if (!list.length) return "";
  const chips = list
    .map((person) => {
      const color =
        person.userId != null
          ? colorForUserId(person.userId)
          : colorForTaskId(person.name);
      return `<span class="${styles.questTipChip}"><span class="${styles.questTipDot}" style="background:${escapeHtml(color)}"></span>${escapeHtml(person.name)}</span>`;
    })
    .join("");
  return `<span class="${styles.questTipPeople}">${chips}</span>`;
}

function overlayBubbleStepsHtml(row: QuestBubbleRow): string {
  const steps =
    row.steps && row.steps.length
      ? row.steps
      : row.subtitle
        ? [{ text: row.subtitle, active: true }]
        : row.kind === "spawn"
          ? [{ text: "可能刷新点", active: true }]
          : row.kind === "zone"
            ? [{ text: "目标区域", active: true }]
            : [];
  if (!steps.length) return "";
  return `<span class="${styles.questTipSteps}">${steps
    .map((step) => {
      const on = step.active ? ` ${styles.questTipStepOn}` : "";
      const color = step.active
        ? ` style="color:${escapeHtml(row.color)}"`
        : "";
      return `<span class="${styles.questTipStep}${on}"${color}>${escapeHtml(step.text)}</span>`;
    })
    .join("")}</span>`;
}

function overlayBubbleHtml(row: QuestBubbleRow): string {
  const keys = (row.keyNames || [])
    .filter(Boolean)
    .map(
      (name) =>
        `<span class="${styles.questTipKey}">${escapeHtml(name)}</span>`,
    )
    .join("");
  const keyRow = keys
    ? `<span class="${styles.questTipKeys}"><span class="${styles.questTipKeyLabel}">所需钥匙</span>${keys}</span>`
    : "";
  return `<span class="${styles.questTip}"><span class="${styles.questTipRow}">${questTraderImgHtml(row.traderSlug)}<span class="${styles.questTipName}" style="color:${row.color}">${escapeHtml(row.title)}</span></span>${overlayBubbleStepsHtml(row)}${keyRow}${questParticipantChipsHtml(row.participants)}</span>`;
}

function traderSlugForIcon(slug: string): string {
  return slug.trim().toLowerCase().replace(/[^a-z0-9-]/g, "");
}

function questTraderImgHtml(slug: string): string {
  const safe = traderSlugForIcon(slug);
  if (!safe) return "";
  const icon = escapeHtml(traderIconUrl(safe));
  const portrait = escapeHtml(traderPortraitUrl(safe));
  return `<img class="${styles.questTrader}" src="${icon}" alt="" width="20" height="20" onerror="this.onerror=function(){this.remove()};this.src='${portrait}'">`;
}

function questLabelLineHtml(
  item: RaidPrepOverlayLabelItem,
  offFloor = false,
): string {
  const title = item.optional ? `${item.title}（可选）` : item.title;
  const keyMark = item.keyNames.length
    ? `<span class="${styles.questLabelKey}">${escapeHtml(formatRaidPrepOverlayKeyLabel(item.keyNames, item.showNoKey) || "钥匙")}</span>`
    : "";
  const dim = offFloor ? ` ${styles.questLabelOff}` : "";
  return `<span class="${styles.questLabelRow}${dim}" data-task-id="${escapeHtml(item.taskId)}">${questTraderImgHtml(item.traderSlug)}<span class="${styles.questName}" style="color:${item.color}">${escapeHtml(title)}</span>${keyMark}</span>`;
}

function applyQuestLabelHighlight(
  root: HTMLElement | undefined,
  highlightTaskId: string,
) {
  if (!root) return;
  const on = (highlightTaskId || "").trim();
  for (const node of root.querySelectorAll<HTMLElement>("[data-task-id]")) {
    const id = node.getAttribute("data-task-id") || "";
    if (on && id === on) node.setAttribute("data-on", "true");
    else node.removeAttribute("data-on");
  }
}

function overlayByLabelItem(
  overlays: TarkovRaidPrepOverlay[],
): Map<string, TarkovRaidPrepOverlay> {
  const map = new Map<string, TarkovRaidPrepOverlay>();
  for (const row of overlays) {
    const key = `${row.taskId}\0${row.optional ? "1" : "0"}\0${row.title}`;
    if (!map.has(key)) map.set(key, row);
  }
  return map;
}

type QuestClickHandler = (
  taskId: string,
  height?: RaidPrepHeightSpan | null,
  at?: RaidPrepPoint,
) => boolean | void;

function bindQuestBubble(
  layer: L.Layer,
  row: QuestBubbleRow,
  onClick?: QuestClickHandler,
) {
  const html = overlayBubbleHtml(row);
  layer.bindTooltip(html, {
    direction: "top",
    opacity: 1,
    sticky: true,
    className: styles.questTooltip,
  });
  const taskId = (row.taskId || "").trim();
  if (!onClick || !taskId) return;
  layer.on("click", (event) => {
    const handled = onClick(taskId, row.height, row.at);
    if (handled === false) return;
    L.DomEvent.stopPropagation(event);
  });
}

function overlayFloorAt(
  row: { points?: RaidPrepPoint[]; outline?: RaidPrepPoint[] } | null | undefined,
): RaidPrepPoint | undefined {
  return row?.points?.[0] || row?.outline?.[0];
}

function questBubbleFromOverlay(
  row: TarkovRaidPrepOverlay,
  namesByTask?: ReadonlyMap<string, readonly RaidPrepMapParticipant[]>,
): QuestBubbleRow {
  return {
    taskId: row.taskId,
    title: row.title,
    subtitle: row.subtitle,
    steps: row.steps,
    color: row.color,
    traderSlug: row.traderSlug,
    keyNames: row.keyNames,
    showNoKey: row.showNoKey,
    optional: row.optional,
    kind: row.kind,
    height: row.height,
    at: overlayFloorAt(row),
    participants: raidPrepParticipants(namesByTask?.get(row.taskId)),
  };
}

function addQuestOverlays(
  group: L.LayerGroup,
  overlays: TarkovRaidPrepOverlay[],
  namesByTask: ReadonlyMap<string, readonly RaidPrepMapParticipant[]> | undefined,
  onClick: QuestClickHandler | undefined,
  floor: string,
  floorBands: ReturnType<typeof mapLayerFloorBands>,
) {
  group.clearLayers();
  for (const row of overlays) {
    const bubble = questBubbleFromOverlay(row, namesByTask);
    const onFloor = overlayVisibleOnFloor(
      row.height,
      floor,
      floorBands,
      overlayFloorAt(row),
    );
    const fade = onFloor ? 1 : RAID_ROOM_OTHER_FLOOR_OPACITY;
    if (row.outline.length >= 3) {
      const polygon = L.polygon(
        row.outline.map((point) => pos({ x: point.x, z: point.z })),
        {
          color: row.color,
          weight: 2,
          dashArray: row.optional ? "5 4" : undefined,
          fillColor: row.color,
          opacity: fade,
          fillOpacity: (row.optional ? 0.1 : 0.18) * fade,
          className: styles.questHit,
        },
      );
      bindQuestBubble(polygon, bubble, onClick);
      polygon.addTo(group);
    }
    for (const point of row.points) {
      const marker = L.circleMarker(pos({ x: point.x, z: point.z }), {
        radius: row.kind === "spawn" ? 5 : 7,
        color: "#111",
        weight: 1,
        dashArray: row.optional ? "3 2" : undefined,
        fillColor: row.color,
        opacity: fade,
        fillOpacity: (row.optional ? 0.55 : 0.92) * fade,
        className: styles.questHit,
      });
      bindQuestBubble(marker, bubble, onClick);
      marker.addTo(group);
    }
  }
}

/** Leaflet 在首次 setView/fitBounds 前调用 latLngToLayerPoint 会抛错。 */
function isLeafletViewReady(map: L.Map): boolean {
  return Boolean((map as unknown as { _loaded?: boolean })._loaded);
}

function questLabelProject(map: L.Map) {
  return (point: { x: number; z: number }) => {
    const layer = map.latLngToLayerPoint(L.latLng(pos(point)));
    return { x: layer.x, z: layer.y };
  };
}

function addQuestLabels(
  group: L.LayerGroup,
  overlays: TarkovRaidPrepOverlay[],
  map: L.Map,
  onLabelClick: QuestClickHandler | undefined,
  namesByTask: ReadonlyMap<string, readonly RaidPrepMapParticipant[]> | undefined,
  floor: string,
  floorBands: ReturnType<typeof mapLayerFloorBands>,
) {
  group.clearLayers();
  /* 抽象图 SVG 异步加载期间 map 已创建但尚未 fitBounds，此时投影会白屏 */
  if (!isLeafletViewReady(map)) return;
  const labels = clusterRaidPrepOverlayLabels(overlays, {
    gap: RAID_PREP_LABEL_CLUSTER_PX,
    project: questLabelProject(map),
  });
  const byItem = overlayByLabelItem(overlays);
  const lineH = 22;
  for (const label of labels) {
    label.items.forEach((item, index) => {
      const source = byItem.get(
        `${item.taskId}\0${item.optional ? "1" : "0"}\0${item.title}`,
      );
      const at = overlayFloorAt(source) || { x: label.x, z: label.z };
      const offFloor = !overlayVisibleOnFloor(
        item.height,
        floor,
        floorBands,
        at,
      );
      const marker = L.marker(pos({ x: label.x, z: label.z }), {
        icon: L.divIcon({
          className: styles.questIcon,
          html: `<span class="${styles.questLabelStack}">${questLabelLineHtml(item, offFloor)}</span>`,
          iconSize: [1, 1],
          iconAnchor: [0, -index * lineH],
        }),
        interactive: true,
        keyboard: false,
        bubblingMouseEvents: false,
      });
      bindQuestBubble(
        marker,
        {
          taskId: item.taskId,
          title: item.title,
          subtitle: source?.subtitle || item.subtitle,
          steps: source?.steps,
          color: item.color,
          traderSlug: item.traderSlug,
          keyNames: item.keyNames,
          showNoKey: item.showNoKey,
          optional: item.optional,
          height: item.height,
          at,
          participants: raidPrepParticipants(namesByTask?.get(item.taskId)),
        },
        onLabelClick,
      );
      marker.addTo(group);
    });
  }
}

function playerHeadingCssDeg(
  mark: TarkovMapPlayerMark,
  map: L.Map | undefined,
  mapRotation: number,
): number | null {
  if (mark.yaw == null) return null;
  if (map) {
    const step = gameForwardXZ(mark.yaw);
    const from = map.latLngToLayerPoint(L.latLng(pos({ x: mark.x, z: mark.z })));
    const to = map.latLngToLayerPoint(
      L.latLng(pos({ x: mark.x + step.x, z: mark.z + step.z })),
    );
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    if (dx !== 0 || dy !== 0) return screenDeltaToCssDeg(dx, dy);
  }
  return gameYawToCssDeg(mark.yaw, mapRotation);
}

function playerFixMarkerHtml(
  mark: TarkovMapPlayerMark,
  map: L.Map | undefined,
  mapRotation: number,
  currentFloor: string,
  floorBands: ReturnType<typeof mapLayerFloorBands>,
): { html: string; name: string } {
  const yaw = playerHeadingCssDeg(mark, map, mapRotation);
  const floor = overlayFloorForPoint(mark.y, floorBands, mark);
  const current = !floor || !currentFloor || floor === currentFloor;
  const color = escapeHtml(mark.color);
  const name = escapeHtml(playerFixMarkerCaption(mark.name));
  const pip =
    yaw == null
      ? `<span class="${styles.playerDot}"></span>`
      : `<span class="${styles.playerArrow}" style="transform:rotate(${yaw}deg)"></span>`;
  const label = name
    ? `<span class="${styles.playerName}">${name}</span>`
    : "";
  return {
    name,
    html: `<span class="${styles.playerMark}" style="color:${color};opacity:${current ? 1 : RAID_ROOM_OTHER_FLOOR_OPACITY}"><span class="${styles.playerGlow}"></span>${pip}${label}</span>`,
  };
}

function syncPlayerFixMarkers(
  runtime: MapRuntime,
  marks: TarkovMapPlayerMark[],
  mapRotation = 0,
  currentFloor = "",
  floorBands: ReturnType<typeof mapLayerFloorBands> = [],
) {
  const group = runtime.player;
  const keep = new Set(marks.map((mark) => mark.key));
  for (const [key, layer] of [...runtime.playerLayers.entries()]) {
    if (keep.has(key)) continue;
    group.removeLayer(layer);
    runtime.playerLayers.delete(key);
  }
  for (const mark of marks) {
    const { html, name } = playerFixMarkerHtml(
      mark,
      runtime.map,
      mapRotation,
      currentFloor,
      floorBands,
    );
    const icon = L.divIcon({
      className: styles.playerIcon,
      html,
      iconSize: [32, name ? 44 : 32],
      iconAnchor: [16, 16],
    });
    let marker = runtime.playerLayers.get(mark.key);
    if (!marker) {
      marker = L.marker(pos({ x: mark.x, z: mark.z }), {
        icon,
        interactive: false,
        keyboard: false,
        zIndexOffset: mark.self ? 920 : 900,
      });
      marker.addTo(group);
      runtime.playerLayers.set(mark.key, marker);
      continue;
    }
    marker.setLatLng(pos({ x: mark.x, z: mark.z }));
    marker.setIcon(icon);
    marker.setZIndexOffset(mark.self ? 920 : 900);
  }
}

function syncRemoteDrafts(
  runtime: MapRuntime,
  drafts: RaidRoomDraftStroke[],
  floor: string,
) {
  const keep = new Set(
    drafts.map((row) => row.userId).filter((id): id is number => Boolean(id)),
  );
  for (const [userId, layer] of [...runtime.draftLayers.entries()]) {
    if (keep.has(userId)) continue;
    runtime.remote.removeLayer(layer);
    runtime.draftLayers.delete(userId);
  }
  for (const draft of drafts) {
    const userId = draft.userId;
    if (!userId) continue;
    const current = markMatchesFloor(draft, floor);
    const existing = runtime.draftLayers.get(userId);
    if (existing instanceof L.Polyline) {
      existing.setLatLngs(strokeLatLngs(draft.points));
      existing.setStyle(strokePathOptions(draft.color, current, false));
      continue;
    }
    if (existing) {
      runtime.remote.removeLayer(existing);
      runtime.draftLayers.delete(userId);
    }
    const painted = addStrokeLayer(
      runtime.remote,
      draft.points,
      draft.color,
      current,
      false,
    );
    if (painted) runtime.draftLayers.set(userId, painted);
  }
}

function attachPanPerfGuards(map: L.Map, wrapEl: HTMLElement) {
  const setPanning = (on: boolean) => {
    wrapEl.classList.toggle(styles.isPanning, on);
    /* 拖动中关掉气泡即可；Leaflet 在尚未 bind tooltip / 初次 fitBounds 时
       closeTooltip() 会读到 undefined.close，把整张底图初始化打崩。 */
    if (on) {
      try {
        const tooltip = (
          map as unknown as { _tooltip?: { _close?: () => void } | null }
        )._tooltip;
        if (tooltip && typeof tooltip._close === "function") {
          tooltip._close();
        }
      } catch {
        /* ignore */
      }
    }
  };
  const onStart = () => setPanning(true);
  const onEnd = () => setPanning(false);
  map.on("dragstart", onStart);
  map.on("zoomstart", onStart);
  map.on("dragend", onEnd);
  map.on("zoomend", onEnd);
  return () => {
    map.off("dragstart", onStart);
    map.off("zoomstart", onStart);
    map.off("dragend", onEnd);
    map.off("zoomend", onEnd);
    wrapEl.classList.remove(styles.isPanning);
  };
}

function attachZoomControl(map: L.Map) {
  L.control
    .zoom({
      position: "bottomleft",
      zoomInTitle: "放大",
      zoomOutTitle: "缩小",
    })
    .addTo(map);
}

function strokePathOptions(
  color: string,
  current: boolean,
  interactive: boolean,
): L.PolylineOptions {
  const opacity = current ? 1 : RAID_ROOM_OTHER_FLOOR_OPACITY;
  return {
    color,
    weight: interactive ? 10 : current ? 4 : 2.5,
    opacity,
    lineCap: "round",
    lineJoin: "round",
    smoothFactor: 0.75,
    interactive,
    bubblingMouseEvents: false,
    pane: BOARD_PANE,
  };
}

function strokeLatLngs(points: StrokePoint[]): L.LatLngExpression[] {
  if (!points.length) return [];
  if (points.length === 1) {
    const point = points[0];
    return [pos(point), pos({ x: point.x + 0.45, z: point.z })];
  }
  return points.map((point) => pos(point));
}

function addStrokeLayer(
  group: L.LayerGroup,
  points: StrokePoint[],
  color: string,
  current: boolean,
  interactive: boolean,
  title?: string,
): L.Layer | null {
  if (!points.length) return null;
  const layer = L.polyline(
    strokeLatLngs(points),
    strokePathOptions(color, current, interactive),
  );
  if (title) layer.bindTooltip(title, { direction: "top" });
  layer.addTo(group);
  return layer;
}

function renderLocalDraft(
  runtime: MapRuntime,
  points: StrokePoint[],
  color: string,
) {
  if (!points.length) {
    runtime.localStroke?.remove();
    runtime.localStroke = undefined;
    return;
  }
  const latlngs = strokeLatLngs(points);
  if (runtime.localStroke) {
    runtime.localStroke.setLatLngs(latlngs);
    runtime.localStroke.setStyle(strokePathOptions(color, true, false));
    return;
  }
  runtime.localStroke = L.polyline(
    latlngs,
    strokePathOptions(color, true, false),
  ).addTo(runtime.live);
}

function strokeToMark(
  stroke: { floor: string; points: StrokePoint[] },
  authorUserId: number,
): RaidRoomMarkLike {
  const first = stroke.points[0];
  const last = stroke.points[stroke.points.length - 1] || first;
  return {
    id: -Date.now(),
    kind: "stroke",
    floor: stroke.floor,
    x: first.x,
    z: first.z,
    x2: last.x,
    z2: last.z,
    points: stroke.points.map((point) => [point.x, point.z]),
    author_user_id: authorUserId,
  };
}

function parkLocalStroke(
  runtime: MapRuntime,
  points: StrokePoint[],
  color: string,
  floor: string,
) {
  const key = strokeFingerprint(strokeToMark({ floor, points }, 0));
  runtime.mineKeys.add(key);
  const line = runtime.localStroke;
  runtime.localStroke = undefined;
  if (line) {
    line.setLatLngs(strokeLatLngs(points));
    line.setStyle(strokePathOptions(color, true, false));
    runtime.live.removeLayer(line);
    if (!runtime.mine.hasLayer(line)) runtime.mine.addLayer(line);
    runtime.strokeLayers.set(key, line);
    return;
  }
  const painted = addStrokeLayer(runtime.mine, points, color, true, false);
  if (painted) runtime.strokeLayers.set(key, painted);
}

function addPinLayer(
  group: L.LayerGroup,
  mark: RaidRoomMarkLike,
  current: boolean,
  interactive: boolean,
): L.Layer {
  const opacity = current ? 1 : RAID_ROOM_OTHER_FLOOR_OPACITY;
  const layer = L.circleMarker(pos({ x: mark.x, z: mark.z }), {
    radius: interactive ? 10 : current ? 7 : 5,
    color: "#111",
    weight: 1,
    fillColor: colorForUserId(mark.author_user_id),
    fillOpacity: opacity,
    opacity,
    interactive,
    pane: BOARD_PANE,
  });
  const title = mark.author_display_name || "";
  if (title) layer.bindTooltip(title, { direction: "top" });
  layer.addTo(group);
  return layer;
}

function bindEraseHandler(
  layer: L.Layer,
  markId: number,
  eraseMode: boolean,
  onErase?: (markId: number) => void,
) {
  layer.off("click");
  if (!eraseMode) return;
  layer.on("click", (event: L.LeafletMouseEvent) => {
    L.DomEvent.stop(event);
    onErase?.(markId);
  });
}

function addBoardMarks(
  runtime: MapRuntime,
  marks: RaidRoomMarkLike[],
  currentFloor: string,
  eraseMode: boolean,
  onErase?: (markId: number) => void,
) {
  const group = runtime.board;
  const keep = new Set(marks.map((mark) => strokeFingerprint(mark)));
  for (const key of [...runtime.mineKeys]) {
    keep.add(key);
  }
  for (const [key, layer] of [...runtime.strokeLayers.entries()]) {
    if (keep.has(key)) continue;
    group.removeLayer(layer);
    runtime.mine.removeLayer(layer);
    runtime.strokeLayers.delete(key);
    runtime.mineKeys.delete(key);
  }
  for (const mark of marks) {
    const key = strokeFingerprint(mark);
    if (runtime.mineKeys.has(key)) {
      const mineLayer = runtime.strokeLayers.get(key);
      if (mineLayer) bindEraseHandler(mineLayer, mark.id, eraseMode, onErase);
      continue;
    }
    const current = markMatchesFloor(mark, currentFloor);
    const color = colorForUserId(mark.author_user_id);
    const title = mark.author_display_name || "";
    let layer = runtime.strokeLayers.get(key);
    if (!layer) {
      if (mark.kind === "line" || mark.kind === "stroke") {
        const painted = addStrokeLayer(
          group,
          markStrokePoints(mark),
          color,
          current,
          eraseMode,
          title,
        );
        if (!painted) continue;
        layer = painted;
      } else {
        layer = addPinLayer(group, mark, current, eraseMode);
      }
      runtime.strokeLayers.set(key, layer);
    } else if (layer instanceof L.Polyline) {
      layer.setStyle(strokePathOptions(color, current, eraseMode));
    }
    bindEraseHandler(layer, mark.id, eraseMode, onErase);
  }
}

export function TarkovMapViewer({
  slug,
  parentSlug,
  extracts = [],
  bosses = [],
  spawns = [],
  questOverlays = [],
  fill = false,
  className = "",
  boardMarks = [],
  remoteDrafts = [],
  remotePlayerFixes = [],
  suppressLocalFix = false,
  drawColor = "#c8932a",
  authorUserId = 0,
  authorDisplayName = "",
  drawMode = "pan",
  onStroke,
  onPin,
  onLine,
  onDraftStroke,
  onEraseMark,
  onFloorChange,
  onQuestLabelClick,
  questParticipantsByTask,
  highlightTaskId = "",
  overlayMode = "all",
  layerChrome = "full",
  focusRequest,
  topRight,
  places = [],
  placeEdit,
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
  const lineStartRef = useRef<StrokePoint | null>(null);
  const onDraftStrokeRef = useRef(onDraftStroke);
  const onEraseMarkRef = useRef(onEraseMark);
  const onQuestLabelClickRef = useRef(onQuestLabelClick);
  const placeEditRef = useRef(placeEdit);
  const drawColorRef = useRef(drawColor);
  const authorUserIdRef = useRef(authorUserId);
  const overlaySigRef = useRef("");
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
  const floorRef = useRef("");
  const styleRef = useRef("");
  const coordsElRef = useRef<HTMLDivElement | null>(null);
  const wrapElRef = useRef<HTMLDivElement | null>(null);
  const shotWatch = useTarkovScreenshotPosition();
  const playerFixSigRef = useRef("");
  const shotResumeOnceRef = useRef(false);
  const [prefs, setPrefs] = useState(loadTarkovMapViewerPrefs);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(0);
  const [spaceHeld, setSpaceHeld] = useState(false);
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
  const floor = resolveMapFloor(
    prefs.floorsByMap[interactive?.key || ""],
    floorNames,
  );
  const visiblePlaces = useMemo(
    () =>
      placeLabels.filter((row) => placeVisibleOnFloor(row.floor, floor)),
    [placeLabels, floor],
  );
  const floorBands = useMemo(
    () => mapLayerFloorBands(interactive),
    [interactive],
  );
  const questPeople = useMemo(
    () => collectRaidPrepQuestFilterPeople(questParticipantsByTask),
    [questParticipantsByTask],
  );
  useEffect(() => {
    if (questPersonSeededRef.current) return;
    const off = defaultQuestPersonOffKeys(questPeople, authorUserId);
    if (off == null) return;
    questPersonSeededRef.current = true;
    setQuestPersonOff(new Set(off));
  }, [questPeople, authorUserId]);
  const questTree = questOverlays.length > 0 && questPeople.length >= 2;
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
      questOverlays.filter((row) =>
        raidPrepQuestOverlayVisible(
          raidPrepParticipants(questParticipantsByTask?.get(row.taskId)),
          selectedQuestKeys,
        ),
      ),
    [questOverlays, questParticipantsByTask, selectedQuestKeys],
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
          const people = raidPrepParticipants(
            displayedParticipantsByTask?.get(row.taskId),
          );
          const sig = people
            .map((person) => `${person.userId ?? ""}:${person.name}`)
            .join(",");
          return `${row.key}:${sig}`;
        })
        .join("\0") + `\0${floor}`,
    [displayedQuestOverlays, displayedParticipantsByTask, floor],
  );
  const highlightTaskIdRef = useRef(highlightTaskId);
  highlightTaskIdRef.current = highlightTaskId;
  const overlay = overlayFlagsForMode(prefs, overlayMode);
  const { extractKinds, spawnKinds, showLabels, showQuests } = overlay;
  const showPointLayers = layerChrome !== "floors";
  const extractKindOptions = TARKOV_EXTRACT_KINDS;
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
  onDraftStrokeRef.current = onDraftStroke;
  onEraseMarkRef.current = onEraseMark;
  onQuestLabelClickRef.current = onQuestLabelClick;
  placeEditRef.current = placeEdit;
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
        saveTarkovMapViewerPrefs(next);
        return next;
      });
    },
    [],
  );
  updatePrefsRef.current = updatePrefs;

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
    onFloorChange?.(floor);
  }, [floor, onFloorChange]);

  useEffect(() => {
    const el = mapDivRef.current;
    if (!el) return;
    let cancelled = false;
    let detachDraw = () => {};
    const runtime: MapRuntime = {
      map: null as unknown as L.Map,
      floorTiles: new Map(),
      extracts: L.layerGroup(),
      spawns: L.layerGroup(),
      bosses: L.layerGroup(),
      labels: L.layerGroup(),
      placeBoxes: L.layerGroup(),
      quests: L.layerGroup(),
      questLabels: L.layerGroup(),
      board: L.layerGroup(),
      live: L.layerGroup(),
      mine: L.layerGroup(),
      remote: L.layerGroup(),
      player: L.layerGroup(),
      mineKeys: new Set(),
      strokeLayers: new Map(),
      draftLayers: new Map(),
      playerLayers: new Map(),
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
      attachZoomControl(map);
      const scaled = getScaledBounds(layer.bounds || [], 1.5);
      if (scaled) map.setMaxBounds(scaled);
      map.createPane(BOARD_PANE);
      const boardPane = map.getPane(BOARD_PANE);
      if (boardPane) {
        boardPane.style.zIndex = "650";
        boardPane.style.pointerEvents = "none";
        runtime.boardPane = boardPane;
      }
      map.createPane(SVG_BASE_PANE);
      const svgPane = map.getPane(SVG_BASE_PANE);
      if (svgPane) {
        svgPane.style.zIndex = "250";
        svgPane.style.pointerEvents = "none";
      }
      map.on("mousemove", (event: L.LeafletMouseEvent) => {
        const node = coordsElRef.current;
        if (!node) return;
        node.textContent = `x ${event.latlng.lng.toFixed(1)}  z ${event.latlng.lat.toFixed(1)}`;
        node.hidden = false;
      });
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
        if (spaceHeldRef.current) return;
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
      runtime.extracts.addTo(map);
      runtime.spawns.addTo(map);
      runtime.bosses.addTo(map);
      runtime.labels.addTo(map);
      runtime.placeBoxes.addTo(map);
      runtime.quests.addTo(map);
      runtime.questLabels.addTo(map);
      runtime.board.addTo(map);
      runtime.mine.addTo(map);
      runtime.live.addTo(map);
      runtime.remote.addTo(map);
      runtime.player.addTo(map);
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
      attachZoomControl(map);
      const bounds = L.latLngBounds([0, 0], [img.height, img.width]);
      L.imageOverlay(url, bounds).addTo(map);
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
      runtimeRef.current = null;
      runtime.map?.remove();
    };
  }, [interactive, raster]);

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
        }
        if (runtime.svgOverlay) {
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

  const handleQuestClick = useCallback<QuestClickHandler>((taskId, height, at) => {
    if (isMapDrawTool(drawModeRef.current)) return false;
    const nextFloor = overlayFloorForSpan(height, floorBandsRef.current, at);
    if (nextFloor !== floorRef.current) {
      const mapKey = interactiveKeyRef.current;
      if (mapKey) {
        updatePrefsRef.current((prev) =>
          withMapFloor(prev, mapKey, nextFloor),
        );
      }
      return true;
    }
    onQuestLabelClickRef.current?.(taskId);
    return true;
  }, []);

  useEffect(() => {
    const runtime = runtimeRef.current;
    if (!ready || !runtime?.map || !interactive) return;
    if (anyPresentExtractKindOn(extractKinds, extractKindOptions)) {
      addExtractMarkers(runtime.extracts, extracts, extractKinds);
    } else runtime.extracts.clearLayers();
    if (spawnKinds.pmc || spawnKinds.scav) {
      addPlayerSpawnMarkers(runtime.spawns, spawns, {
        pmc: spawnKinds.pmc,
        scav: spawnKinds.scav,
      });
    } else runtime.spawns.clearLayers();
    if (spawnKinds.boss) {
      addBossMarkers(
        runtime.bosses,
        bosses,
        interactive.normalizedName || interactive.key,
      );
    } else runtime.bosses.clearLayers();
    const showPlaceLayer = showLabels || Boolean(placeEdit);
    if (showPlaceLayer) {
      const edit = {
        mode: placeEdit?.mode ?? "off",
        selectedId: placeEdit?.selectedId,
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
      addLabelMarkers(runtime.labels, visiblePlaces, placeEdit ? edit : undefined);
      addPlaceBoxes(runtime.placeBoxes, visiblePlaces, placeEdit ? edit : undefined);
    } else {
      runtime.labels.clearLayers();
      runtime.placeBoxes.clearLayers();
    }
    setSvgBakedTextHidden(
      runtime.svgRoot,
      showPlaceLayer && visiblePlaces.length > 0,
    );
  }, [
    extracts,
    bosses,
    spawns,
    extractKinds,
    spawnKinds,
    showLabels,
    interactive,
    visiblePlaces,
    placeEdit?.mode,
    placeEdit?.selectedId,
    Boolean(placeEdit),
    ready,
    extractKindOptions,
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
  ]);

  useEffect(() => {
    const runtime = runtimeRef.current;
    const map = runtime?.map;
    if (!ready || !runtime || !map) return undefined;
    if (!showQuests) {
      runtime.questLabels.clearLayers();
      return undefined;
    }
    addQuestLabels(
      runtime.questLabels,
      displayedQuestOverlays,
      map,
      handleQuestClick,
      displayedParticipantsByTask,
      floor,
      floorBands,
    );
    applyQuestLabelHighlight(map.getContainer(), highlightTaskIdRef.current);
    let zoomTimer = 0;
    const refreshQuestLabels = () => {
      window.clearTimeout(zoomTimer);
      zoomTimer = window.setTimeout(() => {
        addQuestLabels(
          runtime.questLabels,
          displayedQuestOverlays,
          map,
          handleQuestClick,
          displayedParticipantsByTask,
          floor,
          floorBands,
        );
        applyQuestLabelHighlight(map.getContainer(), highlightTaskIdRef.current);
      }, QUEST_LABEL_ZOOM_MS);
    };
    map.on("zoomend", refreshQuestLabels);
    return () => {
      window.clearTimeout(zoomTimer);
      map.off("zoomend", refreshQuestLabels);
    };
  }, [
    displayedQuestOverlays,
    displayedParticipantsByTask,
    floor,
    floorBands,
    showQuests,
    ready,
    handleQuestClick,
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
      (markId) => onEraseMarkRef.current?.(markId),
    );
  }, [visibleMarks, floor, drawMode, ready]);

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
    const refresh = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        const map = runtimeRef.current?.map;
        if (!map) return;
        if (wrap.clientWidth < 2 || wrap.clientHeight < 2) return;
        map.invalidateSize({ animate: false });
      }, 80);
    };
    refresh();
    const ro =
      typeof ResizeObserver === "undefined" ? null : new ResizeObserver(refresh);
    ro?.observe(wrap);
    window.addEventListener("resize", refresh);
    return () => {
      window.clearTimeout(timer);
      ro?.disconnect();
      window.removeEventListener("resize", refresh);
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
      const zoom = Math.max(current.getZoom(), current.getMinZoom() + 1);
      current.flyTo(latLng, zoom, { animate: true, duration: 0.35 });
    };
    fly();
    const timer = window.setTimeout(fly, 180);
    return () => window.clearTimeout(timer);
  }, [focusRequest, ready, floorBands, interactive?.key, updatePrefs]);

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
    if (!fix) return;
    const sig = `${fix.fileName}:${fix.lastModified}`;
    if (playerFixSigRef.current === sig) return;
    const hadFix = Boolean(playerFixSigRef.current);
    playerFixSigRef.current = sig;
    const mapKey = interactive?.key || "";
    const nextFloor = overlayFloorForPoint(fix.y, floorBands, fix);
    if (mapKey && nextFloor !== floorRef.current) {
      updatePrefs((prev) => withMapFloor(prev, mapKey, nextFloor));
    }
    const latLng = L.latLng(pos({ x: fix.x, z: fix.z }));
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

  useEffect(() => {
    const map = runtimeRef.current?.map;
    const pane = runtimeRef.current?.boardPane;
    if (!map) return;
    const drawing =
      ((isMapDrawTool(drawMode) || isPlaceEditTool(placeEdit?.mode)) &&
        !spaceHeld);
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
  }, [drawMode, placeEdit?.mode, spaceHeld, ready]);

  useEffect(() => {
    if (drawMode !== "line") lineStartRef.current = null;
    const map = runtimeRef.current?.map;
    if (!ready || !map) return undefined;
    const onClick = (event: L.LeafletMouseEvent) => {
      const mode = drawModeRef.current;
      if (mode !== "pin" && mode !== "line") return;
      if (spaceHeldRef.current) return;
      const floor = floorRef.current;
      const x = event.latlng.lng;
      const z = event.latlng.lat;
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
    const map = runtimeRef.current?.map;
    if (!ready || !map) return undefined;
    const onClick = (event: L.LeafletMouseEvent) => {
      const edit = placeEditRef.current;
      if (edit?.mode !== "point") return;
      if (spaceHeldRef.current) return;
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
      if (spaceHeldRef.current) return;
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

  if (!interactive && !raster) {
    return (
      <div className={styles.status}>这张图还没有可嵌入的底图。</div>
    );
  }

  return (
    <div
      ref={wrapElRef}
      className={`${styles.wrap} ${fill ? styles.wrapFill : ""} ${topRight ? styles.wrapTopRight : ""} ${isMapDrawTool(drawMode) ? styles.wrapDraw : ""} ${drawMode === "erase" ? styles.wrapErase : ""} ${isPlaceEditTool(placeEdit?.mode) ? styles.wrapPlaceEdit : ""} ${placeEdit?.mode === "select" ? styles.wrapPlaceSelect : ""} ${spaceHeld ? styles.wrapSpace : ""} ${className}`.trim()}
      onPointerDown={() => {
        if (suppressLocalFix) return;
        if (shotResumeOnceRef.current) return;
        if (shotWatch.perm !== "prompt" || !shotWatch.hasStored) return;
        shotResumeOnceRef.current = true;
        void shotWatch.enable();
      }}
    >
      <div className={styles.map} ref={mapDivRef} />
      {topRight ? <div className={styles.topRight}>{topRight}</div> : null}
      {loading ? (
        <div className={`${styles.status} ${styles.overlay}`}>
          <Spin />
        </div>
      ) : null}
      {error ? (
        <div className={`${styles.status} ${styles.overlay}`}>{error}</div>
      ) : null}
      {canSvg || canTile || floors.length || interactive ? (
        <div className={styles.filterPanel} aria-label="地图筛选">
          {canSvg || canTile ? (
            <div className={styles.filterGroup} role="radiogroup" aria-label="底图样式">
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
              <div className={styles.filterGroup} role="radiogroup" aria-label="切换高度">
                <label className={styles.filterRow}>
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
                  <label key={item.name} className={styles.filterRow}>
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
              </div>
            </>
          ) : null}
          {showPointLayers && interactive ? (
            <>
              {canSvg || canTile || floors.length ? (
                <span className={styles.filterSplit} aria-hidden="true" />
              ) : null}
              <div className={styles.filterGroup} aria-label="展示点位">
                <div className={styles.filterSubgroup}>
                  <label className={styles.filterRow}>
                    <input
                      ref={extractsParentRef}
                      className={styles.filterCheck}
                      type="checkbox"
                      checked={extractsParentOn}
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
                    <span>撤离点</span>
                  </label>
                  {extractKindOptions.map((kind) => (
                    <label
                      key={kind}
                      className={`${styles.filterRow} ${styles.filterRowChild}`}
                    >
                      <input
                        className={styles.filterCheck}
                        type="checkbox"
                        checked={extractKinds[kind]}
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
                      <img
                        className={styles.filterIcon}
                        src={tarkovExtractIconUrl(kind)}
                        alt=""
                        width={14}
                        height={14}
                      />
                      <span>{TARKOV_EXTRACT_KIND_LABELS[kind]}</span>
                    </label>
                  ))}
                </div>
                {spawnKindOptions.length ? (
                  <div className={styles.filterSubgroup}>
                    <label className={styles.filterRow}>
                      <input
                        ref={spawnsParentRef}
                        className={styles.filterCheck}
                        type="checkbox"
                        checked={spawnsParentOn}
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
                      <span>出生点</span>
                    </label>
                    {spawnKindOptions.map((kind) => (
                      <label
                        key={kind}
                        className={`${styles.filterRow} ${styles.filterRowChild}`}
                      >
                        <input
                          className={styles.filterCheck}
                          type="checkbox"
                          checked={spawnKinds[kind]}
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
                        <img
                          className={styles.filterIcon}
                          src={tarkovSpawnIconUrl(kind)}
                          alt=""
                          width={14}
                          height={14}
                        />
                        <span>{TARKOV_SPAWN_KIND_LABELS[kind]}</span>
                      </label>
                    ))}
                  </div>
                ) : null}
                {placeLabels.length ? (
                  <label className={styles.filterRow}>
                    <input
                      className={styles.filterCheck}
                      type="checkbox"
                      checked={showLabels}
                      onChange={() =>
                        updatePrefs({ showLabels: !showLabels })
                      }
                    />
                    <span>地名</span>
                  </label>
                ) : null}
                {questOverlays.length ? (
                  questTree ? (
                    <div className={styles.filterSubgroup}>
                      <label className={styles.filterRow}>
                        <input
                          ref={questsParentRef}
                          className={styles.filterCheck}
                          type="checkbox"
                          checked={questsParentOn}
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
                        <span>任务</span>
                      </label>
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
                                  questPeople.map((person) =>
                                    raidPrepPersonKey(person),
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
                    </div>
                  ) : (
                    <label className={styles.filterRow}>
                      <input
                        className={styles.filterCheck}
                        type="checkbox"
                        checked={showQuests}
                        onChange={() =>
                          updatePrefs({ showQuests: !showQuests })
                        }
                      />
                      <span>任务</span>
                    </label>
                  )
                ) : null}
                {shotWatch.supported ? (
                  shotWatch.perm === "granted" ? (
                    <span className={styles.filterRow}>
                      <span className={styles.playerStatus}>
                        {shotWatch.fix
                          ? "截图定位中"
                          : shotWatch.lastFileName
                            ? "截图无坐标，请在战局里用游戏截图键"
                            : "战局里按游戏截图键定位"}
                      </span>
                    </span>
                  ) : (
                    <button
                      type="button"
                      className={styles.playerEnable}
                      disabled={shotWatch.busy || shotWatch.perm === "unknown"}
                      onClick={() => void shotWatch.enable()}
                    >
                      {shotWatch.hasStored
                        ? "继续读取截图目录"
                        : "设定截图目录"}
                    </button>
                  )
                ) : null}
              </div>
            </>
          ) : null}
        </div>
      ) : null}
      <div className={styles.meta}>
        <div className={styles.coords} ref={coordsElRef} hidden />
        <a
          className={`${styles.link} ${styles.credit}`}
          href="https://github.com/the-hideout/tarkov-dev-svg-maps"
          target="_blank"
          rel="noreferrer"
        >
          底图 CC BY-NC-SA · tarkov.dev
        </a>
      </div>
      {!interactive && raster ? (
        <div className={styles.note}>平面图，坐标标记仅互动图层可用。</div>
      ) : null}
    </div>
  );
}
