import { useCallback, useEffect, useState } from "react";
import { TARKOV_MAPS, TARKOV_TRADERS } from "@/lib/tarkovHomeNav";
import {
  orderObjectiveTypes,
  tarkovObjectiveTypeLabel,
} from "@/lib/tarkovTaskObjective";

/** 与后端 MAP_SLUG_EQUIV_GROUPS 对齐。 */
export const MAP_SLUG_EQUIV_GROUPS: readonly (readonly string[])[] = [
  ["streets", "streets-of-tarkov"],
  ["lab", "the-lab"],
  ["labyrinth", "the-labyrinth"],
  ["night-factory", "factory-night"],
  ["ground-zero", "ground-zero-21", "ground-zero-tutorial"],
  ["customs", "bigmap"],
];

export const RAID_PREP_MAX_SELECTED = 40;

/** 原文写明「任意」且候选不少于这么多种时，收成一条，文案用目标描述。 */
export const RAID_PREP_ANY_OF_MIN = 4;

/** 准备总结：物品 / 任务物成对合成一列。 */
export const RAID_PREP_SUMMARY_TYPE_MERGE: Readonly<Record<string, string>> = {
  findQuestItem: "findItem",
  giveQuestItem: "giveItem",
  plantQuestItem: "plantItem",
};

/** 要带进战局的目标列（跟「所需钥匙」一组，排在找到/上交前面）。 */
export const RAID_PREP_SUMMARY_BRING_TYPES = [
  "plantItem",
  "mark",
  "useItem",
] as const;

export const RAID_PREP_SUMMARY_BRING_GROUP_LABEL = "进局携带";

/** 总结表单独一列：展示击杀目标原文，不跟找到/上交混在一起。 */
export const RAID_PREP_SUMMARY_SHOOT_TYPE = "shoot";

export function raidPrepSummaryColumnType(type: string): string {
  const key = (type || "").trim();
  if (!key) return "item";
  return RAID_PREP_SUMMARY_TYPE_MERGE[key] || key;
}

export function isRaidPrepSummaryBringType(type: string): boolean {
  return (RAID_PREP_SUMMARY_BRING_TYPES as readonly string[]).includes(
    raidPrepSummaryColumnType(type),
  );
}

export function isRaidPrepSummaryShootType(type: string): boolean {
  return raidPrepSummaryColumnType(type) === RAID_PREP_SUMMARY_SHOOT_TYPE;
}

/** 钥匙旁：藏匿 / 标记 / 使用在前，找到、上交、击杀等在后。 */
export function orderRaidPrepSummaryTypeColumns(
  types: string[] | null | undefined,
): string[] {
  const ordered = orderObjectiveTypes(types);
  const bring = RAID_PREP_SUMMARY_BRING_TYPES.filter((type) =>
    ordered.includes(type),
  );
  const rest = ordered.filter(
    (type) =>
      !isRaidPrepSummaryBringType(type) && !isRaidPrepSummaryShootType(type),
  );
  return [...bring, ...rest];
}

/** 勾选任务里有藏匿、标记或使用时，总结表合成一列。 */
export function raidPrepSummaryHasBringTypes(
  rows: readonly RaidPrepTaskSummary[],
  typeColumns?: readonly string[],
): boolean {
  if (typeColumns?.some(isRaidPrepSummaryBringType)) return true;
  return rows.some((row) =>
    (row.types || []).some((type) => isRaidPrepSummaryBringType(type)),
  );
}

/** 勾选任务里有击杀目标时，总结表单独出列。 */
export function raidPrepSummaryHasShootTypes(
  rows: readonly RaidPrepTaskSummary[],
): boolean {
  return rows.some(
    (row) =>
      (row.shootSlots || []).length > 0 ||
      (row.types || []).some((type) => isRaidPrepSummaryShootType(type)),
  );
}

export type RaidPrepSummaryBringSlot = {
  type: string;
  item?: RaidPrepNeededItem;
};

export type RaidPrepSummaryShootSlot = {
  id: string;
  text: string;
  optional: boolean;
  /** 击杀次数；武器芯片不带这个数，避免被当成要带几把枪。 */
  count: number;
  items: RaidPrepNeededItem[];
};

export function raidPrepObjectiveCount(obj: {
  count?: number | null;
}): number {
  const count = obj.count;
  if (typeof count === "number" && Number.isFinite(count) && count > 0) {
    return Math.trunc(count);
  }
  return 1;
}

export type RaidPrepSummaryItemLine = {
  key: RaidPrepNeededItem | null;
  bring: RaidPrepSummaryBringSlot | null;
  shoot: RaidPrepSummaryShootSlot | null;
  rest: Record<string, RaidPrepNeededItem | null>;
};

export type RaidPrepSummaryItemGrid = {
  lines: RaidPrepSummaryItemLine[];
  spanKey: boolean;
  spanBring: boolean;
  spanShoot: boolean;
  spanRest: Record<string, boolean>;
};

function taskHasSummaryType(
  row: RaidPrepTaskSummary,
  columnType: string,
): boolean {
  return (row.types || []).some(
    (type) => raidPrepSummaryColumnType(type) === columnType,
  );
}

function summaryBringSlots(
  row: RaidPrepTaskSummary,
  showBringTypes: boolean,
): RaidPrepSummaryBringSlot[] {
  if (!showBringTypes) return [];
  const out: RaidPrepSummaryBringSlot[] = [];
  const byType = row.itemsByType || {};
  for (const type of RAID_PREP_SUMMARY_BRING_TYPES) {
    const items = byType[type] || [];
    if (items.length) {
      for (const item of items) out.push({ type, item });
      continue;
    }
    if (taskHasSummaryType(row, type)) out.push({ type });
  }
  return out;
}

/** 总结表一行一件：钥匙、藏匿/标记/使用、击杀、其它类型各自拆开，按列对齐。 */
export function expandRaidPrepSummaryItemLines(
  row: RaidPrepTaskSummary,
  restTypes: readonly string[],
  showBringTypes: boolean,
  showShootTypes = false,
): RaidPrepSummaryItemGrid {
  const keys = row.keys || [];
  const bring = summaryBringSlots(row, showBringTypes);
  const shoots = showShootTypes ? row.shootSlots || [] : [];
  const byType = row.itemsByType || {};
  const restLists = new Map<string, RaidPrepNeededItem[]>();
  const spanRest: Record<string, boolean> = {};
  let restMax = 0;
  for (const type of restTypes) {
    if (isRaidPrepSummaryShootType(type) || isRaidPrepSummaryBringType(type)) {
      continue;
    }
    const items = byType[type] || [];
    restLists.set(type, items);
    spanRest[type] = items.length <= 1;
    if (items.length > restMax) restMax = items.length;
  }
  const count = Math.max(keys.length, bring.length, shoots.length, restMax, 1);
  const lines: RaidPrepSummaryItemLine[] = [];
  for (let i = 0; i < count; i += 1) {
    const rest: Record<string, RaidPrepNeededItem | null> = {};
    for (const type of restTypes) {
      if (isRaidPrepSummaryShootType(type) || isRaidPrepSummaryBringType(type)) {
        continue;
      }
      rest[type] = restLists.get(type)?.[i] ?? null;
    }
    lines.push({
      key: keys[i] ?? null,
      bring: bring[i] ?? null,
      shoot: shoots[i] ?? null,
      rest,
    });
  }
  return {
    lines,
    spanKey: keys.length <= 1,
    spanBring: bring.length <= 1,
    spanShoot: shoots.length <= 1,
    spanRest,
  };
}

