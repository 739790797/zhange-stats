/** 按随从组合把多张图合成一套刷法（地点横向、随从只写一次）。 */

export type BossSpawnMapChip = {
  slug: string;
  name: string;
  spawnChance: string;
};

export type BossSpawnPoint = {
  x: number;
  y: number;
  z: number;
};

export type BossSpawnLocationChip = {
  mapSlug: string;
  mapName: string;
  name: string;
  chance: number;
  positions: BossSpawnPoint[];
};

export type BossSpawnEscortChip = {
  slug: string;
  name: string;
  count: number;
  chance: number;
};

export type BossSpawnGroup = {
  maps: BossSpawnMapChip[];
  sharedSpawnChance: string | null;
  landLabel: string;
  locations: BossSpawnLocationChip[];
  escorts: BossSpawnEscortChip[];
  showLocationChance: boolean;
};

export type BossSpawnGroupInput = {
  maps?: {
    slug?: string | null;
    name?: string | null;
    spawn_chance?: string | null;
  }[] | null;
  spawn_locations?: {
    map?: string | null;
    map_slug?: string | null;
    name?: string | null;
    chance?: number | null;
    positions?: { x?: number | null; y?: number | null; z?: number | null }[] | null;
  }[] | null;
  escorts?: {
    slug?: string | null;
    name?: string | null;
    count?: number | null;
    chance?: number | null;
    map?: string | null;
    map_slug?: string | null;
  }[] | null;
};

function mapKey(slug?: string | null, name?: string | null): string {
  const s = (slug || "").trim().toLowerCase();
  if (s) return s;
  return (name || "").trim().toLowerCase();
}

function recipeKey(escorts: BossSpawnEscortChip[]): string {
  return escorts
    .map(
      (row) =>
        `${row.slug}\t${row.count}\t${Number.isFinite(row.chance) ? row.chance.toFixed(4) : "0"}`,
    )
    .sort()
    .join("|");
}

function toSpawnPoints(
  raw: { x?: number | null; y?: number | null; z?: number | null }[] | null | undefined,
): BossSpawnPoint[] {
  const out: BossSpawnPoint[] = [];
  for (const row of raw || []) {
    const x = Number(row.x);
    const z = Number(row.z);
    if (!Number.isFinite(x) || !Number.isFinite(z)) continue;
    const y = Number(row.y);
    out.push({ x, y: Number.isFinite(y) ? y : 0, z });
  }
  return out;
}

function toEscort(row: NonNullable<BossSpawnGroupInput["escorts"]>[number]): BossSpawnEscortChip {
  return {
    slug: (row.slug || "").trim(),
    name: (row.name || row.slug || "").trim(),
    count: Number(row.count) || 0,
    chance: Number(row.chance) || 0,
  };
}

function roundedChance(chance: number): number {
  return Math.round((Number(chance) || 0) * 1000);
}

export function escortChipLabel(row: BossSpawnEscortChip): string {
  const name = (row.name || row.slug || "").trim() || "随从";
  const qty = row.count > 0 ? `×${row.count}` : "";
  const showPct = Number.isFinite(row.chance) && row.chance > 0 && row.chance < 0.995;
  const pct = showPct ? `（${Math.round(row.chance * 100)}%）` : "";
  return [name, qty].filter(Boolean).join(" ") + pct;
}

function escortMobKey(row: { slug?: string | null; name?: string | null }): string {
  return (row.slug || row.name || "").trim().toLowerCase();
}

/** 同一随从多种人数：互斥档位，不是同时带这么多。 */
export function isSameMobCountVariants(
  escorts: readonly { slug?: string | null; name?: string | null }[],
): boolean {
  if (escorts.length < 2) return false;
  const keys = new Set(escorts.map(escortMobKey).filter(Boolean));
  return keys.size === 1;
}

export function formatEscortMember(
  row: Pick<BossSpawnEscortChip, "name" | "slug" | "count"> & { chance?: number },
): string {
  const name = (row.name || row.slug || "随从").trim() || "随从";
  const chance = Number(row.chance);
  const pct =
    Number.isFinite(chance) && chance > 0 && chance < 0.995
      ? `（${Math.round(chance * 100)}%）`
      : "";
  return `${name} ×${row.count}${pct}`;
}

export function formatEscortComposition(
  escorts: readonly Pick<BossSpawnEscortChip, "name" | "slug" | "count" | "chance">[],
): string {
  if (!escorts.length) return "无";
  return escorts.map(formatEscortMember).join("、");
}

/** 同图多套刷法（破冰船保镖人数）标成组合 1/2/3。 */
export function spawnGroupComboNumbers(
  groups: readonly Pick<BossSpawnGroup, "maps">[],
): (number | null)[] {
  const byMaps = new Map<string, number[]>();
  groups.forEach((group, index) => {
    const key = group.maps
      .map((row) => (row.slug || row.name).trim().toLowerCase())
      .filter(Boolean)
      .sort()
      .join("|");
    const list = byMaps.get(key) || [];
    list.push(index);
    byMaps.set(key, list);
  });
  const out: (number | null)[] = groups.map(() => null);
  for (const idxs of byMaps.values()) {
    if (idxs.length < 2) continue;
    idxs.forEach((index, n) => {
      out[index] = n + 1;
    });
  }
  return out;
}

