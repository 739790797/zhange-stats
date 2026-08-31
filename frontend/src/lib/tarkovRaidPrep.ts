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

export const RAID_PREP_LIST_SCOPES = [
  "all",
  "picked",
  "active",
  "todo",
  "done",
] as const;

export type RaidPrepListScope = (typeof RAID_PREP_LIST_SCOPES)[number];

export type RaidPrepTaskProgressStatus = "active" | "todo" | "done";

export const RAID_PREP_LIST_SCOPE_LABELS: Record<RaidPrepListScope, string> = {
  all: "全部",
  picked: "已选",
  active: "进行中",
  todo: "未完成",
  done: "已完成",
};

/** 与个人中心任务管理下拉一致：未完成 / 进行中 / 已完成。 */
export const RAID_PREP_STATUS_SELECT_OPTIONS: readonly {
  value: RaidPrepTaskProgressStatus;
  label: string;
}[] = [
  { value: "todo", label: RAID_PREP_LIST_SCOPE_LABELS.todo },
  { value: "active", label: RAID_PREP_LIST_SCOPE_LABELS.active },
  { value: "done", label: RAID_PREP_LIST_SCOPE_LABELS.done },
];

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

/** 参与人在哪些任务上；找不到自己时返回 null（按全部任务算）。 */
export function raidPrepTaskIdsForParticipant(
  participantsByTask:
    | ReadonlyMap<string, readonly { userId?: number | null }[]>
    | null
    | undefined,
  userId: number | null | undefined,
): Set<string> | null {
  if (userId == null || !Number.isFinite(userId) || userId <= 0) return null;
  if (!participantsByTask?.size) return null;
  const ids = new Set<string>();
  for (const [taskId, people] of participantsByTask) {
    if ((people || []).some((person) => person.userId === userId)) {
      ids.add(taskId);
    }
  }
  return ids;
}

