import { apiError } from "@/lib/apiError";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
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
  clusterRaidPrepOverlayLabels,
  collectRaidPrepQuestFilterPeople,
  colorForTaskId,
  colorForUserId,
  mapLayerFloorBands,
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
  type RaidPrepPoint,
  type TarkovRaidPrepOverlay,
} from "@/lib/tarkovRaidPrep";
import { traderIconUrl, traderPortraitUrl } from "@/lib/tarkovHomeNav";
import {
  RAID_ROOM_OTHER_FLOOR_OPACITY,
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
  resolveMapFloor,
  resolveMapStyle,
  saveTarkovMapViewerPrefs,
  withExtractKind,
  withMapFloor,
  withSpawnKind,
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
  drawColor?: string;
  authorUserId?: number;
  drawMode?: TarkovMapDrawMode;
  onStroke?: (stroke: { floor: string; points: StrokePoint[] }) => void;
  onDraftStroke?: (draft: { floor: string; points: StrokePoint[] } | null) => void;
  onEraseMark?: (markId: number) => void;
  onFloorChange?: (floor: string) => void;
  /** 点击任务点位或名称：打开该任务攻略 */
  onQuestLabelClick?: (taskId: string) => void;
  /** 任务 id → 参与者，供地图悬浮窗展示 */
  questParticipantsByTask?: ReadonlyMap<string, readonly RaidPrepMapParticipant[]>;
  highlightTaskId?: string;
  /** 外部请求将地图平移到指定游戏坐标（seq 递增可重复定位同一点） */
  focusRequest?: TarkovMapFocusRequest | null;
  topRight?: ReactNode;
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
  quests: L.LayerGroup;
  questLabels: L.LayerGroup;
  board: L.LayerGroup;
  live: L.LayerGroup;
  mine: L.LayerGroup;
  remote: L.LayerGroup;
  localStroke?: L.Polyline;
  mineKeys: Set<string>;
  strokeLayers: Map<string, L.Layer>;
  boardPane?: HTMLElement;
  svgRoot?: SVGSVGElement;
};

const BOARD_PANE = "boardPane";
const SVG_BASE_PANE = "svgBasePane";
const DRAFT_THROTTLE_MS = 48;

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

function addLabelMarkers(group: L.LayerGroup, layer: TarkovDevMapLayer) {
  group.clearLayers();
  const mapKey = layer.normalizedName || layer.key;
  for (const label of layer.labels || []) {
    if (!label.position || label.position.length < 2) continue;
    const size = Math.max(11, Math.round((label.size || 80) / 7));
    const rotation = label.rotation || 0;
    const text = tarkovMapLabel(label.text, mapKey);
    const marker = L.marker(pos({ x: label.position[0], z: label.position[1] }), {
      icon: L.divIcon({
        className: styles.labelIcon,
        html: `<span class="${styles.labelText}" style="font-size:${size}px;transform:rotate(${rotation}deg)">${escapeHtml(text)}</span>`,
        iconSize: [160, 20],
        iconAnchor: [80, 10],
      }),
      interactive: false,
    });
    marker.addTo(group);
  }
}

