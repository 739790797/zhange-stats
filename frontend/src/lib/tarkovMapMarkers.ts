/** 对齐 tarkov.dev 地图门锁 / 危险区 / 开关 / 固定武器 / BTR / 战利品容器。 */

import { inventoryThumbUrl } from "./tarkovItemImages";
import { itemHrefFromTypes } from "./tarkovItemTypes";
import { lockTypeLabel } from "./tarkovKeyPacks";
import {
  mapLayerFloorBands,
  overlayVisibleOnFloor,
  type RaidPrepFloorBand,
  type RaidPrepHeightSpan,
} from "./tarkovRaidPrep";
import {
  formatKeyBringHint,
  formatKeyOwnHint,
  userBroughtKey,
  userOwnsKey,
  type RaidRoomKeyBringLike,
} from "./tarkovRaidRooms";

export type TarkovMapMarkerPoint = {
  x?: number | null;
  y?: number | null;
  z?: number | null;
  top?: number | null;
  bottom?: number | null;
};

export type TarkovMapLockLike = TarkovMapMarkerPoint & {
  id?: string | null;
  lock_type?: string | null;
  needs_power?: boolean | null;
  key_id?: string | null;
  key_name?: string | null;
  key_short_name?: string | null;
  key_icon?: string | null;
};

export type TarkovMapHazardLike = TarkovMapMarkerPoint & {
  id?: string | null;
  hazard_type?: string | null;
  name?: string | null;
};

export type TarkovMapSwitchLike = TarkovMapMarkerPoint & {
  id?: string | null;
  name?: string | null;
  switch_type?: string | null;
  activated_by?: string | null;
  activates?: ReadonlyArray<{
    operation?: string | null;
    name?: string | null;
    kind?: string | null;
  }> | null;
};

export type TarkovMapStationaryLike = TarkovMapMarkerPoint & {
  id?: string | null;
  name?: string | null;
};

export type TarkovMapBtrStopLike = TarkovMapMarkerPoint & {
  id?: string | null;
  name?: string | null;
};

export type TarkovMapLootContainerLike = TarkovMapMarkerPoint & {
  id?: string | null;
  container_id?: string | null;
  name?: string | null;
  normalized_name?: string | null;
};

export type TarkovMapKindFlags = Record<string, boolean>;

/** tarkov.dev map-images.mjs：容器 normalizedName → interactive 文件名。 */
const CONTAINER_ICON_FILES: Record<string, string> = {
  "bank-cash-register": "container_cash-register",
  "bank-safe": "container_safe",
  "buried-barrel-cache": "container_buried-barrel-cache",
  "cash-register": "container_cash-register",
  "cash-register-tar2-2": "container_cash-register",
  "dead-civilian": "container_dead-scav",
  "dead-scav": "container_dead-scav",
  "festive-airdrop-supply-crate": "container_festive-airdrop-supply-crate",
  "pmc-body": "container_dead-scav",
  "civilian-body": "container_dead-scav",
  drawer: "container_drawer",
  "duffle-bag": "container_duffle-bag",
  "grenade-box": "container_grenade-box",
  "ground-cache": "container_ground-cache",
  jacket: "container_jacket",
  "lab-technician-body": "container_dead-scav",
  "medbag-smu06": "container_medbag-smu06",
  medcase: "container_medcase",
  "medical-supply-crate": "container_crate",
  "pc-block": "container_pc-block",
  "plastic-suitcase": "container_plastic-suitcase",
  "ration-supply-crate": "container_crate",
  safe: "container_safe",
  "scav-body": "container_dead-scav",
  "shturmans-stash": "container_weapon-box",
  "technical-supply-crate": "container_crate",
  toolbox: "container_toolbox",
  "weapon-box": "container_weapon-box",
  "wooden-ammo-box": "container_wooden-ammo-box",
  "wooden-crate": "container_wooden-crate",
};

const HAZARD_KIND_LABELS: Record<string, string> = {
  minefield: "雷区",
  sniper: "狙击",
  mortar: "迫击炮",
};

const HAZARD_KIND_ORDER = ["minefield", "sniper", "mortar"] as const;

const HEX_ITEM_ID = /^[0-9a-f]{20,}$/i;

export const LOOT_CONTAINER_OTHER_KIND = "other";

