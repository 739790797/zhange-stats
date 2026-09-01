import { isTopLevelNamedBoss } from "./tarkovBossKinds";
import {
  resolveBossSpawnGroups,
  type BossSpawnGroup,
  type BossSpawnGroupApi,
  type BossSpawnGroupInput,
} from "./tarkovBossSpawnGroups";

export type BossHubItem = {
  id?: string | null;
  slug?: string | null;
  parent_ids?: string[] | null;
  spawn_groups?: BossSpawnGroupApi[] | null;
} & BossSpawnGroupInput;

export type BossHubRow<T extends BossHubItem = BossHubItem> = {
  key: string;
  boss: T;
  group: BossSpawnGroup | null;
  nameSpan: number;
  mapSpan: number;
  landSpan: number;
};

function mapsKey(group: BossSpawnGroup | null): string {
  if (!group?.maps.length) return "";
  return group.maps
    .map((row) => {
      const id = (row.slug || row.name).trim().toLowerCase();
      const chance = (row.spawnChance || group.sharedSpawnChance || "").trim();
      return `${id}:${chance}`;
    })
    .join("|");
}

function landKey(group: BossSpawnGroup | null): string {
  return (group?.landLabel || "").trim();
}

function applyColumnSpans<T extends BossHubItem>(
  rows: BossHubRow<T>[],
  field: "mapSpan" | "landSpan",
  getKey: (row: BossHubRow<T>) => string,
): void {
  let index = 0;
  while (index < rows.length) {
    const bossId = String(rows[index].boss.id || rows[index].boss.slug || "");
    const key = getKey(rows[index]);
    let end = index + 1;
    while (
      end < rows.length &&
      String(rows[end].boss.id || rows[end].boss.slug || "") === bossId &&
      getKey(rows[end]) === key
    ) {
      end += 1;
    }
    rows[index][field] = end - index;
    for (let i = index + 1; i < end; i += 1) {
      rows[i][field] = 0;
    }
    index = end;
  }
}

/** 同一 Boss 连续相同的地图（含出生率）/ 出生时间合并单元格。 */
export function flattenBossHubRows<T extends BossHubItem>(
  items: readonly T[],
): BossHubRow<T>[] {
  const out: BossHubRow<T>[] = [];
  for (const boss of items) {
    const groups = resolveBossSpawnGroups(boss);
    const list: Array<BossSpawnGroup | null> = groups.length ? groups : [null];
    list.forEach((group, index) => {
      out.push({
        key: `${boss.id || boss.slug || "boss"}-${index}`,
        boss,
        group,
        nameSpan: index === 0 ? list.length : 0,
        mapSpan: 1,
        landSpan: 1,
      });
    });
  }
  applyColumnSpans(out, "mapSpan", (row) => mapsKey(row.group));
  applyColumnSpans(out, "landSpan", (row) => landKey(row.group));
  return out;
}

function spawnGroupLooksIndependent(group: BossSpawnGroup): boolean {
  return group.locations.length > 0 || group.escorts.length > 0;
}

function groupToApi(group: BossSpawnGroup): BossSpawnGroupApi {
  return {
    maps: group.maps.map((row) => ({
      slug: row.slug,
      name: row.name,
      spawn_chance: row.spawnChance,
    })),
    shared_spawn_chance: group.sharedSpawnChance || "",
    land_label: group.landLabel,
    locations: group.locations.map((row) => ({
      map: row.mapName,
      map_slug: row.mapSlug,
      name: row.name,
      chance: row.chance,
    })),
    escorts: group.escorts.map((row) => ({
      slug: row.slug,
      name: row.name,
      count: row.count,
      chance: row.chance,
    })),
    show_location_chance: group.showLocationChance,
  };
}

/**
 * 非 Boss 热力：只挂在具名 Boss 随从里、没有自己刷点的不列；
 * 灯塔游荡者这种既当随从又独立刷新的，只保留独立刷的那几套。
 */
export function selectIndependentOtherBosses<T extends BossHubItem>(
  items: readonly T[],
): T[] {
  const out: T[] = [];
  for (const item of items) {
    if (isTopLevelNamedBoss(item.id, item.parent_ids)) continue;
    const parents = (item.parent_ids || []).filter(Boolean);
    if (!parents.length) {
      out.push(item);
      continue;
    }
    const kept = resolveBossSpawnGroups(item).filter(spawnGroupLooksIndependent);
    if (!kept.length) continue;
    out.push({ ...item, spawn_groups: kept.map(groupToApi) });
  }
  return out;
}
