export type GunsmithNamed = { id: string; name?: string };

export type GunsmithStatsSlice = {
  ergonomics?: number | null;
  recoil_vertical?: number | null;
  recoil_horizontal?: number | null;
  weight?: number | null;
  mag_capacity?: number | null;
  sighting_range?: number | null;
};

export type GunsmithSpec = {
  id: string;
  task_id: string;
  objective_id?: string | null;
  task_name: string;
  weapon_id: string;
  weapon_name?: string;
  weapon_image?: string;
  trader_name?: string;
  trader_slug?: string;
  constraints?: Record<string, number> | null;
  required_items?: GunsmithNamed[] | null;
  required_category_groups?: GunsmithNamed[][] | null;
  loadable?: boolean;
};

export type GunsmithLiveCheck = {
  ok: boolean;
  missingItemIds: string[];
  missingCategoryGroups: GunsmithNamed[][];
  unmetConstraints: string[];
  recoilSum: number;
};

const CONSTRAINT_LABELS: Record<string, string> = {
  min_ergonomics: "人机",
  max_recoil_sum: "后坐和",
  max_weight: "重量",
  min_mag_capacity: "弹匣容量",
  max_mag_capacity: "弹匣容量",
  min_sighting_range: "瞄准距离",
  min_durability: "耐久",
  max_width: "格仓宽",
  max_height: "格仓高",
  min_width: "格仓宽",
  min_height: "格仓高",
};

const CONSTRAINT_ORDER = [
  "min_durability",
  "min_ergonomics",
  "max_recoil_sum",
  "max_weight",
  "min_mag_capacity",
  "max_mag_capacity",
  "min_sighting_range",
  "max_width",
  "max_height",
] as const;

const LIVE_CONSTRAINTS = new Set([
  "min_ergonomics",
  "max_recoil_sum",
  "max_weight",
  "min_mag_capacity",
  "max_mag_capacity",
  "min_sighting_range",
]);

export function isGunsmithObjectiveType(type: string | null | undefined): boolean {
  return (type || "").trim() === "buildWeapon";
}

export function isGunsmithTask(types: readonly string[] | null | undefined): boolean {
  return (types || []).some((type) => isGunsmithObjectiveType(type));
}

export function gunsmithConstraintLabel(key: string): string {
  return CONSTRAINT_LABELS[key] || key;
}

export function isGunsmithConstraintLive(key: string): boolean {
  return LIVE_CONSTRAINTS.has(key);
}

export function orderedGunsmithConstraints(
  constraints: Record<string, number> | null | undefined,
): Array<[string, number]> {
  const rows = Object.entries(constraints || {}).filter(
    (entry): entry is [string, number] => entry[1] != null,
  );
  const rank = new Map(CONSTRAINT_ORDER.map((key, index) => [key, index]));
  rows.sort((a, b) => {
    const left = rank.get(a[0] as (typeof CONSTRAINT_ORDER)[number]);
    const right = rank.get(b[0] as (typeof CONSTRAINT_ORDER)[number]);
    if (left == null && right == null) return a[0].localeCompare(b[0]);
    if (left == null) return 1;
    if (right == null) return -1;
    return left - right;
  });
  return rows;
}

export function formatGunsmithConstraint(key: string, value: number): string {
  const label = gunsmithConstraintLabel(key);
  const shown =
    key === "min_durability"
      ? `${value}%`
      : Number.isInteger(value)
        ? String(value)
        : String(value);
  if (key.startsWith("min_")) return `${label} ≥ ${shown}`;
  if (key.startsWith("max_")) return `${label} ≤ ${shown}`;
  return `${label} ${shown}`;
}

export function categoryGroupKey(group: readonly GunsmithNamed[]): string {
  return group.map((row) => row.id).join("\0");
}

export function collectInstalledCategoryIds(
  parts: Array<{ category_ids?: readonly string[] | null }>,
): string[] {
  const out: string[] = [];
  for (const part of parts) {
    for (const id of part.category_ids || []) {
      if (id) out.push(id);
    }
  }
  return out;
}

export function findGunsmithSpec(
  items: readonly GunsmithSpec[] | null | undefined,
  taskId: string,
  objectiveId?: string | null,
): GunsmithSpec | null {
  const tid = taskId.trim();
  const oid = (objectiveId || "").trim();
  if (!tid) return null;
  const rows = (items || []).filter((row) => row.task_id === tid);
  if (!rows.length) return null;
  if (oid) return rows.find((row) => row.objective_id === oid) || rows[0];
  return rows[0];
}

export function gunsmithLiveCheck(
  spec: GunsmithSpec | null | undefined,
  stats: GunsmithStatsSlice | null | undefined,
  installedIds: readonly string[],
  installedCategoryIds: readonly string[] = [],
): GunsmithLiveCheck | null {
  if (!spec) return null;
  const have = new Set(installedIds.filter(Boolean));
  const cats = new Set(installedCategoryIds.filter(Boolean));
  const missingItemIds = (spec.required_items || [])
    .map((row) => row.id)
    .filter((id) => id && !have.has(id));
  const missingCategoryGroups = (spec.required_category_groups || []).filter(
    (group) => {
      const ids = group.map((row) => row.id).filter(Boolean);
      return ids.length > 0 && !ids.some((id) => cats.has(id));
    },
  );
  const recoilSum =
    (stats?.recoil_vertical || 0) + (stats?.recoil_horizontal || 0);
  const unmetConstraints: string[] = [];
  const constraints = spec.constraints || {};
  const minErgo = constraints.min_ergonomics;
  if (minErgo != null && (stats?.ergonomics || 0) < minErgo) {
    unmetConstraints.push("min_ergonomics");
  }
  const maxRecoil = constraints.max_recoil_sum;
  if (maxRecoil != null && recoilSum > maxRecoil) {
    unmetConstraints.push("max_recoil_sum");
  }
  const maxWeight = constraints.max_weight;
  if (maxWeight != null && (stats?.weight || 0) > maxWeight) {
    unmetConstraints.push("max_weight");
  }
  const minMag = constraints.min_mag_capacity;
  if (minMag != null && (stats?.mag_capacity || 0) < minMag) {
    unmetConstraints.push("min_mag_capacity");
  }
  const maxMag = constraints.max_mag_capacity;
  if (maxMag != null) {
    const mag = stats?.mag_capacity || 0;
    if (mag <= 0 || mag > maxMag) unmetConstraints.push("max_mag_capacity");
  }
  const minSight = constraints.min_sighting_range;
  if (minSight != null && (stats?.sighting_range || 0) < minSight) {
    unmetConstraints.push("min_sighting_range");
  }
  return {
    ok:
      missingItemIds.length === 0 &&
      missingCategoryGroups.length === 0 &&
      unmetConstraints.length === 0,
    missingItemIds,
    missingCategoryGroups,
    unmetConstraints,
    recoilSum,
  };
}