const CONTAINER_KIND_LABELS: Record<string, string> = {
  "bank-cash-register": "银行收银机",
  "bank-safe": "银行保险箱",
  "buried-barrel-cache": "埋藏桶",
  "cash-register": "收银机",
  "dead-civilian": "平民尸体",
  "dead-scav": "Scav 尸体",
  drawer: "抽屉",
  "duffle-bag": "旅行袋",
  "grenade-box": "手雷箱",
  "ground-cache": "地面藏匿处",
  jacket: "夹克",
  "medbag-smu06": "医疗包",
  medcase: "医疗箱",
  "medical-supply-crate": "医疗补给箱",
  "pc-block": "机箱",
  "plastic-suitcase": "塑料手提箱",
  "ration-supply-crate": "口粮补给箱",
  safe: "保险箱",
  "scav-body": "Scav 尸体",
  toolbox: "工具箱",
  "weapon-box": "武器箱",
  "wooden-ammo-box": "木制弹药箱",
  "wooden-crate": "木箱",
  [LOOT_CONTAINER_OTHER_KIND]: "其他容器",
};

export function isLikelyTarkovItemId(value: string): boolean {
  return HEX_ITEM_ID.test(value.trim());
}

export const TARKOV_HAZARD_KIND_LABELS = HAZARD_KIND_LABELS;

export function defaultTarkovMapKindFlags(): TarkovMapKindFlags {
  return {};
}

export function isHazardKindOn(
  flags: TarkovMapKindFlags,
  kind: string,
): boolean {
  return flags[kind] !== false;
}

export function isLootContainerKindOn(
  flags: TarkovMapKindFlags,
  kind: string,
): boolean {
  return flags[kind] === true;
}

export function allPresentKindsOn(
  flags: TarkovMapKindFlags,
  present: readonly string[],
  defaultOn: boolean,
): boolean {
  if (!present.length) return false;
  return present.every((kind) =>
    defaultOn ? isHazardKindOn(flags, kind) : isLootContainerKindOn(flags, kind),
  );
}

export function anyPresentKindOn(
  flags: TarkovMapKindFlags,
  present: readonly string[],
  defaultOn: boolean,
): boolean {
  return present.some((kind) =>
    defaultOn ? isHazardKindOn(flags, kind) : isLootContainerKindOn(flags, kind),
  );
}

export function withKindsForPresent(
  flags: TarkovMapKindFlags,
  present: readonly string[],
  on: boolean,
): TarkovMapKindFlags {
  if (!present.length) return flags;
  const next = { ...flags };
  for (const kind of present) next[kind] = on;
  return next;
}

/** 无子类时跟父级开关；有子类时要全部打开才算勾上。 */
export function lootFilterParentOn(
  layerOn: boolean,
  present: readonly string[],
  flags: TarkovMapKindFlags,
): boolean {
  if (!present.length) return layerOn;
  return layerOn && allPresentKindsOn(flags, present, false);
}

/** 父级已开、子类刚到且尚未写入时，把当前图上的类全部打开。 */
export function withArrivedLootKindsOn(
  flags: TarkovMapKindFlags,
  present: readonly string[],
  layerOn: boolean,
): TarkovMapKindFlags {
  if (!layerOn || !present.length) return flags;
  let next: TarkovMapKindFlags | null = null;
  for (const kind of present) {
    if (flags[kind] !== undefined) continue;
    if (!next) next = { ...flags };
    next[kind] = true;
  }
  return next || flags;
}

export function uniqueKinds(
  values: Iterable<string>,
  preferred: readonly string[] = [],
): string[] {
  const seen = new Set<string>();
  for (const value of values) {
    const kind = value.trim();
    if (kind) seen.add(kind);
  }
  const preferredHit = preferred.filter((kind) => seen.has(kind));
  const rest = [...seen].filter((kind) => !preferred.includes(kind)).sort();
  return [...preferredHit, ...rest];
}

export function hazardKindsPresent(
  rows: ReadonlyArray<TarkovMapHazardLike>,
): string[] {
  return uniqueKinds(
    rows.map((row) => String(row.hazard_type || "")),
    HAZARD_KIND_ORDER,
  );
}

export function lootContainerKindKey(
  row: TarkovMapLootContainerLike,
): string {
  const kind = String(row.normalized_name || "").trim();
  if (kind && !isLikelyTarkovItemId(kind)) return kind;
  return LOOT_CONTAINER_OTHER_KIND;
}