export const RAID_PREP_TASK_COLORS = [
  "#e8c36a",
  "#6cb6ff",
  "#6fbf4a",
  "#e08a2c",
  "#d44a4a",
  "#c77dff",
  "#4ab8b8",
  "#f0a3c2",
] as const;

export type RaidPrepMapOption = {
  id: string;
  label: string;
  english: string;
  icon: string;
};

export type RaidPrepPoint = {
  x: number;
  z: number;
  y?: number;
};

export type RaidPrepHeightSpan = {
  min: number;
  max: number;
};

export type RaidPrepFloorBand = {
  name: string;
  min: number;
  max: number;
};

export type TarkovRaidPrepOverlay = {
  key: string;
  taskId: string;
  kind: "zone" | "spawn";
  color: string;
  title: string;
  subtitle: string;
  traderSlug: string;
  keyNames: string[];
  /** 同任务其它点要钥匙时，本点明确标「不需要钥匙」。 */
  showNoKey: boolean;
  /** 来自目标 optional；可选目标在地图上单独标出。 */
  optional: boolean;
  outline: RaidPrepPoint[];
  points: RaidPrepPoint[];
  height: RaidPrepHeightSpan | null;
};

export type RaidPrepOverlayLabelItem = {
  taskId: string;
  title: string;
  color: string;
  traderSlug: string;
  subtitle: string;
  keyNames: string[];
  showNoKey: boolean;
  count: number;
  optional: boolean;
  height: RaidPrepHeightSpan | null;
};

/** 地图上一条任务名：可能叠了多个邻近任务。 */
export type RaidPrepOverlayLabel = {
  x: number;
  z: number;
  items: RaidPrepOverlayLabelItem[];
};

/** 同簇点位在此距离（游戏坐标，约等于米）内共用一条名称。 */
export const RAID_PREP_LABEL_CLUSTER_GAP = 36;

/** 地图标签按屏幕像素聚类：放大后贴着点，缩小时才合并。 */
export const RAID_PREP_LABEL_CLUSTER_PX = 48;

export type RaidPrepLabelClusterOpts = {
  gap: number;
  project?: (point: RaidPrepPoint) => RaidPrepPoint;
};

type LocationRef = {
  map_slug?: string | null;
  map_id?: string | null;
  map_name?: string | null;
};

type ZoneLike = LocationRef & {
  id?: string | null;
  x?: number | null;
  y?: number | null;
  z?: number | null;
  top?: number | null;
  bottom?: number | null;
  outline?: Array<{ x?: number | null; y?: number | null; z?: number | null }> | null;
};

type PossibleLocationLike = LocationRef & {
  positions?: Array<{ x?: number | null; z?: number | null }> | null;
};

export type RaidPrepNamedRef = {
  id?: string | null;
  slug?: string | null;
  name?: string | null;
  icon_link?: string | null;
  types?: string[] | null;
};

export type RaidPrepObjectiveLike = {
  id?: string | null;
  type?: string | null;
  description?: string | null;
  optional?: boolean | null;
  count?: number | null;
  found_in_raid?: boolean | null;
  maps?: RaidPrepNamedRef[] | null;
  items?: RaidPrepNamedRef[] | null;
  required_keys?: RaidPrepNamedRef[][] | null;
  zones?: ZoneLike[] | null;
  possible_locations?: PossibleLocationLike[] | null;
  zone_names?: string[] | null;
};

export type RaidPrepTaskLike = {
  id: string;
  name?: string | null;
  normalized_name?: string | null;
  trader_slug?: string | null;
  trader_name?: string | null;
  objectives?: RaidPrepObjectiveLike[] | null;
  needed_keys?: Array<{
    map?: { slug?: string | null } | null;
    keys?: RaidPrepNamedRef[] | null;
  }> | null;
};

export type RaidPrepNeededItem = {
  id: string;
  name: string;
  icon_link: string;
  types: string[];
  count: number;
  found_in_raid: boolean;
  optional: boolean;
  kind: "key" | "item";
  role: string;
  /** 上游 objective.type，用于按类型分列。 */
  objectiveType: string;
  /** 原文「任意某一类」的候选。有值时本条是汇总，name 用目标描述。 */
  anyOf?: RaidPrepNeededItem[];
};

export type RaidPrepObjectiveHint = {
  id: string;
  text: string;
  optional: boolean;
  keyNames: string[];
};

export type RaidPrepTaskSummary = {
  taskId: string;
  taskName: string;
  traderSlug: string;
  traderName: string;
  /** 按 objective.type 分组的物品（仅带 items 的目标）。 */
  itemsByType: Record<string, RaidPrepNeededItem[]>;
  keys: RaidPrepNeededItem[];
  /** 当前地图未勾掉的击杀目标（总结表单独一列）。 */
  shootSlots: RaidPrepSummaryShootSlot[];
  /** 当前地图适用的全部目标类型（含无物品的 mark / visit 等）。 */
  types: string[];
  /** 当前地图适用的目标文案（任务详情「目标」描述）。 */
  objectiveLines: string[];
  /** 当前地图全部目标（含已勾掉），供勾选进度。 */
  objectives: RaidPrepObjectiveHint[];
};

/** 任务 id → 已勾掉（本局不用再做）的目标 id。 */
export type RaidPrepSkipMap = ReadonlyMap<string, ReadonlySet<string>>;

const EMPTY_SKIP: ReadonlySet<string> = new Set();
const RAID_PREP_OBJ_DONE_STORAGE = "zhange.tarkov.raidPrep.objDone.v1";

