/** 对齐 tarkov.dev map/index.jsx：散落物按物品 handbookCategories 分子图层。 */

import { inventoryThumbUrl } from "./tarkovItemImages";
import { TARKOV_HANDBOOK_ROOTS } from "./tarkovItemTypes";
import {
  tarkovLooseLootIconUrl,
  uniqueKinds,
  type TarkovMapKindFlags,
} from "./tarkovMapMarkers";

export const LOOT_LOOSE_OTHER_KIND = "5b47574386f77428ca22b2f4";

/** 侧栏子项顺序，对齐 tarkov.dev zh Loose Loot 常见手册类。 */
export const LOOT_LOOSE_KIND_ORDER = [
  "5b47574386f77428ca22b2f1", // 贵重物品
  "5b5f6fa186f77409407a7eb7", // 容器
  "5b47574386f77428ca22b341", // 情报物品
  "5c518ed586f774119a772aee", // 电子钥匙
  "5b47574386f77428ca22b2ef", // 电子产品
  "5b47574386f77428ca22b2ed", // 能源物品
  "5b47574386f77428ca22b33a", // 注射器
  "5b47574386f77428ca22b335", // 饮品
  LOOT_LOOSE_OTHER_KIND, // 其他
  "5b47574386f77428ca22b2f2", // 易燃物品
  "5c518ec986f7743b68682ce2", // 机械钥匙
  "5b47574386f77428ca22b345", // 特殊装备
] as const;

const HANDBOOK_KIND_ID = /^[0-9a-f]{24}$/i;

/** tarkov.dev map 图层用 handbookCategories.imageLink。 */
export function tarkovLooseLootKindIconUrl(kind: string): string {
  const id = (kind || "").trim();
  if (!HANDBOOK_KIND_ID.test(id)) return tarkovLooseLootIconUrl();
  return `https://assets.tarkov.dev/handbook-category-${id}-icon.webp`;
}

const HANDBOOK_LABEL_BY_ID: Record<string, string> = {};
const HANDBOOK_CHILD_IDS = new Set<string>();
const HANDBOOK_ROOT_IDS = new Set<string>();

for (const root of TARKOV_HANDBOOK_ROOTS) {
  HANDBOOK_LABEL_BY_ID[root.id] = root.label;
  HANDBOOK_ROOT_IDS.add(root.id);
  for (const child of root.children) {
    HANDBOOK_LABEL_BY_ID[child.id] = child.label;
    HANDBOOK_CHILD_IDS.add(child.id);
  }
}

export type TarkovMapLootLooseItemLike = {
  id?: string | null;
  name?: string | null;
  short_name?: string | null;
  icon_link?: string | null;
  handbook_ids?: readonly string[] | null;
  types?: readonly string[] | null;
  count?: number | null;
};

export type TarkovLootLooseTooltipClasses = {
  tip: string;
  icon: string;
  item?: string;
  count?: string;
  card?: string;
  cardIcon?: string;
  cardBody?: string;
  cardName?: string;
  cardMeta?: string;
};

export const TARKOV_LOOT_ITEM_ATTR = "data-tarkov-loot-item";
export const TARKOV_LOOT_TYPES_ATTR = "data-tarkov-loot-types";

export function lootItemFromChip(el: {
  getAttribute(name: string): string | null;
}): { id: string; types: string[] } | null {
  const id = (el.getAttribute(TARKOV_LOOT_ITEM_ATTR) || "").trim();
  if (!id) return null;
  const types = (el.getAttribute(TARKOV_LOOT_TYPES_ATTR) || "")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  return { id, types };
}

export type TarkovMapLootLooseLike = {
  items?: readonly TarkovMapLootLooseItemLike[] | null;
};

export function lootLooseKindLabel(kind: string): string {
  const key = (kind || "").trim();
  return HANDBOOK_LABEL_BY_ID[key] || "其他";
}

export function lootLooseKindFromItem(item: TarkovMapLootLooseItemLike): string {
  const ids = (item.handbook_ids || [])
    .map((raw) => String(raw || "").trim())
    .filter(Boolean);
  for (const id of ids) {
    if (HANDBOOK_CHILD_IDS.has(id)) return id;
  }
  for (const id of ids) {
    if (HANDBOOK_ROOT_IDS.has(id)) return id;
  }
  return LOOT_LOOSE_OTHER_KIND;
}

