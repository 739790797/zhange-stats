import { isNamedBossId } from "@/lib/tarkovBossKinds";
import { TARKOV_MAPS, tarkovMapMarkByName } from "@/lib/tarkovHomeNav";
import {
  escortChipLabel,
  formatEscortComposition,
  formatEscortMember,
  isSameMobCountVariants,
  resolveBossSpawnGroups,
  type BossSpawnEscortChip,
  type BossSpawnGroup,
  type BossSpawnGroupApi,
  type BossSpawnGroupInput,
  type BossSpawnLocationChip,
} from "@/lib/tarkovBossSpawnGroups";

export type HeatmapBossInput = {
  id?: string | null;
  slug?: string | null;
  name?: string | null;
  portrait_link?: string | null;
  spawn_groups?: BossSpawnGroupApi[] | null;
} & BossSpawnGroupInput;

export type HeatmapBoss = {
  id: string;
  slug: string;
  name: string;
  portrait: string;
};

export type HeatmapMapCol = {
  slug: string;
  name: string;
  short: string;
  pool: boolean;
};

export type HeatmapCell = {
  label: string;
  recipeCount: number;
  locationCount: number;
  pool: boolean;
  chancePct: number;
  recipes: HeatmapRecipe[];
  spawnPoints: HeatmapSpawnPoint[];
};

export type HeatmapSpawnPoint = {
  name: string;
  chance: number;
  x: number;
  y: number;
  z: number;
};

export type HeatmapRecipe = {
  chance: string;
  chancePct: number;
  land: string;
  escorts: BossSpawnEscortChip[];
  escortLabel: string;
  locations?: string[];
};

export type HeatmapMapEntry = {
  boss: HeatmapBoss;
  recipes: HeatmapRecipe[];
};

export type HeatmapMapDrilldown = {
  slug: string;
  name: string;
  pool: boolean;
  entries: HeatmapMapEntry[];
};

export type HeatmapModel = {
  bosses: HeatmapBoss[];
  maps: HeatmapMapCol[];
  cells: HeatmapCell[][];
  drilldowns: Record<string, HeatmapMapDrilldown>;
};

const MAP_SLUG_ALIAS: Record<string, string> = {
  "streets-of-tarkov": "streets",
  "the-lab": "lab",
};

const NAV_IDS = TARKOV_MAPS.map((row) => row.id);

export function parseChancePct(raw: string | null | undefined): number {
  const nums = [...String(raw || "").matchAll(/(\d+(?:\.\d+)?)/g)].map((m) =>
    Number(m[1]),
  );
  if (!nums.length) return 0;
  return Math.max(...nums);
}

export function mapColumnShort(name: string, slug = ""): string {
  const text = (name || slug).trim();
  if (text.includes("夜间")) return "夜工";
  if (text.includes("街区") || slug.includes("streets")) return "街区";
  if (text.includes("实验室") || slug === "lab" || slug === "the-lab") return "实验室";
  const mark = tarkovMapMarkByName(text) || (slug ? tarkovMapMarkByName(slug) : null);
  return (mark?.label || text || slug).replace(/塔科夫/g, "");
}

function mapKey(slug: string, name: string): string {
  const s = slug.trim().toLowerCase();
  if (s) return s;
  return name.trim().toLowerCase();
}

function mapOrder(slug: string, name: string): number {
  if (slug === "night-factory" || name.includes("夜间")) {
    const factory = NAV_IDS.indexOf("factory");
    return factory >= 0 ? factory + 0.5 : 99;
  }
  const aliased = MAP_SLUG_ALIAS[slug] || slug;
  const byId = NAV_IDS.indexOf(aliased);
  if (byId >= 0) return byId;
  const mark = tarkovMapMarkByName(name) || (slug ? tarkovMapMarkByName(slug) : null);
  if (mark) {
    const idx = NAV_IDS.indexOf(mark.id);
    if (idx >= 0) return idx;
  }
  return 80;
}

function locClusterKey(group: BossSpawnGroup, slug: string, name: string): string {
  const key = mapKey(slug, name);
  const names = group.locations
    .filter((row) => mapKey(row.mapSlug, row.mapName) === key)
    .map((row) => row.name)
    .sort()
    .join("|");
  return `${names}::${group.landLabel}`;
}

