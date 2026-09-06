export const TARKOV_BOSS_GEAR_GROUPS = [
  {
    id: "wear",
    label: "穿着",
    keys: [
      "headwear",
      "face",
      "eyewear",
      "earpiece",
      "armor",
      "rig",
      "backpack",
    ],
  },
  {
    id: "arms",
    label: "武装",
    keys: ["gun", "pistol", "melee", "grenade"],
  },
  {
    id: "carry",
    label: "携带",
    keys: [
      "ammo",
      "meds",
      "provisions",
      "keys",
      "special",
      "container",
      "other",
    ],
  },
] as const;

export type BossGearSlotGroup<T> = {
  id: string;
  label: string;
  slots: T[];
};

export function groupBossGearSlots<T extends { key?: string | null }>(
  slots: readonly T[],
): BossGearSlotGroup<T>[] {
  const assigned = new Set<T>();
  const groups: BossGearSlotGroup<T>[] = [];
  for (const group of TARKOV_BOSS_GEAR_GROUPS) {
    const keySet = new Set<string>(group.keys);
    const hit = slots.filter((row) => keySet.has(String(row.key || "")));
    if (!hit.length) continue;
    hit.forEach((row) => assigned.add(row));
    groups.push({ id: group.id, label: group.label, slots: hit });
  }
  const rest = slots.filter((row) => !assigned.has(row));
  if (!rest.length) return groups;
  const carry = groups.find((row) => row.id === "carry");
  if (carry) {
    carry.slots.push(...rest);
    return groups;
  }
  groups.push({ id: "carry", label: "携带", slots: [...rest] });
  return groups;
}

export function bossGearItemLabel(
  item: {
    name?: string | null;
    short_name?: string | null;
    item_id?: string | null;
    count?: number | null;
  },
  compact = false,
): string {
  const full = (item.name || item.short_name || item.item_id || "").trim();
  const short = (item.short_name || full).trim();
  const text = compact ? short || full : full;
  const count = Number(item.count) || 1;
  return count > 1 ? `${count}× ${text}` : text;
}

export type BossGearContainedKind = "magazine" | "ammo" | "plate" | "other";

export function bossGearContainedKind(item: {
  kind?: string | null;
  types?: readonly string[] | null;
}): BossGearContainedKind {
  const kind = String(item.kind || "")
    .trim()
    .toLowerCase();
  if (kind === "magazine" || kind === "ammo" || kind === "plate") return kind;
  const types = new Set(
    (item.types || []).map((row) => String(row).trim().toLowerCase()),
  );
  if (types.has("ammo") || types.has("ammobox")) return "ammo";
  if (types.has("armorplate")) return "plate";
  return "other";
}

export function splitBossGearContains<
  T extends { kind?: string | null; types?: readonly string[] | null },
>(items: readonly T[]): {
  magazines: T[];
  ammo: T[];
  plates: T[];
  other: T[];
} {
  const magazines: T[] = [];
  const ammo: T[] = [];
  const plates: T[] = [];
  const other: T[] = [];
  for (const item of items) {
    const kind = bossGearContainedKind(item);
    if (kind === "magazine") magazines.push(item);
    else if (kind === "ammo") ammo.push(item);
    else if (kind === "plate") plates.push(item);
    else other.push(item);
  }
  return { magazines, ammo, plates, other };
}

function optionalInt(value: unknown): number | null {
  if (value == null || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

export type BossGearAmmoStats = {
  damage: number | null;
  penetration: number | null;
  armorDamage: number | null;
};

export function bossGearAmmoStats(item: {
  damage?: number | null;
  penetration?: number | null;
  armor_damage?: number | null;
}): BossGearAmmoStats {
  return {
    damage: optionalInt(item.damage),
    penetration: optionalInt(item.penetration),
    armorDamage: optionalInt(item.armor_damage),
  };
}
