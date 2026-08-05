import type { ArknightsCompareRow, ArknightsOperator } from "@/api/types";

export type RarityProgress = {
  rarity: number;
  owned: number;
  total: number;
};

export function computeRarityProgress(
  row: ArknightsCompareRow,
  catalog: ArknightsOperator[],
): RarityProgress[] {
  const totalBy: Record<number, number> = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0 };
  const ownedBy: Record<number, number> = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0 };
  for (const op of catalog) {
    const r = op.rarity;
    if (r < 1 || r > 6) continue;
    totalBy[r] += 1;
    if (row.owned?.[op.char_id]) ownedBy[r] += 1;
  }
  return [6, 5, 4, 3, 2, 1].map((rarity) => ({
    rarity,
    owned: ownedBy[rarity],
    total: totalBy[rarity],
  }));
}

export function formatProgressPct(owned: number, total: number) {
  if (total <= 0) return "0.0%";
  return `${((owned / total) * 100).toFixed(1)}%`;
}