function recipeLabel(chances: string[]): string {
  const cleaned = chances.map((row) => row.trim()).filter(Boolean);
  if (!cleaned.length) return "";
  const uniq = [...new Set(cleaned)];
  if (uniq.length === 1) return uniq[0] || "";
  const pcts = cleaned.map(parseChancePct);
  const lo = Math.min(...pcts);
  const hi = Math.max(...pcts);
  return lo === hi ? `${hi}%` : `${lo}–${hi}%`;
}

function uniqueNames(names: readonly string[]): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const raw of names) {
    const name = raw.trim();
    if (!name || seen.has(name)) continue;
    seen.add(name);
    out.push(name);
  }
  return out;
}

function toRecipe(row: Placement): HeatmapRecipe {
  return {
    chance: row.chance,
    chancePct: row.chancePct,
    land: row.land,
    escorts: row.escorts,
    escortLabel: row.escorts.length
      ? row.escorts.map(escortChipLabel).join(" · ")
      : "无随从",
    locations: uniqueNames(row.locations),
  };
}

function toEscortRow(row: BossSpawnEscortChip): HeatmapHoverEscort {
  return {
    slug: row.slug,
    name: (row.name || row.slug || "随从").trim() || "随从",
    count: row.count,
    chance: Number(row.chance) || 0,
  };
}

export type HeatmapHoverEscort = {
  slug: string;
  name: string;
  count: number;
  chance: number;
};

export type HeatmapSquadSize = {
  size: number;
  chance: string;
};

export type HeatmapHoverBlock = {
  chance: string;
  showChance: boolean;
  land: string;
  escorts: HeatmapHoverEscort[];
  squadSizes: HeatmapSquadSize[];
  /** 各区域人数表不同时才带区域名；共用一套表时为空。 */
  locations?: string[];
};

export function escortMatchesBoss(
  escort: { slug?: string | null; name?: string | null },
  boss: Pick<HeatmapBoss, "id" | "slug" | "name">,
): boolean {
  const keys = new Set(
    [boss.id, boss.slug, boss.name]
      .map((row) => row.trim().toLowerCase())
      .filter(Boolean),
  );
  for (const raw of [escort.slug, escort.name]) {
    const key = String(raw || "").trim().toLowerCase();
    if (key && keys.has(key)) return true;
  }
  return false;
}

export function squadSizeOfEscorts(
  escorts: readonly BossSpawnEscortChip[],
  boss: Pick<HeatmapBoss, "id" | "slug" | "name">,
): { size: number; others: HeatmapHoverEscort[] } {
  let extra = 0;
  const others: HeatmapHoverEscort[] = [];
  for (const row of escorts) {
    if (escortMatchesBoss(row, boss)) extra += Math.max(0, row.count);
    else others.push(toEscortRow(row));
  }
  return { size: 1 + extra, others };
}

export function formatHoverSquadSizes(
  sizes: readonly HeatmapSquadSize[],
  showChance: boolean,
): string {
  if (!sizes.length) return "";
  if (showChance) {
    return sizes.map((row) => `${row.size}（${row.chance}）`).join(" / ");
  }
  const nums = sizes.map((row) => row.size);
  if (nums.length === 1) return String(nums[0]);
  const contiguous = nums.every((n, index) => index === 0 || n === nums[index - 1]! + 1);
  return contiguous ? `${nums[0]}–${nums[nums.length - 1]}` : nums.join(" / ");
}

export function formatHoverSquadCount(
  sizes: readonly HeatmapSquadSize[],
  showChance: boolean,
): string {
  const core = formatHoverSquadSizes(sizes, showChance);
  if (!core || showChance) return core;
  return `${core}个`;
}

export function hoverUsesLocationCounts(
  blocks: readonly HeatmapHoverBlock[],
): boolean {
  return blocks.some((row) => (row.locations || []).length > 0);
}

export function hoverSquadCountForLocation(
  blocks: readonly HeatmapHoverBlock[],
  name: string,
): string {
  const block = blocks.find((row) => (row.locations || []).includes(name));
  if (!block?.squadSizes.length) return "";
  return formatHoverSquadCount(block.squadSizes, block.showChance);
}

export type HoverEscortScheme = {
  index: number;
  line: string;
  chance: string;
  showChance: boolean;
  land: string;
  escorts: HeatmapHoverEscort[];
};

export function sharedHoverLand(blocks: readonly HeatmapHoverBlock[]): string {
  const lands = [
    ...new Set(blocks.map((row) => row.land.trim()).filter(Boolean)),
  ];
  return lands.length === 1 ? lands[0] : "";
}

