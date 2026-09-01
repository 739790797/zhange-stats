import type { TarkovDevLabel, TarkovDevMapLayer } from "@/lib/tarkovMapImages";
import { tarkovMapLabel } from "@/lib/tarkovMapLabelsZh";

export type TarkovMapPlaceKind = "point" | "box";

export type TarkovMapPlaceLike = {
  id?: number;
  kind?: string | null;
  name?: string | null;
  x: number;
  z: number;
  x2?: number | null;
  z2?: number | null;
  label_x?: number | null;
  label_z?: number | null;
  size?: number | null;
  floor?: string | null;
};

export type ResolvedMapPlace = TarkovDevLabel & {
  id?: number;
  kind: TarkovMapPlaceKind;
  x?: number;
  z?: number;
  x2?: number;
  z2?: number;
  label_x?: number;
  label_z?: number;
  floor?: string;
};

export type TarkovMapPlaceImportItem = {
  kind: TarkovMapPlaceKind;
  name: string;
  x: number;
  z: number;
  x2?: number;
  z2?: number;
  size?: number;
  floor: string;
};

export type TarkovMapPlaceEditMode = "off" | "point" | "box" | "select";

export type TarkovMapPlaceEdit = {
  mode: TarkovMapPlaceEditMode;
  selectedId?: number | null;
  onPoint?: (pt: { x: number; z: number; floor: string }) => void;
  onBox?: (box: {
    x: number;
    z: number;
    x2: number;
    z2: number;
    floor: string;
  }) => void;
  onSelect?: (id: number) => void;
  onMove?: (id: number, at: { x: number; z: number }) => void;
};

/**
 * 地名层：有自定义表的地图完全弃用 tarkov.dev labels，只画这里的中文点。
 * 坐标仍用同一套游戏 xz（与 maps.json 一致），位置按社区图拆点，不跟上游英文名走。
 * 库里有行时以此为准；空库才回退本表。
 */
const CUSTOM_MAP_PLACE_LABELS: Record<string, TarkovDevLabel[]> = {
  shoreline: [
    { text: "疗养院", position: [-258.2, -71.2], size: 100 },
    { text: "行政楼", position: [-252, -146] },
    { text: "西楼", position: [-171, -83] },
    { text: "东楼", position: [-329, -83] },
    { text: "停车场", position: [-85, -32] },
    { text: "假别墅", position: [162, 86] },
    { text: "真别墅", position: [96, 108] },
    { text: "蓝铁皮", position: [52, 134] },
    { text: "红白电塔", position: [-708.9, 93.91] },
    { text: "雷达站", position: [-496, 257] },
    { text: "变电站", position: [-215.8, 178.4] },
    { text: "加油站", position: [-189.3, 420] },
    { text: "沼泽", position: [326, -118.5] },
    { text: "村落", position: [418.4, 118] },
    { text: "小屋", position: [288, 144] },
    { text: "坦克桥", position: [-355, 188] },
    { text: "码头", position: [-338.6, 525] },
    { text: "灯塔", position: [216, 424] },
    { text: "公交站", position: [-96, -6] },
    { text: "地堡", position: [-153, -290] },
    { text: "吊车", position: [-625, 484] },
    { text: "农场", position: [-622, -202] },
  ],
};

function mapPlaceKey(layer: Pick<TarkovDevMapLayer, "key" | "normalizedName">): string {
  return (layer.normalizedName || layer.key || "").trim().toLowerCase();
}

export function hasCustomMapPlaceLabels(
  mapKey: string,
  dbPlaces?: readonly unknown[] | null,
): boolean {
  if (dbPlaces && dbPlaces.length > 0) return true;
  return Object.prototype.hasOwnProperty.call(
    CUSTOM_MAP_PLACE_LABELS,
    (mapKey || "").trim().toLowerCase(),
  );
}

export function placeBoxCenter(
  x: number,
  z: number,
  x2: number,
  z2: number,
): [number, number] {
  return [(x + x2) / 2, (z + z2) / 2];
}

/** 文字落点：框可用独立标注坐标，否则框中心 / 点坐标。 */
export function placeLabelPosition(row: TarkovMapPlaceLike): [number, number] {
  if (row.label_x != null && row.label_z != null) {
    return [row.label_x, row.label_z];
  }
  if (row.kind === "box" && row.x2 != null && row.z2 != null) {
    return placeBoxCenter(row.x, row.z, row.x2, row.z2);
  }
  return [row.x, row.z];
}

/** 拖文字：点改 x/z；框只改标注坐标，框本身不动。 */
export function placeLabelMovePatch(
  row: TarkovMapPlaceLike,
  at: { x: number; z: number },
): { x: number; z: number } | { label_x: number; label_z: number } {
  if (row.kind === "box") {
    return { label_x: at.x, label_z: at.z };
  }
  return { x: at.x, z: at.z };
}

export function placeVisibleOnFloor(
  floor: string | null | undefined,
  selected: string,
): boolean {
  const value = (floor || "").trim();
  if (!value) return true;
  return value === selected;
}

