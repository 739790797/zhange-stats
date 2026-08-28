/** 对齐 tarkov.dev 地图出生点：PMC / Scav / Boss 图层与 interactive/spawn_*.png。 */

export const TARKOV_SPAWN_KINDS = ["pmc", "scav", "boss"] as const;

export type TarkovSpawnKind = (typeof TARKOV_SPAWN_KINDS)[number];

export type TarkovSpawnKindFlags = Record<TarkovSpawnKind, boolean>;

/** 图层筛选文案，对齐 tarkov.dev zh Spawns 子项。 */
export const TARKOV_SPAWN_KIND_LABELS: Record<TarkovSpawnKind, string> = {
  pmc: "PMC",
  scav: "Scav",
  boss: "Boss",
};

export function defaultSpawnKindFlags(on = true): TarkovSpawnKindFlags {
  return { pmc: on, scav: on, boss: on };
}

export function tarkovSpawnIconUrl(kind: TarkovSpawnKind): string {
  return `/tarkov/map-icons/spawn_${kind}.png`;
}

/** PMC 三角锚在底边，其余居中；对齐 tarkov.dev map/index.jsx。 */
export function tarkovSpawnIconAnchor(kind: TarkovSpawnKind): [number, number] {
  return kind === "pmc" ? [12, 24] : [12, 12];
}

export function tarkovSpawnTooltipAnchor(kind: TarkovSpawnKind): [number, number] {
  return kind === "pmc" ? [0, -24] : [0, -12];
}

export function spawnKindsPresent(input: {
  spawns?: ReadonlyArray<{ kind?: string | null }>;
  bosses?: ReadonlyArray<unknown>;
}): TarkovSpawnKind[] {
  const seen = new Set<TarkovSpawnKind>();
  for (const row of input.spawns || []) {
    const kind = String(row.kind || "").trim().toLowerCase();
    if (kind === "pmc" || kind === "scav") seen.add(kind);
  }
  if ((input.bosses || []).length) seen.add("boss");
  return TARKOV_SPAWN_KINDS.filter((kind) => seen.has(kind));
}

export function allPresentSpawnKindsOn(
  flags: TarkovSpawnKindFlags,
  present: readonly TarkovSpawnKind[],
): boolean {
  return present.length > 0 && present.every((kind) => flags[kind]);
}

export function anyPresentSpawnKindOn(
  flags: TarkovSpawnKindFlags,
  present: readonly TarkovSpawnKind[],
): boolean {
  return present.some((kind) => flags[kind]);
}

export function withSpawnKindsForPresent(
  flags: TarkovSpawnKindFlags,
  present: readonly TarkovSpawnKind[],
  on: boolean,
): TarkovSpawnKindFlags {
  if (!present.length) return flags;
  const next = { ...flags };
  for (const kind of present) next[kind] = on;
  return next;
}
