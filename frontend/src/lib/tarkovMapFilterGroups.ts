/** 对齐 tarkov.dev zh maps.json 的图层分组与子项文案。 */

export const TARKOV_MAP_FILTER_GROUP_LABELS = {
  style: "底图样式",
  levels: "层级",
  extracts: "撤离点",
  spawns: "出生点",
  usable: "可使用",
  lootable: "可搜刮物品",
  tasks: "任务",
  hazards: "危险区",
  landmarks: "地名",
  lootLoose: "散落物",
  screenshot: "截图定位",
} as const;

export const TARKOV_MAP_FILTER_ITEM_LABELS = {
  locks: "锁",
  stationary: "固定机枪",
  switches: "开关",
  btrStop: "BTR 停车点",
  placeNames: "地名",
  lootLoose: "散落物",
} as const;

/** 侧栏分组顺序：底图 → 层级 → 点位组 → 任务 → 截图定位。 */
export const TARKOV_MAP_FILTER_GROUP_ORDER = [
  "style",
  "levels",
  "landmarks",
  "extracts",
  "spawns",
  "usable",
  "hazards",
  "lootable",
  "lootLoose",
  "tasks",
  "screenshot",
] as const;

export type TarkovMapFilterGroupId =
  (typeof TARKOV_MAP_FILTER_GROUP_ORDER)[number];

const FILTER_GROUP_IDS = new Set<string>(TARKOV_MAP_FILTER_GROUP_ORDER);

/** 缺省展开；只把明确收起的大类记下来。 */
export function parseFilterGroupsCollapsed(
  raw: unknown,
): Partial<Record<TarkovMapFilterGroupId, boolean>> {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  const out: Partial<Record<TarkovMapFilterGroupId, boolean>> = {};
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    if (!FILTER_GROUP_IDS.has(key) || value !== true) continue;
    out[key as TarkovMapFilterGroupId] = true;
  }
  return out;
}

export function isFilterGroupCollapsed(
  collapsed: Partial<Record<TarkovMapFilterGroupId, boolean>> | undefined,
  key: TarkovMapFilterGroupId,
): boolean {
  return collapsed?.[key] === true;
}

export function toggleFilterGroupCollapsed(
  collapsed: Partial<Record<TarkovMapFilterGroupId, boolean>> | undefined,
  key: TarkovMapFilterGroupId,
): Partial<Record<TarkovMapFilterGroupId, boolean>> {
  const next: Partial<Record<TarkovMapFilterGroupId, boolean>> = {
    ...collapsed,
  };
  if (next[key]) delete next[key];
  else next[key] = true;
  return next;
}

export type TarkovMapFilterFlagItem = {
  key: string;
  on: boolean;
};

export function filterGroupAllOn(
  items: readonly TarkovMapFilterFlagItem[],
): boolean {
  return items.length > 0 && items.every((item) => item.on);
}

export function filterGroupAnyOn(
  items: readonly TarkovMapFilterFlagItem[],
): boolean {
  return items.some((item) => item.on);
}

export function filterGroupPartial(
  items: readonly TarkovMapFilterFlagItem[],
): boolean {
  return filterGroupAnyOn(items) && !filterGroupAllOn(items);
}

export function withFilterGroupOn<T extends Record<string, boolean>>(
  flags: T,
  keys: readonly (keyof T & string)[],
  on: boolean,
): T {
  if (!keys.length) return flags;
  const next = { ...flags };
  for (const key of keys) {
    (next as Record<string, boolean>)[key] = on;
  }
  return next;
}
