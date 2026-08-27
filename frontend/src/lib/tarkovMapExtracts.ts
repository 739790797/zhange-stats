/** 对齐 tarkov.dev 地图撤离点：阵营盾牌图标 + 标签色。
 * GraphQL MapExtract 只有 faction，没有独立 icon 字段；图标与
 * https://tarkov.dev/maps/interactive/extract_{pmc|scav|shared|transit}.png 同源。
 */

export const TARKOV_EXTRACT_KINDS = ["pmc", "scav", "shared", "transit"] as const;

export type TarkovExtractKind = (typeof TARKOV_EXTRACT_KINDS)[number];

export type TarkovExtractStyle = {
  kind: TarkovExtractKind;
  color: string;
  iconUrl: string;
  zIndex: number;
};

/** tarkov.dev map/index.jsx colorMap / extract-name 色。 */
export const TARKOV_EXTRACT_COLORS: Record<TarkovExtractKind, string> = {
  pmc: "#00e599",
  scav: "#ff7800",
  shared: "#00e4e5",
  transit: "#e53500",
};

/** 图层筛选文案，对齐 tarkov.dev zh Extracts 子项。 */
export const TARKOV_EXTRACT_KIND_LABELS: Record<TarkovExtractKind, string> = {
  pmc: "PMC",
  scav: "Scav",
  shared: "共享",
  transit: "转移点",
};

export type TarkovExtractKindFlags = Record<TarkovExtractKind, boolean>;

export function defaultExtractKindFlags(
  on = true,
): TarkovExtractKindFlags {
  return {
    pmc: on,
    scav: on,
    shared: on,
    transit: on,
  };
}

export function isExtractKindVisible(
  flags: TarkovExtractKindFlags,
  faction?: string | null,
): boolean {
  return Boolean(flags[tarkovExtractKind(faction)]);
}

export function extractKindsPresent(
  extracts: ReadonlyArray<{ faction?: string | null }>,
): TarkovExtractKind[] {
  const seen = new Set<TarkovExtractKind>();
  for (const row of extracts) {
    seen.add(tarkovExtractKind(row.faction));
  }
  return TARKOV_EXTRACT_KINDS.filter((kind) => seen.has(kind));
}

export function allPresentExtractKindsOn(
  flags: TarkovExtractKindFlags,
  present: readonly TarkovExtractKind[],
): boolean {
  return present.length > 0 && present.every((kind) => flags[kind]);
}

export function anyPresentExtractKindOn(
  flags: TarkovExtractKindFlags,
  present: readonly TarkovExtractKind[],
): boolean {
  return present.some((kind) => flags[kind]);
}

export function withExtractKindsForPresent(
  flags: TarkovExtractKindFlags,
  present: readonly TarkovExtractKind[],
  on: boolean,
): TarkovExtractKindFlags {
  if (!present.length) return flags;
  const next = { ...flags };
  for (const kind of present) next[kind] = on;
  return next;
}

const Z_INDEX: Record<TarkovExtractKind, number> = {
  pmc: 150,
  shared: 125,
  scav: 100,
  transit: 150,
};

const KIND_BY_FACTION: Record<string, TarkovExtractKind> = {
  pmc: "pmc",
  scav: "scav",
  shared: "shared",
  all: "shared",
  any: "shared",
  通用: "shared",
  transit: "transit",
  转图: "transit",
  转移: "transit",
  转移点: "transit",
};

export function tarkovExtractIconUrl(kind: TarkovExtractKind): string {
  return `/tarkov/map-icons/extract_${kind}.png`;
}

export function tarkovExtractKind(faction?: string | null): TarkovExtractKind {
  const key = (faction || "").trim().toLowerCase();
  return KIND_BY_FACTION[key] || KIND_BY_FACTION[(faction || "").trim()] || "shared";
}

export function tarkovExtractStyle(faction?: string | null): TarkovExtractStyle {
  const kind = tarkovExtractKind(faction);
  return {
    kind,
    color: TARKOV_EXTRACT_COLORS[kind],
    iconUrl: tarkovExtractIconUrl(kind),
    zIndex: Z_INDEX[kind],
  };
}