function isFiniteNumber(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

const TARKOV_HEX_ID_RE = /^[a-f0-9]{24}$/i;
const TARKOV_GARBLED_NAME_RE = /^[?？\uFFFD\s]+$/;

/** BSG 物品/任务主键；当名称解析失败时会原样露出来。 */
export function isTarkovHexId(value: string): boolean {
  return TARKOV_HEX_ID_RE.test((value || "").trim());
}

/** 中文 locale 缺译时上游会给 ???? / ？？？？，不能当名称。 */
export function isGarbledTarkovName(value: string): boolean {
  const text = (value || "").trim();
  return Boolean(text) && TARKOV_GARBLED_NAME_RE.test(text);
}

/** 可展示的物品/钥匙名；ID、空串、问号占位不当名称。 */
export function tarkovReadableName(
  name: string | null | undefined,
  id?: string | null,
): string {
  const text = (name || "").trim();
  if (!text) return "";
  const ident = (id || "").trim();
  if (ident && text === ident) return "";
  if (isTarkovHexId(text)) return "";
  if (isGarbledTarkovName(text)) return "";
  return text;
}

/** 任务卡片 / 地图标签：中文名 → 英文 slug → id，绝不露出 ????。 */
export function displayRaidPrepTaskName(task: {
  id: string;
  name?: string | null;
  normalized_name?: string | null;
}): string {
  return (
    tarkovReadableName(task.name, task.id) ||
    tarkovReadableName(task.normalized_name, task.id) ||
    (task.normalized_name || "").trim() ||
    task.id
  );
}

/** 地图悬浮窗 / 标签用的参与者，去空白与重复（有 userId 时按人去重）。 */
export type RaidPrepMapParticipant = {
  name: string;
  userId?: number;
};

export function raidPrepPersonKey(person: {
  name: string;
  userId?: number;
}): string {
  return person.userId != null ? `id:${person.userId}` : `name:${person.name}`;
}

export function raidPrepParticipants(
  people:
    | readonly { name?: string | null; userId?: number | null }[]
    | null
    | undefined,
): RaidPrepMapParticipant[] {
  const seen = new Set<string>();
  const out: RaidPrepMapParticipant[] = [];
  for (const person of people || []) {
    const name = (person.name || "").trim();
    if (!name) continue;
    const userId =
      typeof person.userId === "number" && Number.isFinite(person.userId)
        ? person.userId
        : undefined;
    const row = userId != null ? { name, userId } : { name };
    const key = raidPrepPersonKey(row);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(row);
  }
  return out;
}

/** 任务点位筛选：按勾选并集收集房间内的人，顺序与首次出现一致。 */
export function collectRaidPrepQuestFilterPeople(
  byTask:
    | ReadonlyMap<
        string,
        readonly { name?: string | null; userId?: number | null }[]
      >
    | null
    | undefined,
): RaidPrepMapParticipant[] {
  if (!byTask) return [];
  const flat: { name?: string | null; userId?: number | null }[] = [];
  for (const people of byTask.values()) {
    for (const person of people) flat.push(person);
  }
  return raidPrepParticipants(flat);
}

/** `selectedKeys` 为 null 表示不过滤；空集合表示全关。无参与者的点位在有人选中时仍显示。 */
export function raidPrepQuestOverlayVisible(
  people: readonly RaidPrepMapParticipant[],
  selectedKeys: ReadonlySet<string> | null,
): boolean {
  if (selectedKeys == null) return true;
  if (!selectedKeys.size) return false;
  if (!people.length) return true;
  return people.some((person) => selectedKeys.has(raidPrepPersonKey(person)));
}

/** 地图悬浮窗 / 文案用的参与者显示名。 */
export function raidPrepParticipantNames(
  people:
    | readonly { name?: string | null; userId?: number | null }[]
    | null
    | undefined,
): string[] {
  return raidPrepParticipants(people).map((person) => person.name);
}

/** 地图任务点悬浮纯文本（标签 UI 用 raidPrepParticipants）。 */
export function formatRaidPrepParticipantLine(
  names: readonly string[],
): string {
  const list = names.map((name) => name.trim()).filter(Boolean);
  if (!list.length) return "有哪些用户参与该任务：暂无";
  return `有哪些用户参与该任务：${list.join("、")}`;
}

export function mapSlugKeys(mapSlug: string): Set<string> {
  const key = (mapSlug || "").trim().toLowerCase();
  if (!key) return new Set();
  const keys = new Set<string>([key]);
  for (const group of MAP_SLUG_EQUIV_GROUPS) {
    if (group.includes(key)) {
      for (const item of group) keys.add(item);
      break;
    }
  }
  return keys;
}

export function locationHitsMap(
  loc: LocationRef,
  mapSlug: string | Set<string>,
): boolean {
  const keys = mapSlug instanceof Set ? mapSlug : mapSlugKeys(mapSlug);
  const slug = (loc.map_slug || "").trim().toLowerCase();
  if (slug && keys.has(slug)) return true;
  const name = (loc.map_name || "").trim().toLowerCase();
  if (!name) return false;
  if (keys.has(name.replace(/[\s_]+/g, "-"))) return true;
  for (const option of raidPrepMapOptions()) {
    if (!keys.has(option.id)) continue;
    if (option.label.toLowerCase() === name) return true;
    if (option.english.toLowerCase() === name) return true;
  }
  return false;
}

export function colorForTaskId(id: string): string {
  let hash = 2166136261;
  for (let i = 0; i < id.length; i += 1) {
    hash ^= id.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  const index = Math.abs(hash) % RAID_PREP_TASK_COLORS.length;
  return RAID_PREP_TASK_COLORS[index];
}

export function colorForTaskIndex(index: number): string {
  const n = RAID_PREP_TASK_COLORS.length;
  const i = Number.isFinite(index) ? Math.abs(Math.trunc(index)) : 0;
  return RAID_PREP_TASK_COLORS[i % n];
}

export function colorForUserId(userId: number): string {
  return colorForTaskId(`user:${userId}`);
}

export function traderFilterLabel(
  slug: string,
  apiName: string,
): { english: string; chinese: string } {
  const known = TARKOV_TRADERS.find((item) => item.id === slug);
  if (known) return { english: known.english, chinese: known.chinese };
  const match = apiName.match(/^(.*?)\s*[（(](.+?)[）)]\s*$/);
  if (match) {
    return { english: match[1].trim(), chinese: match[2].trim() };
  }
  return { english: apiName, chinese: "" };
}

/** 与后端 filter_task_rows 对齐；前端单次拉全量后本地筛。 */
export function filterRaidPrepRows<
  T extends {
    id?: string | null;
    name?: string | null;
    normalized_name?: string | null;
    trader_id?: string | null;
    trader_slug?: string | null;
    trader_name?: string | null;
    map_name?: string | null;
    progress_status?: string | null;
  },
>(
  rows: T[],
  opts: {
    trader?: string;
    q?: string;
    progressStatus?: string;
  } = {},
): T[] {
  const traderKey = (opts.trader || "").trim().toLowerCase();
  const needle = (opts.q || "").trim().toLowerCase();
  const statusKey = (opts.progressStatus || "").trim().toLowerCase();
  const statusFilter =
    statusKey && statusKey !== "all" ? statusKey : "";
  return rows.filter((row) => {
    if (traderKey) {
      const slug = String(row.trader_slug || "").toLowerCase();
      const tid = String(row.trader_id || "").toLowerCase();
      const tname = String(row.trader_name || "").toLowerCase();
      if (traderKey !== slug && traderKey !== tid && !tname.includes(traderKey)) {
        return false;
      }
    }
    if (statusFilter && String(row.progress_status || "") !== statusFilter) {
      return false;
    }
    if (needle) {
      const blob = [
        row.name,
        row.normalized_name,
        row.id,
        row.trader_name,
        row.map_name,
      ]
        .map((v) => String(v || "").toLowerCase())
        .join(" ");
      if (!blob.includes(needle)) return false;
    }
    return true;
  });
}

function validPoints(
  rows: Array<{ x?: number | null; y?: number | null; z?: number | null }> | null | undefined,
): RaidPrepPoint[] {
  const out: RaidPrepPoint[] = [];
  for (const row of rows || []) {
    if (!isFiniteNumber(row.x) || !isFiniteNumber(row.z)) continue;
    const point: RaidPrepPoint = { x: row.x, z: row.z };
    if (isFiniteNumber(row.y)) point.y = row.y;
    out.push(point);
  }
  return out;
}

export function spansOverlap(
  a: RaidPrepHeightSpan,
  b: RaidPrepHeightSpan,
): boolean {
  return a.min <= b.max && b.min <= a.max;
}

export function zoneHeightSpan(zone: ZoneLike): RaidPrepHeightSpan | null {
  if (isFiniteNumber(zone.top) && isFiniteNumber(zone.bottom)) {
    return {
      min: Math.min(zone.top, zone.bottom),
      max: Math.max(zone.top, zone.bottom),
    };
  }
  if (isFiniteNumber(zone.y)) return { min: zone.y, max: zone.y };
  return null;
}

export function pointsHeightSpan(
  points: RaidPrepPoint[],
): RaidPrepHeightSpan | null {
  const ys = points
    .map((point) => point.y)
    .filter((value): value is number => isFiniteNumber(value));
  if (!ys.length) return null;
  return { min: Math.min(...ys), max: Math.max(...ys) };
}

/** 无高度的点只在地面层；有高度则与楼层 extents 相交才显示。 */
export function overlayVisibleOnFloor(
  span: RaidPrepHeightSpan | null | undefined,
  floorName: string,
  bands: readonly RaidPrepFloorBand[],
): boolean {
  if (!bands.length) return true;
  if (!floorName) {
    if (!span) return true;
    const ground = bands.find((band) => !band.name);
    if (!ground) return true;
    return spansOverlap(span, ground);
  }
  if (!span) return false;
  const named = bands.find((band) => band.name === floorName);
  if (!named) return true;
  return spansOverlap(span, named);
}

export function overlayFloorNames(
  span: RaidPrepHeightSpan | null | undefined,
  bands: readonly RaidPrepFloorBand[],
): string[] {
  if (!span) return [];
  const names: string[] = [];
  for (const band of bands) {
    if (!band.name) continue;
    if (!spansOverlap(span, band)) continue;
    names.push(band.name);
  }
  return names;
}

/** 点位应对齐的楼层名；空字符串是地面。 */
export function overlayFloorForSpan(
  span: RaidPrepHeightSpan | null | undefined,
  bands: readonly RaidPrepFloorBand[],
): string {
  if (!bands.length) return "";
  if (!span) return "";
  const named = overlayFloorNames(span, bands);
  if (named.length) return named[0]!;
  const ground = bands.find((band) => !band.name);
  if (ground && spansOverlap(span, ground)) return "";
  const mid = (span.min + span.max) / 2;
  let best = "";
  let bestDist = Number.POSITIVE_INFINITY;
  for (const band of bands) {
    const clamped = Math.min(band.max, Math.max(band.min, mid));
    const dist = Math.abs(mid - clamped);
    if (dist < bestDist) {
      bestDist = dist;
      best = band.name;
    }
  }
  return best;
}

export function overlayFloorForPoint(
  y: number | null | undefined,
  bands: readonly RaidPrepFloorBand[],
): string {
  if (!isFiniteNumber(y)) return "";
  return overlayFloorForSpan({ min: y, max: y }, bands);
}

export function mapLayerFloorBands(
  layer:
    | {
        heightRange?: number[] | null;
        layers?: Array<{
          name?: string;
          extents?: Array<{ height?: number[] }> | null;
        }> | null;
      }
    | null
    | undefined,
): RaidPrepFloorBand[] {
  if (!layer) return [];
  const bands: RaidPrepFloorBand[] = [];
  const range = layer.heightRange;
  if (
    range &&
    range.length >= 2 &&
    Number.isFinite(range[0]) &&
    Number.isFinite(range[1])
  ) {
    bands.push({
      name: "",
      min: Math.min(range[0]!, range[1]!),
      max: Math.max(range[0]!, range[1]!),
    });
  }
  for (const floor of layer.layers || []) {
    const height = floor.extents?.[0]?.height;
    const name = (floor.name || "").trim();
    if (!name || !height || height.length < 2) continue;
    if (!Number.isFinite(height[0]) || !Number.isFinite(height[1])) continue;
    bands.push({
      name,
      min: Math.min(height[0]!, height[1]!),
      max: Math.max(height[0]!, height[1]!),
    });
  }
  return bands;
}

export function raidPrepMapOptions(): RaidPrepMapOption[] {
  const ready = TARKOV_MAPS.filter(
    (item) => item.status === "ready" && !item.comingSoon,
  );
  const factory = ready.find((item) => item.id === "factory");
  const out: RaidPrepMapOption[] = [];
  for (const item of ready) {
    out.push({
      id: item.id,
      label: item.label,
      english: item.english,
      icon: item.icon,
    });
    if (item.id === "factory" && factory) {
      out.push({
        id: "night-factory",
        label: "夜间工厂",
        english: "Factory (Night)",
        icon: factory.icon,
      });
    }
  }
  return out;
}

export function normalizeRaidPrepMapId(raw: string): string {
  const keys = mapSlugKeys(raw);
  if (!keys.size) return "";
  for (const option of raidPrepMapOptions()) {
    const optionKeys = mapSlugKeys(option.id);
    for (const key of keys) {
      if (optionKeys.has(key)) return option.id;
    }
  }
  return "";
}

export function parseCsvParam(raw: string | null | undefined): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of (raw || "").split(",")) {
    const item = part.trim();
    if (!item || seen.has(item)) continue;
    seen.add(item);
    out.push(item);
  }
  return out;
}