export function lootContainerKindsPresent(
  rows: ReadonlyArray<TarkovMapLootContainerLike>,
): string[] {
  return uniqueKinds(rows.map((row) => lootContainerKindKey(row)));
}

export function tarkovHazardKindLabel(
  kind: string,
  fallbackName = "",
): string {
  const key = kind.trim();
  return HAZARD_KIND_LABELS[key] || fallbackName.trim() || key || "危险区";
}

export function lootContainerKindLabel(
  kind: string,
  rows: ReadonlyArray<TarkovMapLootContainerLike>,
): string {
  const hit = rows.find((row) => lootContainerKindKey(row) === kind);
  const name = (hit?.name || "").trim();
  if (name && !isLikelyTarkovItemId(name)) return name;
  return CONTAINER_KIND_LABELS[kind] || kind;
}

function lockDisplayName(value: string | null | undefined): string {
  const text = (value || "").trim();
  if (!text || isLikelyTarkovItemId(text) || / Name$/.test(text) || text.includes("/")) {
    return "";
  }
  return text;
}

export function tarkovStationaryLabel(row: TarkovMapStationaryLike): string {
  return lockDisplayName(row.name) || "固定武器";
}

export function tarkovBtrStopLabel(row: TarkovMapBtrStopLike): string {
  return lockDisplayName(row.name) || "BTR";
}

export function tarkovLockLabel(row: TarkovMapLockLike): string {
  return lockDisplayName(row.key_name) || lockDisplayName(row.key_short_name) || "门锁";
}

export function tarkovLockHref(keyId: string): string {
  return itemHrefFromTypes(keyId, ["keys"]);
}

export function tarkovLockThumbUrl(row: TarkovMapLockLike): string {
  return inventoryThumbUrl(row.key_icon, row.key_id);
}

export function tarkovLockIconUrl(): string {
  return "/tarkov/map-icons/lock.png";
}

export type TarkovLockKeyMode = "neutral" | "solo" | "party";
export type TarkovLockKeyBadge = "own" | "missing" | "teammate";

export type TarkovLockKeyContext = {
  mode?: TarkovLockKeyMode | null;
  viewerId?: number | null;
  owns?: readonly RaidRoomKeyBringLike[] | null;
  brings?: readonly RaidRoomKeyBringLike[] | null;
};

export type TarkovLockTooltipClasses = {
  tip: string;
  icon: string;
  text: string;
  status?: string;
  chips?: string;
  chip?: string;
  chipLabel?: string;
};

function lockKeyId(keyId: string | null | undefined): string {
  return (keyId || "").trim();
}

function namesForLockKey(
  rows: readonly RaidRoomKeyBringLike[] | null | undefined,
  keyId: string,
): string[] {
  const names: string[] = [];
  const seen = new Set<number>();
  for (const row of rows || []) {
    if (String(row.item_id || "").trim() !== keyId) continue;
    if (seen.has(row.user_id)) continue;
    seen.add(row.user_id);
    names.push((row.display_name || "").trim() || `用户${row.user_id}`);
  }
  return names;
}

function lockKeyHeldByOther(
  keyId: string,
  owns: readonly RaidRoomKeyBringLike[] | null | undefined,
  brings: readonly RaidRoomKeyBringLike[] | null | undefined,
  viewerId: number | null,
): boolean {
  const other = (row: RaidRoomKeyBringLike) =>
    String(row.item_id || "").trim() === keyId &&
    (viewerId == null || row.user_id !== viewerId);
  return (owns || []).some(other) || (brings || []).some(other);
}

export function tarkovLockKeyBadge(
  keyId: string | null | undefined,
  ctx: TarkovLockKeyContext = {},
): TarkovLockKeyBadge | undefined {
  const id = lockKeyId(keyId);
  const mode = ctx.mode || "neutral";
  if (!id || mode === "neutral") return undefined;
  const viewerId = ctx.viewerId ?? null;
  if (
    userOwnsKey(ctx.owns, id, viewerId) ||
    userBroughtKey(ctx.brings, id, viewerId)
  ) {
    return "own";
  }
  if (mode === "party" && lockKeyHeldByOther(id, ctx.owns, ctx.brings, viewerId)) {
    return "teammate";
  }
  return "missing";
}

