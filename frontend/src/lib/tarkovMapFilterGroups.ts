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
  landmarks: "地标",
  lootLoose: "散落物",
} as const;

export const TARKOV_MAP_FILTER_ITEM_LABELS = {
  locks: "锁",
  stationary: "固定机枪",
  switches: "开关",
  btrStop: "BTR 停车点",
  placeNames: "地名",
  lootLoose: "散落物",
} as const;

/** 侧栏分组顺序，对齐 tarkov.dev groupedLayers：底图 → 层级 → 点位组。 */
export const TARKOV_MAP_FILTER_GROUP_ORDER = [
  "style",
  "levels",
  "extracts",
  "spawns",
  "usable",
  "lootable",
  "tasks",
  "hazards",
  "landmarks",
  "lootLoose",
] as const;

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
