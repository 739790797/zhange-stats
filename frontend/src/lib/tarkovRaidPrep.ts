import { TARKOV_MAPS } from "@/lib/tarkovHomeNav";
import { tarkovObjectiveTypeLabel } from "@/lib/tarkovTaskObjective";

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

/** 战局准备默认展示的目标类型（可再并上当前列表里出现的 type）。 */
export const RAID_PREP_TYPE_FILTERS = [
  "shoot",
  "findItem",
  "findQuestItem",
  "plantItem",
  "plantQuestItem",
  "mark",
  "visit",
  "useItem",
  "extract",
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
  outline: RaidPrepPoint[];
  points: RaidPrepPoint[];
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

export type RaidPrepObjectiveLike = {
  id?: string | null;
  type?: string | null;
  description?: string | null;
  zones?: ZoneLike[] | null;
  possible_locations?: PossibleLocationLike[] | null;
  zone_names?: string[] | null;
};

export type RaidPrepTaskLike = {
  id: string;
  name?: string | null;
  objectives?: RaidPrepObjectiveLike[] | null;
  needed_keys?: Array<{
    map?: { slug?: string | null } | null;
    keys?: Array<{ name?: string | null }> | null;
  }> | null;
};

function isFiniteNumber(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
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
      const name = (key.name || "").trim();
      if (!name || seen.has(name)) continue;
      seen.add(name);
      out.push(name);
    }
  }
  return out;
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
    for (const obj of task.objectives || []) {
      const typeLabel = tarkovObjectiveTypeLabel(obj.type || "");
      const description = (obj.description || "").trim();
      const subtitle = [typeLabel, description].filter(Boolean).join(" · ");
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
          outline: [],
          points: positions,
        });
        locIdx += 1;
      }
    }
  }
  return overlays;
}