export function serializeSelectedIds(ids: string[]): string {
  return parseCsvParam(ids.join(",")).slice(0, RAID_PREP_MAX_SELECTED).join(",");
}

/** 按勾选顺序从整图目录取出已选任务。 */
export function selectedTasksFromCatalog<T extends { id: string }>(
  catalog: readonly T[],
  selectedIds: readonly string[],
): T[] {
  const byId = new Map(catalog.map((row) => [row.id, row]));
  const out: T[] = [];
  for (const id of selectedIds) {
    const row = byId.get(id);
    if (row) out.push(row);
  }
  return out;
}

/** 已选单独成区；筛选列表不再包含已选项。 */
export function partitionRaidPrepRows<T extends { id: string }>(
  filteredRows: readonly T[],
  selectedRows: readonly T[],
): { picked: T[]; rest: T[] } {
  const selectedIds = new Set(selectedRows.map((row) => row.id));
  return {
    picked: [...selectedRows],
    rest: filteredRows.filter((row) => !selectedIds.has(row.id)),
  };
}

/** 勾选任务置顶，组内保持原列表相对顺序。 */
export function pinSelectedRaidPrepRows<T extends { id: string }>(
  rows: readonly T[],
  selectedIds: ReadonlySet<string>,
): T[] {
  if (!selectedIds.size) return [...rows];
  const picked: T[] = [];
  const rest: T[] = [];
  for (const row of rows) {
    if (selectedIds.has(row.id)) picked.push(row);
    else rest.push(row);
  }
  return picked.length ? [...picked, ...rest] : [...rows];
}

export function objectiveZoneNames(task: RaidPrepTaskLike): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const obj of task.objectives || []) {
    for (const name of obj.zone_names || []) {
      const text = String(name || "").trim();
      if (!text || seen.has(text)) continue;
      seen.add(text);
      out.push(text);
    }
  }
  return out;
}

export function neededKeyNamesForMap(
  task: RaidPrepTaskLike,
  mapSlug: string,
): string[] {
  const keys = mapSlugKeys(mapSlug);
  const seen = new Set<string>();
  const out: string[] = [];
  for (const row of task.needed_keys || []) {
    const slug = (row.map?.slug || "").trim().toLowerCase();
    if (slug && !keys.has(slug)) continue;
    for (const key of row.keys || []) {
      const name = tarkovReadableName(key.name, key.id);
      if (!name || seen.has(name)) continue;
      seen.add(name);
      out.push(name);
    }
  }
  return out;
}

/** 只读该目标 required_keys，不回退任务级 needed_keys，避免把别的点的钥匙挂过来。 */
export function objectiveKeyNames(obj: RaidPrepObjectiveLike): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const group of obj.required_keys || []) {
    for (const key of group || []) {
      const name = tarkovReadableName(key.name, key.id);
      if (!name || seen.has(name)) continue;
      seen.add(name);
      out.push(name);
    }
  }
  return out;
}

