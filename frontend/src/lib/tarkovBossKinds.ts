export const TARKOV_BOSS_KINDS = ["boss", "elite", "soldier"] as const;

export type TarkovBossKind = (typeof TARKOV_BOSS_KINDS)[number];

export const TARKOV_BOSS_KIND_LABELS: Record<TarkovBossKind, string> = {
  boss: "Boss",
  elite: "Elite",
  soldier: "Soldier",
};

export const TARKOV_BOSS_HUB_SECTIONS = ["boss", "other"] as const;

export type TarkovBossHubSection = (typeof TARKOV_BOSS_HUB_SECTIONS)[number];

export const TARKOV_BOSS_HUB_SECTION_LABELS: Record<TarkovBossHubSection, string> = {
  boss: "Boss",
  other: "非 Boss",
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

export function isNamedBossId(id: string | undefined | null): boolean {
  return String(id || "")
    .trim()
    .toLowerCase()
    .startsWith("boss");
}

export function isFollowerMobId(id: string | undefined | null): boolean {
  return String(id || "")
    .trim()
    .toLowerCase()
    .startsWith("follower");
}

/** parent_ids 里第一个具名 Boss（如 bossBoar）。 */
export function namedBossParentId(
  parentIds: readonly (string | null | undefined)[] | null | undefined,
): string {
  for (const raw of parentIds || []) {
    const id = String(raw || "").trim();
    if (isNamedBossId(id)) return id;
  }
  return "";
}

/** 热力 / 导航顶行：id 是 boss*，且没有挂到另一个具名 Boss 下。 */
export function isTopLevelNamedBoss(
  id: string | undefined | null,
  parentIds?: readonly (string | null | undefined)[] | null,
): boolean {
  return isNamedBossId(id) && !namedBossParentId(parentIds);
}

export function selectTopLevelNamedBosses<
  T extends { id?: string | null; parent_ids?: string[] | null },
>(items: readonly T[]): T[] {
  return items.filter((row) => isTopLevelNamedBoss(row.id, row.parent_ids));
}

/** follower*，或 id 虽是 boss* 但 parent_ids 已指向具名 Boss（如 bossBoarSniper）。 */
export function isHangableUnderNamedBoss(
  id: string | undefined | null,
  parentIds?: readonly (string | null | undefined)[] | null,
): boolean {
  const parent = namedBossParentId(parentIds);
  if (!parent) return false;
  const self = String(id || "").trim();
  if (!self || self === parent) return false;
  return isFollowerMobId(id) || isNamedBossId(id);
}

export function isCatalogBossKind(kind: string | undefined | null): boolean {
  const key = normalizeBossKind(kind);
  return key === "boss" || key === "elite";
}

export function filterCatalogBosses<T extends { id?: string | null; kind?: string | null }>(
  items: readonly T[],
): T[] {
  return items.filter(
    (item) => isCatalogBossKind(item.kind) && !isFollowerMobId(item.id),
  );
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

export type TarkovBossTreeRow<T> = T & { children?: TarkovBossTreeRow<T>[] };

/** 具名 BOSS 作父行；follower* 以及 parent 为具名 Boss 的 boss*（如狙击手）挂到父级下。游荡者等仍进非 Boss。 */
export function groupBossCatalogTree<
  T extends { id?: string | null; parent_ids?: string[] | null },
>(items: readonly T[]): {
  bosses: TarkovBossTreeRow<T>[];
  others: TarkovBossTreeRow<T>[];
} {
  const bosses = selectTopLevelNamedBosses(items);
  const nestedIds = new Set<string>();
  const bossTrees: TarkovBossTreeRow<T>[] = bosses.map((parent) => {
    const parentId = parent.id || "";
    const children = items.filter((row) => {
      const id = row.id || "";
      if (!id || nestedIds.has(id)) return false;
      if (!isHangableUnderNamedBoss(id, row.parent_ids)) return false;
      if (namedBossParentId(row.parent_ids) !== parentId) return false;
      nestedIds.add(id);
      return true;
    });
    return children.length ? { ...parent, children } : { ...parent };
  });
  const others = items.filter(
    (row) => !isNamedBossId(row.id) && !nestedIds.has(row.id || ""),
  );
  return { bosses: bossTrees, others };
}
