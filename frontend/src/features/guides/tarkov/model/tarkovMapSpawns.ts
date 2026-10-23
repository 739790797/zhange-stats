/** 对齐 tarkov.dev 地图出生点：PMC / Scav / 狙击 Scav / Boss 图层与 interactive/spawn_*.png。 */

import { normalizeBossKind } from "./tarkovBossKinds";

export const TARKOV_SPAWN_KINDS = ["pmc", "scav", "sniper", "boss"] as const;

export type TarkovSpawnKind = (typeof TARKOV_SPAWN_KINDS)[number];

export type TarkovSpawnKindFlags = Record<TarkovSpawnKind, boolean>;

/** 图层筛选文案，对齐 tarkov.dev zh Spawns 子项。 */
export const TARKOV_SPAWN_KIND_LABELS: Record<TarkovSpawnKind, string> = {
  pmc: "PMC",
  scav: "Scav",
  sniper: "狙击 Scav",
  boss: "Boss",
};

export function defaultSpawnKindFlags(on = true): TarkovSpawnKindFlags {
  return { pmc: on, scav: on, sniper: on, boss: on };
}

export function tarkovSpawnIconUrl(kind: TarkovSpawnKind): string {
  if (kind === "sniper") return "/tarkov/map-icons/spawn_sniper_scav.png";
  return `/tarkov/map-icons/spawn_${kind}.png`;
}

/** PMC 三角锚在底边，其余居中；对齐 tarkov.dev map/index.jsx。 */
export function tarkovSpawnIconAnchor(kind: TarkovSpawnKind): [number, number] {
  return kind === "pmc" ? [12, 24] : [12, 12];
}

/** 具名 BOSS 标比普通骷髅略大，给下沿的 BOSS 字留出可读高度。 */
export const TARKOV_NAMED_BOSS_ICON_SIZE: [number, number] = [32, 32];
export const TARKOV_NAMED_BOSS_ICON_ANCHOR: [number, number] = [16, 16];

const GENERIC_BOSS_ICON_SIZE: [number, number] = [24, 24];

export type TarkovBossMarkerIcon = {
  iconUrl: string;
  iconSize: [number, number];
  iconAnchor: [number, number];
};

/** kind=boss 用带 BOSS 字样的骷髅；精英和小兵仍用原出生点骷髅。 */
export function tarkovBossMarkerIcon(
  kind: string | null | undefined,
): TarkovBossMarkerIcon {
  if (normalizeBossKind(kind) === "boss") {
    return {
      iconUrl: "/tarkov/map-icons/spawn_boss_named.png",
      iconSize: TARKOV_NAMED_BOSS_ICON_SIZE,
      iconAnchor: TARKOV_NAMED_BOSS_ICON_ANCHOR,
    };
  }
  return {
    iconUrl: tarkovSpawnIconUrl("boss"),
    iconSize: GENERIC_BOSS_ICON_SIZE,
    iconAnchor: tarkovSpawnIconAnchor("boss"),
  };
}

export function spawnKindsPresent(input: {
  spawns?: ReadonlyArray<{ kind?: string | null }>;
  bosses?: ReadonlyArray<unknown>;
}): TarkovSpawnKind[] {
  const seen = new Set<TarkovSpawnKind>();
  for (const row of input.spawns || []) {
    const kind = String(row.kind || "").trim().toLowerCase();
    if (kind === "pmc" || kind === "scav" || kind === "sniper") seen.add(kind);
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
