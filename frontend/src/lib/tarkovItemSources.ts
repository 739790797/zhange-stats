import type { TarkovItemDetail } from "@/api/guidesApi";
import {
  bossPortraitUrl,
  tarkovBossHref,
} from "@/lib/tarkovHomeNav";
import {
  bossHubSectionForRow,
  TARKOV_BOSS_HUB_SECTION_LABELS,
  type TarkovBossHubSection,
} from "@/lib/tarkovBossKinds";
import { itemHasFlea, type VendorOffer } from "@/lib/tarkovItemFormat";
import { tarkovObjectiveTypeLabel } from "@/lib/tarkovTaskObjective";

export type TarkovItemSources = NonNullable<TarkovItemDetail["sources"]>;
export type TarkovItemUses = NonNullable<TarkovItemDetail["uses"]>;
export type TarkovItemDropSource = NonNullable<
  TarkovItemSources["drops"]
>[number];

export function itemDropSection(
  row: Pick<TarkovItemDropSource, "id" | "parent_ids">,
): TarkovBossHubSection {
  return bossHubSectionForRow(row.id, row.parent_ids);
}

export function splitItemDropSources(
  drops: TarkovItemDropSource[] | null | undefined,
): Record<TarkovBossHubSection, TarkovItemDropSource[]> {
  const out: Record<TarkovBossHubSection, TarkovItemDropSource[]> = {
    boss: [],
    other: [],
  };
  for (const row of drops || []) {
    out[itemDropSection(row)].push(row);
  }
  return out;
}

export function dropSourcePortrait(row: TarkovItemDropSource): string {
  const direct = String(row.portrait_link || "").trim();
  if (direct) return direct;
  return bossPortraitUrl(row.slug || row.id || "");
}

export function dropSourceHref(row: TarkovItemDropSource): string {
  const slug = String(row.slug || row.id || "").trim();
  return slug ? tarkovBossHref(slug) : "";
}

export function dropSourceSectionLabel(section: TarkovBossHubSection): string {
  return TARKOV_BOSS_HUB_SECTION_LABELS[section];
}

export type ItemFleaQuote = {
  lastLow: number | null;
  avg24: number | null;
  change48?: number | null;
  change48p?: number | null;
};