export function tarkovLockKeyStatusLines(
  keyId: string | null | undefined,
  ctx: TarkovLockKeyContext = {},
): string[] {
  const id = lockKeyId(keyId);
  const mode = ctx.mode || "neutral";
  if (!id || mode === "neutral") return [];
  const ownNames = namesForLockKey(ctx.owns, id);
  const bringNames = namesForLockKey(ctx.brings, id);
  return [
    formatKeyOwnHint(ownNames) || "没人拥有这把钥匙",
    formatKeyBringHint(bringNames, { canToggle: false }),
  ];
}

function escapeLockTipHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function tarkovLockTypeLine(
  lockType: string | null | undefined,
): string {
  const type = lockTypeLabel(lockType || undefined);
  return type ? `锁的类型：${type}` : "";
}

function lockTypeChipHtml(
  label: string,
  classes: TarkovLockTooltipClasses,
): string {
  const chipClass = classes.chip || "";
  const text = `<span class="${classes.chipLabel || ""}">${escapeLockTipHtml(label)}</span>`;
  return `<span class="${chipClass}">${text}</span>`;
}

export function tarkovLockTypeChipsHtml(
  row: TarkovMapLockLike,
  classes: TarkovLockTooltipClasses,
): string {
  const chips: string[] = [];
  const type = tarkovLockTypeLine(row.lock_type);
  if (type) chips.push(lockTypeChipHtml(type, classes));
  if (row.needs_power) chips.push(lockTypeChipHtml("需供电", classes));
  if (!chips.length) return "";
  return `<div class="${classes.chips || ""}">${chips.join("")}</div>`;
}

export function tarkovLockTooltipHtml(
  row: TarkovMapLockLike,
  classes: TarkovLockTooltipClasses,
  ctx: TarkovLockKeyContext = {},
): string {
  const name = tarkovLockLabel(row);
  const thumb = tarkovLockThumbUrl(row);
  const img = thumb
    ? `<img class="${classes.icon}" src="${escapeLockTipHtml(thumb)}" alt="" width="32" height="32"/>`
    : "";
  const statusClass = classes.status || "";
  const status = tarkovLockKeyStatusLines(row.key_id, ctx)
    .map((line) => {
      const cls = statusClass ? ` class="${statusClass}"` : "";
      return `<div${cls}>${escapeLockTipHtml(line)}</div>`;
    })
    .join("");
  const chips = tarkovLockTypeChipsHtml(row, classes);
  return `<div class="${classes.tip}">${chips}${img}<div class="${classes.text}"><strong>${escapeLockTipHtml(name)}</strong>${status}</div></div>`;
}

export function tarkovHazardIconUrl(kind: string): string {
  return kind.trim() === "mortar"
    ? "/tarkov/map-icons/hazard_mortar.png"
    : "/tarkov/map-icons/hazard.png";
}

export function tarkovSwitchIconUrl(): string {
  return "/tarkov/map-icons/switch.png";
}

export function tarkovStationaryIconUrl(): string {
  return "/tarkov/map-icons/stationarygun.png";
}

export function tarkovBtrIconUrl(): string {
  return "/tarkov/map-icons/btr_stop.png";
}

export function tarkovContainerIconUrl(normalizedName: string): string {
  const key = normalizedName.trim();
  const file = CONTAINER_ICON_FILES[key] || "container_crate";
  return `/tarkov/map-icons/${file}.png`;
}

export function tarkovLooseLootIconUrl(): string {
  return "/tarkov/map-icons/loose_loot.png";
}