export function groupBossSpawnWaves(input: BossSpawnGroupInput): BossSpawnGroup[] {
  const mapsIn = input.maps || [];
  const locationsIn = input.spawn_locations || [];
  const escortsIn = input.escorts || [];

  const byKey = new Map<string, BossSpawnMapChip>();
  const order: string[] = [];

  const ensureMap = (slug?: string | null, name?: string | null, spawnChance?: string | null) => {
    const key = mapKey(slug, name);
    if (!key) return;
    const existing = byKey.get(key);
    if (existing) {
      if (!existing.slug && slug) existing.slug = slug.trim();
      if (!existing.name && name) existing.name = (name || "").trim();
      if (!existing.spawnChance && spawnChance) existing.spawnChance = spawnChance.trim();
      return;
    }
    byKey.set(key, {
      slug: (slug || "").trim(),
      name: (name || slug || "").trim(),
      spawnChance: (spawnChance || "").trim(),
    });
    order.push(key);
  };

  for (const row of mapsIn) {
    ensureMap(row.slug, row.name, row.spawn_chance);
  }
  for (const row of locationsIn) {
    ensureMap(row.map_slug, row.map, "");
  }
  for (const row of escortsIn) {
    ensureMap(row.map_slug, row.map, "");
  }

  const escortsByMap = new Map<string, BossSpawnEscortChip[]>();
  for (const row of escortsIn) {
    const key = mapKey(row.map_slug, row.map);
    if (!key) continue;
    const list = escortsByMap.get(key) || [];
    list.push(toEscort(row));
    escortsByMap.set(key, list);
  }

  const groupOrder: string[] = [];
  const groups = new Map<string, string[]>();
  for (const key of order) {
    const recipe = recipeKey(escortsByMap.get(key) || []);
    const members = groups.get(recipe);
    if (members) {
      members.push(key);
      continue;
    }
    groups.set(recipe, [key]);
    groupOrder.push(recipe);
  }

  return groupOrder.map((recipe) => {
    const mapKeys = groups.get(recipe) || [];
    const maps = mapKeys
      .map((key) => byKey.get(key))
      .filter((row): row is BossSpawnMapChip => Boolean(row));
    const keySet = new Set(mapKeys);
    const locations: BossSpawnLocationChip[] = [];
    for (const row of locationsIn) {
      const key = mapKey(row.map_slug, row.map);
      if (!keySet.has(key)) continue;
      const mapRow = byKey.get(key);
      const name = (row.name || "").trim();
      if (!name) continue;
      locations.push({
        mapSlug: (row.map_slug || mapRow?.slug || "").trim(),
        mapName: (row.map || mapRow?.name || "").trim(),
        name,
        chance: Number(row.chance) || 0,
        positions: toSpawnPoints(row.positions),
      });
    }
    const firstKey = mapKeys[0];
    const escorts = firstKey ? [...(escortsByMap.get(firstKey) || [])] : [];
    const chances = maps.map((row) => row.spawnChance).filter(Boolean);
    const shared =
      chances.length === maps.length &&
      chances.length > 0 &&
      chances.every((item) => item === chances[0])
        ? chances[0]
        : null;
    const locChanceKeys = new Set(locations.map((row) => roundedChance(row.chance)));
    return {
      maps,
      sharedSpawnChance: shared,
      landLabel: "",
      locations,
      escorts,
      showLocationChance: locChanceKeys.size > 1,
    };
  });
}

export function locationChipLabel(
  row: BossSpawnLocationChip,
  group: Pick<BossSpawnGroup, "locations">,
  translate: (name: string, mapSlug: string) => string = (name) => name,
): string {
  const text = translate(row.name, row.mapSlug) || row.name;
  const dup = group.locations.filter((item) => item.name === row.name).length > 1;
  if (dup && row.mapName) return `${row.mapName} ${text}`;
  return text;
}

export type BossSpawnGroupApi = {
  maps?: {
    id?: string | null;
    slug?: string | null;
    name?: string | null;
    spawn_chance?: string | null;
  }[] | null;
  shared_spawn_chance?: string | null;
  land_label?: string | null;
  locations?: {
    map?: string | null;
    map_slug?: string | null;
    name?: string | null;
    chance?: number | null;
    positions?: { x?: number | null; y?: number | null; z?: number | null }[] | null;
  }[] | null;
  escorts?: {
    slug?: string | null;
    name?: string | null;
    count?: number | null;
    chance?: number | null;
  }[] | null;
  show_location_chance?: boolean | null;
};

export function spawnGroupFromApi(raw: BossSpawnGroupApi): BossSpawnGroup {
  const maps = (raw.maps || []).map((row) => ({
    slug: (row.slug || "").trim(),
    name: (row.name || row.slug || "").trim(),
    spawnChance: (row.spawn_chance || "").trim(),
  }));
  const shared = (raw.shared_spawn_chance || "").trim();
  return {
    maps,
    sharedSpawnChance: shared || null,
    landLabel: (raw.land_label || "").trim(),
    locations: (raw.locations || [])
      .map((row) => ({
        mapSlug: (row.map_slug || "").trim(),
        mapName: (row.map || "").trim(),
        name: (row.name || "").trim(),
        chance: Number(row.chance) || 0,
        positions: toSpawnPoints(row.positions),
      }))
      .filter((row) => row.name),
    escorts: (raw.escorts || []).map((row) => ({
      slug: (row.slug || "").trim(),
      name: (row.name || row.slug || "").trim(),
      count: Number(row.count) || 0,
      chance: Number(row.chance) || 0,
    })),
    showLocationChance: Boolean(raw.show_location_chance),
  };
}

export function resolveBossSpawnGroups(input: {
  spawn_groups?: BossSpawnGroupApi[] | null;
  maps?: BossSpawnGroupInput["maps"];
  spawn_locations?: BossSpawnGroupInput["spawn_locations"];
  escorts?: BossSpawnGroupInput["escorts"];
}): BossSpawnGroup[] {
  const groups = input.spawn_groups || [];
  if (groups.length) return groups.map(spawnGroupFromApi);
  return groupBossSpawnWaves(input);
}
