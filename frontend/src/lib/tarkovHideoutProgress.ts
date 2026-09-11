/** 藏身处规划器：仓库默认 1、设施前置、降级级联。 */

export const TARKOV_HIDEOUT_STASH_SLUG = "stash";

export type HideoutReqStatus = "met" | "unmet" | "unset";

export type HideoutStationReq = {
  station_id?: string;
  station_slug?: string;
  station_name?: string;
  level?: number;
};

export type HideoutTraderReq = {
  id?: string;
  slug?: string;
  name?: string;
  level?: number;
};

export type HideoutSkillReq = {
  skill?: string;
  skill_id?: string;
  level?: number;
};

export type HideoutItemReq = {
  id?: string;
  name?: string;
  icon_link?: string;
  count?: number;
  found_in_raid?: boolean;
};

export type HideoutLevelSpec = {
  id?: string;
  level?: number;
  construction_time?: number;
  description?: string;
  item_requirements?: HideoutItemReq[];
  station_requirements?: HideoutStationReq[];
  trader_requirements?: HideoutTraderReq[];
  skill_requirements?: HideoutSkillReq[];
  bonuses?: Array<{ type?: string; name?: string; value?: number }>;
};

export type HideoutStationSpec = {
  id?: string;
  slug?: string;
  name?: string;
  image_link?: string;
  levels?: HideoutLevelSpec[];
};

export type HideoutUserContext = {
  traderLevels?: Record<string, number>;
  skillLevels?: Record<string, number>;
  itemCounts?: Record<string, number>;
};

export function hideoutDefaultLevel(station: HideoutStationSpec | undefined): number {
  return (station?.slug || "").trim().toLowerCase() === TARKOV_HIDEOUT_STASH_SLUG
    ? 1
    : 0;
}

export function hideoutMaxLevel(station: HideoutStationSpec | undefined): number {
  let highest = 0;
  for (const row of station?.levels || []) {
    const level = Number(row.level || 0);
    if (Number.isFinite(level)) highest = Math.max(highest, level);
  }
  return highest;
}

export function clampHideoutLevel(
  station: HideoutStationSpec | undefined,
  raw: unknown,
): number {
  const low = hideoutDefaultLevel(station);
  const high = Math.max(hideoutMaxLevel(station), low);
  const value = Number(raw);
  if (!Number.isFinite(value)) return low;
  return Math.min(Math.max(Math.trunc(value), low), high);
}

export function indexHideoutStations(
  stations: HideoutStationSpec[] | undefined,
): Map<string, HideoutStationSpec> {
  const out = new Map<string, HideoutStationSpec>();
  for (const row of stations || []) {
    const ident = (row.id || "").trim();
    if (ident) out.set(ident, row);
  }
  return out;
}

export function filledHideoutLevels(
  stations: HideoutStationSpec[] | undefined,
  stored: Record<string, number> | undefined,
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const station of stations || []) {
    const ident = (station.id || "").trim();
    if (!ident) continue;
    if (stored && Object.prototype.hasOwnProperty.call(stored, ident)) {
      out[ident] = clampHideoutLevel(station, stored[ident]);
    } else {
      out[ident] = hideoutDefaultLevel(station);
    }
  }
  return out;
}

export function hideoutLevelSpec(
  station: HideoutStationSpec | undefined,
  level: number,
): HideoutLevelSpec | undefined {
  return (station?.levels || []).find((row) => Number(row.level || 0) === level);
}

export function stationPrereqsMet(
  spec: HideoutLevelSpec | undefined,
  levels: Record<string, number>,
  byId: Map<string, HideoutStationSpec>,
): boolean {
  for (const req of spec?.station_requirements || []) {
    const otherId = (req.station_id || "").trim();
    if (!otherId) continue;
    const need = Number(req.level || 0);
    const have =
      levels[otherId] ?? hideoutDefaultLevel(byId.get(otherId));
    if (have < need) return false;
  }
  return true;
}

export function canSetHideoutLevel(
  station: HideoutStationSpec | undefined,
  target: number,
  levels: Record<string, number>,
  byId: Map<string, HideoutStationSpec>,
): boolean {
  if (!station) return false;
  const low = hideoutDefaultLevel(station);
  const high = hideoutMaxLevel(station);
  if (target < low || target > high) return false;
  if (target === low) return true;
  const spec = hideoutLevelSpec(station, target);
  if (!spec) return false;
  return stationPrereqsMet(spec, levels, byId);
}

