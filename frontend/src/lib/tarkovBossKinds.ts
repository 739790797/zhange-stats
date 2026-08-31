export const TARKOV_BOSS_KINDS = ["boss", "elite", "soldier"] as const;

export type TarkovBossKind = (typeof TARKOV_BOSS_KINDS)[number];

export const TARKOV_BOSS_KIND_LABELS: Record<TarkovBossKind, string> = {
  boss: "Boss",
  elite: "Elite",
  soldier: "Soldier",
};

export function normalizeBossKind(
  raw: string | undefined | null,
): TarkovBossKind {
  const key = String(raw || "")
    .trim()
    .toLowerCase();
  if (key === "elite" || key === "soldier") return key;
  return "boss";
}

export function isCatalogBossKind(kind: string | undefined | null): boolean {
  const key = normalizeBossKind(kind);
  return key === "boss" || key === "elite";
}

export function filterCatalogBosses<T extends { kind?: string | null }>(
  items: readonly T[],
): T[] {
  return items.filter((item) => isCatalogBossKind(item.kind));
}

export function groupBossesByKind<T extends { kind?: string | null }>(
  items: readonly T[],
): Record<TarkovBossKind, T[]> {
  const out: Record<TarkovBossKind, T[]> = {
    boss: [],
    elite: [],
    soldier: [],
  };
  for (const item of items) {
    out[normalizeBossKind(item.kind)].push(item);
  }
  return out;
}
