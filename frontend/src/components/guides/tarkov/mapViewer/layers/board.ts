/** 战术板图层：涂鸦笔迹、图钉、文字与橡皮擦。 */

import { escapeHtml } from "@/lib/escapeHtml";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "@/components/guides/tarkov/tarkovFonts.css";
import { pos } from "@/lib/tarkovMapCrs";
import { colorForUserId } from "@/lib/tarkovRaidPrep";
import {
  RAID_ROOM_OTHER_FLOOR_OPACITY,
  markAuthorTooltipHtml,
  markMatchesFloor,
  markStrokePoints,
  normalizeMarkLabel,
  strokeFingerprint,
  type RaidRoomMarkLike,
  type StrokePoint,
} from "@/lib/tarkovRaidRooms";
import styles from "../../TarkovMapViewer.module.css";
import { type MapRuntime, BOARD_PANE } from "../runtime";

export function strokePathOptions(
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

export function strokeLatLngs(points: StrokePoint[]): L.LatLngExpression[] {
  if (!points.length) return [];
  if (points.length === 1) {
    const point = points[0];
    return [pos(point), pos({ x: point.x + 0.45, z: point.z })];
  }
  return points.map((point) => pos(point));
}

export function addStrokeLayer(
  group: L.LayerGroup,
  points: StrokePoint[],
  color: string,
  current: boolean,
  interactive: boolean,
  tooltipHtml?: string,
): L.Layer | null {
  if (!points.length) return null;
  const layer = L.polyline(
    strokeLatLngs(points),
    strokePathOptions(color, current, interactive),
  );
  if (tooltipHtml) layer.bindTooltip(tooltipHtml, { direction: "top" });
  layer.addTo(group);
  return layer;
}

export function renderLocalDraft(
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

export function strokeToMark(
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

export function parkLocalStroke(
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

function boardTextSize(label: string): { w: number; h: number } {
  let width = 0;
  for (const ch of Array.from(label)) {
    const code = ch.codePointAt(0) || 0;
    width += code > 255 ? 14 : 8;
  }
  return { w: Math.max(24, width + 8), h: 20 };
}

function addTextLayer(
  group: L.LayerGroup,
  mark: RaidRoomMarkLike,
  current: boolean,
  interactive: boolean,
  draggable: boolean,
): L.Layer | null {
  const label = normalizeMarkLabel(mark.label || "");
  if (!label) return null;
  const color = colorForUserId(mark.author_user_id);
  const safeColor = /^#[0-9a-fA-F]{6}$/.test(color) ? color : "#e8c36a";
  const box = boardTextSize(label);
  const layer = L.marker(pos({ x: mark.x, z: mark.z }), {
    icon: L.divIcon({
      className: styles.boardTextIcon,
      html: `<span class="${styles.boardText}" style="color:${safeColor}">${escapeHtml(label)}</span>`,
      iconSize: [box.w, box.h],
      iconAnchor: [box.w / 2, box.h / 2],
    }),
      interactive,
      draggable,
      autoPan: false,
      keyboard: false,
      pane: BOARD_PANE,
      opacity: current ? 1 : RAID_ROOM_OTHER_FLOOR_OPACITY,
    });
  const tooltipHtml = markAuthorTooltipHtml(mark);
  if (tooltipHtml) layer.bindTooltip(tooltipHtml, { direction: "top" });
  layer.addTo(group);
  return layer;
}

function boardLayerInteractive(layer: L.Layer): boolean {
  const options = (layer as { options?: { interactive?: boolean } }).options;
  return Boolean(options?.interactive);
}

function boardLayerDraggable(layer: L.Layer): boolean {
  const options = (layer as { options?: { draggable?: boolean } }).options;
  return Boolean(options?.draggable);
}

function bindTextDrag(
  layer: L.Marker,
  markId: number,
  onMove?: (mark: { id: number; x: number; z: number }) => void,
  guard?: { current: boolean },
) {
  layer.off("click");
  layer.off("dragstart");
  layer.off("dragend");
  layer.on("click", (event: L.LeafletMouseEvent) => {
    L.DomEvent.stop(event);
  });
  layer.on("dragstart", () => {
    if (guard) guard.current = true;
  });
  layer.on("dragend", () => {
    const latlng = layer.getLatLng();
    onMove?.({ id: markId, x: latlng.lng, z: latlng.lat });
    window.setTimeout(() => {
      if (guard) guard.current = false;
    }, 0);
  });
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
  const tooltipHtml = markAuthorTooltipHtml(mark);
  if (tooltipHtml) layer.bindTooltip(tooltipHtml, { direction: "top" });
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

export function addBoardMarks(
  runtime: MapRuntime,
  marks: RaidRoomMarkLike[],
  currentFloor: string,
  eraseMode: boolean,
  dragText: boolean,
  onErase?: (markId: number) => void,
  onTextMove?: (mark: { id: number; x: number; z: number }) => void,
  textDragGuard?: { current: boolean },
  canDragText?: (mark: RaidRoomMarkLike) => boolean,
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
    const tooltipHtml = markAuthorTooltipHtml(mark);
    // 只有作者或房主能拖（与后端 move_text_mark 同一判定）；别人连拖都拖不起来
    const wantDrag =
      dragText && mark.kind === "text" && mark.id > 0 && (canDragText?.(mark) ?? true);
    const wantInteractive = eraseMode || wantDrag;
    let layer = runtime.strokeLayers.get(key);
    if (
      layer &&
      (boardLayerInteractive(layer) !== wantInteractive ||
        (mark.kind === "text" && boardLayerDraggable(layer) !== wantDrag))
    ) {
      group.removeLayer(layer);
      runtime.mine.removeLayer(layer);
      runtime.strokeLayers.delete(key);
      layer = undefined;
    }
    if (!layer) {
      if (mark.kind === "line" || mark.kind === "stroke") {
        const painted = addStrokeLayer(
          group,
          markStrokePoints(mark),
          color,
          current,
          eraseMode,
          tooltipHtml,
        );
        if (!painted) continue;
        layer = painted;
      } else if (mark.kind === "text") {
        const painted = addTextLayer(group, mark, current, wantInteractive, wantDrag);
        if (!painted) continue;
        layer = painted;
      } else {
        layer = addPinLayer(group, mark, current, eraseMode);
      }
      runtime.strokeLayers.set(key, layer);
    } else if (layer instanceof L.Polyline) {
      layer.setStyle(strokePathOptions(color, current, eraseMode));
    } else if (layer instanceof L.Marker) {
      layer.setOpacity(current ? 1 : RAID_ROOM_OTHER_FLOOR_OPACITY);
    }
    if (wantDrag && layer instanceof L.Marker) {
      bindTextDrag(layer, mark.id, onTextMove, textDragGuard);
    } else {
      bindEraseHandler(layer, mark.id, eraseMode, onErase);
    }
  }
}