/** 多套刷法或同一随从多种人数：互斥组合，不是同时全出。 */
export function hoverEscortSchemes(
  blocks: readonly HeatmapHoverBlock[],
): HoverEscortScheme[] | null {
  if (blocks.length > 1) {
    const onlySquad = blocks.every(
      (row) => row.squadSizes.length > 0 && !row.escorts.length,
    );
    if (onlySquad) return null;
    return blocks.map((row, index) => ({
      index: index + 1,
      line: formatEscortComposition(row.escorts),
      chance: row.chance,
      showChance: row.showChance,
      land: row.land,
      escorts: row.escorts,
    }));
  }
  const only = blocks[0];
  if (only && isSameMobCountVariants(only.escorts)) {
    return only.escorts.map((row, index) => ({
      index: index + 1,
      line: formatEscortMember(row),
      chance: only.chance,
      showChance: false,
      land: only.land,
      escorts: [row],
    }));
  }
  return null;
}

export function formatHoverAria(blocks: readonly HeatmapHoverBlock[]): string {
  const parts: string[] = [];
  const landOnce = sharedHoverLand(blocks);
  const schemes = hoverEscortSchemes(blocks);
  if (landOnce) parts.push(`出生时间：${landOnce}`);
  for (const block of blocks) {
    if (!schemes && !landOnce && block.land) parts.push(`出生时间：${block.land}`);
    if (!schemes && block.showChance && block.chance && !block.squadSizes.length) {
      parts.push(block.chance);
    }
    if (block.squadSizes.length > 1 && !block.locations?.length) {
      parts.push(
        `出生数量：${block.squadSizes
          .map((row, index) => `组合${index + 1}：${row.size}人`)
          .join("；")}`,
      );
    } else if (block.squadSizes.length) {
      parts.push(
        `出生数量：${
          block.locations?.length
            ? formatHoverSquadCount(block.squadSizes, block.showChance)
            : formatHoverSquadSizes(block.squadSizes, block.showChance)
        }`,
      );
    }
    if (block.locations?.length) {
      parts.push(`区域：${block.locations.join("、")}`);
    }
  }
  if (schemes) {
    parts.push(
      `出生伴随：${schemes
        .map((row) => {
          const chance = row.showChance && row.chance ? `（${row.chance}）` : "";
          const land = !landOnce && row.land ? ` · ${row.land}` : "";
          return `组合${row.index}${chance}：${row.line}${land}`;
        })
        .join("；")}`,
    );
    return parts.join("，");
  }
  for (const block of blocks) {
    const rows = block.escorts.length
      ? block.escorts.map((row) => `${row.name} ×${row.count}`)
      : [];
    if (rows.length || !block.squadSizes.length) {
      parts.push(`出生伴随：${rows.length ? rows.join("，") : "无"}`);
    }
  }
  return parts.join("，");
}

type PortraitSource = {
  id?: string | null;
  slug?: string | null;
  name?: string | null;
  portrait_link?: string | null;
};

export function buildBossPortraitIndex(
  items: readonly PortraitSource[],
): Map<string, string> {
  const map = new Map<string, string>();
  const set = (raw: string, url: string) => {
    const key = raw.trim().toLowerCase();
    if (!key || map.has(key)) return;
    map.set(key, url);
  };
  for (const row of items) {
    const url = String(row.portrait_link || "").trim();
    if (!url) continue;
    set(String(row.id || ""), url);
    set(String(row.slug || ""), url);
    set(String(row.name || ""), url);
  }
  return map;
}

export function lookupEscortPortrait(
  escort: { slug?: string; name?: string },
  portraits: ReadonlyMap<string, string>,
): string {
  for (const raw of [escort.slug, escort.name]) {
    const key = String(raw || "").trim().toLowerCase();
    const hit = key ? portraits.get(key) : "";
    if (hit) return hit;
  }
  return "";
}

