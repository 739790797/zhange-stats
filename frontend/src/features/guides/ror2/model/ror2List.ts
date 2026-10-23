import {
  ROR2_EXPANSION_WIKI_TITLES,
  ROR2_INTERNAL_EXPANSION_IDS,
  ror2ExpansionId,
} from "@/features/guides/ror2/model/ror2Expansion";

const ROR2_PINYIN_COLLATOR = new Intl.Collator("zh-CN-u-co-pinyin", {
  sensitivity: "base",
  numeric: true,
});

export type Ror2ListSortPolicy = "source-name" | "name" | "canonical";

export type Ror2ListSortableRow = {
  name: string;
  name_zh?: string;
  expansion?: string;
};

/**
 * Shared release order for ROR2 lists and the survivor/source menus: base game,
 * known DLCs in topbar order, then unknown source ids alphabetically.
 */
export function ror2ExpansionOrder(rows: readonly { expansion?: string }[]): string[] {
  const present = new Set(
    rows
      .map((row) => ror2ExpansionId(row.expansion))
      .filter((id) => id === "base" || !ROR2_INTERNAL_EXPANSION_IDS.has(id)),
  );
  const knownIds = Object.keys(ROR2_EXPANSION_WIKI_TITLES);
  const known = knownIds.filter((id) => present.has(id));
  const rest = [...present]
    .filter((id) => id !== "base" && !knownIds.includes(id))
    .sort(compareRor2StableText);
  const dlcs = [...known, ...rest];
  return present.has("base") ? ["base", ...dlcs] : dlcs;
}

export function ror2ExpansionRankMap(expansionOrder: readonly string[]): Map<string, number> {
  return new Map(expansionOrder.map((id, index) => [id, index] as const));
}

export function compareRor2Expansions(
  left: string | undefined,
  right: string | undefined,
  ranks: ReadonlyMap<string, number>,
): number {
  const leftId = ror2ExpansionId(left);
  const rightId = ror2ExpansionId(right);
  if (leftId === "base") return rightId === "base" ? 0 : -1;
  if (rightId === "base") return 1;

  const leftRank = ranks.get(leftId);
  const rightRank = ranks.get(rightId);
  if (leftRank == null && rightRank == null) return compareRor2StableText(leftId, rightId);
  if (leftRank == null) return 1;
  if (rightRank == null) return -1;
  return leftRank - rightRank;
}

export function ror2ListName(row: Pick<Ror2ListSortableRow, "name" | "name_zh">): string {
  return row.name_zh?.trim() || row.name;
}

export function compareRor2PinyinNames(left: string, right: string): number {
  return ROR2_PINYIN_COLLATOR.compare(left, right);
}

/** Stable code-point fallback for equal pinyin or untranslated/unknown names. */
export function compareRor2StableText(left: string, right: string): number {
  if (left === right) return 0;
  return left < right ? -1 : 1;
}

/**
 * Reusable within-list sorter. "canonical" intentionally preserves upstream or
 * curated sequence; all other policies use the approved Chinese name when present.
 */
export function sortRor2Rows<T extends Ror2ListSortableRow>(
  rows: readonly T[],
  policy: Ror2ListSortPolicy,
  expansionOrder?: readonly string[],
): T[] {
  if (policy === "canonical") return [...rows];
  const expansionRanks = ror2ExpansionRankMap(expansionOrder ?? ror2ExpansionOrder(rows));
  return [...rows].sort((left, right) => {
    if (policy === "source-name") {
      const bySource = compareRor2Expansions(left.expansion, right.expansion, expansionRanks);
      if (bySource !== 0) return bySource;
    }
    const byPinyin = compareRor2PinyinNames(ror2ListName(left), ror2ListName(right));
    if (byPinyin !== 0) return byPinyin;
    return compareRor2StableText(left.name, right.name);
  });
}