export function lootLooseKindsOfRow(row: TarkovMapLootLooseLike): string[] {
  const seen = new Set<string>();
  for (const item of row.items || []) {
    seen.add(lootLooseKindFromItem(item));
  }
  if (!seen.size) seen.add(LOOT_LOOSE_OTHER_KIND);
  return [...seen];
}

export function lootLooseKindsPresent(
  rows: ReadonlyArray<TarkovMapLootLooseLike>,
): string[] {
  return uniqueKinds(
    rows.flatMap((row) => lootLooseKindsOfRow(row)),
    LOOT_LOOSE_KIND_ORDER,
  );
}

export function isLootLooseKindOn(
  flags: TarkovMapKindFlags,
  kind: string,
): boolean {
  return flags[kind] === true;
}

export function lootLooseRowVisible(
  row: TarkovMapLootLooseLike,
  flags: TarkovMapKindFlags,
): boolean {
  return lootLooseKindsOfRow(row).some((kind) => isLootLooseKindOn(flags, kind));
}

/** 地图标点一律用手叶子类图；混类一堆才用散落物齿轮。 */
export function lootLooseMarkerIconUrl(row: TarkovMapLootLooseLike): string {
  const kinds = lootLooseKindsOfRow(row);
  if (kinds.length === 1) return tarkovLooseLootKindIconUrl(kinds[0]);
  return tarkovLooseLootIconUrl();
}

function escapeTipHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function lootLooseItemLabel(item: TarkovMapLootLooseItemLike): string {
  return (item.name || item.short_name || item.id || "").trim();
}

function lootLooseItemIconSrc(item: TarkovMapLootLooseItemLike): string {
  return inventoryThumbUrl(item.icon_link, item.id) || tarkovLooseLootIconUrl();
}

function lootLooseItemTypesAttr(
  types: readonly string[] | null | undefined,
): string {
  return (types || [])
    .map((type) => String(type || "").trim())
    .filter(Boolean)
    .join(",");
}

function lootLooseItemChipHtml(
  item: TarkovMapLootLooseItemLike,
  classes: TarkovLootLooseTooltipClasses,
): string {
  const label = lootLooseItemLabel(item) || "散落物";
  const short = (item.short_name || "").trim();
  const src = lootLooseItemIconSrc(item);
  const alt = escapeTipHtml(label);
  const count = Number(item.count || 1);
  const id = (item.id || "").trim();
  const types = lootLooseItemTypesAttr(item.types);
  const itemClass = classes.item || "";
  const countClass = classes.count || "";
  const cardClass = classes.card || "";
  const cardIconClass = classes.cardIcon || "";
  const cardBodyClass = classes.cardBody || "";
  const cardNameClass = classes.cardName || "";
  const cardMetaClass = classes.cardMeta || "";
  const attrs = id
    ? ` ${TARKOV_LOOT_ITEM_ATTR}="${escapeTipHtml(id)}" ${TARKOV_LOOT_TYPES_ATTR}="${escapeTipHtml(types)}"`
    : "";
  const countBadge =
    count > 1 && countClass
      ? `<span class="${countClass}">×${escapeTipHtml(String(count))}</span>`
      : count > 1
        ? `<span>×${escapeTipHtml(String(count))}</span>`
        : "";
  const metaBits = [
    short && short !== label ? escapeTipHtml(short) : "",
    count > 1 ? `×${escapeTipHtml(String(count))}` : "",
  ].filter(Boolean);
  const meta = metaBits.length
    ? `<span class="${cardMetaClass}">${metaBits.join(" · ")}</span>`
    : "";
  return `<span class="${itemClass}" data-tarkov-loot-chip="1"${attrs} tabindex="0"><img class="${classes.icon}" src="${escapeTipHtml(src)}" alt="${alt}" width="32" height="32"/>${countBadge}<span class="${cardClass}" role="tooltip"><img class="${cardIconClass}" src="${escapeTipHtml(src)}" alt="" width="48" height="48"/><span class="${cardBodyClass}"><strong class="${cardNameClass}">${alt}</strong>${meta}</span></span></span>`;
}

export function tarkovLootLooseTooltipHtml(
  items: ReadonlyArray<TarkovMapLootLooseItemLike>,
  classes: TarkovLootLooseTooltipClasses,
): string {
  const chips = (items.length ? items : [{}]).map((item) =>
    lootLooseItemChipHtml(item, classes),
  );
  return `<span class="${classes.tip}">${chips.join("")}</span>`;
}