/** 藏匿 / 标记 / 使用：同物品跨任务、跨类型合成一件。 */
export function collectRaidPrepBringKit(
  rows: readonly RaidPrepTaskSummary[],
  taskIds?: ReadonlySet<string> | null,
): RaidPrepNeededItem[] {
  const items: RaidPrepNeededItem[] = [];
  for (const row of rows) {
    if (taskIds && !taskIds.has(row.taskId)) continue;
    const byType = row.itemsByType || {};
    for (const type of RAID_PREP_SUMMARY_BRING_TYPES) {
      for (const item of byType[type] || []) items.push(item);
    }
  }
  const merged = new Map<string, RaidPrepNeededItem>();
  const leftover: RaidPrepNeededItem[] = [];
  for (const item of items) {
    if (item.anyOf?.length) {
      leftover.push(item);
      continue;
    }
    const key = [
      item.id,
      item.found_in_raid ? "fir" : "stash",
      item.optional ? "opt" : "req",
    ].join("|");
    const prev = merged.get(key);
    if (!prev) {
      merged.set(key, { ...item });
      continue;
    }
    prev.count = raidPrepObjectiveCount(prev) + raidPrepObjectiveCount(item);
  }
  return [...merged.values(), ...leftover];
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

export type RaidPrepFloorAt = {
  x: number;
  z: number;
};

export type RaidPrepFloorBounds = {
  minX: number;
  maxX: number;
  minZ: number;
  maxZ: number;
};

export type RaidPrepFloorExtent = {
  min: number;
  max: number;
  bounds?: RaidPrepFloorBounds[];
};

export type RaidPrepFloorBand = {
  name: string;
  min: number;
  max: number;
  extents?: RaidPrepFloorExtent[];
};

export type RaidPrepOverlayStep = {
  id: string;
  text: string;
  optional: boolean;
  active: boolean;
};

export type TarkovRaidPrepOverlay = {
  key: string;
  taskId: string;
  kind: "zone" | "spawn";
  color: string;
  title: string;
  subtitle: string;
  /** 当前图全部步骤；active 对应该处目标。 */
  steps: RaidPrepOverlayStep[];
  traderSlug: string;
  keyNames: string[];
  /** 同任务其它点要钥匙时，本点明确标「不需要钥匙」。 */
  showNoKey: boolean;
  /** 来自目标 optional；可选目标在地图上单独标出。 */
  optional: boolean;
  /** 该点对应的目标 id；个人勾选后只对自己隐藏。 */
  objectiveId: string;
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

/** 跨地图任务：当前图以外的目标，按地图分组提示。 */
export type RaidPrepOtherMapGroup = {
  mapSlug: string;
  mapLabel: string;
  lines: string[];
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
  /** 当前用户已勾完本图必做步骤。 */
  mapComplete: boolean;
  /** 其他地图仍要做的步骤（只提示，不在本图勾选）。 */
  otherMapGroups: RaidPrepOtherMapGroup[];
};

/** 任务 id → 已勾掉（本局不用再做）的目标 id。 */
export type RaidPrepSkipMap = ReadonlyMap<string, ReadonlySet<string>>;

/** 房间/本机「谁做完了哪条目标」。 */
export type RaidPrepObjectiveDoneLike = {
  task_id: string;
  objective_id: string;
  user_id: number;
  display_name?: string | null;
};

export type RaidPrepCompletedUser = {
  name: string;
  userId: number;
};

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

/** 父级「任务」：全开则全关并记下所有人；未全开则全开。 */
export function nextQuestPeopleParentSelection(
  personKeys: readonly string[],
  parentOn: boolean,
): { showQuests: boolean; offKeys: string[] } {
  if (parentOn) {
    return { showQuests: false, offKeys: [...personKeys] };
  }
  return { showQuests: true, offKeys: [] };
}

/**
 * 点一个人。父级关着时只开这个人（避免 off 集合还是空的、勾一下变成反选）。
 * 已开则按当前 off 切换。
 */
export function nextQuestPersonSelection(
  personKeys: readonly string[],
  offKeys: ReadonlySet<string>,
  showQuests: boolean,
  toggledKey: string,
): { showQuests: true; offKeys: string[] } {
  if (!showQuests) {
    return {
      showQuests: true,
      offKeys: personKeys.filter((key) => key && key !== toggledKey),
    };
  }
  const next = new Set(offKeys);
  if (next.has(toggledKey)) next.delete(toggledKey);
  else next.add(toggledKey);
  return { showQuests: true, offKeys: [...next] };
}

/** 默认只勾自己；人不够或找不到自己时不改。 */
export function defaultQuestPersonOffKeys(
  people: readonly RaidPrepMapParticipant[],
  selfUserId: number | null | undefined,
): string[] | null {
  if (people.length < 2) return null;
  if (selfUserId == null || !Number.isFinite(selfUserId) || selfUserId <= 0) {
    return null;
  }
  const self = people.find((person) => person.userId === selfUserId);
  if (!self) return null;
  const selfKey = raidPrepPersonKey(self);
  return people
    .map((person) => raidPrepPersonKey(person))
    .filter((key) => key !== selfKey);
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
  },
>(
  rows: T[],
  opts: {
    trader?: string;
    q?: string;
    excludeIds?: readonly string[];
  } = {},
): T[] {
  const traderKey = (opts.trader || "").trim().toLowerCase();
  const needle = (opts.q || "").trim().toLowerCase();
  const exclude = new Set(
    (opts.excludeIds || []).map((id) => (id || "").trim()).filter(Boolean),
  );
  return rows.filter((row) => {
    if (exclude.size && exclude.has(String(row.id || "").trim())) {
      return false;
    }
    if (traderKey) {
      const slug = String(row.trader_slug || "").toLowerCase();
      const tid = String(row.trader_id || "").toLowerCase();
      const tname = String(row.trader_name || "").toLowerCase();
      if (traderKey !== slug && traderKey !== tid && !tname.includes(traderKey)) {
        return false;
      }
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

function parseFloorExtentHeight(
  height: number[] | null | undefined,
): { min: number; max: number } | null {
  if (!height || height.length < 2) return null;
  if (!Number.isFinite(height[0]) || !Number.isFinite(height[1])) return null;
  return {
    min: Math.min(height[0]!, height[1]!),
    max: Math.max(height[0]!, height[1]!),
  };
}

function parseFloorExtentBounds(raw: unknown): RaidPrepFloorBounds[] | undefined {
  if (!Array.isArray(raw) || !raw.length) return undefined;
  const out: RaidPrepFloorBounds[] = [];
  for (const item of raw) {
    if (!Array.isArray(item) || item.length < 2) continue;
    const a = item[0];
    const b = item[1];
    if (!Array.isArray(a) || !Array.isArray(b) || a.length < 2 || b.length < 2) {
      continue;
    }
    const x1 = Number(a[0]);
    const z1 = Number(a[1]);
    const x2 = Number(b[0]);
    const z2 = Number(b[1]);
    if (
      !Number.isFinite(x1) ||
      !Number.isFinite(z1) ||
      !Number.isFinite(x2) ||
      !Number.isFinite(z2)
    ) {
      continue;
    }
    out.push({
      minX: Math.min(x1, x2),
      maxX: Math.max(x1, x2),
      minZ: Math.min(z1, z2),
      maxZ: Math.max(z1, z2),
    });
  }
  return out.length ? out : undefined;
}

function bandExtents(band: RaidPrepFloorBand): RaidPrepFloorExtent[] {
  if (band.extents?.length) return band.extents;
  return [{ min: band.min, max: band.max }];
}

function pointInFloorBounds(
  at: RaidPrepFloorAt,
  bounds: RaidPrepFloorBounds,
): boolean {
  return (
    at.x >= bounds.minX &&
    at.x <= bounds.maxX &&
    at.z >= bounds.minZ &&
    at.z <= bounds.maxZ
  );
}

function extentMatchesFloor(
  extent: RaidPrepFloorExtent,
  span: RaidPrepHeightSpan,
  at?: RaidPrepFloorAt | null,
): boolean {
  if (!spansOverlap(span, { min: extent.min, max: extent.max })) return false;
  if (!extent.bounds?.length) return true;
  if (!at || !isFiniteNumber(at.x) || !isFiniteNumber(at.z)) return false;
  return extent.bounds.some((box) => pointInFloorBounds(at, box));
}

function bandMatchesFloor(
  band: RaidPrepFloorBand,
  span: RaidPrepHeightSpan,
  at?: RaidPrepFloorAt | null,
): boolean {
  return bandExtents(band).some((extent) =>
    extentMatchesFloor(extent, span, at),
  );
}

function extentBoundsOk(
  extent: RaidPrepFloorExtent,
  at?: RaidPrepFloorAt | null,
): boolean {
  if (!extent.bounds?.length) return true;
  if (!at || !isFiniteNumber(at.x) || !isFiniteNumber(at.z)) return false;
  return extent.bounds.some((box) => pointInFloorBounds(at, box));
}

function spanOverlapLen(a: RaidPrepHeightSpan, b: RaidPrepHeightSpan): number {
  return Math.max(0, Math.min(a.max, b.max) - Math.max(a.min, b.min));
}

function extentContainsSpan(
  extent: RaidPrepFloorExtent,
  span: RaidPrepHeightSpan,
): boolean {
  return extent.min <= span.min && span.max <= extent.max;
}

/** 整段高度都落在该层内（触发盒探出一层不算）。 */
function bandContainsSpan(
  band: RaidPrepFloorBand,
  span: RaidPrepHeightSpan,
  at?: RaidPrepFloorAt | null,
): boolean {
  return bandExtents(band).some(
    (extent) => extentContainsSpan(extent, span) && extentBoundsOk(extent, at),
  );
}

function bandOverlapLen(
  band: RaidPrepFloorBand,
  span: RaidPrepHeightSpan,
  at?: RaidPrepFloorAt | null,
): number | null {
  let best = 0;
  let hit = false;
  for (const extent of bandExtents(band)) {
    if (!extentBoundsOk(extent, at)) continue;
    if (!spansOverlap(span, { min: extent.min, max: extent.max })) continue;
    hit = true;
    best = Math.max(best, spanOverlapLen(span, extent));
  }
  return hit ? best : null;
}

function bandNearestDist(
  band: RaidPrepFloorBand,
  mid: number,
  at?: RaidPrepFloorAt | null,
): number | null {
  let best = Number.POSITIVE_INFINITY;
  let hit = false;
  for (const extent of bandExtents(band)) {
    if (extent.bounds?.length) {
      if (!at || !isFiniteNumber(at.x) || !isFiniteNumber(at.z)) continue;
      if (!extent.bounds.some((box) => pointInFloorBounds(at, box))) continue;
    }
    const clamped = Math.min(extent.max, Math.max(extent.min, mid));
    const dist = Math.abs(mid - clamped);
    if (dist < best) best = dist;
    hit = true;
  }
  return hit ? best : null;
}

/** 无高度的点只在地面层；有高度则与楼层 extents 相交才显示。带 bounds 的层要落在框内。 */
export function overlayVisibleOnFloor(
  span: RaidPrepHeightSpan | null | undefined,
  floorName: string,
  bands: readonly RaidPrepFloorBand[],
  at?: RaidPrepFloorAt | null,
): boolean {
  if (!bands.length) return true;
  if (!floorName) {
    if (!span) return true;
    if (
      bands.some(
        (band) => band.name && bandContainsSpan(band, span, at),
      )
    ) {
      return false;
    }
    const ground = bands.find((band) => !band.name);
    if (!ground) return true;
    return bandMatchesFloor(ground, span, at);
  }
  if (!span) return false;
  const named = bands.find((band) => band.name === floorName);
  if (!named) return true;
  return bandMatchesFloor(named, span, at);
}

export function overlayFloorNames(
  span: RaidPrepHeightSpan | null | undefined,
  bands: readonly RaidPrepFloorBand[],
  at?: RaidPrepFloorAt | null,
): string[] {
  if (!span) return [];
  const names: string[] = [];
  for (const band of bands) {
    if (!band.name) continue;
    if (!bandMatchesFloor(band, span, at)) continue;
    names.push(band.name);
  }
  return names;
}

/** 点位应对齐的楼层名；空字符串是地面。 */
export function overlayFloorForSpan(
  span: RaidPrepHeightSpan | null | undefined,
  bands: readonly RaidPrepFloorBand[],
  at?: RaidPrepFloorAt | null,
): string {
  if (!bands.length) return "";
  if (!span) return "";
  const mid = (span.min + span.max) / 2;
  const containedNamed = bands.filter(
    (band) => band.name && bandContainsSpan(band, span, at),
  );
  const pool = containedNamed.length
    ? containedNamed
    : bands.filter((band) => bandOverlapLen(band, span, at) != null);
  if (pool.length) {
    let best = pool[0]!;
    let bestOverlap = bandOverlapLen(best, span, at) ?? 0;
    let bestDist = bandNearestDist(best, mid, at) ?? Number.POSITIVE_INFINITY;
    for (const band of pool.slice(1)) {
      const overlap = bandOverlapLen(band, span, at) ?? 0;
      const dist = bandNearestDist(band, mid, at) ?? Number.POSITIVE_INFINITY;
      if (overlap < bestOverlap) continue;
      if (overlap === bestOverlap && dist >= bestDist) continue;
      best = band;
      bestOverlap = overlap;
      bestDist = dist;
    }
    return best.name;
  }
  let best = "";
  let bestDist = Number.POSITIVE_INFINITY;
  for (const band of bands) {
    const dist = bandNearestDist(band, mid, at);
    if (dist == null || dist >= bestDist) continue;
    bestDist = dist;
    best = band.name;
  }
  return best;
}

export function overlayFloorForPoint(
  y: number | null | undefined,
  bands: readonly RaidPrepFloorBand[],
  at?: RaidPrepFloorAt | null,
): string {
  if (!isFiniteNumber(y)) return "";
  return overlayFloorForSpan({ min: y, max: y }, bands, at);
}

export function mapLayerFloorBands(
  layer:
    | {
        heightRange?: number[] | null;
        layers?: Array<{
          name?: string;
          extents?: Array<{
            height?: number[];
            bounds?: unknown;
          }> | null;
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
    const min = Math.min(range[0]!, range[1]!);
    const max = Math.max(range[0]!, range[1]!);
    bands.push({
      name: "",
      min,
      max,
      extents: [{ min, max }],
    });
  }
  for (const floor of layer.layers || []) {
    const name = (floor.name || "").trim();
    if (!name) continue;
    const extents: RaidPrepFloorExtent[] = [];
    for (const raw of floor.extents || []) {
      const height = parseFloorExtentHeight(raw.height);
      if (!height) continue;
      const bounds = parseFloorExtentBounds(raw.bounds);
      extents.push(bounds ? { ...height, bounds } : height);
    }
    if (!extents.length) continue;
    bands.push({
      name,
      min: Math.min(...extents.map((item) => item.min)),
      max: Math.max(...extents.map((item) => item.max)),
      extents,
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

/** 匹配成功 / 倒计时 / 开战：足以认定「正在进这张图」。 */
export const RAID_PREP_AUTO_MAP_KINDS = [
  "match_found",
  "raid_starting",
  "raid_started",
] as const;

export function isRaidPrepAutoMapKind(kind: string | null | undefined): boolean {
  const key = (kind || "").trim();
  return (RAID_PREP_AUTO_MAP_KINDS as readonly string[]).includes(key);
}

export function raidPrepMapsEquivalent(a: string, b: string): boolean {
  const left = normalizeRaidPrepMapId(a) || (a || "").trim();
  const right = normalizeRaidPrepMapId(b) || (b || "").trim();
  if (!left || !right) return false;
  const keys = mapSlugKeys(left);
  for (const key of mapSlugKeys(right)) {
    if (keys.has(key)) return true;
  }
  return false;
}

/**
 * 日志要切到哪张图；空字符串表示不切。
 * 开战类相位：当前图不同就切。
 * 未选图时：可用上一场日志图垫上（单人 / 房主空房）。
 * 房间开战切图另走「同一 shortId」共识，不单独用这条。
 */
export function raidPrepAutoSwitchMapId(opts: {
  currentMapId: string;
  logMapId: string;
  phaseKind?: string | null;
  fillEmpty?: boolean;
}): string {
  const next = normalizeRaidPrepMapId(opts.logMapId);
  if (!next) return "";
  const current = normalizeRaidPrepMapId(opts.currentMapId);
  if (current && raidPrepMapsEquivalent(next, current)) return "";
  if (isRaidPrepAutoMapKind(opts.phaseKind)) return next;
  if (opts.fillEmpty && !current) return next;
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

function trimIdList(ids: readonly string[] | null | undefined): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const id of ids || []) {
    const key = (id || "").trim();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(key);
  }
  return out;
}

/** 个人中心「进行中」里、本图目录也有的任务（目录顺序；已完成的排除）。 */
export function raidPrepIdsFromTaskProgress(
  catalogIds: readonly string[],
  startedIds: readonly string[],
  doneIds: readonly string[] = [],
): string[] {
  const started = new Set(trimIdList(startedIds));
  const done = new Set(trimIdList(doneIds));
  const out: string[] = [];
  const seen = new Set<string>();
  for (const id of catalogIds) {
    const key = (id || "").trim();
    if (!key || seen.has(key) || !started.has(key) || done.has(key)) continue;
    seen.add(key);
    out.push(key);
  }
  return out;
}

export function describeRaidPrepTaskProgressSync(input: {
  startedCount: number;
  matchedCount: number;
  addedCount: number;
  capped?: boolean;
}): string {
  const { startedCount, matchedCount, addedCount, capped } = input;
  if (addedCount > 0) {
    const base = `已勾选 ${addedCount} 个进行中任务`;
    return capped ? `${base}（已达 ${RAID_PREP_MAX_SELECTED} 个上限）` : base;
  }
  if (capped) return `无法继续勾选（已达 ${RAID_PREP_MAX_SELECTED} 个上限）`;
  if (matchedCount > 0) return "进行中的本图任务已全部勾选";
  if (startedCount <= 0) return "个人中心没有进行中的任务";
  return "没有进行中且属于本图的任务";
}

export type RaidPrepTaskProgressSyncPlan = {
  matchedIds: string[];
  addedIds: string[];
  nextIds: string[];
  hint: string;
};

/** 把进行中的本图任务并进已选；房间可传入 occupiedIds 按全房独立任务数封顶。 */
export function planRaidPrepTaskProgressSync(opts: {
  catalogIds: readonly string[];
  selectedIds: readonly string[];
  startedIds: readonly string[];
  doneIds?: readonly string[];
  max?: number;
  occupiedIds?: readonly string[];
}): RaidPrepTaskProgressSyncPlan {
  const max = opts.max ?? RAID_PREP_MAX_SELECTED;
  const matchedIds = raidPrepIdsFromTaskProgress(
    opts.catalogIds,
    opts.startedIds,
    opts.doneIds,
  );
  const selected = trimIdList(opts.selectedIds);
  const occupied = new Set(trimIdList(opts.occupiedIds ?? selected));
  let unique = occupied.size;
  const nextIds = [...selected];
  const seen = new Set(selected);
  const addedIds: string[] = [];
  let capped = false;
  for (const id of matchedIds) {
    if (seen.has(id)) continue;
    const isNewUnique = !occupied.has(id);
    if (isNewUnique && unique >= max) {
      capped = true;
      continue;
    }
    seen.add(id);
    nextIds.push(id);
    addedIds.push(id);
    if (isNewUnique) {
      unique += 1;
      occupied.add(id);
    }
  }
  return {
    matchedIds,
    addedIds,
    nextIds,
    hint: describeRaidPrepTaskProgressSync({
      startedCount: trimIdList(opts.startedIds).length,
      matchedCount: matchedIds.length,
      addedCount: addedIds.length,
      capped,
    }),
  };
}

export function hideCompletedRaidPrepRows<T extends { id: string }>(
  rows: readonly T[],
  doneIds: readonly string[] | null | undefined,
): T[] {
  const done = new Set(trimIdList(doneIds));
  if (!done.size) return [...rows];
  return rows.filter((row) => !done.has(row.id));
}

function asIdSet(
  ids: ReadonlySet<string> | readonly string[] | null | undefined,
): Set<string> {
  if (!ids) return new Set();
  if (Array.isArray(ids)) return new Set(trimIdList(ids));
  return new Set(ids);
}

/** 个人中心任务进度：已完成 > 进行中 > 未完成。 */
export function raidPrepTaskProgressStatus(
  taskId: string,
  doneIds?: ReadonlySet<string> | readonly string[] | null,
  startedIds?: ReadonlySet<string> | readonly string[] | null,
): RaidPrepTaskProgressStatus {
  const id = String(taskId || "").trim();
  if (id && asIdSet(doneIds).has(id)) return "done";
  if (id && asIdSet(startedIds).has(id)) return "active";
  return "todo";
}

export function raidPrepTaskProgressLabel(
  status: RaidPrepTaskProgressStatus,
): string {
  if (status === "done") return RAID_PREP_LIST_SCOPE_LABELS.done;
  if (status === "active") return RAID_PREP_LIST_SCOPE_LABELS.active;
  return RAID_PREP_LIST_SCOPE_LABELS.todo;
}

const RAID_PREP_PROGRESS_SORT: Record<RaidPrepTaskProgressStatus, number> = {
  active: 0,
  todo: 1,
  done: 2,
};

/** 筛选结果：进行中 → 未完成 → 已完成，同状态保持原相对顺序。 */
export function sortRaidPrepRowsByProgress<T extends { id: string }>(
  rows: readonly T[],
  doneIds?: ReadonlySet<string> | readonly string[] | null,
  startedIds?: ReadonlySet<string> | readonly string[] | null,
): T[] {
  return [...rows].sort(
    (a, b) =>
      RAID_PREP_PROGRESS_SORT[
        raidPrepTaskProgressStatus(a.id, doneIds, startedIds)
      ] -
      RAID_PREP_PROGRESS_SORT[
        raidPrepTaskProgressStatus(b.id, doneIds, startedIds)
      ],
  );
}

export const RAID_PREP_PROGRESS_STATUSES: readonly RaidPrepTaskProgressStatus[] =
  ["active", "todo", "done"];

/** 按进行中 → 未完成 → 已完成分段；组内可再置顶已选。 */
export function groupRaidPrepRowsByProgress<T extends { id: string }>(
  rows: readonly T[],
  doneIds?: ReadonlySet<string> | readonly string[] | null,
  startedIds?: ReadonlySet<string> | readonly string[] | null,
): Record<RaidPrepTaskProgressStatus, T[]> {
  const groups: Record<RaidPrepTaskProgressStatus, T[]> = {
    active: [],
    todo: [],
    done: [],
  };
  for (const row of rows) {
    groups[raidPrepTaskProgressStatus(row.id, doneIds, startedIds)].push(row);
  }
  return groups;
}

export function filterRaidPrepRowsByScope<T extends { id: string }>(
  rows: readonly T[],
  scope: RaidPrepListScope,
  opts: {
    selectedIds?: ReadonlySet<string> | readonly string[] | null;
    doneIds?: ReadonlySet<string> | readonly string[] | null;
    startedIds?: ReadonlySet<string> | readonly string[] | null;
  } = {},
): T[] {
  if (scope === "all") return [...rows];
  if (scope === "picked") {
    const selected = asIdSet(opts.selectedIds);
    return rows.filter((row) => selected.has(row.id));
  }
  return rows.filter(
    (row) =>
      raidPrepTaskProgressStatus(row.id, opts.doneIds, opts.startedIds) ===
      scope,
  );
}

export function countRaidPrepRowsByScope<T extends { id: string }>(
  rows: readonly T[],
  opts: {
    selectedIds?: ReadonlySet<string> | readonly string[] | null;
    doneIds?: ReadonlySet<string> | readonly string[] | null;
    startedIds?: ReadonlySet<string> | readonly string[] | null;
  } = {},
): Record<RaidPrepListScope, number> {
  const selected = asIdSet(opts.selectedIds);
  const counts: Record<RaidPrepListScope, number> = {
    all: rows.length,
    picked: 0,
    active: 0,
    todo: 0,
    done: 0,
  };
  for (const row of rows) {
    if (selected.has(row.id)) counts.picked += 1;
    counts[raidPrepTaskProgressStatus(row.id, opts.doneIds, opts.startedIds)] +=
      1;
  }
  return counts;
}

export function mergeRaidPrepNeededItems(
  items: readonly RaidPrepNeededItem[],
): RaidPrepNeededItem[] {
  const merged = new Map<string, RaidPrepNeededItem>();
  const leftover: RaidPrepNeededItem[] = [];
  for (const item of items) {
    if (item.anyOf?.length) {
      leftover.push(item);
      continue;
    }
    const key = [
      item.kind,
      item.id,
      item.objectiveType,
      item.found_in_raid ? "fir" : "stash",
      item.optional ? "opt" : "req",
    ].join("|");
    const prev = merged.get(key);
    if (!prev) {
      merged.set(key, { ...item });
      continue;
    }
    prev.count = raidPrepObjectiveCount(prev) + raidPrepObjectiveCount(item);
  }
  return [...merged.values(), ...leftover];
}

export function raidPrepKeyIsMissing(
  ownNames: readonly string[] | null | undefined,
  bringNames: readonly string[] | null | undefined,
): boolean {
  return !(ownNames || []).length && !(bringNames || []).length;
}

export const RAID_PREP_UNAVAILABLE_KEY_HINT =
  "所需钥匙还没人点「我有」，仅作提醒。语音里说有也行，地图上仍会标出。";

export function mergeRaidPrepAvailableKeyIds(
  ...lists: Array<readonly { item_id?: string | null }[] | null | undefined>
): Set<string> {
  const ids = new Set<string>();
  for (const list of lists) {
    for (const row of list || []) {
      const id = String(row.item_id || "").trim();
      if (id) ids.add(id);
    }
  }
  return ids;
}

function raidPrepKeyItemAvailable(
  item: RaidPrepNeededItem,
  availableIds: ReadonlySet<string>,
): boolean {
  if (item.anyOf?.length) {
    return item.anyOf.some((opt) => raidPrepKeyItemAvailable(opt, availableIds));
  }
  return availableIds.has(item.id);
}

/** 有必带钥匙，且每把都没人拥有。可选钥匙不挡。 */
export function raidPrepTaskKeysUnavailable(
  keys: readonly RaidPrepNeededItem[] | null | undefined,
  availableIds: ReadonlySet<string>,
): boolean {
  const required = (keys || []).filter(
    (item) => item.kind === "key" && !item.optional,
  );
  if (!required.length) return false;
  return required.every((item) => !raidPrepKeyItemAvailable(item, availableIds));
}

export function collectUnavailableRaidPrepTaskIds(
  tasks: readonly RaidPrepTaskLike[],
  mapSlug: string,
  skippedByTask: RaidPrepSkipMap | undefined,
  availableIds: ReadonlySet<string>,
): Set<string> {
  const hidden = new Set<string>();
  for (const task of tasks) {
    const keys = collectRaidPrepTaskKeys(
      task,
      mapSlug,
      raidPrepSkippedIds(skippedByTask, task.id),
    );
    if (raidPrepTaskKeysUnavailable(keys, availableIds)) hidden.add(task.id);
  }
  return hidden;
}

export function formatRaidPrepOverlayKeyLabel(
  keyNames: readonly string[] | null | undefined,
  showNoKey = false,
): string {
  if (showNoKey) return "不需要钥匙";
  const names = (keyNames || []).map((name) => name.trim()).filter(Boolean);
  if (!names.length) return "";
  if (names.length <= 2) return names.join("、");
  return `${names.slice(0, 2).join("、")}…`;
}

export function settleRaidPrepSelection(opts: {
  selectedIds: readonly string[];
  completedIds: readonly string[];
  aborted?: boolean;
}): { nextIds: string[]; removedIds: string[] } {
  const selected = trimIdList(opts.selectedIds);
  if (opts.aborted) return { nextIds: selected, removedIds: [] };
  const done = new Set(trimIdList(opts.completedIds));
  if (!done.size) return { nextIds: selected, removedIds: [] };
  const removedIds = selected.filter((id) => done.has(id));
  return {
    nextIds: selected.filter((id) => !done.has(id)),
    removedIds,
  };
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

/** 个人进度已完成时，当前用户视角把步骤视为全勾，不写共享勾选。 */
export function raidPrepObjectiveCheckedForViewer(
  objectiveId: string,
  skipped?: ReadonlySet<string> | null,
  taskDone?: boolean,
): boolean {
  if (taskDone) return true;
  const id = String(objectiveId || "").trim();
  return Boolean(id && skipped?.has(id));
}

export function raidPrepRequiredObjectiveIds(
  task: RaidPrepTaskLike,
  mapSlug: string,
): string[] {
  const required: string[] = [];
  const optional: string[] = [];
  for (const { obj, index } of mapObjectives(task, mapSlug)) {
    const id = raidPrepObjectiveKey(obj, index);
    if (obj.optional) optional.push(id);
    else required.push(id);
  }
  return required.length ? required : optional;
}

/** 本图必做步骤（无必做则看可选）是否都已勾完。无本图目标不算完成。 */
export function raidPrepMapObjectivesComplete(
  task: RaidPrepTaskLike,
  mapSlug: string,
  skipped?: ReadonlySet<string> | null,
): boolean {
  const needed = raidPrepRequiredObjectiveIds(task, mapSlug);
  if (!needed.length) return false;
  const have = skipped || EMPTY_SKIP;
  return needed.every((id) => have.has(id));
}

type RaidPrepMapRefLite = { slug: string; name: string };

function objectiveMapRefs(obj: RaidPrepObjectiveLike): RaidPrepMapRefLite[] {
  const out: RaidPrepMapRefLite[] = [];
  const seen = new Set<string>();
  const add = (slug: string, name: string) => {
    const s = (slug || "").trim();
    const n = (name || "").trim();
    const key = (s || n).toLowerCase();
    if (!key || seen.has(key)) return;
    seen.add(key);
    out.push({ slug: s, name: n });
  };
  for (const map of obj.maps || []) {
    add(map.slug || "", map.name || "");
  }
  for (const zone of obj.zones || []) {
    add(zone.map_slug || "", zone.map_name || "");
  }
  for (const loc of obj.possible_locations || []) {
    add(loc.map_slug || "", loc.map_name || "");
  }
  return out;
}

function raidPrepMapRefLabel(ref: RaidPrepMapRefLite): string {
  const readable = tarkovReadableName(ref.name, ref.slug);
  if (readable) return readable;
  const canon = ref.slug ? normalizeRaidPrepMapId(ref.slug) : "";
  if (canon) {
    const opt = raidPrepMapOptions().find((item) => item.id === canon);
    if (opt) return opt.label;
  }
  return (ref.name || ref.slug).trim();
}

function raidPrepOtherMapGroupKey(slug: string, label: string): string {
  return (normalizeRaidPrepMapId(slug) || slug || label).trim().toLowerCase();
}

/** 当前图以外的目标，按地图分组；本图目标若还标了别的图，只出地图名。 */
export function collectRaidPrepOtherMapGroups(
  task: RaidPrepTaskLike,
  mapSlug: string,
): RaidPrepOtherMapGroup[] {
  const currentKeys = mapSlugKeys(mapSlug);
  if (!currentKeys.size) return [];
  const byKey = new Map<string, RaidPrepOtherMapGroup>();
  const ensure = (slug: string, label: string): RaidPrepOtherMapGroup | null => {
    const text = (label || "").trim();
    if (!text) return null;
    const key = raidPrepOtherMapGroupKey(slug, text);
    if (!key) return null;
    const canonKeys = slug ? mapSlugKeys(slug) : new Set<string>();
    for (const item of currentKeys) {
      if (canonKeys.has(item)) return null;
    }
    let group = byKey.get(key);
    if (!group) {
      group = { mapSlug: slug, mapLabel: text, lines: [] };
      byKey.set(key, group);
    }
    return group;
  };

  (task.objectives || []).forEach((obj) => {
    const refs = objectiveMapRefs(obj);
    if (objectiveAppliesToMap(obj, mapSlug)) {
      for (const ref of refs) {
        if (!ref.slug || currentKeys.has(ref.slug.toLowerCase())) continue;
        if (mapSlugKeys(ref.slug).size && [...mapSlugKeys(ref.slug)].some((k) => currentKeys.has(k))) {
          continue;
        }
        ensure(ref.slug, raidPrepMapRefLabel(ref));
      }
      return;
    }
    const other = refs.filter((ref) => {
      if (!ref.slug) return true;
      const keys = mapSlugKeys(ref.slug);
      for (const item of currentKeys) {
        if (keys.has(item)) return false;
      }
      return true;
    });
    const primary = other[0] || refs[0];
    const label = primary ? raidPrepMapRefLabel(primary) : "其他地图";
    const slug = primary?.slug || "";
    const group = ensure(slug, label || "其他地图");
    const text = raidPrepObjectiveStepText(obj);
    if (group && text && !group.lines.includes(text)) group.lines.push(text);
  });

  const order = new Map(
    raidPrepMapOptions().map((item, index) => [item.id, index] as const),
  );
  return [...byKey.values()].sort((a, b) => {
    const ia = order.get(normalizeRaidPrepMapId(a.mapSlug) || a.mapSlug) ?? 999;
    const ib = order.get(normalizeRaidPrepMapId(b.mapSlug) || b.mapSlug) ?? 999;
    if (ia !== ib) return ia - ib;
    return a.mapLabel.localeCompare(b.mapLabel, "zh");
  });
}

export function formatRaidPrepOtherMapsLead(
  groups: readonly RaidPrepOtherMapGroup[] | null | undefined,
): string {
  const labels = (groups || [])
    .map((row) => row.mapLabel.trim())
    .filter(Boolean);
  if (!labels.length) return "";
  return `此任务还需在${labels.join("、")}完成`;
}

/** 当前地图上该任务的全部目标（含可选），整任务完成时用来回填个人勾选。 */
export function raidPrepMapObjectiveIds(
  task: RaidPrepTaskLike,
  mapSlug: string,
): string[] {
  return mapObjectives(task, mapSlug).map(({ obj, index }) =>
    raidPrepObjectiveKey(obj, index),
  );
}

function addObjectiveDoneToSkipMap(
  out: Map<string, Set<string>>,
  row: RaidPrepObjectiveDoneLike,
) {
  const taskId = String(row.task_id || "").trim();
  const objId = String(row.objective_id || "").trim();
  if (!taskId || !objId) return;
  let bucket = out.get(taskId);
  if (!bucket) {
    bucket = new Set();
    out.set(taskId, bucket);
  }
  bucket.add(objId);
}

export function objectiveDonesToSkipMap(
  dones: readonly RaidPrepObjectiveDoneLike[] | null | undefined,
  userId: number | null | undefined,
): Map<string, Set<string>> {
  const out = new Map<string, Set<string>>();
  if (userId == null) return out;
  for (const row of dones || []) {
    if (row.user_id !== userId) continue;
    addObjectiveDoneToSkipMap(out, row);
  }
  return out;
}

/** 日志整任务完成后，还没被当前用户标过的本图目标。 */
export function roomObjectiveMarksForCompletedTasks(
  completedIds: readonly string[],
  tasks: readonly RaidPrepTaskLike[],
  mapSlug: string,
  dones: readonly RaidPrepObjectiveDoneLike[] | null | undefined,
  userId: number | null | undefined,
): Array<{ taskId: string; objectiveId: string }> {
  const out: Array<{ taskId: string; objectiveId: string }> = [];
  const slug = (mapSlug || "").trim();
  if (!slug || !completedIds.length) return out;
  const byId = new Map(tasks.map((task) => [task.id, task]));
  for (const taskId of completedIds) {
    const task = byId.get(taskId);
    if (!task) continue;
    for (const objectiveId of raidPrepMapObjectiveIds(task, slug)) {
      if (userMarkedObjective(dones, taskId, objectiveId, userId)) continue;
      out.push({ taskId, objectiveId });
    }
  }
  return out;
}

export function skipMapToObjectiveDones(
  skipped: RaidPrepSkipMap | undefined,
  user: { userId: number; name: string },
): RaidPrepObjectiveDoneLike[] {
  const out: RaidPrepObjectiveDoneLike[] = [];
  if (!skipped) return out;
  for (const [taskId, ids] of skipped) {
    for (const objectiveId of ids) {
      out.push({
        task_id: taskId,
        objective_id: objectiveId,
        user_id: user.userId,
        display_name: user.name,
      });
    }
  }
  return out;
}

export function collectRaidPrepCompletedUsers(
  tasks: readonly RaidPrepTaskLike[],
  mapSlug: string,
  dones: readonly RaidPrepObjectiveDoneLike[] | null | undefined,
): Map<string, RaidPrepCompletedUser[]> {
  const byUserTask = new Map<string, Set<string>>();
  const nameByUser = new Map<number, string>();
  const orderByTask = new Map<string, number[]>();
  for (const row of dones || []) {
    const taskId = String(row.task_id || "").trim();
    const objId = String(row.objective_id || "").trim();
    if (!taskId || !objId) continue;
    const key = `${row.user_id}\t${taskId}`;
    let bucket = byUserTask.get(key);
    if (!bucket) {
      bucket = new Set();
      byUserTask.set(key, bucket);
    }
    bucket.add(objId);
    if (!nameByUser.has(row.user_id)) {
      nameByUser.set(
        row.user_id,
        (row.display_name || "").trim() || `用户${row.user_id}`,
      );
    }
    let order = orderByTask.get(taskId);
    if (!order) {
      order = [];
      orderByTask.set(taskId, order);
    }
    if (!order.includes(row.user_id)) order.push(row.user_id);
  }

  const out = new Map<string, RaidPrepCompletedUser[]>();
  for (const task of tasks) {
    const needed = raidPrepRequiredObjectiveIds(task, mapSlug);
    if (!needed.length) continue;
    const people: RaidPrepCompletedUser[] = [];
    for (const userId of orderByTask.get(task.id) || []) {
      const have = byUserTask.get(`${userId}\t${task.id}`);
      if (!have) continue;
      if (needed.every((id) => have.has(id))) {
        people.push({
          userId,
          name: nameByUser.get(userId) || `用户${userId}`,
        });
      }
    }
    if (people.length) out.set(task.id, people);
  }
  return out;
}

export function userMarkedObjective(
  dones: readonly RaidPrepObjectiveDoneLike[] | null | undefined,
  taskId: string,
  objectiveId: string,
  userId: number | null | undefined,
): boolean {
  if (userId == null) return false;
  const tid = String(taskId || "").trim();
  const oid = String(objectiveId || "").trim();
  if (!tid || !oid) return false;
  return (dones || []).some(
    (row) =>
      row.user_id === userId &&
      String(row.task_id || "").trim() === tid &&
      String(row.objective_id || "").trim() === oid,
  );
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

export function mergeRaidPrepSkipMaps(
  ...maps: Array<RaidPrepSkipMap | null | undefined>
): Map<string, Set<string>> {
  const out = new Map<string, Set<string>>();
  for (const skipped of maps) {
    if (!skipped) continue;
    for (const [taskId, ids] of skipped) {
      const key = String(taskId || "").trim();
      if (!key || !ids?.size) continue;
      const bucket = new Set(out.get(key) || []);
      for (const id of ids) {
        const objectiveId = String(id || "").trim();
        if (objectiveId) bucket.add(objectiveId);
      }
      if (bucket.size) out.set(key, bucket);
    }
  }
  return out;
}

export function raidPrepSkipMapsEqual(
  left: RaidPrepSkipMap | null | undefined,
  right: RaidPrepSkipMap | null | undefined,
): boolean {
  const a = serializeRaidPrepObjectiveDone(left || new Map());
  const b = serializeRaidPrepObjectiveDone(right || new Map());
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const key of keys) {
    const leftIds = [...(a[key] || [])].sort().join("\0");
    const rightIds = [...(b[key] || [])].sort().join("\0");
    if (leftIds !== rightIds) return false;
  }
  return true;
}

export function readRaidPrepObjectiveDone(scope: string): Map<string, Set<string>> {
  const key = (scope || "").trim();
  if (!key) return new Map();
  return parseRaidPrepObjectiveDone(readObjectiveDoneStore()[key]);
}

export function readRaidPrepObjectiveDoneWithLegacy(
  scope: string,
  legacyScopes: readonly string[] = [],
): Map<string, Set<string>> {
  return mergeRaidPrepSkipMaps(
    readRaidPrepObjectiveDone(scope),
    ...legacyScopes.map((item) => readRaidPrepObjectiveDone(item)),
  );
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

/** 个人步骤进度：账号 + 模式 + 地图。 */
export function raidPrepObjectiveDoneScope(
  mapId: string,
  gameMode = "pvp",
  userId?: number | null,
): string {
  const map = (mapId || "").trim();
  if (!map) return "";
  const mode = (gameMode || "pvp").trim() || "pvp";
  const user =
    userId != null && Number.isFinite(userId) ? String(userId) : "guest";
  return `user:${user}:${mode}:${map}`;
}

export function raidPrepObjectiveDoneLegacyScopes(
  mapId: string,
  roomId?: string | null,
): string[] {
  const out: string[] = [];
  const map = (mapId || "").trim();
  if (map) out.push(`solo:${map}`);
  const room = (roomId || "").trim();
  if (room) out.push(`room:${room}`);
  return out;
}

export function useRaidPrepObjectiveDone(
  scope: string,
  legacyScopes: readonly string[] = [],
) {
  const legacyKey = legacyScopes.filter(Boolean).join("\0");
  const [done, setDone] = useState(() =>
    readRaidPrepObjectiveDoneWithLegacy(scope, legacyScopes),
  );
  useEffect(() => {
    const next = readRaidPrepObjectiveDoneWithLegacy(
      scope,
      legacyKey ? legacyKey.split("\0") : [],
    );
    setDone(next);
    if (scope) writeRaidPrepObjectiveDone(scope, next);
  }, [legacyKey, scope]);
  const toggle = useCallback((taskId: string, objectiveId: string) => {
    setDone((current) => {
      const next = toggleRaidPrepObjectiveDone(current, taskId, objectiveId);
      writeRaidPrepObjectiveDone(scope, next);
      return next;
    });
  }, [scope]);
  const replace = useCallback((next: RaidPrepSkipMap) => {
    const copy = new Map<string, Set<string>>();
    for (const [taskId, ids] of next) copy.set(taskId, new Set(ids));
    writeRaidPrepObjectiveDone(scope, copy);
    setDone(copy);
  }, [scope]);
  return [done, toggle, replace] as const;
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

/** 地图/总结步骤原文：有描述就不用 type 标签。 */
export function raidPrepObjectiveStepText(obj: RaidPrepObjectiveLike): string {
  const description = tarkovReadableName(obj.description, obj.id);
  const typeLabel = tarkovObjectiveTypeLabel(obj.type || "");
  const text = description || typeLabel;
  if (!text) return "";
  return obj.optional ? `${text}（可选）` : text;
}

export function collectRaidPrepOverlaySteps(
  task: RaidPrepTaskLike,
  mapSlug: string,
  activeObjectiveId = "",
): RaidPrepOverlayStep[] {
  const active = String(activeObjectiveId || "").trim();
  return collectRaidPrepTaskObjectives(task, mapSlug).map((obj) => ({
    id: obj.id,
    text: obj.text,
    optional: obj.optional,
    active: Boolean(active) && obj.id === active,
  }));
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
    const text = raidPrepObjectiveStepText(obj);
    if (!text) return;
    out.push({
      id: raidPrepObjectiveKey(obj, index),
      text,
      optional: Boolean(obj.optional),
      keyNames: objectiveKeyNames(obj),
    });
  });
  return out;
}

/** 右侧任务列表气泡：贴在侧栏左缘外侧，整块夹在视口内。 */
export function placeRaidPrepListHint(opts: {
  viewW: number;
  viewH: number;
  boxW: number;
  boxH: number;
  /** 侧栏左缘；气泡右缘落在这左侧 */
  edgeRight: number;
  triggerTop: number;
  pad?: number;
  gap?: number;
}): { left: number; top: number; maxWidth: number; maxHeight: number } {
  const pad = opts.pad ?? 8;
  const gap = opts.gap ?? 8;
  const viewW = Math.max(opts.viewW, pad * 2);
  const viewH = Math.max(opts.viewH, pad * 2);
  const leftRoom = opts.edgeRight - gap - pad;
  const maxWidth = Math.max(
    160,
    Math.min(viewW - pad * 2, leftRoom >= 160 ? leftRoom : viewW - pad * 2),
  );
  const maxHeight = Math.max(80, viewH - pad * 2);
  const bw = Math.min(Math.max(opts.boxW, 1), maxWidth);
  const bh = Math.min(Math.max(opts.boxH, 1), maxHeight);
  const left = Math.min(
    Math.max(opts.edgeRight - gap - bw, pad),
    viewW - pad - bw,
  );
  const top = Math.min(Math.max(opts.triggerTop, pad), viewH - pad - bh);
  return { left, top, maxWidth, maxHeight };
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
    const items = mergeRaidPrepNeededItems(
      collectRaidPrepTaskItems(task, mapSlug, skipped),
    );
    const keys = mergeRaidPrepNeededItems(
      collectRaidPrepTaskKeys(task, mapSlug, skipped),
    );
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
      mapComplete: raidPrepMapObjectivesComplete(task, mapSlug, skipped),
      otherMapGroups: collectRaidPrepOtherMapGroups(task, mapSlug),
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

/** 同一任务多个地图点：用「第N处」编号，避免「湿活-2」+「1」读成「湿活-21」。 */
export function formatRaidPrepOverlayPointTitle(
  taskName: string,
  index: number,
  total: number,
): string {
  const name = (taskName || "").trim();
  if (!name) return "";
  if (total <= 1) return name;
  return `${name}（第${index + 1}处）`;
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
    list.forEach((row, index) => {
      row.title = formatRaidPrepOverlayPointTitle(row.title, index, list.length);
      row.showNoKey = anyKey && row.keyNames.length === 0;
    });
  }
  return overlays;
}

/** 当前用户已勾掉的步骤：只从自己的地图上拿掉对应点，不影响别人。 */
export function filterRaidPrepOverlaysForViewer(
  overlays: readonly TarkovRaidPrepOverlay[],
  skippedByTask?: RaidPrepSkipMap,
): TarkovRaidPrepOverlay[] {
  if (!skippedByTask?.size) return [...overlays];
  return overlays.filter((row) => {
    const done = skippedByTask.get(row.taskId);
    if (!done?.size) return true;
    const id = (row.objectiveId || "").trim();
    if (!id) return true;
    return !done.has(id);
  });
}

/** 地图任务点：按本图几何生成；缺钥匙不藏点。个人勾选由 filterRaidPrepOverlaysForViewer 处理。 */
export function buildRaidPrepOverlays(
  tasks: RaidPrepTaskLike[],
  mapSlug: string,
): TarkovRaidPrepOverlay[] {
  const keys = mapSlugKeys(mapSlug);
  const overlays: TarkovRaidPrepOverlay[] = [];
  tasks.forEach((task, taskIndex) => {
    const color = colorForTaskIndex(taskIndex);
    const taskName = displayRaidPrepTaskName(task);
    const traderSlug = (task.trader_slug || "").trim();
    const taskSteps = collectRaidPrepTaskObjectives(task, mapSlug);
    (task.objectives || []).forEach((obj, objIndex) => {
      const objId = raidPrepObjectiveKey(obj, objIndex);
      const steps = taskSteps.map((step) => ({
        id: step.id,
        text: step.text,
        optional: step.optional,
        active: step.id === objId,
      }));
      const subtitle =
        steps.find((step) => step.active)?.text ||
        raidPrepObjectiveStepText(obj);
      const optional = Boolean(obj.optional);
      const keyNames = objectiveKeyNames(obj);
      let zoneIdx = 0;
      const seenZones = new Set<string>();
      for (const zone of obj.zones || []) {
        if (!locationHitsMap(zone, keys)) continue;
        const dedupe = zoneDedupeKey(zone);
        if (dedupe) {
          if (seenZones.has(dedupe)) continue;
          seenZones.add(dedupe);
        }
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
          key: `${task.id}:obj:${obj.id || objIndex}:zone:${zone.id || zoneIdx}`,
          taskId: task.id,
          kind: "zone",
          color,
          title: taskName,
          subtitle,
          steps,
          traderSlug,
          keyNames,
          showNoKey: false,
          optional,
          objectiveId: objId,
          outline: polygon,
          points,
          height: zoneHeightSpan(zone) || pointsHeightSpan(points),
        });
        zoneIdx += 1;
      }
      let locIdx = 0;
      for (const loc of obj.possible_locations || []) {
        if (!locationHitsMap(loc, keys)) continue;
        const positions = uniqueRaidPrepPoints(validPoints(loc.positions));
        if (!positions.length) continue;
        overlays.push({
          key: `${task.id}:obj:${obj.id || objIndex}:spawn:${locIdx}`,
          taskId: task.id,
          kind: "spawn",
          color,
          title: taskName,
          subtitle: subtitle || "可能刷新点",
          steps,
          traderSlug,
          keyNames,
          showNoKey: false,
          optional,
          objectiveId: objId,
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

/** 同一目标里上游常把同一触发区写两遍；按米级坐标去重。 */
function raidPrepPointKey(point: RaidPrepPoint): string {
  const y = isFiniteNumber(point.y) ? `:${Math.round(point.y)}` : "";
  return `${Math.round(point.x)}:${Math.round(point.z)}${y}`;
}

function uniqueRaidPrepPoints(points: RaidPrepPoint[]): RaidPrepPoint[] {
  const seen = new Set<string>();
  const out: RaidPrepPoint[] = [];
  for (const point of points) {
    const key = raidPrepPointKey(point);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(point);
  }
  return out;
}

function zoneDedupeKey(zone: ZoneLike): string | null {
  const point = zoneAnchorPoint(zone);
  if (point) return raidPrepPointKey(point);
  const id = String(zone.id || "").trim();
  return id ? `id:${id}` : null;
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

export type RaidPrepLocateTarget = RaidPrepPoint & { objectiveId: string };

/** 任务在当前地图的定位点：非 optional 在前，可选在后。 */
export function resolveRaidPrepLocateTargets(
  task: RaidPrepTaskLike,
  mapSlug: string,
  skipped?: ReadonlySet<string>,
): RaidPrepLocateTarget[] {
  const keys = mapSlugKeys(mapSlug);
  const required: RaidPrepLocateTarget[] = [];
  const optional: RaidPrepLocateTarget[] = [];
  const seen = new Set<string>();
  const done = skipped || EMPTY_SKIP;
  const pushPoint = (
    bucket: RaidPrepLocateTarget[],
    point: RaidPrepPoint,
    objectiveId: string,
  ) => {
    const key = raidPrepPointKey(point);
    if (seen.has(key)) return;
    seen.add(key);
    bucket.push({ ...point, objectiveId });
  };
  (task.objectives || []).forEach((obj, index) => {
    const objectiveId = raidPrepObjectiveKey(obj, index);
    if (done.has(objectiveId)) return;
    const bucket = obj.optional ? optional : required;
    for (const zone of obj.zones || []) {
      if (!locationHitsMap(zone, keys)) continue;
      const point = zoneAnchorPoint(zone);
      if (point) pushPoint(bucket, point, objectiveId);
    }
    for (const loc of obj.possible_locations || []) {
      if (!locationHitsMap(loc, keys)) continue;
      for (const point of validPoints(loc.positions)) {
        pushPoint(bucket, point, objectiveId);
      }
    }
  });
  return [...required, ...optional];
}

export function resolveRaidPrepLocatePoints(
  task: RaidPrepTaskLike,
  mapSlug: string,
  skipped?: ReadonlySet<string>,
): RaidPrepPoint[] {
  return resolveRaidPrepLocateTargets(task, mapSlug, skipped).map(
    ({ objectiveId: _objectiveId, ...point }) => point,
  );
}

/** 任务在当前地图的首个定位点：优先非 optional 目标的首个 zone / 刷新点。 */
export function resolveRaidPrepLocatePoint(
  task: RaidPrepTaskLike,
  mapSlug: string,
): RaidPrepPoint | null {
  return resolveRaidPrepLocatePoints(task, mapSlug)[0] ?? null;
}

/**
 * 还有能画在地图上、且未勾完的点时才显示定位。
 * 几何还没灌进来时，目录标记有点且本图还有未勾步骤，先留着按钮。
 */
export function raidPrepTaskCanLocate(
  task: RaidPrepTaskLike,
  mapSlug: string,
  skipped?: ReadonlySet<string> | null,
  opts?: { taskDone?: boolean; hasMapMarkers?: boolean },
): boolean {
  if (opts?.taskDone) return false;
  const done = skipped || undefined;
  if (resolveRaidPrepLocateTargets(task, mapSlug, done).length) return true;
  if (resolveRaidPrepLocateTargets(task, mapSlug).length) return false;
  if (!opts?.hasMapMarkers) return false;
  const steps = collectRaidPrepTaskObjectives(task, mapSlug);
  if (!steps.length) return true;
  const have = skipped || EMPTY_SKIP;
  return steps.some((step) => !have.has(step.id));
}

function raidPrepPointXZKey(point: RaidPrepPoint): string {
  return `${Math.round(point.x)}:${Math.round(point.z)}`;
}

/** 定位点对应的地图 overlay：按米级 xz 对齐，忽略高度差。 */
export function matchRaidPrepOverlayAtPoint(
  overlays: readonly TarkovRaidPrepOverlay[],
  taskId: string,
  point: RaidPrepPoint,
): TarkovRaidPrepOverlay | undefined {
  const tid = String(taskId || "").trim();
  const key = raidPrepPointXZKey(point);
  return overlays.find((row) => {
    if (row.taskId !== tid) return false;
    return [...row.points, ...row.outline].some(
      (hit) => raidPrepPointXZKey(hit) === key,
    );
  });
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
  const cell = Math.max(gap, 1);
  const buckets = new Map<string, number[]>();
  for (let i = 0; i < pts.length; i += 1) {
    const point = pts[i]!;
    const key = `${Math.floor(point.x / cell)}:${Math.floor(point.z / cell)}`;
    const list = buckets.get(key);
    if (list) list.push(i);
    else buckets.set(key, [i]);
  }
  for (let i = 0; i < pts.length; i += 1) {
    const a = pts[i]!;
    const gx = Math.floor(a.x / cell);
    const gz = Math.floor(a.z / cell);
    for (let ox = -1; ox <= 1; ox += 1) {
      for (let oz = -1; oz <= 1; oz += 1) {
        const list = buckets.get(`${gx + ox}:${gz + oz}`);
        if (!list) continue;
        for (const j of list) {
          if (j <= i) continue;
          const b = pts[j]!;
          const dx = a.x - b.x;
          const dz = a.z - b.z;
          if (dx * dx + dz * dz > gap2) continue;
          const ra = find(i);
          const rb = find(j);
          if (ra !== rb) parent[rb] = ra;
        }
      }
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

export type RaidPrepVirtualWindow = {
  start: number;
  end: number;
  padTop: number;
  padBottom: number;
};

/** 侧栏未选列表窗口：按估算行高切一段，overscan 避免白边。 */
export function raidPrepVirtualWindow(opts: {
  scrollTop: number;
  viewportHeight: number;
  count: number;
  rowHeight: number;
  overscan?: number;
}): RaidPrepVirtualWindow {
  const count = Math.max(0, Math.trunc(opts.count));
  const rowHeight = Math.max(1, opts.rowHeight);
  if (!count) return { start: 0, end: 0, padTop: 0, padBottom: 0 };
  const overscan = Math.max(0, Math.trunc(opts.overscan ?? 8));
  const scrollTop = Math.max(0, opts.scrollTop);
  const viewport = Math.max(0, opts.viewportHeight);
  const start = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
  const visible = Math.ceil(viewport / rowHeight) + overscan * 2;
  const end = Math.min(count, start + visible);
  return {
    start,
    end,
    padTop: start * rowHeight,
    padBottom: Math.max(0, (count - end) * rowHeight),
  };
}

export const RAID_PREP_REST_VIRTUAL_MIN = 24;
export const RAID_PREP_REST_ROW_PX = 40;

export function missingRaidPrepGeometryIds(
  cached: Readonly<Record<string, { id?: string }>> | null | undefined,
  ids: readonly string[],
): string[] {
  const have = cached || {};
  const out: string[] = [];
  const seen = new Set<string>();
  for (const raw of ids) {
    const id = (raw || "").trim();
    if (!id || seen.has(id) || have[id]) continue;
    seen.add(id);
    out.push(id);
  }
  return out;
}

export function mergeRaidPrepGeometryItems<T extends { id?: string }>(
  cached: Readonly<Record<string, T>> | null | undefined,
  items: readonly T[],
): Record<string, T> {
  const next: Record<string, T> = { ...(cached || {}) };
  for (const item of items) {
    const id = (item.id || "").trim();
    if (id) next[id] = item;
  }
  return next;
}

export function raidPrepGeometryQueryKey(gameMode: string, mapId: string) {
  return ["guides-tarkov-raid-prep-geometry", gameMode, mapId] as const;
}

export function hydrateRaidPrepCatalogRows<T extends { id?: string }>(
  catalog: readonly T[],
  byId: Readonly<Record<string, T>>,
): T[] {
  if (!catalog.length) return [];
  return catalog.map((row) => {
    const id = (row.id || "").trim();
    return (id && byId[id]) || row;
  });
}