function cascadeHideoutLevels(
  levels: Record<string, number>,
  byId: Map<string, HideoutStationSpec>,
): Record<string, number> {
  let changed = true;
  while (changed) {
    changed = false;
    for (const [ident, station] of byId) {
      let current = levels[ident] ?? hideoutDefaultLevel(station);
      const low = hideoutDefaultLevel(station);
      while (current > low) {
        const spec = hideoutLevelSpec(station, current);
        if (spec && stationPrereqsMet(spec, levels, byId)) break;
        current -= 1;
        changed = true;
      }
      if (levels[ident] !== current) {
        levels[ident] = current;
        changed = true;
      }
    }
  }
  return levels;
}

export function applyHideoutLevel(
  stations: HideoutStationSpec[] | undefined,
  stored: Record<string, number> | undefined,
  stationId: string,
  target: number,
): Record<string, number> {
  const ident = stationId.trim();
  const byId = indexHideoutStations(stations);
  const station = byId.get(ident);
  if (!station) throw new Error("未找到藏身处模块");
  const current = filledHideoutLevels(stations, stored);
  const want = clampHideoutLevel(station, target);
  const now = current[ident] ?? hideoutDefaultLevel(station);
  if (want === now) return current;
  if (want > now) {
    if (want !== now + 1) throw new Error("只能逐级升级");
    if (!canSetHideoutLevel(station, want, current, byId)) {
      throw new Error("升级前置未满足");
    }
    current[ident] = want;
    return current;
  }
  if (want !== now - 1) throw new Error("只能逐级降级");
  current[ident] = want;
  return cascadeHideoutLevels(current, byId);
}

export function hideoutReqStatus(met: boolean | null | undefined): HideoutReqStatus {
  if (met == null) return "unset";
  return met ? "met" : "unmet";
}

export function stationReqMet(
  req: HideoutStationReq,
  levels: Record<string, number>,
  byId: Map<string, HideoutStationSpec>,
): boolean {
  const otherId = (req.station_id || "").trim();
  const need = Number(req.level || 0);
  const have = levels[otherId] ?? hideoutDefaultLevel(byId.get(otherId));
  return have >= need;
}

export function traderReqMet(
  req: HideoutTraderReq,
  traderLevels: Record<string, number> | undefined,
): boolean | null {
  if (!traderLevels) return null;
  const ident = (req.id || "").trim();
  const slug = (req.slug || "").trim().toLowerCase();
  const need = Number(req.level || 0);
  const have = traderLevels[ident] ?? (slug ? traderLevels[slug] : undefined);
  if (have == null) return false;
  return have >= need;
}

export function skillReqMet(
  req: HideoutSkillReq,
  skillLevels: Record<string, number> | undefined,
): boolean | null {
  if (!skillLevels) return null;
  const ident = (req.skill_id || req.skill || "").trim();
  const need = Number(req.level || 0);
  const have = skillLevels[ident];
  if (have == null) return false;
  return have >= need;
}

export function itemReqMet(
  req: HideoutItemReq,
  itemCounts: Record<string, number> | undefined,
): boolean | null {
  if (!itemCounts) return null;
  const ident = (req.id || "").trim();
  const need = Number(req.count ?? 1);
  const have = itemCounts[ident];
  if (have == null) return false;
  return have >= need;
}

const UNLOCK_TYPES = new Set([
  "UnlockArmorRepair",
  "UnlockWeaponRepair",
  "UnlockWeaponModification",
]);
const COUNT_TYPES = new Set([
  "StashSize",
  "AdditionalSlots",
  "MaximumEnergyReserve",
]);

export function formatHideoutBonusValue(type: string, value: number): string {
  if (UNLOCK_TYPES.has(type)) return "解锁";
  if (COUNT_TYPES.has(type)) {
    const n = Number.isInteger(value) ? String(value) : String(value);
    return `+${n}`;
  }
  const pct = Math.round(value * 100);
  if (pct === 0 && value === 0) return "0%";
  return `${pct > 0 ? "+" : ""}${pct}%`;
}

export function hideoutLevelsFromRows(
  rows: Array<{ station_id?: string; level?: number }> | undefined,
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const row of rows || []) {
    const ident = (row.station_id || "").trim();
    if (!ident) continue;
    out[ident] = Number(row.level || 0);
  }
  return out;
}

export function nextHideoutLevelSpec(
  station: HideoutStationSpec | undefined,
  current: number,
): HideoutLevelSpec | undefined {
  return hideoutLevelSpec(station, current + 1);
}

export function currentHideoutLevelSpec(
  station: HideoutStationSpec | undefined,
  current: number,
): HideoutLevelSpec | undefined {
  if (current <= 0) return undefined;
  return hideoutLevelSpec(station, current);
}
