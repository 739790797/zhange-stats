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
];

export const RAID_PREP_MAX_SELECTED = 40;

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
};

export type TarkovRaidPrepOverlay = {
  key: string;
  kind: "zone" | "spawn";
  color: string;
  title: string;
  subtitle: string;
  traderSlug: string;
  keyNames: string[];
  /** 来自目标 optional；可选目标在地图上单独标出。 */
  optional: boolean;
  outline: RaidPrepPoint[];
  points: RaidPrepPoint[];
};

export type RaidPrepOverlayLabelItem = {
  title: string;
  color: string;
  traderSlug: string;
  count: number;
  optional: boolean;
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
};

type ZoneLike = LocationRef & {
  id?: string | null;
  x?: number | null;
  z?: number | null;
  outline?: Array<{ x?: number | null; z?: number | null }> | null;
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
};

export type RaidPrepTaskSummary = {
  taskId: string;
  taskName: string;
  traderSlug: string;
  traderName: string;
  items: RaidPrepNeededItem[];
  keys: RaidPrepNeededItem[];
  types: string[];
};

function isFiniteNumber(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

const TARKOV_HEX_ID_RE = /^[a-f0-9]{24}$/i;

/** BSG 物品/任务主键；当名称解析失败时会原样露出来。 */
export function isTarkovHexId(value: string): boolean {
  return TARKOV_HEX_ID_RE.test((value || "").trim());
}

/** 可展示的物品/钥匙名；ID 或空串不当名称。 */
export function tarkovReadableName(
  name: string | null | undefined,
  id?: string | null,
): string {
  const text = (name || "").trim();
  if (!text) return "";
  const ident = (id || "").trim();
  if (ident && text === ident) return "";
  if (isTarkovHexId(text)) return "";
  return text;
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
  return Boolean(slug && keys.has(slug));
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

function validPoints(
  rows: Array<{ x?: number | null; z?: number | null }> | null | undefined,
): RaidPrepPoint[] {
  const out: RaidPrepPoint[] = [];
  for (const row of rows || []) {
    if (!isFiniteNumber(row.x) || !isFiniteNumber(row.z)) continue;
    out.push({ x: row.x, z: row.z });
  }
  return out;
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

/** 单目标 required_keys；有则优先于任务级 needed_keys，避免把别的目标钥匙挂到本点。 */
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
    existing.count += item.count;
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

/** 当前地图任务详情 needed_keys，与任务页「所需钥匙」同源。 */
export function collectRaidPrepTaskKeys(
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
      });
      if (item) mergeNeededItem(index, out, item);
    }
  }
  return out;
}

/** 勾选任务在当前地图上要上交 / 要捡的物品（不含钥匙）。 */
export function collectRaidPrepTaskItems(
  task: RaidPrepTaskLike,
  mapSlug: string,
): RaidPrepNeededItem[] {
  const out: RaidPrepNeededItem[] = [];
  const index = new Map<string, RaidPrepNeededItem>();

  for (const obj of task.objectives || []) {
    if (!objectiveAppliesToMap(obj, mapSlug)) continue;
    const refs = obj.items || [];
    if (!refs.length) continue;
    const role = tarkovObjectiveTypeLabel(obj.type || "") || "物品";
    const count = objectiveItemCount(obj, refs.length);
    for (const ref of refs) {
      const item = namedRefItem(ref, {
        count,
        found_in_raid: Boolean(obj.found_in_raid),
        optional: Boolean(obj.optional),
        kind: "item",
        role,
      });
      if (item) mergeNeededItem(index, out, item);
    }
  }
  return out;
}

export function collectRaidPrepTaskTypes(
  task: RaidPrepTaskLike,
  mapSlug: string,
): string[] {
  const types: string[] = [];
  for (const obj of task.objectives || []) {
    if (!objectiveAppliesToMap(obj, mapSlug)) continue;
    const type = (obj.type || "").trim();
    if (type) types.push(type);
  }
  return orderObjectiveTypes(types);
}