function isFiniteHeight(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** 图标用落点 y 判层；top/bottom 是体积盒，街区炮区会跨整栋楼。 */
export function tarkovMarkerHeightSpan(
  row: TarkovMapMarkerPoint,
): RaidPrepHeightSpan | null {
  const y = row.y;
  if (isFiniteHeight(y)) return { min: y, max: y };
  const top = row.top;
  const bottom = row.bottom;
  if (!isFiniteHeight(top) && !isFiniteHeight(bottom)) return null;
  const lo = isFiniteHeight(bottom) ? bottom : top!;
  const hi = isFiniteHeight(top) ? top : bottom!;
  return { min: Math.min(lo, hi), max: Math.max(lo, hi) };
}

const STREETS_MAP_KEYS = new Set(["streets-of-tarkov", "streets"]);

/**
 * 街区 maps.json 地面带到 10、楼上从 10 起；门锁/容器实际多在 0–8。
 * 图标按楼层故事高度淡化，任务区仍走官方带。
 */
export const STREETS_MARKER_STORY_HEIGHT: Readonly<
  Record<string, { min: number; max: number }>
> = {
  "": { min: -6, max: 2.5 },
  "2nd Floor": { min: 2.5, max: 5.5 },
  "3rd Floor": { min: 5.5, max: 8.5 },
  "4th Floor": { min: 8.5, max: 12 },
  "5th Floor": { min: 12, max: 10_000 },
  Underground: { min: -10_000, max: -6 },
};

export function mapLayerMarkerFloorBands(
  layer: Parameters<typeof mapLayerFloorBands>[0] & {
    key?: string | null;
    normalizedName?: string | null;
  },
): ReturnType<typeof mapLayerFloorBands> {
  const bands = mapLayerFloorBands(layer);
  const key = String(layer?.normalizedName || layer?.key || "")
    .trim()
    .toLowerCase();
  if (!STREETS_MAP_KEYS.has(key)) return bands;
  return bands.map((band) => {
    const height = STREETS_MARKER_STORY_HEIGHT[band.name];
    if (!height) return band;
    return {
      ...band,
      min: height.min,
      max: height.max,
      extents: [{ min: height.min, max: height.max }],
    };
  });
}

/** 官方带过宽、楼上从地面带顶开始、又没有建筑框：街上二层会被算进地面。 */
export function floorBandsNeedStoryRemap(
  bands: ReturnType<typeof mapLayerFloorBands>,
): boolean {
  const ground = bands.find((band) => !band.name);
  const named = bands.filter((band) => band.name);
  if (!ground || !named.length) return false;
  const namedHasBounds = named.some((band) =>
    (band.extents || []).some((extent) => (extent.bounds?.length ?? 0) > 0),
  );
  if (namedHasBounds) return false;
  if (ground.max - ground.min < 8) return false;
  return named.some(
    (band) => band.min >= 8 && Math.abs(band.min - ground.max) <= 0.05,
  );
}

function markerFloorAt(
  row: TarkovMapMarkerPoint,
): { x: number; z: number } | undefined {
  const x = row.x;
  const z = row.z;
  if (typeof x !== "number" || typeof z !== "number") return undefined;
  if (!Number.isFinite(x) || !Number.isFinite(z)) return undefined;
  return { x, z };
}

/** 无高度的点各层都显示；有 top/bottom/y 则按楼层带判定是否「当前层」。 */
export function tarkovMarkerVisibleOnFloor(
  row: TarkovMapMarkerPoint,
  floor: string,
  bands: readonly RaidPrepFloorBand[],
): boolean {
  const span = tarkovMarkerHeightSpan(row);
  if (!span) return true;
  return overlayVisibleOnFloor(span, floor, bands, markerFloorAt(row));
}

/** 非当前高度仍画出，略淡以便和当前层区分。 */
export const MARKER_OTHER_FLOOR_OPACITY = 0.42;

/** 当前层叠在淡化点之上，避免被挡住。 */
export const MARKER_ON_FLOOR_Z_BOOST = 80;

export type TarkovMarkerFloorDisplay = {
  onFloor: boolean;
  opacity: number;
  zBoost: number;
};

/** 无高度或落在当前层：不透明；其它高度：始终显示但降透明度。 */
export function tarkovMarkerFloorDisplay(
  row: TarkovMapMarkerPoint,
  floor: string,
  bands: readonly RaidPrepFloorBand[],
): TarkovMarkerFloorDisplay {
  const onFloor = tarkovMarkerVisibleOnFloor(row, floor, bands);
  return {
    onFloor,
    opacity: onFloor ? 1 : MARKER_OTHER_FLOOR_OPACITY,
    zBoost: onFloor ? MARKER_ON_FLOOR_Z_BOOST : 0,
  };
}

export function parseKindFlags(raw: unknown): TarkovMapKindFlags {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  const out: TarkovMapKindFlags = {};
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    if (!key || typeof value !== "boolean") continue;
    out[key] = value;
  }
  return out;
}
