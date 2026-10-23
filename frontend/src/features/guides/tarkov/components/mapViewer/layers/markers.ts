/** 画布点位：出生点 / Boss / 门锁 / 危险区 / 开关 / 固定武器 / BTR / 战利品。 */

import { escapeHtml } from "@/shared/lib/escapeHtml";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "@/features/guides/tarkov/components/tarkovFonts.css";
import {
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
} from "@/features/guides/tarkov/api/guidesApi";
import { type TarkovCanvasMarker } from "@/features/guides/tarkov/model/tarkovMapCanvasMarkers";
import { pos } from "@/features/guides/tarkov/model/tarkovMapCrs";
import { tarkovBossMapLabel, tarkovMapLabel } from "@/features/guides/tarkov/model/tarkovMapLabelsZh";
import { mapLayerFloorBands } from "@/features/guides/tarkov/model/tarkovRaidPrep";
import { inventoryThumbUrl } from "@/features/guides/tarkov/model/tarkovItemImages";
import { itemHrefFromTypes } from "@/features/guides/tarkov/model/tarkovItemTypes";
import {
  addMarkerOutline,
  bindMarkerOutlineHover,
} from "@/features/guides/tarkov/model/tarkovMapMarkerOutlineLayers";
import { hazardOutlineColor } from "@/features/guides/tarkov/model/tarkovMapMarkerOutlines";
import {
  isExtractKindVisible,
  tarkovExtractFloorDisplay,
  tarkovExtractStyle,
  type TarkovExtractKindFlags,
} from "@/features/guides/tarkov/model/tarkovMapExtracts";
import {
  TARKOV_SPAWN_KIND_LABELS,
  tarkovBossMarkerIcon,
  tarkovSpawnIconAnchor,
  tarkovSpawnIconUrl,
  type TarkovSpawnKind,
  type TarkovSpawnKindFlags,
} from "@/features/guides/tarkov/model/tarkovMapSpawns";
import {
  lootContainerKindKey,
  tarkovBtrIconUrl,
  tarkovBtrStopLabel,
  tarkovContainerIconUrl,
  tarkovHazardIconUrl,
  tarkovHazardKindLabel,
  tarkovLockIconUrl,
  tarkovLockKeyBadge,
  tarkovLockTooltipHtml,
  tarkovMarkerFloorDisplay,
  tarkovStationaryIconUrl,
  tarkovStationaryLabel,
  tarkovSwitchIconUrl,
  type TarkovLockKeyContext,
  type TarkovMapMarkerPoint,
} from "@/features/guides/tarkov/model/tarkovMapMarkers";
import {
  lootLooseMarkerIconUrl,
  tarkovLootLooseTooltipHtml,
} from "@/features/guides/tarkov/model/tarkovMapLootLoose";
import styles from "../../TarkovMapViewer.module.css";

const CANVAS_ICON_SIZE: [number, number] = [24, 24];
const CANVAS_ANCHOR_CENTER: [number, number] = [12, 12];

const CANVAS_Z = {
  loose: 8,
  loot: 10,
  hazard: 20,
  stationary: 30,
  switch: 40,
  lock: 50,
  spawn: 60,
  boss: 70,
} as const;

function withFloorFade(
  row: TarkovMapMarkerPoint,
  floor: string,
  floorBands: ReturnType<typeof mapLayerFloorBands>,
  marker: TarkovCanvasMarker,
): TarkovCanvasMarker {
  const view = tarkovMarkerFloorDisplay(row, floor, floorBands);
  return {
    ...marker,
    opacity: view.opacity,
    zIndex: (marker.zIndex ?? 0) + view.zBoost,
  };
}