type QuestBubbleRow = {
  taskId?: string;
  title: string;
  subtitle: string;
  color: string;
  traderSlug: string;
  keyNames?: string[];
  showNoKey?: boolean;
  optional?: boolean;
  kind?: "zone" | "spawn";
  height?: RaidPrepHeightSpan | null;
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

function overlayBubbleHtml(row: QuestBubbleRow): string {
  const kind =
    row.kind === "spawn"
      ? "可能刷新点"
      : row.kind === "zone"
        ? "目标区域"
        : "";
  const meta = row.subtitle || kind;
  const optionalTag = row.optional
    ? `<span class="${styles.questTipOptional}">可选</span>`
    : "";
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
  return `<span class="${styles.questTip}"><span class="${styles.questTipRow}">${questTraderImgHtml(row.traderSlug)}<span class="${styles.questTipName}" style="color:${row.color}">${escapeHtml(row.title)}</span></span><span class="${styles.questTipMeta}">${optionalTag}${escapeHtml(meta)}</span>${keyRow}${questParticipantChipsHtml(row.participants)}</span>`;
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
  highlightTaskId?: string,
  offFloor = false,
): string {
  const title = item.optional ? `${item.title}（可选）` : item.title;
  const on = highlightTaskId && item.taskId === highlightTaskId ? " data-on=\"true\"" : "";
  const keyMark = item.keyNames.length
    ? `<span class="${styles.questLabelKey}">需要钥匙</span>`
    : "";
  const dim = offFloor ? ` ${styles.questLabelOff}` : "";
  return `<span class="${styles.questLabelRow}${dim}" data-task-id="${escapeHtml(item.taskId)}"${on}>${questTraderImgHtml(item.traderSlug)}<span class="${styles.questName}" style="color:${item.color}">${escapeHtml(title)}</span>${keyMark}</span>`;
}

type QuestClickHandler = (
  taskId: string,
  height?: RaidPrepHeightSpan | null,
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
    const handled = onClick(taskId, row.height);
    if (handled === false) return;
    L.DomEvent.stopPropagation(event);
  });
}