/** 目标气泡：需要宿舍 114 钥匙 / 需要 TerraGroup 会议室钥匙。 */
export function formatRaidPrepKeyNeedLine(
  keyNames: string[] | null | undefined,
): string {
  const names = (keyNames || [])
    .map((name) => name.trim())
    .filter(Boolean)
    .map((name) => (name.includes("钥匙") ? name : `${name}钥匙`));
  if (!names.length) return "";
  return `需要${names.join("、")}`;
}

/** 无地图限制的目标（如上交）算本局需要；标了别的图则排除。 */
export function objectiveAppliesToMap(
  obj: RaidPrepObjectiveLike,
  mapSlug: string,
): boolean {
  const keys = mapSlugKeys(mapSlug);
  const maps = obj.maps || [];
  const zones = obj.zones || [];
  const locs = obj.possible_locations || [];
  const hasLocation =
    maps.some((map) => (map.slug || "").trim()) ||
    zones.length > 0 ||
    locs.length > 0;
  if (!hasLocation) return true;
  if (
    maps.some((map) => keys.has((map.slug || "").trim().toLowerCase()))
  ) {
    return true;
  }
  if (zones.some((zone) => locationHitsMap(zone, keys))) return true;
  if (locs.some((loc) => locationHitsMap(loc, keys))) return true;
  return false;
}

export function raidPrepObjectiveKey(
  obj: RaidPrepObjectiveLike,
  index: number,
): string {
  const id = (obj.id || "").trim();
  return id || `i:${index}`;
}

export function raidPrepSkippedIds(
  skippedByTask: RaidPrepSkipMap | undefined,
  taskId: string,
): ReadonlySet<string> {
  return skippedByTask?.get(taskId) || EMPTY_SKIP;
}

export function toggleRaidPrepObjectiveDone(
  current: RaidPrepSkipMap,
  taskId: string,
  objectiveId: string,
): Map<string, Set<string>> {
  const next = new Map<string, Set<string>>();
  for (const [id, ids] of current) next.set(id, new Set(ids));
  const bucket = new Set(next.get(taskId) || []);
  if (bucket.has(objectiveId)) bucket.delete(objectiveId);
  else bucket.add(objectiveId);
  if (bucket.size) next.set(taskId, bucket);
  else next.delete(taskId);
  return next;
}

type StoredObjectiveDone = Record<string, Record<string, string[]>>;

function readObjectiveDoneStore(): StoredObjectiveDone {
  try {
    const raw = localStorage.getItem(RAID_PREP_OBJ_DONE_STORAGE);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return {};
    return parsed as StoredObjectiveDone;
  } catch {
    return {};
  }
}

function writeObjectiveDoneStore(data: StoredObjectiveDone) {
  try {
    localStorage.setItem(RAID_PREP_OBJ_DONE_STORAGE, JSON.stringify(data));
  } catch {
    /* ignore quota / private mode */
  }
}

export function parseRaidPrepObjectiveDone(
  raw: Record<string, string[]> | null | undefined,
): Map<string, Set<string>> {
  const out = new Map<string, Set<string>>();
  for (const [taskId, ids] of Object.entries(raw || {})) {
    if (!taskId || !Array.isArray(ids)) continue;
    const bucket = new Set<string>();
    for (const id of ids) {
      const key = String(id || "").trim();
      if (key) bucket.add(key);
    }
    if (bucket.size) out.set(taskId, bucket);
  }
  return out;
}

export function serializeRaidPrepObjectiveDone(
  skipped: RaidPrepSkipMap,
): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  for (const [taskId, ids] of skipped) {
    if (!ids.size) continue;
    out[taskId] = [...ids];
  }
  return out;
}

export function readRaidPrepObjectiveDone(scope: string): Map<string, Set<string>> {
  const key = (scope || "").trim();
  if (!key) return new Map();
  return parseRaidPrepObjectiveDone(readObjectiveDoneStore()[key]);
}

export function writeRaidPrepObjectiveDone(
  scope: string,
  skipped: RaidPrepSkipMap,
) {
  const key = (scope || "").trim();
  if (!key) return;
  const all = readObjectiveDoneStore();
  const serialized = serializeRaidPrepObjectiveDone(skipped);
  if (Object.keys(serialized).length) all[key] = serialized;
  else delete all[key];
  writeObjectiveDoneStore(all);
}

export function raidPrepObjectiveDoneScope(
  kind: "solo" | "room",
  id: string,
): string {
  const key = (id || "").trim();
  if (!key) return "";
  return kind === "room" ? `room:${key}` : `solo:${key}`;
}

export function useRaidPrepObjectiveDone(scope: string) {
  const [done, setDone] = useState(() => readRaidPrepObjectiveDone(scope));
  useEffect(() => {
    setDone(readRaidPrepObjectiveDone(scope));
  }, [scope]);
  const toggle = useCallback((taskId: string, objectiveId: string) => {
    setDone((current) => {
      const next = toggleRaidPrepObjectiveDone(current, taskId, objectiveId);
      writeRaidPrepObjectiveDone(scope, next);
      return next;
    });
  }, [scope]);
  return [done, toggle] as const;
}

function namedRefItem(
  ref: RaidPrepNamedRef,
  extras: Omit<RaidPrepNeededItem, "id" | "name" | "icon_link" | "types">,
): RaidPrepNeededItem | null {
  const id = (ref.id || "").trim();
  if (!id) return null;
  const name = tarkovReadableName(ref.name, id) || id;
  return {
    id,
    name,
    icon_link: (ref.icon_link || "").trim(),
    types: (ref.types || []).filter(Boolean).map(String),
    ...extras,
  };
}

function mergeNeededItem(
  index: Map<string, RaidPrepNeededItem>,
  out: RaidPrepNeededItem[],
  item: RaidPrepNeededItem,
) {
  const key = [
    item.kind,
    item.id,
    item.role,
    item.found_in_raid ? "1" : "0",
    item.optional ? "1" : "0",
  ].join("|");
  const existing = index.get(key);
  if (existing) {
    if (item.kind !== "key") existing.count += item.count;
    return;
  }
  index.set(key, item);
  out.push(item);
}

function objectiveItemCount(
  obj: RaidPrepObjectiveLike,
  itemCount: number,
): number {
  const count = obj.count;
  if (itemCount === 1 && typeof count === "number" && count > 0) return count;
  return 1;
}

/** 目标原文写明「任意」某一类，且候选够多：收成一条展示。 */
export function isRaidPrepAnyOfCategoryObjective(
  obj: RaidPrepObjectiveLike,
  itemCount: number,
): boolean {
  if (itemCount < RAID_PREP_ANY_OF_MIN) return false;
  return (obj.description || "").includes("任意");
}

function objectiveHasRequiredKeys(obj: RaidPrepObjectiveLike): boolean {
  return (obj.required_keys || []).some((group) =>
    (group || []).some((key) =>
      Boolean((key.id || "").trim() || tarkovReadableName(key.name, key.id)),
    ),
  );
}

function mergeObjectiveRequiredKeys(
  obj: RaidPrepObjectiveLike,
  index: Map<string, RaidPrepNeededItem>,
  out: RaidPrepNeededItem[],
) {
  for (const group of obj.required_keys || []) {
    for (const key of group || []) {
      const item = namedRefItem(key, {
        count: 1,
        found_in_raid: false,
        optional: Boolean(obj.optional),
        kind: "key",
        role: "钥匙",
        objectiveType: "key",
      });
      if (item) mergeNeededItem(index, out, item);
    }
  }
}