function extractPopupExtraHtml(row: TarkovMapExtract): string {
  const lines: string[] = [];
  const switches = (row.switches || [])
    .map((item) => (item.name || item.id || "").trim())
    .filter(Boolean);
  if (switches.length) lines.push(escapeHtml(`由 ${switches.join("、")} 激活`));
  const item = row.transfer_item;
  if (item?.id) {
    const label = (item.name || item.short_name || item.id).trim();
    const count = item.count && item.count !== 1 ? `${item.count} × ` : "";
    const href = itemHrefFromTypes(item.id, item.types || []);
    const thumb = inventoryThumbUrl(item.icon_link, item.id);
    const img = thumb
      ? `<img src="${escapeHtml(thumb)}" alt="" width="18" height="18"/>`
      : "";
    const text = `需携带 ${count}${label}`;
    lines.push(
      href
        ? `${img}<a href="${escapeHtml(href)}">${escapeHtml(text)}</a>`
        : `${img}${escapeHtml(text)}`,
    );
  }
  return lines
    .map((line) => `<span class="${styles.extractPopupMeta}">${line}</span>`)
    .join("");
}

export function addExtractMarkers(
  group: L.LayerGroup,
  extracts: TarkovMapExtract[],
  kindFlags: TarkovExtractKindFlags,
  floor: string,
  floorBands: ReturnType<typeof mapLayerFloorBands>,
  outlines: L.LayerGroup,
) {
  group.clearLayers();
  for (const row of extracts) {
    if (row.x == null || row.z == null) continue;
    if (!isExtractKindVisible(kindFlags, row.faction)) continue;
    const floorView = tarkovExtractFloorDisplay(row, floor, floorBands);
    const style = tarkovExtractStyle(row.faction);
    const marker = L.marker(pos({ x: row.x, z: row.z }), {
      icon: L.divIcon({
        className: styles.extractIcon,
        html: `<span class="${styles.extractRow}"><img class="${styles.extractBadge}" src="${escapeHtml(style.iconUrl)}" alt="" width="24" height="24"/><span class="${styles.extractName}" style="color:${style.color}">${escapeHtml(row.name)}</span></span>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      }),
      title: `${row.name}（${row.faction || "撤离"}）`,
      opacity: floorView.opacity,
      zIndexOffset: style.zIndex + floorView.zBoost,
      riseOnHover: true,
    });
    marker.bindPopup(
      `<div class="${styles.extractPopup}"><img src="${escapeHtml(style.iconUrl)}" alt="" width="18" height="18"/><strong style="color:${style.color}">${escapeHtml(row.name)}</strong><span>${escapeHtml(row.faction || "撤离")}</span>${extractPopupExtraHtml(row)}</div>`,
    );
    const polygon = addMarkerOutline(outlines, row.outline, style.color);
    bindMarkerOutlineHover(marker, polygon, style.color);
    marker.addTo(group);
  }
}

export function collectPlayerSpawnMarkers(
  spawns: TarkovMapSpawn[],
  kindFlags: TarkovSpawnKindFlags,
  floor: string,
  floorBands: ReturnType<typeof mapLayerFloorBands>,
): TarkovCanvasMarker[] {
  const out: TarkovCanvasMarker[] = [];
  spawns.forEach((row, index) => {
    const kind = String(row.kind || "").trim().toLowerCase() as TarkovSpawnKind;
    if (kind !== "pmc" && kind !== "scav" && kind !== "sniper") return;
    if (!kindFlags[kind]) return;
    if (row.x == null || row.z == null) return;
    const label = TARKOV_SPAWN_KIND_LABELS[kind];
    const zone = (row.zone_name || "").trim();
    out.push(
      withFloorFade(row, floor, floorBands, {
        id: `spawn:${kind}:${index}`,
        x: row.x,
        z: row.z,
        iconUrl: tarkovSpawnIconUrl(kind),
        iconSize: CANVAS_ICON_SIZE,
        iconAnchor: tarkovSpawnIconAnchor(kind),
        tooltipHtml: zone
          ? `<strong>${escapeHtml(label)}</strong><div>${escapeHtml(zone)}</div>`
          : `<strong>${escapeHtml(label)}</strong>`,
        zIndex: CANVAS_Z.spawn,
      }),
    );
  });
  return out;
}

export function collectBossMarkers(
  bosses: TarkovMapBoss[],
  floor: string,
  floorBands: ReturnType<typeof mapLayerFloorBands>,
  mapKey?: string,
): TarkovCanvasMarker[] {
  const out: TarkovCanvasMarker[] = [];
  bosses.forEach((boss, bossIndex) => {
    const label = tarkovBossMapLabel(boss.name);
    const chance =
      boss.spawn_chance != null && boss.spawn_chance > 0
        ? `${boss.spawn_chance}%`
        : "";
    (boss.locations || []).forEach((loc, locIndex) => {
      (loc.positions || []).forEach((point, pointIndex) => {
        if (point.x == null || point.z == null) return;
        const locLabel = loc.name ? tarkovMapLabel(loc.name, mapKey) : "";
        const icon = tarkovBossMarkerIcon(boss.kind);
        out.push(
          withFloorFade(point, floor, floorBands, {
            id: `boss:${boss.id || bossIndex}:${locIndex}:${pointIndex}`,
            x: point.x,
            z: point.z,
            iconUrl: icon.iconUrl,
            iconSize: icon.iconSize,
            iconAnchor: icon.iconAnchor,
            tooltipHtml: [
              `<strong>${escapeHtml(label)}</strong>`,
              chance ? `<div>出生率 ${escapeHtml(chance)}</div>` : "",
              locLabel && locLabel !== label
                ? `<div>${escapeHtml(locLabel)}</div>`
                : "",
            ]
              .filter(Boolean)
              .join(""),
            zIndex: CANVAS_Z.boss,
          }),
        );
      });
    });
  });
  return out;
}

export function collectLockMarkers(
  locks: TarkovMapLock[],
  floor: string,
  floorBands: ReturnType<typeof mapLayerFloorBands>,
  onLockClick?: (keyId: string) => void,
  lockKey?: TarkovLockKeyContext,
  emphasize = false,
): TarkovCanvasMarker[] {
  const out: TarkovCanvasMarker[] = [];
  const iconUrl = tarkovLockIconUrl();
  const size: [number, number] = emphasize ? [32, 32] : CANVAS_ICON_SIZE;
  const anchor: [number, number] = emphasize ? [16, 16] : CANVAS_ANCHOR_CENTER;
  const tipClasses = {
    tip: styles.lockTip,
    icon: styles.lockTipIcon,
    text: styles.lockTipText,
    status: styles.lockTipStatus,
    chips: styles.lockTipChips,
    chip: styles.lockTipChip,
    chipLabel: styles.lockTipChipLabel,
  };
  locks.forEach((row, index) => {
    if (row.x == null || row.z == null) return;
    const keyId = (row.key_id || "").trim();
    const badge = tarkovLockKeyBadge(keyId, lockKey);
    const marker = withFloorFade(row, floor, floorBands, {
      id: `lock:${row.id || index}`,
      x: row.x,
      z: row.z,
      iconUrl,
      iconSize: size,
      iconAnchor: anchor,
      tooltipHtml: tarkovLockTooltipHtml(row, tipClasses, lockKey),
      onClick: keyId && onLockClick ? () => onLockClick(keyId) : undefined,
      zIndex: CANVAS_Z.lock,
      badge,
    });
    if (emphasize) {
      marker.opacity = 1;
      marker.highlight = true;
      marker.zIndex = (marker.zIndex ?? 0) + 20;
    }
    out.push(marker);
  });
  return out;
}

export function collectHazardMarkers(
  hazards: TarkovMapHazard[],
  kindOn: (kind: string) => boolean,
  floor: string,
  floorBands: ReturnType<typeof mapLayerFloorBands>,
): TarkovCanvasMarker[] {
  const out: TarkovCanvasMarker[] = [];
  hazards.forEach((row, index) => {
    if (row.x == null || row.z == null) return;
    const kind = String(row.hazard_type || "").trim();
    if (!kindOn(kind)) return;
    const name = tarkovHazardKindLabel(kind, row.name || "");
    out.push(
      withFloorFade(row, floor, floorBands, {
        id: `hazard:${row.id || index}`,
        x: row.x,
        z: row.z,
        iconUrl: tarkovHazardIconUrl(kind),
        iconSize: CANVAS_ICON_SIZE,
        iconAnchor: CANVAS_ANCHOR_CENTER,
        tooltipHtml: `<strong>${escapeHtml(name)}</strong>`,
        zIndex: CANVAS_Z.hazard,
      }),
    );
  });
  return out;
}

export function addHazardOutlines(
  group: L.LayerGroup,
  byId: Map<string, L.Polygon>,
  hazards: TarkovMapHazard[],
  kindOn: (kind: string) => boolean,
) {
  hazards.forEach((row, index) => {
    if (row.x == null || row.z == null) return;
    const kind = String(row.hazard_type || "").trim();
    if (!kindOn(kind)) return;
    const polygon = addMarkerOutline(
      group,
      row.outline,
      hazardOutlineColor(kind),
    );
    if (polygon) byId.set(`hazard:${row.id || index}`, polygon);
  });
}

export function collectSwitchMarkers(
  switches: TarkovMapSwitch[],
  floor: string,
  floorBands: ReturnType<typeof mapLayerFloorBands>,
): TarkovCanvasMarker[] {
  const out: TarkovCanvasMarker[] = [];
  const iconUrl = tarkovSwitchIconUrl();
  switches.forEach((row, index) => {
    if (row.x == null || row.z == null) return;
    const name = (row.name || "").trim() || "开关";
    const lines = [name];
    const activated = (row.activated_by || "").trim();
    if (activated) lines.push(`由 ${activated} 激活`);
    for (const item of row.activates || []) {
      const target = (item.name || "").trim();
      if (!target) continue;
      const kind = item.kind === "extract" ? "撤离" : "开关";
      lines.push(`${item.operation || "激活"} ${kind} ${target}`);
    }
    out.push(
      withFloorFade(row, floor, floorBands, {
        id: `switch:${row.id || index}`,
        x: row.x,
        z: row.z,
        iconUrl,
        iconSize: CANVAS_ICON_SIZE,
        iconAnchor: CANVAS_ANCHOR_CENTER,
        tooltipHtml: lines
          .map((line, lineIndex) =>
            lineIndex === 0
              ? `<strong>${escapeHtml(line)}</strong>`
              : `<div>${escapeHtml(line)}</div>`,
          )
          .join(""),
        zIndex: CANVAS_Z.switch,
      }),
    );
  });
  return out;
}

export function collectStationaryMarkers(
  weapons: TarkovMapStationaryWeapon[],
  floor: string,
  floorBands: ReturnType<typeof mapLayerFloorBands>,
): TarkovCanvasMarker[] {
  const out: TarkovCanvasMarker[] = [];
  const iconUrl = tarkovStationaryIconUrl();
  weapons.forEach((row, index) => {
    if (row.x == null || row.z == null) return;
    const name = tarkovStationaryLabel(row);
    out.push(
      withFloorFade(row, floor, floorBands, {
        id: `stationary:${row.id || index}`,
        x: row.x,
        z: row.z,
        iconUrl,
        iconSize: CANVAS_ICON_SIZE,
        iconAnchor: CANVAS_ANCHOR_CENTER,
        tooltipHtml: `<strong>${escapeHtml(name)}</strong>`,
        zIndex: CANVAS_Z.stationary,
      }),
    );
  });
  return out;
}

export function addBtrMarkers(
  group: L.LayerGroup,
  stops: TarkovMapBtrStop[],
  floor: string,
  floorBands: ReturnType<typeof mapLayerFloorBands>,
) {
  group.clearLayers();
  for (const row of stops) {
    if (row.x == null || row.z == null) continue;
    const name = tarkovBtrStopLabel(row);
    const floorView = tarkovMarkerFloorDisplay(row, floor, floorBands);
    const marker = L.marker(pos({ x: row.x, z: row.z }), {
      icon: L.divIcon({
        className: styles.extractIcon,
        html: `<span class="${styles.extractRow}"><img class="${styles.extractBadge}" src="${escapeHtml(tarkovBtrIconUrl())}" alt="" width="24" height="24"/><span class="${styles.extractName}">${escapeHtml(name)}</span></span>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      }),
      title: `BTR · ${name}`,
      opacity: floorView.opacity,
      zIndexOffset: floorView.zBoost,
      riseOnHover: true,
    });
    marker.bindPopup(
      `<div class="${styles.extractPopup}"><img src="${escapeHtml(tarkovBtrIconUrl())}" alt="" width="18" height="18"/><strong>${escapeHtml(name)}</strong><span>BTR 停靠</span></div>`,
    );
    marker.addTo(group);
  }
}