function finiteOrNull(value: unknown): number | null {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function positiveMoney(value: unknown): number | null {
  const n = finiteOrNull(value);
  return n != null && n > 0 ? n : null;
}

export function hasFleaQuote(flea: ItemFleaQuote | null | undefined): boolean {
  if (!flea) return false;
  return positiveMoney(flea.lastLow) != null || positiveMoney(flea.avg24) != null;
}

export function buildItemFleaQuote(
  item: Record<string, unknown> | undefined,
  opts?: { withChange?: boolean; fallbackOffers?: VendorOffer[] },
): ItemFleaQuote | null {
  if (!itemHasFlea(item)) return null;
  let lastLow = positiveMoney(item?.lastLowPrice);
  let avg24 = positiveMoney(item?.avg24hPrice);
  if (lastLow == null && avg24 == null) {
    const offer = opts?.fallbackOffers?.[0];
    lastLow = positiveMoney(offer?.priceRub ?? offer?.price);
  }
  if (lastLow == null && avg24 == null) return null;
  return {
    lastLow,
    avg24,
    change48: opts?.withChange ? finiteOrNull(item?.changeLast48h) : null,
    change48p: opts?.withChange ? finiteOrNull(item?.changeLast48hPercent) : null,
  };
}

export const ITEM_RELATION_PREVIEW = 8;

export function previewRows<T>(
  rows: T[] | null | undefined,
  expanded: boolean,
  limit = ITEM_RELATION_PREVIEW,
): T[] {
  const list = rows || [];
  if (expanded || list.length <= limit) return list;
  return list.slice(0, limit);
}

export function itemHasSources(
  sources: TarkovItemSources | null | undefined,
): boolean {
  if (!sources) return false;
  return Boolean(
    sources.barters?.length ||
      sources.crafts?.length ||
      sources.quest_rewards?.length ||
      sources.drops?.length,
  );
}

export function itemHasUses(uses: TarkovItemUses | null | undefined): boolean {
  if (!uses) return false;
  return Boolean(
    uses.barters?.length ||
      uses.crafts?.length ||
      uses.hideout?.length ||
      uses.tasks?.length,
  );
}

export function itemHasBarterRelations(
  sources: TarkovItemSources | null | undefined,
  uses: TarkovItemUses | null | undefined,
): boolean {
  return Boolean(sources?.barters?.length || uses?.barters?.length);
}

export function itemHasQuestRelations(
  sources: TarkovItemSources | null | undefined,
  uses: TarkovItemUses | null | undefined,
): boolean {
  return Boolean(sources?.quest_rewards?.length || uses?.tasks?.length);
}

export function itemHasCraftRelations(
  sources: TarkovItemSources | null | undefined,
  uses: TarkovItemUses | null | undefined,
): boolean {
  return Boolean(sources?.crafts?.length || uses?.crafts?.length);
}

export function itemHasHideoutRelations(
  uses: TarkovItemUses | null | undefined,
): boolean {
  return Boolean(uses?.hideout?.length);
}

export function itemHasDropRelations(
  sources: TarkovItemSources | null | undefined,
): boolean {
  return Boolean(sources?.drops?.length);
}

export function craftRecipeSourceLabel(
  taskUnlock?: string | null,
  taskUnlockName?: string | null,
): string {
  if (!String(taskUnlock || "").trim()) return "默认";
  return String(taskUnlockName || "").trim() || "任务解锁";
}

export function questRewardKindLabel(kind: string | undefined): string {
  if (kind === "start") return "接取奖励";
  if (kind === "finish") return "完成奖励";
  return "任务奖励";
}

export function questKindChip(kind: string | undefined): string {
  if (kind === "start") return "接取";
  if (kind === "finish") return "完成";
  if (kind === "require") return "需求";
  if (kind === "build") return "建造";
  return "任务";
}

export type QuestRelationStep = {
  id?: string;
  type?: string;
  count?: number | null;
  found_in_raid?: boolean | null;
  text?: string | null;
};

export function questStepLabel(type: string | undefined): string {
  const key = (type || "").trim();
  if (key === "start" || key === "finish") return questRewardKindLabel(key);
  if (key === "neededKeys") return "钥匙";
  if (key === "wearing") return "穿戴";
  return tarkovObjectiveTypeLabel(key) || "相关";
}

export function questStepCountText(count: number | null | undefined): string {
  if (count == null) return "";
  const n = Number(count);
  if (!Number.isFinite(n) || n <= 0) return "";
  return `×${Number.isInteger(n) ? n : n}`;
}

export function questStepPrimaryText(step: QuestRelationStep): string {
  const text = String(step.text || "").trim();
  if (text) return text;
  return questStepLabel(step.type);
}

export function questStepDisplayText(step: QuestRelationStep): string {
  const primary = questStepPrimaryText(step);
  const count = questStepCountText(step.count);
  return count ? `${primary} ${count}` : primary;
}

export function questRelationSteps(row: {
  steps?: QuestRelationStep[] | null;
  kind?: string | null;
  count?: number | null;
  found_in_raid?: boolean | null;
}): QuestRelationStep[] {
  if (row.steps?.length) return row.steps;
  if (row.kind || row.count != null) {
    return [
      {
        type: row.kind || "",
        count: row.count,
        found_in_raid: row.found_in_raid,
      },
    ];
  }
  return [];
}

export function requiredItemCount(
  items: Array<{ id?: string; count?: number }> | undefined,
  itemId: string,
): number {
  let total = 0;
  for (const item of items || []) {
    if (item.id !== itemId) continue;
    const count = Number(item.count ?? 1);
    if (Number.isFinite(count) && count > 0) total += count;
  }
  return total;
}

export function requiredItemFoundInRaid(
  items: Array<{ id?: string; found_in_raid?: boolean | null }> | undefined,
  itemId: string,
): boolean {
  return (items || []).some(
    (item) => item.id === itemId && Boolean(item.found_in_raid),
  );
}