function collectNeededKeysForMap(
  task: RaidPrepTaskLike,
  mapSlug: string,
): RaidPrepNeededItem[] {
  const out: RaidPrepNeededItem[] = [];
  const index = new Map<string, RaidPrepNeededItem>();
  const mapKeys = mapSlugKeys(mapSlug);
  for (const row of task.needed_keys || []) {
    const slug = (row.map?.slug || "").trim().toLowerCase();
    if (slug && !mapKeys.has(slug)) continue;
    for (const key of row.keys || []) {
      const item = namedRefItem(key, {
        count: 1,
        found_in_raid: false,
        optional: false,
        kind: "key",
        role: "钥匙",
        objectiveType: "key",
      });
      if (item) mergeNeededItem(index, out, item);
    }
  }
  return out;
}

function mapObjectives(
  task: RaidPrepTaskLike,
  mapSlug: string,
): Array<{ obj: RaidPrepObjectiveLike; index: number }> {
  const out: Array<{ obj: RaidPrepObjectiveLike; index: number }> = [];
  (task.objectives || []).forEach((obj, index) => {
    if (!objectiveAppliesToMap(obj, mapSlug)) return;
    out.push({ obj, index });
  });
  return out;
}

/** 当前地图任务详情钥匙：有分目标钥匙时只算未勾掉的点；否则回退 needed_keys。 */
export function collectRaidPrepTaskKeys(
  task: RaidPrepTaskLike,
  mapSlug: string,
  skipped?: ReadonlySet<string>,
): RaidPrepNeededItem[] {
  const done = skipped || EMPTY_SKIP;
  const applicable = mapObjectives(task, mapSlug);
  const remaining = applicable.filter(
    ({ obj, index }) => !done.has(raidPrepObjectiveKey(obj, index)),
  );
  if (done.size && applicable.length && remaining.length === 0) return [];

  const fromRemaining: RaidPrepNeededItem[] = [];
  const remainingIndex = new Map<string, RaidPrepNeededItem>();
  for (const { obj } of remaining) {
    mergeObjectiveRequiredKeys(obj, remainingIndex, fromRemaining);
  }
  const mapHasObjKeys = applicable.some(({ obj }) => objectiveHasRequiredKeys(obj));
  if (mapHasObjKeys) {
    if (fromRemaining.length) return fromRemaining;
    const skippedObjs = applicable.filter(({ obj, index }) =>
      done.has(raidPrepObjectiveKey(obj, index)),
    );
    if (skippedObjs.some(({ obj }) => objectiveHasRequiredKeys(obj))) {
      const skipNames = new Set(
        skippedObjs.flatMap(({ obj }) => objectiveKeyNames(obj)),
      );
      return collectNeededKeysForMap(task, mapSlug).filter(
        (item) => !skipNames.has(item.name),
      );
    }
    return collectNeededKeysForMap(task, mapSlug);
  }
  return collectNeededKeysForMap(task, mapSlug);
}

function collectObjectiveNeededItems(
  obj: RaidPrepObjectiveLike,
  objIndex: number,
): RaidPrepNeededItem[] {
  const refs = obj.items || [];
  if (!refs.length) return [];
  const objectiveType = (obj.type || "").trim();
  const role = tarkovObjectiveTypeLabel(objectiveType) || "物品";
  const extras = {
    found_in_raid: Boolean(obj.found_in_raid),
    optional: Boolean(obj.optional),
    kind: "item" as const,
    role,
    objectiveType,
  };
  const members: RaidPrepNeededItem[] = [];
  for (const ref of refs) {
    const item = namedRefItem(ref, { count: 1, ...extras });
    if (item) members.push(item);
  }
  if (!members.length) return [];
  if (isRaidPrepAnyOfCategoryObjective(obj, members.length)) {
    const lead = members[0]!;
    const qty =
      typeof obj.count === "number" && obj.count > 0 ? obj.count : 1;
    return [
      {
        ...lead,
        id: `any:${raidPrepObjectiveKey(obj, objIndex)}`,
        name: (obj.description || "").trim() || "物品",
        count: qty,
        anyOf: members,
      },
    ];
  }
  const count = objectiveItemCount(obj, members.length);
  return members.map((item) => ({ ...item, count }));
}

/** 勾选任务在当前地图上要上交 / 要捡的物品（不含钥匙）。 */
export function collectRaidPrepTaskItems(
  task: RaidPrepTaskLike,
  mapSlug: string,
  skipped?: ReadonlySet<string>,
): RaidPrepNeededItem[] {
  const out: RaidPrepNeededItem[] = [];
  const index = new Map<string, RaidPrepNeededItem>();
  const done = skipped || EMPTY_SKIP;

  (task.objectives || []).forEach((obj, objIndex) => {
    if (!objectiveAppliesToMap(obj, mapSlug)) return;
    if (done.has(raidPrepObjectiveKey(obj, objIndex))) return;
    for (const item of collectObjectiveNeededItems(obj, objIndex)) {
      mergeNeededItem(index, out, item);
    }
  });
  return out;
}

function shootObjectiveText(obj: RaidPrepObjectiveLike): string {
  const description = tarkovReadableName(obj.description, obj.id);
  const typeLabel = tarkovObjectiveTypeLabel(obj.type || "") || "击杀";
  const text = description || typeLabel;
  return obj.optional ? `${text}（可选）` : text;
}

/** 当前地图未勾掉的击杀目标：总结表一列一条描述。 */
export function collectRaidPrepTaskShootSlots(
  task: RaidPrepTaskLike,
  mapSlug: string,
  skipped?: ReadonlySet<string>,
): RaidPrepSummaryShootSlot[] {
  const out: RaidPrepSummaryShootSlot[] = [];
  const done = skipped || EMPTY_SKIP;
  (task.objectives || []).forEach((obj, index) => {
    if (!objectiveAppliesToMap(obj, mapSlug)) return;
    if (done.has(raidPrepObjectiveKey(obj, index))) return;
    if (!isRaidPrepSummaryShootType(obj.type || "")) return;
    out.push({
      id: raidPrepObjectiveKey(obj, index),
      text: shootObjectiveText(obj),
      optional: Boolean(obj.optional),
      count: raidPrepObjectiveCount(obj),
      items: collectObjectiveNeededItems(obj, index).map((item) =>
        item.anyOf ? item : { ...item, count: 1 },
      ),
    });
  });
  return out;
}

/** 按准备总结列分组：找到/捡取、上交、藏匿各自合成一列。 */
export function groupRaidPrepItemsByType(
  items: RaidPrepNeededItem[],
): Record<string, RaidPrepNeededItem[]> {
  const out: Record<string, RaidPrepNeededItem[]> = {};
  for (const item of items) {
    const key = raidPrepSummaryColumnType(item.objectiveType);
    const bucket = out[key];
    if (bucket) bucket.push(item);
    else out[key] = [item];
  }
  return out;
}

/** 勾选任务里带了物品的目标类型；进局携带列排在找到/上交前面。 */
export function collectRaidPrepSummaryTypeColumns(
  rows: readonly RaidPrepTaskSummary[],
): string[] {
  const types: string[] = [];
  for (const row of rows) types.push(...Object.keys(row.itemsByType || {}));
  return orderRaidPrepSummaryTypeColumns(types);
}

export function collectRaidPrepTaskTypes(
  task: RaidPrepTaskLike,
  mapSlug: string,
  skipped?: ReadonlySet<string>,
): string[] {
  const types: string[] = [];
  const done = skipped || EMPTY_SKIP;
  (task.objectives || []).forEach((obj, index) => {
    if (!objectiveAppliesToMap(obj, mapSlug)) return;
    if (done.has(raidPrepObjectiveKey(obj, index))) return;
    const type = (obj.type || "").trim();
    if (type) types.push(type);
  });
  return orderObjectiveTypes(types);
}