export function buildRaidPrepSummary(
  tasks: RaidPrepTaskLike[],
  mapSlug: string,
): RaidPrepTaskSummary[] {
  return tasks.map((task) => {
    const items = collectRaidPrepTaskItems(task, mapSlug);
    const keys = collectRaidPrepTaskKeys(task, mapSlug);
    return {
      taskId: task.id,
      taskName: (task.name || "").trim() || task.id,
      traderSlug: (task.trader_slug || "").trim(),
      traderName: (task.trader_name || "").trim(),
      items,
      keys,
      types: collectRaidPrepTaskTypes(task, mapSlug),
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

export function buildRaidPrepOverlays(
  tasks: RaidPrepTaskLike[],
  mapSlug: string,
): TarkovRaidPrepOverlay[] {
  const keys = mapSlugKeys(mapSlug);
  const overlays: TarkovRaidPrepOverlay[] = [];
  for (const task of tasks) {
    const color = colorForTaskId(task.id);
    const taskName = (task.name || "").trim() || task.id;
    const traderSlug = (task.trader_slug || "").trim();
    const taskKeyNames = neededKeyNamesForMap(task, mapSlug);
    for (const obj of task.objectives || []) {
      const typeLabel = tarkovObjectiveTypeLabel(obj.type || "");
      const description = tarkovReadableName(obj.description, obj.id);
      const subtitle = [typeLabel, description].filter(Boolean).join(" · ");
      const optional = Boolean(obj.optional);
      const fromObj = objectiveKeyNames(obj);
      const keyNames = fromObj.length ? fromObj : taskKeyNames;
      let zoneIdx = 0;
      for (const zone of obj.zones || []) {
        if (!locationHitsMap(zone, keys)) continue;
        const outline = validPoints(zone.outline);
        const center =
          isFiniteNumber(zone.x) && isFiniteNumber(zone.z)
            ? [{ x: zone.x, z: zone.z }]
            : [];
        const polygon = outline.length >= 3 ? outline : [];
        const points = polygon.length ? center : [...center, ...outline];
        if (!polygon.length && !points.length) continue;
        overlays.push({
          key: `${task.id}:zone:${zone.id || zoneIdx}`,
          kind: "zone",
          color,
          title: taskName,
          subtitle,
          traderSlug,
          keyNames,
          optional,
          outline: polygon,
          points,
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
          kind: "spawn",
          color,
          title: taskName,
          subtitle: subtitle || "可能刷新点",
          traderSlug,
          keyNames,
          optional,
          outline: [],
          points: positions,
        });
        locIdx += 1;
      }
    }
  }
  return overlays;
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

function overlayLabelSeeds(row: TarkovRaidPrepOverlay): RaidPrepPoint[] {
  if (row.outline.length >= 3) {
    return row.points.length
      ? [centroidOf(row.points)]
      : [centroidOf(row.outline)];
  }
  return row.points;
}

type OverlayLabelSeed = RaidPrepPoint & {
  title: string;
  color: string;
  traderSlug: string;
  optional: boolean;
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
        title,
        color: row.color,
        traderSlug: (row.traderSlug || "").trim(),
        optional: row.optional,
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
    const byTitle = new Map<string, RaidPrepOverlayLabelItem>();
    for (const seed of group) {
      const bucket = `${seed.title}\0${seed.optional ? "1" : "0"}`;
      const item = byTitle.get(bucket);
      if (item) {
        item.count += 1;
        continue;
      }
      byTitle.set(bucket, {
        title: seed.title,
        color: seed.color,
        traderSlug: seed.traderSlug,
        count: 1,
        optional: seed.optional,
      });
    }
    const items = [...byTitle.values()].sort((a, b) => b.count - a.count);
    labels.push({ x: anchor.x, z: anchor.z, items });
  }
  labels.sort((a, b) => a.z - b.z || a.x - b.x);
  return labels;
}