function questBubbleFromOverlay(
  row: TarkovRaidPrepOverlay,
  namesByTask?: ReadonlyMap<string, readonly RaidPrepMapParticipant[]>,
): QuestBubbleRow {
  return {
    taskId: row.taskId,
    title: row.title,
    subtitle: row.subtitle,
    color: row.color,
    traderSlug: row.traderSlug,
    keyNames: row.keyNames,
    showNoKey: row.showNoKey,
    optional: row.optional,
    kind: row.kind,
    height: row.height,
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
    const onFloor = overlayVisibleOnFloor(row.height, floor, floorBands);
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
  highlightTaskId: string | undefined,
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
  const lineH = 22;
  for (const label of labels) {
    label.items.forEach((item, index) => {
      const offFloor = !overlayVisibleOnFloor(item.height, floor, floorBands);
      const marker = L.marker(pos({ x: label.x, z: label.z }), {
        icon: L.divIcon({
          className: styles.questIcon,
          html: `<span class="${styles.questLabelStack}">${questLabelLineHtml(item, highlightTaskId, offFloor)}</span>`,
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
          subtitle: item.subtitle,
          color: item.color,
          traderSlug: item.traderSlug,
          keyNames: item.keyNames,
          showNoKey: item.showNoKey,
          optional: item.optional,
          height: item.height,
          participants: raidPrepParticipants(namesByTask?.get(item.taskId)),
        },
        onLabelClick,
      );
      marker.addTo(group);
    });
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
  drawColor = "#c8932a",
  authorUserId = 0,
  drawMode = "pan",
  onStroke,
  onDraftStroke,
  onEraseMark,
  onFloorChange,
  onQuestLabelClick,
  questParticipantsByTask,
  highlightTaskId = "",
  focusRequest,
  topRight,
}: Props) {
  const interactive = useMemo(
    () => findInteractiveMap(slug, parentSlug),
    [slug, parentSlug],
  );
  const raster = useMemo(
    () => findRasterMap(slug, parentSlug),
    [slug, parentSlug],
  );
  const mapDivRef = useRef<HTMLDivElement>(null);
  const runtimeRef = useRef<MapRuntime | null>(null);
  const drawModeRef = useRef(drawMode);
  const onStrokeRef = useRef(onStroke);
  const onDraftStrokeRef = useRef(onDraftStroke);
  const onEraseMarkRef = useRef(onEraseMark);
  const onQuestLabelClickRef = useRef(onQuestLabelClick);
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
  const commitStrokeRef = useRef<
    (stroke: { floor: string; points: StrokePoint[] }) => void
  >(() => {});
  const drawingRef = useRef(false);
  const spaceHeldRef = useRef(false);
  const floorRef = useRef("");
  const coordsElRef = useRef<HTMLDivElement | null>(null);
  const wrapElRef = useRef<HTMLDivElement | null>(null);
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
  const floor = resolveMapFloor(
    prefs.floorsByMap[interactive?.key || ""],
    floorNames,
  );
  const floorBands = useMemo(
    () => mapLayerFloorBands(interactive),
    [interactive],
  );
  const questPeople = useMemo(
    () => collectRaidPrepQuestFilterPeople(questParticipantsByTask),
    [questParticipantsByTask],
  );
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
  const overlaySig = displayedQuestOverlays
    .map((row) => {
      const people = raidPrepParticipants(
        displayedParticipantsByTask?.get(row.taskId),
      );
      const sig = people
        .map((person) => `${person.userId ?? ""}:${person.name}`)
        .join(",");
      return `${row.key}:${sig}`;
    })
    .join("\0") + `\0${floor}`;
  const { extractKinds, spawnKinds, showLabels, showQuests } = prefs;
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
  onDraftStrokeRef.current = onDraftStroke;
  onEraseMarkRef.current = onEraseMark;
  onQuestLabelClickRef.current = onQuestLabelClick;
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
      quests: L.layerGroup(),
      questLabels: L.layerGroup(),
      board: L.layerGroup(),
      live: L.layerGroup(),
      mine: L.layerGroup(),
      remote: L.layerGroup(),
      mineKeys: new Set(),
      strokeLayers: new Map(),
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

      const tileSize = layer.tileSize || 256;
      if (layer.tilePath) {
        runtime.tileLayer = L.tileLayer(layer.tilePath, {
          tileSize,
          bounds,
          maxZoom,
          maxNativeZoom: layer.maxZoom ?? 5,
        });
      }
      for (const floorLayer of layer.layers || []) {
        if (!floorLayer.tilePath) continue;
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
      if (layer.svgPath) {
        try {
          const svg = await loadSvgElement(layer.svgPath);
          if (cancelled) return;
          runtime.svgRoot = svg;
          setSvgFloor(svg, layer.svgLayer || "", "");
          const svgBounds = getBounds(layer.svgBounds) || bounds;
          runtime.svgOverlay = L.svgOverlay(svg, svgBounds, {
            pane: SVG_BASE_PANE,
            interactive: false,
          });
        } catch {
          /* 抽象图失败时仍可用瓦片 */
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
      runtime.quests.addTo(map);
      runtime.questLabels.addTo(map);
      runtime.board.addTo(map);
      runtime.mine.addTo(map);
      runtime.live.addTo(map);
      runtime.remote.addTo(map);
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
    if (!ready || !runtime || !map || !interactive) return;
    const svgOverlay = runtime.svgOverlay;
    const wantSvg = style === "svg" && Boolean(svgOverlay);
    const floorLayer = floors.find((item) => item.name === floor);
    const keepBaseOpaque = floorLayer?.show === true;
    if (wantSvg && svgOverlay) {
      svgOverlay.addTo(map);
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
    runtime.svgOverlay?.remove();
    runtime.tileLayer?.addTo(map);
    runtime.tileLayer?.setOpacity(
      mapBaseOffLevel(floor, keepBaseOpaque) ? MAP_OFF_LEVEL_OPACITY : 1,
    );
    for (const [name, tile] of runtime.floorTiles) {
      if (name === floor) tile.addTo(map);
      else tile.remove();
    }
  }, [style, floor, interactive, floors, ready]);

  useEffect(() => {
    const runtime = runtimeRef.current;
    /* ready 表示 fitBounds 已完成；抽象图加载中 map 已有但未 setView */
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
    if (showLabels) addLabelMarkers(runtime.labels, interactive);
    else runtime.labels.clearLayers();
    setSvgBakedTextHidden(
      runtime.svgRoot,
      showLabels && Boolean(interactive.labels?.length),
    );
    const onQuestClick: QuestClickHandler = (taskId, height) => {
      if (isMapDrawTool(drawModeRef.current)) return false;
      const nextFloor = overlayFloorForSpan(height, floorBandsRef.current);
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
    };
    if (showQuests) {
      if (overlaySigRef.current !== overlaySig) {
        overlaySigRef.current = overlaySig;
        addQuestOverlays(
          runtime.quests,
          displayedQuestOverlays,
          displayedParticipantsByTask,
          onQuestClick,
          floor,
          floorBands,
        );
      }
      addQuestLabels(
        runtime.questLabels,
        displayedQuestOverlays,
        runtime.map,
        onQuestClick,
        highlightTaskId,
        displayedParticipantsByTask,
        floor,
        floorBands,
      );
    } else {
      overlaySigRef.current = "";
      runtime.quests.clearLayers();
      runtime.questLabels.clearLayers();
    }
    const refreshQuestLabels = () => {
      if (!showQuests) return;
      addQuestLabels(
        runtime.questLabels,
        displayedQuestOverlays,
        runtime.map,
        onQuestClick,
        highlightTaskId,
        displayedParticipantsByTask,
        floor,
        floorBands,
      );
    };
    runtime.map.on("zoomend", refreshQuestLabels);
    addBoardMarks(
      runtime,
      visibleMarks,
      floor,
      drawMode === "erase",
      (markId) => onEraseMarkRef.current?.(markId),
    );
    return () => {
      runtime.map.off("zoomend", refreshQuestLabels);
    };
  }, [
    extracts,
    bosses,
    spawns,
    questOverlays,
    overlaySig,
    displayedQuestOverlays,
    displayedParticipantsByTask,
    highlightTaskId,
    visibleMarks,
    floor,
    floorBands,
    drawMode,
    extractKinds,
    spawnKinds,
    showLabels,
    showQuests,
    interactive,
    ready,
  ]);

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
    runtime.remote.clearLayers();
    for (const draft of remoteDrafts) {
      addStrokeLayer(
        runtime.remote,
        draft.points,
        draft.color,
        markMatchesFloor(draft, floor),
        false,
      );
    }
  }, [remoteDrafts, floor, interactive, ready]);

  useEffect(() => {
    if (!ready) return undefined;
    const handle = window.setTimeout(() => {
      runtimeRef.current?.map.invalidateSize();
    }, 60);
    return () => window.clearTimeout(handle);
  }, [ready, fill, questOverlays.length]);

  useEffect(() => {
    const map = runtimeRef.current?.map;
    if (!ready || !map || !focusRequest) return;
    const mapKey = interactive?.key || "";
    const nextFloor = overlayFloorForPoint(focusRequest.y, floorBands);
    if (mapKey && nextFloor !== floorRef.current) {
      updatePrefs((prev) => withMapFloor(prev, mapKey, nextFloor));
    }
    const latLng = L.latLng(pos(focusRequest));
    const zoom = Math.max(map.getZoom(), map.getMinZoom() + 1);
    map.flyTo(latLng, zoom, { animate: true, duration: 0.35 });
  }, [focusRequest, ready, floorBands, interactive?.key, updatePrefs]);

  useEffect(() => {
    const map = runtimeRef.current?.map;
    const pane = runtimeRef.current?.boardPane;
    if (!map) return;
    const drawing = isMapDrawTool(drawMode) && !spaceHeld;
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
  }, [drawMode, spaceHeld, ready]);

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
      className={`${styles.wrap} ${fill ? styles.wrapFill : ""} ${topRight ? styles.wrapTopRight : ""} ${isMapDrawTool(drawMode) ? styles.wrapDraw : ""} ${drawMode === "erase" ? styles.wrapErase : ""} ${spaceHeld ? styles.wrapSpace : ""} ${className}`.trim()}
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
                    name={`tarkov-map-floor-${interactive?.key || "map"}`}
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
                      name={`tarkov-map-floor-${interactive?.key || "map"}`}
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
          {interactive ? (
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
                {interactive.labels?.length ? (
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
                            if (questsParentOn) {
                              updatePrefs({ showQuests: false });
                              return;
                            }
                            updatePrefs({ showQuests: true });
                            setQuestPersonOff(new Set());
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
                                setQuestPersonOff((prev) => {
                                  const next = new Set(prev);
                                  if (next.has(key)) next.delete(key);
                                  else next.add(key);
                                  return next;
                                });
                                if (!showQuests) {
                                  updatePrefs({ showQuests: true });
                                }
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