/** 准备总结任务名悬停：当前图适用的目标（含已勾掉，才能取消）。 */
export function collectRaidPrepTaskObjectives(
  task: RaidPrepTaskLike,
  mapSlug: string,
): RaidPrepObjectiveHint[] {
  const out: RaidPrepObjectiveHint[] = [];
  (task.objectives || []).forEach((obj, index) => {
    if (!objectiveAppliesToMap(obj, mapSlug)) return;
    const description = tarkovReadableName(obj.description, obj.id);
    const typeLabel = tarkovObjectiveTypeLabel(obj.type || "");
    const text = description || typeLabel;
    if (!text) return;
    const line = obj.optional ? `${text}（可选）` : text;
    out.push({
      id: raidPrepObjectiveKey(obj, index),
      text: line,
      optional: Boolean(obj.optional),
      keyNames: objectiveKeyNames(obj),
    });
  });
  return out;
}

/** 准备总结任务名悬停：当前图适用的目标描述（无描述则用类型名）。 */
export function collectRaidPrepTaskObjectiveLines(
  task: RaidPrepTaskLike,
  mapSlug: string,
): string[] {
  const lines: string[] = [];
  const seen = new Set<string>();
  for (const obj of collectRaidPrepTaskObjectives(task, mapSlug)) {
    if (seen.has(obj.text)) continue;
    seen.add(obj.text);
    lines.push(obj.text);
  }
  return lines;
}

export function buildRaidPrepSummary(
  tasks: RaidPrepTaskLike[],
  mapSlug: string,
  skippedByTask?: RaidPrepSkipMap,
): RaidPrepTaskSummary[] {
  return tasks.map((task) => {
    const skipped = raidPrepSkippedIds(skippedByTask, task.id);
    const items = collectRaidPrepTaskItems(task, mapSlug, skipped);
    const keys = collectRaidPrepTaskKeys(task, mapSlug, skipped);
    const objectives = collectRaidPrepTaskObjectives(task, mapSlug);
    return {
      taskId: task.id,
      taskName: displayRaidPrepTaskName(task),
      traderSlug: (task.trader_slug || "").trim(),
      traderName: (task.trader_name || "").trim(),
      itemsByType: groupRaidPrepItemsByType(items),
      keys,
      shootSlots: collectRaidPrepTaskShootSlots(task, mapSlug, skipped),
      types: collectRaidPrepTaskTypes(task, mapSlug, skipped),
      objectiveLines: collectRaidPrepTaskObjectiveLines(task, mapSlug),
      objectives,
    };
  });
}

/** 准备总结表：参与人数多的排前面；同人数按任务名。 */
export function sortRaidPrepSummaryByParticipants<
  T extends { taskId: string; taskName?: string },
>(
  rows: readonly T[],
  participantsByTask?: ReadonlyMap<string, readonly unknown[]>,
): T[] {
  return [...rows].sort((a, b) => {
    const na = participantsByTask?.get(a.taskId)?.length ?? 0;
    const nb = participantsByTask?.get(b.taskId)?.length ?? 0;
    if (nb !== na) return nb - na;
    const nameA = (a.taskName || a.taskId).trim() || a.taskId;
    const nameB = (b.taskName || b.taskId).trim() || b.taskId;
    return nameA.localeCompare(nameB, "zh");
  });
}

function distinguishTaskOverlays(
  overlays: TarkovRaidPrepOverlay[],
): TarkovRaidPrepOverlay[] {
  const groups = new Map<string, TarkovRaidPrepOverlay[]>();
  for (const row of overlays) {
    const list = groups.get(row.taskId);
    if (list) list.push(row);
    else groups.set(row.taskId, [row]);
  }
  for (const list of groups.values()) {
    const anyKey = list.some((row) => row.keyNames.length > 0);
    const numbered = list.length > 1;
    list.forEach((row, index) => {
      if (numbered) row.title = `${row.title} ${index + 1}`;
      row.showNoKey = anyKey && row.keyNames.length === 0;
    });
  }
  return overlays;
}

export function buildRaidPrepOverlays(
  tasks: RaidPrepTaskLike[],
  mapSlug: string,
  skippedByTask?: RaidPrepSkipMap,
): TarkovRaidPrepOverlay[] {
  const keys = mapSlugKeys(mapSlug);
  const overlays: TarkovRaidPrepOverlay[] = [];
  tasks.forEach((task, taskIndex) => {
    const color = colorForTaskIndex(taskIndex);
    const taskName = displayRaidPrepTaskName(task);
    const traderSlug = (task.trader_slug || "").trim();
    const skipped = raidPrepSkippedIds(skippedByTask, task.id);
    (task.objectives || []).forEach((obj, objIndex) => {
      if (skipped.has(raidPrepObjectiveKey(obj, objIndex))) return;
      const typeLabel = tarkovObjectiveTypeLabel(obj.type || "");
      const description = tarkovReadableName(obj.description, obj.id);
      const subtitle = [typeLabel, description].filter(Boolean).join(" · ");
      const optional = Boolean(obj.optional);
      const keyNames = objectiveKeyNames(obj);
      let zoneIdx = 0;
      for (const zone of obj.zones || []) {
        if (!locationHitsMap(zone, keys)) continue;
        const outline = validPoints(zone.outline);
        const center =
          isFiniteNumber(zone.x) && isFiniteNumber(zone.z)
            ? [
                {
                  x: zone.x,
                  z: zone.z,
                  ...(isFiniteNumber(zone.y) ? { y: zone.y } : {}),
                },
              ]
            : [];
        const polygon = outline.length >= 3 ? outline : [];
        const points = polygon.length ? center : [...center, ...outline];
        if (!polygon.length && !points.length) continue;
        overlays.push({
          key: `${task.id}:zone:${zone.id || zoneIdx}`,
          taskId: task.id,
          kind: "zone",
          color,
          title: taskName,
          subtitle,
          traderSlug,
          keyNames,
          showNoKey: false,
          optional,
          outline: polygon,
          points,
          height: zoneHeightSpan(zone) || pointsHeightSpan(points),
        });
        zoneIdx += 1;
      }
      let locIdx = 0;
      for (const loc of obj.possible_locations || []) {
        if (!locationHitsMap(loc, keys)) continue;
        const positions = validPoints(loc.positions);
        if (!positions.length) continue;
        overlays.push({
          key: `${task.id}:spawn:${locIdx}`,
          taskId: task.id,
          kind: "spawn",
          color,
          title: taskName,
          subtitle: subtitle || "可能刷新点",
          traderSlug,
          keyNames,
          showNoKey: false,
          optional,
          outline: [],
          points: positions,
          height: pointsHeightSpan(positions),
        });
        locIdx += 1;
      }
    });
  });
  return distinguishTaskOverlays(overlays);
}

function centroidOf(points: RaidPrepPoint[]): RaidPrepPoint {
  let x = 0;
  let z = 0;
  for (const point of points) {
    x += point.x;
    z += point.z;
  }
  const n = points.length || 1;
  return { x: x / n, z: z / n };
}