/** 悬浮：具名 Boss 按伴随列；自己扩编（含 Wedge）折成出生数量；区域人数表不同则分列。 */
export function heatmapCellHoverBlocks(
  recipes: readonly HeatmapRecipe[],
  boss?: Pick<HeatmapBoss, "id" | "slug" | "name"> | null,
): HeatmapHoverBlock[] {
  if (!recipes.length) return [];
  const chances = new Set(
    recipes.map((row) => row.chance.trim()).filter(Boolean),
  );
  const showChance = recipes.length > 1 && chances.size > 1;
  if (!boss || !usesSquadSizeHover(recipes, boss)) {
    return recipes.map((row) => ({
      chance: row.chance,
      showChance,
      land: row.land,
      escorts: row.escorts.map(toEscortRow),
      squadSizes: [],
    }));
  }

  const parsed = recipes.flatMap((row) => {
    if (
      row.escorts.length > 1 &&
      isSameMobCountVariants(row.escorts) &&
      row.escorts.every((escort) => escortMatchesBoss(escort, boss))
    ) {
      return row.escorts.map((escort) => ({
        recipe: row,
        size: 1 + Math.max(0, escort.count),
        others: [] as HeatmapHoverEscort[],
      }));
    }
    const split = squadSizeOfEscorts(row.escorts, boss);
    return [{ recipe: row, ...split }];
  });
  const selfOnly = parsed.filter((row) => !row.others.length);
  const mixed = parsed.filter((row) => row.others.length);
  const locBlocks = locationSquadBlocks(selfOnly);
  const blocks: HeatmapHoverBlock[] = locBlocks ? [...locBlocks] : [];
  if (!locBlocks) {
    const landOrder: string[] = [];
    const byLand = new Map<string, typeof selfOnly>();
    for (const row of selfOnly) {
      const key = row.recipe.land.trim();
      const list = byLand.get(key);
      if (list) {
        list.push(row);
        continue;
      }
      byLand.set(key, [row]);
      landOrder.push(key);
    }
    for (const land of landOrder) {
      const list = byLand.get(land) || [];
      const sizeMap = new Map<number, string[]>();
      for (const row of list) {
        const labels = sizeMap.get(row.size) || [];
        labels.push(row.recipe.chance);
        sizeMap.set(row.size, labels);
      }
      const squadSizes = [...sizeMap.entries()]
        .sort((a, b) => a[0] - b[0])
        .map(([size, labels]) => ({ size, chance: recipeLabel(labels) }));
      const landChances = new Set(
        list.map((row) => row.recipe.chance.trim()).filter(Boolean),
      );
      blocks.push({
        chance: recipeLabel(list.map((row) => row.recipe.chance)),
        showChance: landChances.size > 1,
        land,
        escorts: [],
        squadSizes,
      });
    }
  }
  for (const row of mixed) {
    blocks.push({
      chance: row.recipe.chance,
      showChance,
      land: row.recipe.land,
      escorts: row.others,
      squadSizes: [{ size: row.size, chance: row.recipe.chance }],
    });
  }
  return blocks;
}

function usesSquadSizeHover(
  recipes: readonly HeatmapRecipe[],
  boss: Pick<HeatmapBoss, "id" | "slug" | "name">,
): boolean {
  if (!isNamedBossId(boss.id)) return true;
  const hasForeign = recipes.some((row) =>
    row.escorts.some((escort) => !escortMatchesBoss(escort, boss)),
  );
  if (hasForeign) return false;
  return recipes.some((row) =>
    row.escorts.some((escort) => escortMatchesBoss(escort, boss)),
  );
}

function sizeTableKey(sizes: readonly number[]): string {
  return [...new Set(sizes)].sort((a, b) => a - b).join(",");
}

function locationSquadBlocks(
  rows: readonly { recipe: HeatmapRecipe; size: number }[],
): HeatmapHoverBlock[] | null {
  if (!rows.length) return null;
  const byLoc = new Map<
    string,
    { sizes: Map<number, string[]>; land: string; chances: string[] }
  >();
  for (const row of rows) {
    const names = uniqueNames(row.recipe.locations || []);
    if (!names.length) return null;
    for (const name of names) {
      let bucket = byLoc.get(name);
      if (!bucket) {
        bucket = {
          sizes: new Map(),
          land: row.recipe.land,
          chances: [],
        };
        byLoc.set(name, bucket);
      }
      const labels = bucket.sizes.get(row.size) || [];
      labels.push(row.recipe.chance);
      bucket.sizes.set(row.size, labels);
      bucket.chances.push(row.recipe.chance);
    }
  }
  if (byLoc.size < 2) return null;
  const tables = [...byLoc.values()].map((bucket) =>
    sizeTableKey([...bucket.sizes.keys()]),
  );
  if (new Set(tables).size < 2) return null;

  const groups = new Map<string, string[]>();
  const order: string[] = [];
  for (const [name, bucket] of byLoc) {
    const key = `${bucket.land}\t${sizeTableKey([...bucket.sizes.keys()])}`;
    const list = groups.get(key);
    if (list) {
      list.push(name);
      continue;
    }
    groups.set(key, [name]);
    order.push(key);
  }
  return order.map((key) => {
    const names = groups.get(key) || [];
    const bucket = byLoc.get(names[0] || "")!;
    const squadSizes = [...bucket.sizes.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([size, labels]) => ({ size, chance: recipeLabel(labels) }));
    const landChances = new Set(
      bucket.chances.map((row) => row.trim()).filter(Boolean),
    );
    return {
      chance: recipeLabel(bucket.chances),
      showChance: landChances.size > 1,
      land: bucket.land,
      escorts: [],
      squadSizes,
      locations: names,
    };
  });
}