export function isPlaceEditTool(mode: TarkovMapPlaceEditMode | undefined): boolean {
  return mode === "point" || mode === "box";
}

/** 去掉空行和行首尾空白，保留换行。 */
export function placeNameLines(text: string): string[] {
  return (text || "")
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

export function normalizePlaceName(text: string): string {
  return placeNameLines(text).join("\n");
}

function placeLabelGlyphWidth(text: string): number {
  let width = 0;
  for (const ch of text) {
    width += ch.charCodeAt(0) > 255 ? 1 : 0.62;
  }
  return width;
}

/** 图上地名统一字号（px），不再跟上游 / 库里的 size 走。 */
export const PLACE_LABEL_FONT_PX = 13;

/** Leaflet DivIcon 尺寸：按最长行和行数估算，锚点取中心。 */
export function placeLabelIconSize(
  text: string,
  fontPx: number = PLACE_LABEL_FONT_PX,
): { w: number; h: number } {
  const lines = placeNameLines(text);
  const size = Math.max(1, fontPx);
  const lineH = Math.round(size * 1.2);
  const glyphs = Math.max(1, ...lines.map(placeLabelGlyphWidth));
  return {
    w: Math.max(48, Math.ceil(glyphs * size + 16)),
    h: Math.max(lineH, lines.length * lineH + 4),
  };
}

function asKind(raw: string | null | undefined): TarkovMapPlaceKind {
  return raw === "box" ? "box" : "point";
}

function fromDbPlace(row: TarkovMapPlaceLike): ResolvedMapPlace | null {
  const name = normalizePlaceName(row.name || "");
  if (!name) return null;
  const kind = asKind(row.kind);
  const size = row.size ?? 80;
  const floor = row.floor || "";
  if (kind === "box" && row.x2 != null && row.z2 != null) {
    const position = placeLabelPosition(row);
    return {
      id: row.id,
      kind,
      text: name,
      position,
      size,
      floor,
      x: row.x,
      z: row.z,
      x2: row.x2,
      z2: row.z2,
      label_x: row.label_x ?? undefined,
      label_z: row.label_z ?? undefined,
    };
  }
  return {
    id: row.id,
    kind: "point",
    text: name,
    position: [row.x, row.z],
    size,
    floor,
    x: row.x,
    z: row.z,
  };
}

function fromLabel(label: TarkovDevLabel, id?: number): ResolvedMapPlace | null {
  if (!label.position || label.position.length < 2) return null;
  const text = (label.text || "").trim();
  if (!text) return null;
  return {
    ...label,
    id,
    kind: "point",
    text,
    position: [label.position[0], label.position[1]],
  };
}

/** 最终画在地图上的地名。库里有行则不读 tarkov.dev / 手写表。 */
export function resolveMapPlaceLabels(
  layer: Pick<TarkovDevMapLayer, "key" | "normalizedName" | "labels">,
  dbPlaces?: readonly TarkovMapPlaceLike[] | null,
): ResolvedMapPlace[] {
  if (dbPlaces && dbPlaces.length > 0) {
    const out: ResolvedMapPlace[] = [];
    for (const row of dbPlaces) {
      const place = fromDbPlace(row);
      if (place) out.push(place);
    }
    return out;
  }
  const key = mapPlaceKey(layer);
  const custom = CUSTOM_MAP_PLACE_LABELS[key];
  if (custom) {
    const out: ResolvedMapPlace[] = [];
    for (const label of custom) {
      const place = fromLabel(label);
      if (place) out.push(place);
    }
    return out;
  }
  const out: ResolvedMapPlace[] = [];
  for (const label of layer.labels || []) {
    if (!label.position || label.position.length < 2) continue;
    const place = fromLabel({
      ...label,
      text: tarkovMapLabel(label.text, key),
    });
    if (place) out.push(place);
  }
  return out;
}

/** 接管空图：把当前回退层（手写表或上游译名）写成入库条目。 */
export function fallbackPlacesForImport(
  layer: Pick<TarkovDevMapLayer, "key" | "normalizedName" | "labels">,
): TarkovMapPlaceImportItem[] {
  return resolveMapPlaceLabels(layer).map((row) => {
    const item: TarkovMapPlaceImportItem = {
      kind: row.kind,
      name: row.text,
      x: row.x ?? row.position[0],
      z: row.z ?? row.position[1],
      size: row.size,
      floor: row.floor ?? "",
    };
    if (row.kind === "box" && row.x2 != null && row.z2 != null) {
      item.x2 = row.x2;
      item.z2 = row.z2;
    }
    return item;
  });
}

export function translatePlaceByCenter(
  row: TarkovMapPlaceLike,
  center: { x: number; z: number },
): { x: number; z: number; x2?: number; z2?: number } {
  if (row.kind === "box" && row.x2 != null && row.z2 != null) {
    const [cx, cz] = placeBoxCenter(row.x, row.z, row.x2, row.z2);
    const dx = center.x - cx;
    const dz = center.z - cz;
    return {
      x: row.x + dx,
      z: row.z + dz,
      x2: row.x2 + dx,
      z2: row.z2 + dz,
    };
  }
  return { x: center.x, z: center.z };
}