export function collectLootContainerMarkers(
  containers: TarkovMapLootContainer[],
  kindOn: (kind: string) => boolean,
  floor: string,
  floorBands: ReturnType<typeof mapLayerFloorBands>,
): TarkovCanvasMarker[] {
  const out: TarkovCanvasMarker[] = [];
  containers.forEach((row, index) => {
    if (row.x == null || row.z == null) return;
    const kind = lootContainerKindKey(row);
    if (!kindOn(kind)) return;
    const name = (row.name || "").trim() || kind || "容器";
    out.push(
      withFloorFade(row, floor, floorBands, {
        id: `loot:${row.id || index}`,
        x: row.x,
        z: row.z,
        iconUrl: tarkovContainerIconUrl(kind),
        iconSize: CANVAS_ICON_SIZE,
        iconAnchor: CANVAS_ANCHOR_CENTER,
        tooltipHtml: `<strong>${escapeHtml(name)}</strong>`,
        zIndex: CANVAS_Z.loot,
      }),
    );
  });
  return out;
}

export function collectLootLooseMarkers(
  rows: TarkovMapLootLoose[],
  floor: string,
  floorBands: ReturnType<typeof mapLayerFloorBands>,
  kindOn: (row: TarkovMapLootLoose) => boolean,
  onItemClick?: (itemId: string, types: string[]) => void,
): TarkovCanvasMarker[] {
  const out: TarkovCanvasMarker[] = [];
  rows.forEach((row, index) => {
    if (row.x == null || row.z == null) return;
    if (!kindOn(row)) return;
    const items = row.items || [];
    if (!items.length) return;
    const first = items[0];
    const single = items.length === 1;
    const firstId = (first?.id || "").trim();
    out.push(
      withFloorFade(row, floor, floorBands, {
        id: `loose:${row.id || index}`,
        x: row.x,
        z: row.z,
        iconUrl: lootLooseMarkerIconUrl(row),
        iconSize: CANVAS_ICON_SIZE,
        iconAnchor: CANVAS_ANCHOR_CENTER,
        tooltipHtml: tarkovLootLooseTooltipHtml(items, {
          tip: styles.lootLooseTip,
          icon: styles.lootLooseTipIcon,
          item: styles.lootLooseTipItem,
          count: styles.lootLooseTipCount,
          card: styles.lootLooseItemCard,
          cardIcon: styles.lootLooseItemCardIcon,
          cardBody: styles.lootLooseItemCardBody,
          cardName: styles.lootLooseItemCardName,
          cardMeta: styles.lootLooseItemCardMeta,
        }),
        onClick:
          single && firstId && onItemClick
            ? () => onItemClick(firstId, first?.types || [])
            : undefined,
        zIndex: CANVAS_Z.loose,
      }),
    );
  });
  return out;
}