function toBoss(row: HeatmapBossInput): HeatmapBoss {
  const id = String(row.id || row.slug || "").trim();
  return {
    id,
    slug: String(row.slug || id).trim(),
    name: String(row.name || row.slug || id).trim(),
    portrait: String(row.portrait_link || "").trim(),
  };
}

function mapLocationRows(
  group: BossSpawnGroup,
  slug: string,
  name: string,
): BossSpawnLocationChip[] {
  const key = mapKey(slug, name);
  return group.locations.filter((row) => mapKey(row.mapSlug, row.mapName) === key);
}

function collectSpawnPoints(
  rows: readonly BossSpawnLocationChip[],
): HeatmapSpawnPoint[] {
  const out: HeatmapSpawnPoint[] = [];
  for (const row of rows) {
    for (const point of row.positions) {
      out.push({
        name: row.name,
        chance: row.chance,
        x: point.x,
        y: point.y,
        z: point.z,
      });
    }
  }
  return uniqueSpawnPoints(out);
}

function uniqueSpawnPoints(
  rows: readonly HeatmapSpawnPoint[],
): HeatmapSpawnPoint[] {
  const out: HeatmapSpawnPoint[] = [];
  const seen = new Set<string>();
  for (const row of rows) {
    const token = `${row.name}\t${row.x.toFixed(2)}\t${row.y.toFixed(2)}\t${row.z.toFixed(2)}`;
    if (seen.has(token)) continue;
    seen.add(token);
    out.push(row);
  }
  return out;
}

export function heatmapMapParentSlug(slug: string): string {
  return slug === "night-factory" ? "factory" : "";
}

export function heatmapSpawnLocationOptions(
  points: readonly HeatmapSpawnPoint[],
): HeatmapSpawnPoint[] {
  const byName = new Map<string, HeatmapSpawnPoint[]>();
  for (const row of points) {
    const list = byName.get(row.name) || [];
    list.push(row);
    byName.set(row.name, list);
  }
  return [...byName.entries()].map(([name, pts]) => {
    const n = pts.length;
    return {
      name,
      chance: pts[0]?.chance ?? 0,
      x: pts.reduce((sum, row) => sum + row.x, 0) / n,
      y: pts.reduce((sum, row) => sum + row.y, 0) / n,
      z: pts.reduce((sum, row) => sum + row.z, 0) / n,
    };
  });
}

type Placement = {
  boss: HeatmapBoss;
  slug: string;
  name: string;
  chance: string;
  chancePct: number;
  land: string;
  escorts: BossSpawnEscortChip[];
  cluster: string;
  locations: string[];
  spawnPoints: HeatmapSpawnPoint[];
};

function collectPlacements(rows: readonly HeatmapBossInput[]): Placement[] {
  const out: Placement[] = [];
  for (const row of rows) {
    const boss = toBoss(row);
    if (!boss.id) continue;
    for (const group of resolveBossSpawnGroups(row)) {
      for (const map of group.maps) {
        const slug = map.slug || map.name;
        if (!slug) continue;
        const chance = (map.spawnChance || group.sharedSpawnChance || "").trim();
        out.push({
          boss,
          slug,
          name: map.name || map.slug,
          chance,
          chancePct: parseChancePct(chance),
          land: group.landLabel,
          escorts: group.escorts,
          cluster: locClusterKey(group, map.slug, map.name),
          locations: mapLocationRows(group, map.slug, map.name).map((row) =>
            row.name.trim(),
          ).filter(Boolean),
          spawnPoints: collectSpawnPoints(mapLocationRows(group, map.slug, map.name)),
        });
      }
    }
  }
  return out;
}

