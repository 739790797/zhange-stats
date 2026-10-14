/** 玩家定位：本人 / 队友标记与脉冲连线、远程涂鸦草稿。 */

import { escapeHtml } from "@/lib/escapeHtml";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "@/components/guides/tarkov/tarkovFonts.css";
import { pos } from "@/lib/tarkovMapCrs";
import { mapLayerFloorBands, overlayFloorForPoint } from "@/lib/tarkovRaidPrep";
import {
  RAID_ROOM_OTHER_FLOOR_OPACITY,
  playerFixMarkerCaption,
  playerFixPulseCrossFloor,
  playerFixPulseOpacity,
  type RaidRoomPlayerFixPulseLine,
  type TarkovMapPlayerMark,
  markMatchesFloor,
  type RaidRoomDraftStroke,
} from "@/lib/tarkovRaidRooms";
import {
  gameForwardXZ,
  gameYawToCssDeg,
  screenDeltaToCssDeg,
} from "@/lib/tarkovScreenshotPos";
import styles from "../../TarkovMapViewer.module.css";
import { type MapRuntime, PLAYER_PULSE_PANE } from "../runtime";
import { addStrokeLayer, strokeLatLngs, strokePathOptions } from "./board";

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

export function syncPlayerFixMarkers(
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
    runtime.playerIconHtml.delete(key);
  }
  for (const mark of marks) {
    const { html, name } = playerFixMarkerHtml(
      mark,
      runtime.map,
      mapRotation,
      currentFloor,
      floorBands,
    );
    let marker = runtime.playerLayers.get(mark.key);
    if (!marker) {
      marker = L.marker(pos({ x: mark.x, z: mark.z }), {
        icon: L.divIcon({
          className: styles.playerIcon,
          html,
          iconSize: [32, name ? 44 : 32],
          iconAnchor: [16, 16],
        }),
        interactive: false,
        keyboard: false,
        zIndexOffset: mark.self ? 920 : 900,
      });
      marker.addTo(group);
      runtime.playerLayers.set(mark.key, marker);
      runtime.playerIconHtml.set(mark.key, html);
      continue;
    }
    marker.setLatLng(pos({ x: mark.x, z: mark.z }));
    /* 图标 HTML 没变就不重建标记 DOM；WS 每次推送都 setIcon 会把整层标记重置。 */
    if (runtime.playerIconHtml.get(mark.key) !== html) {
      runtime.playerIconHtml.set(mark.key, html);
      marker.setIcon(
        L.divIcon({
          className: styles.playerIcon,
          html,
          iconSize: [32, name ? 44 : 32],
          iconAnchor: [16, 16],
        }),
      );
    }
    marker.setZIndexOffset(mark.self ? 920 : 900);
  }
}

function pulseLineCrossFloor(
  line: RaidRoomPlayerFixPulseLine,
  floorBands: ReturnType<typeof mapLayerFloorBands>,
): boolean {
  if (line.crossFloor) return true;
  const fromFloor = overlayFloorForPoint(line.y1, floorBands, {
    x: line.x1,
    z: line.z1,
  });
  const toFloor = overlayFloorForPoint(line.y2, floorBands, {
    x: line.x2,
    z: line.z2,
  });
  return playerFixPulseCrossFloor(fromFloor, toFloor);
}

function pulseLinePathOptions(
  line: RaidRoomPlayerFixPulseLine,
  now: number,
  floorBands: ReturnType<typeof mapLayerFloorBands>,
): L.PolylineOptions {
  const fade = playerFixPulseOpacity(line.bornAt, now);
  const cross = pulseLineCrossFloor(line, floorBands);
  return {
    color: line.color,
    weight: 3,
    opacity: fade * (cross ? 0.55 : 1),
    dashArray: cross ? "8 10" : undefined,
    lineCap: "round",
    interactive: false,
    bubblingMouseEvents: false,
    pane: PLAYER_PULSE_PANE,
  };
}

export function syncPlayerFixPulseLines(
  runtime: MapRuntime,
  lines: readonly RaidRoomPlayerFixPulseLine[],
  now: number,
  floorBands: ReturnType<typeof mapLayerFloorBands>,
) {
  const group = runtime.pulse;
  const keep = new Set(lines.map((line) => line.key));
  for (const [key, layer] of [...runtime.pulseLayers.entries()]) {
    if (keep.has(key)) continue;
    group.removeLayer(layer);
    runtime.pulseLayers.delete(key);
  }
  for (const line of lines) {
    if (playerFixPulseOpacity(line.bornAt, now) <= 0) {
      const stale = runtime.pulseLayers.get(line.key);
      if (stale) {
        group.removeLayer(stale);
        runtime.pulseLayers.delete(line.key);
      }
      continue;
    }
    const latlngs: L.LatLngExpression[] = [
      pos({ x: line.x1, z: line.z1 }),
      pos({ x: line.x2, z: line.z2 }),
    ];
    const style = pulseLinePathOptions(line, now, floorBands);
    let layer = runtime.pulseLayers.get(line.key);
    if (!layer) {
      layer = L.polyline(latlngs, style);
      layer.addTo(group);
      runtime.pulseLayers.set(line.key, layer);
      continue;
    }
    layer.setLatLngs(latlngs);
    layer.setStyle(style);
  }
}

export function syncRemoteDrafts(
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