function zoneAnchorPoint(zone: ZoneLike): RaidPrepPoint | null {
  const outline = validPoints(zone.outline);
  const center =
    isFiniteNumber(zone.x) && isFiniteNumber(zone.z)
      ? { x: zone.x, z: zone.z }
      : null;
  const polygon = outline.length >= 3 ? outline : [];
  let point: RaidPrepPoint | null = null;
  if (polygon.length) {
    point = center ?? centroidOf(outline);
  } else if (center) {
    point = center;
  } else if (outline.length) {
    point = outline[0]!;
  }
  if (!point) return null;
  const span = zoneHeightSpan(zone);
  if (span) point = { ...point, y: (span.min + span.max) / 2 };
  return point;
}

/** 任务在当前地图的定位点：非 optional 在前，可选在后。 */
export function resolveRaidPrepLocatePoints(
  task: RaidPrepTaskLike,
  mapSlug: string,
  skipped?: ReadonlySet<string>,
): RaidPrepPoint[] {
  const keys = mapSlugKeys(mapSlug);
  const required: RaidPrepPoint[] = [];
  const optional: RaidPrepPoint[] = [];
  const done = skipped || EMPTY_SKIP;
  (task.objectives || []).forEach((obj, index) => {
    if (done.has(raidPrepObjectiveKey(obj, index))) return;
    const bucket = obj.optional ? optional : required;
    for (const zone of obj.zones || []) {
      if (!locationHitsMap(zone, keys)) continue;
      const point = zoneAnchorPoint(zone);
      if (point) bucket.push(point);
    }
    for (const loc of obj.possible_locations || []) {
      if (!locationHitsMap(loc, keys)) continue;
      bucket.push(...validPoints(loc.positions));
    }
  });
  return [...required, ...optional];
}

/** 任务在当前地图的首个定位点：优先非 optional 目标的首个 zone / 刷新点。 */
export function resolveRaidPrepLocatePoint(
  task: RaidPrepTaskLike,
  mapSlug: string,
): RaidPrepPoint | null {
  return resolveRaidPrepLocatePoints(task, mapSlug)[0] ?? null;
}

function overlayLabelSeeds(row: TarkovRaidPrepOverlay): RaidPrepPoint[] {
  if (row.outline.length >= 3) {
    return row.points.length
      ? [centroidOf(row.points)]
      : [centroidOf(row.outline)];
  }
  return row.points;
}

type OverlayLabelSeed = RaidPrepPoint & {
  taskId: string;
  title: string;
  color: string;
  traderSlug: string;
  subtitle: string;
  keyNames: string[];
  showNoKey: boolean;
  optional: boolean;
  height: RaidPrepHeightSpan | null;
};

function collectOverlayLabelSeeds(
  overlays: TarkovRaidPrepOverlay[],
): OverlayLabelSeed[] {
  const seeds: OverlayLabelSeed[] = [];
  for (const row of overlays) {
    const title = tarkovReadableName(row.title);
    if (!title) continue;
    for (const point of overlayLabelSeeds(row)) {
      seeds.push({
        x: point.x,
        z: point.z,
        taskId: row.taskId,
        title,
        color: row.color,
        traderSlug: (row.traderSlug || "").trim(),
        subtitle: row.subtitle || "",
        keyNames: row.keyNames || [],
        showNoKey: Boolean(row.showNoKey),
        optional: row.optional,
        height: row.height,
      });
    }
  }
  return seeds;
}

function clusterSeedRoots(
  seeds: OverlayLabelSeed[],
  gap: number,
  project: (point: RaidPrepPoint) => RaidPrepPoint,
): number[] {
  const parent = seeds.map((_, index) => index);
  const find = (index: number): number => {
    let cur = index;
    while (parent[cur] !== cur) {
      parent[cur] = parent[parent[cur]!]!;
      cur = parent[cur]!;
    }
    return cur;
  };
  const pts = seeds.map(project);
  const gap2 = gap * gap;
  for (let i = 0; i < pts.length; i += 1) {
    const a = pts[i]!;
    for (let j = i + 1; j < pts.length; j += 1) {
      const b = pts[j]!;
      const dx = a.x - b.x;
      const dz = a.z - b.z;
      if (dx * dx + dz * dz > gap2) continue;
      const ra = find(i);
      const rb = find(j);
      if (ra !== rb) parent[rb] = ra;
    }
  }
  return seeds.map((_, index) => find(index));
}

function nearestSeed(
  group: OverlayLabelSeed[],
  project: (point: RaidPrepPoint) => RaidPrepPoint,
): OverlayLabelSeed {
  if (group.length === 1) return group[0]!;
  const pts = group.map(project);
  let cx = 0;
  let cz = 0;
  for (const point of pts) {
    cx += point.x;
    cz += point.z;
  }
  const n = pts.length;
  cx /= n;
  cz /= n;
  let best = 0;
  let bestD = Infinity;
  for (let i = 0; i < pts.length; i += 1) {
    const dx = pts[i]!.x - cx;
    const dz = pts[i]!.z - cz;
    const dist = dx * dx + dz * dz;
    if (dist < bestD) {
      bestD = dist;
      best = i;
    }
  }
  return group[best]!;
}

function resolveLabelClusterOpts(
  gapOrOpts?: number | RaidPrepLabelClusterOpts,
): {
  gap: number;
  project: (point: RaidPrepPoint) => RaidPrepPoint;
} {
  if (gapOrOpts == null || typeof gapOrOpts === "number") {
    return {
      gap: gapOrOpts ?? RAID_PREP_LABEL_CLUSTER_GAP,
      project: (point) => point,
    };
  }
  return {
    gap: gapOrOpts.gap,
    project: gapOrOpts.project ?? ((point) => point),
  };
}

/**
 * 勾选任务的地图名称：邻近同名点合并成一条，不同任务叠在同一簇则纵向并列。
 * `project` 把世界坐标投到聚类空间（屏幕像素），标签仍锚在真实点位上。
 */
export function clusterRaidPrepOverlayLabels(
  overlays: TarkovRaidPrepOverlay[],
  gapOrOpts: number | RaidPrepLabelClusterOpts = RAID_PREP_LABEL_CLUSTER_GAP,
): RaidPrepOverlayLabel[] {
  const { gap, project } = resolveLabelClusterOpts(gapOrOpts);
  const seeds = collectOverlayLabelSeeds(overlays);
  if (!seeds.length) return [];
  const roots = clusterSeedRoots(seeds, gap, project);
  const groups = new Map<number, OverlayLabelSeed[]>();
  for (let i = 0; i < seeds.length; i += 1) {
    const root = roots[i]!;
    const list = groups.get(root);
    if (list) list.push(seeds[i]!);
    else groups.set(root, [seeds[i]!]);
  }
  const labels: RaidPrepOverlayLabel[] = [];
  for (const group of groups.values()) {
    const anchor = nearestSeed(group, project);
    const byTask = new Map<string, RaidPrepOverlayLabelItem>();
    for (const seed of group) {
      const bucket = `${seed.taskId}\0${seed.optional ? "1" : "0"}\0${seed.title}`;
      const item = byTask.get(bucket);
      if (item) {
        item.count += 1;
        continue;
      }
      byTask.set(bucket, {
        taskId: seed.taskId,
        title: seed.title,
        color: seed.color,
        traderSlug: seed.traderSlug,
        subtitle: seed.subtitle,
        keyNames: seed.keyNames,
        showNoKey: seed.showNoKey,
        count: 1,
        optional: seed.optional,
        height: seed.height,
      });
    }
    const items = [...byTask.values()].sort((a, b) => b.count - a.count);
    labels.push({ x: anchor.x, z: anchor.z, items });
  }
  labels.sort((a, b) => a.z - b.z || a.x - b.x);
  return labels;
}