function detectPoolSlugs(placements: Placement[]): Set<string> {
  const byMap = new Map<string, Placement[]>();
  for (const row of placements) {
    if (!isNamedBossId(row.boss.id)) continue;
    const key = mapKey(row.slug, row.name);
    const list = byMap.get(key) || [];
    list.push(row);
    byMap.set(key, list);
  }
  const pools = new Set<string>();
  for (const [mapId, list] of byMap) {
    const clusters = new Map<string, Placement[]>();
    for (const row of list) {
      const bucket = clusters.get(row.cluster) || [];
      bucket.push(row);
      clusters.set(row.cluster, bucket);
    }
    for (const cluster of clusters.values()) {
      const bossIds = [...new Set(cluster.map((row) => row.boss.id))];
      if (bossIds.length < 2) continue;
      const sum = bossIds.reduce((acc, id) => {
        const max = Math.max(
          ...cluster.filter((row) => row.boss.id === id).map((row) => row.chancePct),
        );
        return acc + max;
      }, 0);
      if (sum >= 95 && sum <= 105) pools.add(mapId);
    }
  }
  return pools;
}

/** 总览热力：格子写出生率；多区域写成 N个区域；五选一只在具名 Boss 同点+概率加总≈100% 时标。 */
export function buildBossHeatmap(
  rows: readonly HeatmapBossInput[],
): HeatmapModel {
  const placements = collectPlacements(rows);
  const poolSlugs = detectPoolSlugs(placements);
  const bosses: HeatmapBoss[] = [];
  const seenBoss = new Set<string>();
  for (const row of rows) {
    const boss = toBoss(row);
    if (!boss.id || seenBoss.has(boss.id)) continue;
    seenBoss.add(boss.id);
    bosses.push(boss);
  }

  const mapMeta = new Map<string, HeatmapMapCol>();
  for (const row of placements) {
    const key = mapKey(row.slug, row.name);
    if (mapMeta.has(key)) continue;
    mapMeta.set(key, {
      slug: row.slug,
      name: row.name,
      short: mapColumnShort(row.name, row.slug),
      pool: poolSlugs.has(key),
    });
  }
  const maps = [...mapMeta.values()].sort((a, b) => {
    const d = mapOrder(a.slug, a.name) - mapOrder(b.slug, b.name);
    return d || a.name.localeCompare(b.name, "zh");
  });

  const cells: HeatmapCell[][] = bosses.map((boss) =>
    maps.map((col) => {
      const hits = placements.filter(
        (row) =>
          row.boss.id === boss.id &&
          mapKey(row.slug, row.name) === mapKey(col.slug, col.name),
      );
      if (!hits.length) {
        return {
          label: "",
          recipeCount: 0,
          locationCount: 0,
          pool: false,
          chancePct: 0,
          recipes: [],
          spawnPoints: [],
        };
      }
      const locationCount = new Set(hits.flatMap((row) => row.locations)).size;
      return {
        label: recipeLabel(hits.map((row) => row.chance)),
        recipeCount: hits.length,
        locationCount,
        pool: col.pool,
        chancePct: Math.max(...hits.map((row) => row.chancePct)),
        recipes: hits.map(toRecipe),
        spawnPoints: uniqueSpawnPoints(hits.flatMap((row) => row.spawnPoints)),
      };
    }),
  );

  const drilldowns: Record<string, HeatmapMapDrilldown> = {};
  for (const col of maps) {
    const key = mapKey(col.slug, col.name);
    const hits = placements.filter(
      (row) => mapKey(row.slug, row.name) === key,
    );
    const byBoss = new Map<string, HeatmapMapEntry>();
    for (const row of hits) {
      const existing = byBoss.get(row.boss.id);
      const recipe = toRecipe(row);
      if (existing) {
        existing.recipes.push(recipe);
        continue;
      }
      byBoss.set(row.boss.id, { boss: row.boss, recipes: [recipe] });
    }
    const entries = bosses
      .map((boss) => byBoss.get(boss.id))
      .filter((row): row is HeatmapMapEntry => Boolean(row));
    drilldowns[col.slug] = {
      slug: col.slug,
      name: col.name,
      pool: col.pool,
      entries,
    };
  }

  return { bosses, maps, cells, drilldowns };
}

export function heatmapDrilldown(
  model: HeatmapModel,
  slug: string,
): HeatmapMapDrilldown | null {
  return model.drilldowns[slug] || null;
}
