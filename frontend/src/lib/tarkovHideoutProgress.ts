/** 藏身处规划器：仓库默认 1（蓝边 4）、设施前置、降级级联。 */

import { guideItemFleaCost, type TarkovGuideItemRef } from "./tarkovGuideItemCost";

export const TARKOV_HIDEOUT_STASH_SLUG = "stash";
export const TARKOV_STASH_FLOOR_STANDARD = 1;
export const TARKOV_STASH_FLOOR_EOD = 4;

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
  short_name?: string;
  icon_link?: string;
  types?: string[] | null;
  count?: number;
  found_in_raid?: boolean;
  flea_price?: number | null;
};

export type HideoutBonus = {
  type?: string;
  name?: string;
  value?: number;
  skill?: string;
  skill_id?: string;
  slot_items?: HideoutItemReq[];
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
  bonuses?: HideoutBonus[];
};

export type HideoutStationSpec = {
  id?: string;
  slug?: string;
  name?: string;
  image_link?: string;
  levels?: HideoutLevelSpec[];
};

export function hideoutDefaultLevel(
  station: HideoutStationSpec | undefined,
  stashFloor = TARKOV_STASH_FLOOR_STANDARD,
): number {
  if ((station?.slug || "").trim().toLowerCase() !== TARKOV_HIDEOUT_STASH_SLUG) {
    return 0;
  }
  const high = Math.max(hideoutMaxLevel(station), 1);
  const floor = Math.trunc(Number(stashFloor));
  if (!Number.isFinite(floor)) return TARKOV_STASH_FLOOR_STANDARD;
  return Math.min(Math.max(floor, 1), high);
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
  stashFloor = TARKOV_STASH_FLOOR_STANDARD,
): number {
  const low = hideoutDefaultLevel(station, stashFloor);
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
  stashFloor = TARKOV_STASH_FLOOR_STANDARD,
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const station of stations || []) {
    const ident = (station.id || "").trim();
    if (!ident) continue;
    if (stored && Object.prototype.hasOwnProperty.call(stored, ident)) {
      out[ident] = clampHideoutLevel(station, stored[ident], stashFloor);
    } else {
      out[ident] = hideoutDefaultLevel(station, stashFloor);
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
  stashFloor = TARKOV_STASH_FLOOR_STANDARD,
): boolean {
  for (const req of spec?.station_requirements || []) {
    const otherId = (req.station_id || "").trim();
    if (!otherId) continue;
    const need = Number(req.level || 0);
    const have =
      levels[otherId] ?? hideoutDefaultLevel(byId.get(otherId), stashFloor);
    if (have < need) return false;
  }
  return true;
}

export function canSetHideoutLevel(
  station: HideoutStationSpec | undefined,
  target: number,
  levels: Record<string, number>,
  byId: Map<string, HideoutStationSpec>,
  stashFloor = TARKOV_STASH_FLOOR_STANDARD,
): boolean {
  if (!station) return false;
  const low = hideoutDefaultLevel(station, stashFloor);
  const high = hideoutMaxLevel(station);
  if (target < low || target > high) return false;
  if (target === low) return true;
  const spec = hideoutLevelSpec(station, target);
  if (!spec) return false;
  return stationPrereqsMet(spec, levels, byId, stashFloor);
}

export type HideoutStationPartition<T extends HideoutStationSpec> = {
  ready: T[];
  blocked: T[];
  maxed: T[];
};

/** 按设施前置拆成可升 / 前置未满足 / 已满级，组内保持目录顺序。 */
export function partitionHideoutStations<T extends HideoutStationSpec>(
  stations: T[] | undefined,
  levels: Record<string, number>,
  byId: Map<string, HideoutStationSpec>,
  stashFloor = TARKOV_STASH_FLOOR_STANDARD,
): HideoutStationPartition<T> {
  const ready: T[] = [];
  const blocked: T[] = [];
  const maxed: T[] = [];
  for (const station of stations || []) {
    const ident = (station.id || "").trim();
    const current = levels[ident] ?? hideoutDefaultLevel(station, stashFloor);
    if (canSetHideoutLevel(station, current + 1, levels, byId, stashFloor)) {
      ready.push(station);
    } else if (current >= hideoutMaxLevel(station)) {
      maxed.push(station);
    } else {
      blocked.push(station);
    }
  }
  return { ready, blocked, maxed };
}

function cascadeHideoutLevels(
  levels: Record<string, number>,
  byId: Map<string, HideoutStationSpec>,
  stashFloor = TARKOV_STASH_FLOOR_STANDARD,
): Record<string, number> {
  let changed = true;
  while (changed) {
    changed = false;
    for (const [ident, station] of byId) {
      let current = levels[ident] ?? hideoutDefaultLevel(station, stashFloor);
      const low = hideoutDefaultLevel(station, stashFloor);
      while (current > low) {
        const spec = hideoutLevelSpec(station, current);
        if (spec && stationPrereqsMet(spec, levels, byId, stashFloor)) break;
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
  stashFloor = TARKOV_STASH_FLOOR_STANDARD,
): Record<string, number> {
  const ident = stationId.trim();
  const byId = indexHideoutStations(stations);
  const station = byId.get(ident);
  if (!station) throw new Error("未找到藏身处模块");
  const current = filledHideoutLevels(stations, stored, stashFloor);
  const want = clampHideoutLevel(station, target, stashFloor);
  const now = current[ident] ?? hideoutDefaultLevel(station, stashFloor);
  if (want === now) return current;
  if (want > now) {
    if (want !== now + 1) throw new Error("只能逐级升级");
    if (!canSetHideoutLevel(station, want, current, byId, stashFloor)) {
      throw new Error("升级前置未满足");
    }
    current[ident] = want;
    return current;
  }
  if (want !== now - 1) throw new Error("只能逐级降级");
  current[ident] = want;
  return cascadeHideoutLevels(current, byId, stashFloor);
}

export function hideoutReqStatus(met: boolean | null | undefined): HideoutReqStatus {
  if (met == null) return "unset";
  return met ? "met" : "unmet";
}

export function stationReqMet(
  req: HideoutStationReq,
  levels: Record<string, number>,
  byId: Map<string, HideoutStationSpec>,
  stashFloor = TARKOV_STASH_FLOOR_STANDARD,
): boolean {
  const otherId = (req.station_id || "").trim();
  const need = Number(req.level || 0);
  const have =
    levels[otherId] ?? hideoutDefaultLevel(byId.get(otherId), stashFloor);
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
  const have =
    (ident ? traderLevels[ident] : undefined) ??
    (slug ? traderLevels[slug] : undefined);
  if (have == null) return null;
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

export function formatHideoutBonusCell(
  type: string,
  value: number | null | undefined,
): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return formatHideoutBonusValue(type, value);
}

export type HideoutBonusTableRow = {
  key: string;
  type: string;
  name: string;
  skill?: string;
  values: Array<number | null>;
  slot_items?: HideoutItemReq[];
};

export function hideoutBonusRowKey(bonus: HideoutBonus): string {
  const type = (bonus.type || "").trim();
  const name = (bonus.name || "").trim();
  const ident = type || name;
  if (!ident) return "";
  const skill = (bonus.skill_id || bonus.skill || "").trim();
  return skill ? `${ident}\0${skill}` : ident;
}

export function hideoutBonusLabel(
  row: Pick<HideoutBonusTableRow, "name" | "type" | "skill">,
): string {
  const name = (row.name || row.type || "").trim();
  const skill = (row.skill || "").trim();
  if (skill && !name.includes(skill)) return `${name}（${skill}）`;
  return name;
}

function hideoutBonusLevels(station: HideoutStationSpec | undefined): number[] {
  const seen = new Set<number>();
  const out: number[] = [];
  for (const spec of station?.levels || []) {
    const level = Number(spec.level || 0);
    if (!Number.isFinite(level) || level <= 0 || seen.has(level)) continue;
    seen.add(level);
    out.push(level);
  }
  out.sort((a, b) => a - b);
  return out;
}

/**
 * 设施各等级效果表：行是加成（类型+技能），列是等级。
 * dump 只在声明该加成的等级上给值；未再声明的更高等级沿用上次（达到该级时仍有效）。
 */
export function buildHideoutBonusTable(
  station: HideoutStationSpec | undefined,
): { levels: number[]; rows: HideoutBonusTableRow[] } {
  const levels = hideoutBonusLevels(station);
  const byLevel = new Map<number, HideoutBonus[]>();
  for (const spec of station?.levels || []) {
    const level = Number(spec.level || 0);
    if (!levels.includes(level)) continue;
    byLevel.set(level, spec.bonuses || []);
  }
  const order: string[] = [];
  const meta = new Map<
    string,
    { type: string; name: string; skill?: string; slot_items?: HideoutItemReq[] }
  >();
  const declared = new Map<string, Map<number, number>>();
  for (const level of levels) {
    for (const bonus of byLevel.get(level) || []) {
      const key = hideoutBonusRowKey(bonus);
      if (!key) continue;
      if (!meta.has(key)) {
        order.push(key);
        meta.set(key, {
          type: (bonus.type || "").trim(),
          name: (bonus.name || bonus.type || "").trim(),
          skill: (bonus.skill || "").trim() || undefined,
          slot_items: bonus.slot_items,
        });
      } else {
        const row = meta.get(key);
        if (row && !row.slot_items?.length && bonus.slot_items?.length) {
          row.slot_items = bonus.slot_items;
        }
        if (row && !row.name && bonus.name) row.name = bonus.name;
      }
      const raw = Number(bonus.value);
      const value = Number.isFinite(raw) ? raw : 0;
      let atLevel = declared.get(key);
      if (!atLevel) {
        atLevel = new Map();
        declared.set(key, atLevel);
      }
      atLevel.set(level, value);
    }
  }
  const rows: HideoutBonusTableRow[] = order.map((key) => {
    const info = meta.get(key);
    const atLevel = declared.get(key);
    let last: number | null = null;
    const values = levels.map((level) => {
      if (atLevel?.has(level)) last = atLevel.get(level) ?? null;
      return last;
    });
    return {
      key,
      type: info?.type || "",
      name: info?.name || "",
      skill: info?.skill,
      values,
      slot_items: info?.slot_items,
    };
  });
  return { levels, rows };
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

export type HideoutUpgradeStationRef = {
  id: string;
  name: string;
  slug: string;
  level: number;
  from?: number;
  to?: number;
};

export type HideoutUpgradeItemNeed = HideoutItemReq & {
  id: string;
  count: number;
  found_in_raid: boolean;
  stations: HideoutUpgradeStationRef[];
};

export type HideoutUpgradeRange = {
  stationId: string;
  from: number;
  to: number;
};

export function hideoutUpgradeItemKey(
  item: Pick<HideoutItemReq, "id" | "found_in_raid">,
): string | null {
  const ident = (item.id || "").trim();
  if (!ident) return null;
  return `${ident}\0${item.found_in_raid ? "1" : "0"}`;
}

export function formatHideoutUpgradeStation(ref: HideoutUpgradeStationRef): string {
  if (ref.from != null && ref.to != null && ref.from !== ref.to) {
    return `${ref.name} ${ref.from}→${ref.to}`;
  }
  return `${ref.name} Lv.${ref.level}`;
}

/** 计算器用图鉴下限：仓库从 1 级起，其它设施从 0。不看版本/当前进度。 */
export function hideoutCatalogMinLevel(
  station: HideoutStationSpec | undefined,
): number {
  if ((station?.slug || "").trim().toLowerCase() === TARKOV_HIDEOUT_STASH_SLUG) {
    return 1;
  }
  return 0;
}

function clampHideoutCatalogLevel(
  station: HideoutStationSpec | undefined,
  raw: unknown,
): number {
  const low = hideoutCatalogMinLevel(station);
  const high = Math.max(hideoutMaxLevel(station), low);
  const value = Number(raw);
  if (!Number.isFinite(value)) return low;
  return Math.min(Math.max(Math.trunc(value), low), high);
}

export function hideoutLevelChoices(
  station: HideoutStationSpec | undefined,
): number[] {
  const low = hideoutCatalogMinLevel(station);
  const high = Math.max(hideoutMaxLevel(station), low);
  const out: number[] = [];
  for (let level = low; level <= high; level += 1) out.push(level);
  return out;
}

export function clampHideoutUpgradeRange(
  station: HideoutStationSpec | undefined,
  fromRaw: unknown,
  toRaw: unknown,
): { from: number; to: number } {
  return {
    from: clampHideoutCatalogLevel(station, fromRaw),
    to: clampHideoutCatalogLevel(station, toRaw),
  };
}

export function defaultHideoutCalcRange(
  station: HideoutStationSpec | undefined,
): { from: number; to: number } {
  const low = hideoutCatalogMinLevel(station);
  const high = Math.max(hideoutMaxLevel(station), low);
  if (high > low) return { from: low, to: low + 1 };
  return { from: low, to: high };
}

function hideoutItemReqCount(raw: unknown): number {
  const value = Number(raw);
  if (!Number.isFinite(value) || value <= 0) return 1;
  return Math.trunc(value);
}

function hideoutStationLabel(station: HideoutStationSpec, ident: string): string {
  return (station.name || station.slug || ident).trim() || ident;
}

function hideoutUpgradeStationSame(
  a: HideoutUpgradeStationRef,
  b: HideoutUpgradeStationRef,
): boolean {
  return (
    a.id === b.id &&
    a.level === b.level &&
    (a.from ?? -1) === (b.from ?? -1) &&
    (a.to ?? -1) === (b.to ?? -1)
  );
}

function mergeHideoutUpgradeItem(
  merged: Map<string, HideoutUpgradeItemNeed>,
  req: HideoutItemReq,
  stationRef: HideoutUpgradeStationRef,
): void {
  const key = hideoutUpgradeItemKey(req);
  if (!key) return;
  const add = hideoutItemReqCount(req.count);
  const existing = merged.get(key);
  if (existing) {
    existing.count += add;
    if (!existing.stations.some((row) => hideoutUpgradeStationSame(row, stationRef))) {
      existing.stations.push(stationRef);
    }
    if (!existing.name && req.name) existing.name = req.name;
    if (!existing.short_name && req.short_name) existing.short_name = req.short_name;
    if (!existing.icon_link && req.icon_link) existing.icon_link = req.icon_link;
    if (!existing.types?.length && req.types?.length) existing.types = req.types;
    if (existing.flea_price == null && req.flea_price != null) {
      existing.flea_price = req.flea_price;
    }
    return;
  }
  merged.set(key, {
    id: (req.id || "").trim(),
    name: req.name,
    short_name: req.short_name,
    icon_link: req.icon_link,
    types: req.types,
    count: add,
    found_in_raid: Boolean(req.found_in_raid),
    flea_price: req.flea_price,
    stations: [stationRef],
  });
}

function sortedHideoutUpgradeNeeds(
  merged: Map<string, HideoutUpgradeItemNeed>,
): HideoutUpgradeItemNeed[] {
  return [...merged.values()].sort((a, b) => {
    const byName = (a.name || a.short_name || a.id).localeCompare(
      b.name || b.short_name || b.id,
      "zh-CN",
    );
    if (byName) return byName;
    return Number(a.found_in_raid) - Number(b.found_in_raid);
  });
}

function hideoutStationRef(
  station: HideoutStationSpec,
  ident: string,
  level: number,
  range?: { from: number; to: number },
): HideoutUpgradeStationRef {
  return {
    id: ident,
    name: hideoutStationLabel(station, ident),
    slug: (station.slug || ident).trim(),
    level,
    ...(range ? { from: range.from, to: range.to } : {}),
  };
}

/** 可升级设施「下一级」材料按物品+战局内合并，组内保持名称序。 */
export function aggregateReadyHideoutUpgradeItems(
  ready: HideoutStationSpec[] | undefined,
  levels: Record<string, number>,
  stashFloor = TARKOV_STASH_FLOOR_STANDARD,
): HideoutUpgradeItemNeed[] {
  const merged = new Map<string, HideoutUpgradeItemNeed>();
  for (const station of ready || []) {
    const ident = (station.id || "").trim();
    if (!ident) continue;
    const current = levels[ident] ?? hideoutDefaultLevel(station, stashFloor);
    const next = nextHideoutLevelSpec(station, current);
    if (!next) continue;
    const targetLevel = Number(next.level || current + 1);
    const stationRef = hideoutStationRef(
      station,
      ident,
      Number.isFinite(targetLevel) ? targetLevel : current + 1,
    );
    for (const req of next.item_requirements || []) {
      mergeHideoutUpgradeItem(merged, req, stationRef);
    }
  }
  return sortedHideoutUpgradeNeeds(merged);
}

/** 多条「从 N 升到 M」按级累加材料；from ≥ to 的行不计。 */
export function aggregateHideoutUpgradeRanges(
  stations: HideoutStationSpec[] | undefined,
  ranges: HideoutUpgradeRange[] | undefined,
): HideoutUpgradeItemNeed[] {
  const byId = indexHideoutStations(stations);
  const merged = new Map<string, HideoutUpgradeItemNeed>();
  for (const range of ranges || []) {
    const ident = (range.stationId || "").trim();
    if (!ident) continue;
    const station = byId.get(ident);
    if (!station) continue;
    const { from, to } = clampHideoutUpgradeRange(station, range.from, range.to);
    if (from >= to) continue;
    const stationRef = hideoutStationRef(station, ident, to, { from, to });
    for (let level = from + 1; level <= to; level += 1) {
      const spec = hideoutLevelSpec(station, level);
      for (const req of spec?.item_requirements || []) {
        mergeHideoutUpgradeItem(merged, req, stationRef);
      }
    }
  }
  return sortedHideoutUpgradeNeeds(merged);
}

/** json.tarkov.dev 卢布物品 id，与 dump 里建造费条目一致。 */
export const TARKOV_ROUBLE_ITEM_ID = "5449016a4bdc2d6f028b456f";

export function isHideoutMoneyItem(
  item: Pick<HideoutItemReq, "id" | "types">,
): boolean {
  const ident = (item.id || "").trim();
  if (
    ident === TARKOV_ROUBLE_ITEM_ID
    || ident === "5696686a4bdc2da3298b456a"
    || ident === "569668774bdc2da2298b4568"
  ) {
    return true;
  }
  return (item.types || []).includes("money");
}

/** 战局内材料买不到跳蚤成品，建造费货币也不是跳蚤购物。 */
export function hideoutItemNeedsFleaBuy(
  item: Pick<HideoutItemReq, "id" | "types" | "found_in_raid">,
): boolean {
  if (item.found_in_raid) return false;
  return !isHideoutMoneyItem(item);
}

/**
 * 材料清单：dump 里的建造费货币置顶。跳蚤估价不是进游戏点升级要交的钱，不并进卢布。
 */
export function hideoutUpgradeMaterialItems<T extends HideoutItemReq>(
  items: T[] | undefined,
): T[] {
  const rows = items || [];
  if (!rows.length) return [];
  const money: T[] = [];
  const others: T[] = [];
  for (const row of rows) {
    if (isHideoutMoneyItem(row)) money.push(row);
    else others.push(row);
  }
  return [...money, ...others];
}

/** 物资跳蚤买入合计，不含建造费货币和战局内材料。 */
export function hideoutUpgradeFleaCost(
  items: HideoutItemReq[] | undefined,
): number | null {
  const goods = (items || []).filter(hideoutItemNeedsFleaBuy);
  return guideItemFleaCost(goods as TarkovGuideItemRef[]);
}
