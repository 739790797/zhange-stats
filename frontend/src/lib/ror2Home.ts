import type { Ror2Item } from "@/api/ror2Api";
import {
  filterRor2Entries,
  ror2RarityKey,
  type Ror2Searchable,
} from "@/lib/ror2Catalog";

export const ROR2_HOME_PATH = "/guides/ror2";
export const ROR2_ITEMS_PATH = "/guides/ror2/items";

export const ROR2_WIKI_ITEMS = "https://riskofrain2.wiki.gg/wiki/Items";
export const ROR2_LICENSE = "https://creativecommons.org/licenses/by-sa/4.0/";

export type Ror2HomeTile = {
  id: string;
  label: string;
  href?: string;
};

/** 首页内容格。两行五列；目前只有物品接到列表。 */
export const ROR2_HOME_TILES: Ror2HomeTile[] = [
  { id: "survivors", label: "幸存者" },
  { id: "items", label: "物品", href: ROR2_ITEMS_PATH },
  { id: "monsters", label: "怪物" },
  { id: "environments", label: "环境" },
  { id: "challenges", label: "成就" },
  { id: "interactables", label: "可交互物" },
  { id: "drones", label: "无人机" },
  { id: "shrines", label: "神龛" },
  { id: "artifacts", label: "神器" },
  { id: "newt-altars", label: "纽特祭坛" },
];

export type Ror2SideLink = {
  id: string;
  label: string;
};

/** 右侧杂项。这一轮都不跳转。 */
export const ROR2_SIDE_LINKS: Ror2SideLink[] = [
  { id: "mechanics", label: "游戏机制" },
  { id: "stacking", label: "物品堆叠" },
  { id: "status", label: "状态效果" },
  { id: "damage", label: "伤害计算" },
  { id: "modes", label: "游戏模式" },
  { id: "logs", label: "日志总览" },
  { id: "modding", label: "模组说明" },
];

const PASSIVE_RARITIES = [
  "Common",
  "Uncommon",
  "Legendary",
  "Boss",
  "Lunar",
  "Void",
  "Meal",
  "Hallowed",
  "Hex",
  "Page",
  "Untiered",
] as const;

const ACTIVE_RARITIES = ["Equipment", "Lunar Equipment", "Elite Equipment"] as const;

export type Ror2RarityChip = {
  id: string;
  label: string;
  count: number;
};

export type Ror2ItemSection = {
  id: string;
  label: string;
  rarities: Ror2RarityChip[];
};

export function ror2PageTitle(pathname: string): string {
  const path = pathname.replace(/\/+$/, "") || "/";
  if (path === ROR2_ITEMS_PATH) return "雨中冒险2 · 物品";
  return "雨中冒险2";
}

export function ror2ItemsHref(rarity = "", query = ""): string {
  const params = new URLSearchParams();
  const cat = rarity.trim();
  const q = query.trim();
  if (cat && cat !== "all") params.set("cat", cat);
  if (q) params.set("q", q);
  const qs = params.toString();
  return qs ? `${ROR2_ITEMS_PATH}?${qs}` : ROR2_ITEMS_PATH;
}

export function ror2CatalogItems(catalog: {
  items: Ror2Item[];
  equipment: Ror2Item[];
}): Ror2Item[] {
  const seen = new Set<string>();
  const out: Ror2Item[] = [];
  for (const item of [...catalog.items, ...catalog.equipment]) {
    const key = `${ror2RarityKey(item.rarity)}\0${item.name}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}

export function ror2ItemSections(items: { rarity?: string }[]): Ror2ItemSection[] {
  const counts = new Map<string, number>();
  for (const item of items) {
    const key = ror2RarityKey(item.rarity);
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  const used = new Set<string>();
  const take = (order: readonly string[]): Ror2RarityChip[] =>
    order
      .filter((id) => counts.has(id))
      .map((id) => {
        used.add(id);
        return { id, label: id, count: counts.get(id) || 0 };
      });
  const sections: Ror2ItemSection[] = [
    { id: "passive", label: "被动", rarities: take(PASSIVE_RARITIES) },
    { id: "active", label: "主动", rarities: take(ACTIVE_RARITIES) },
  ];
  const rest = [...counts.keys()].filter((id) => !used.has(id)).sort();
  if (rest.length) {
    sections.push({
      id: "other",
      label: "其他",
      rarities: rest.map((id) => ({ id, label: id, count: counts.get(id) || 0 })),
    });
  }
  return sections.filter((section) => section.rarities.length > 0);
}

export function ror2ActiveRarity(raw: string | null | undefined, items: { rarity?: string }[]): string {
  const cat = (raw || "").trim();
  if (!cat || cat === "all") return "all";
  const known = new Set(items.map((item) => ror2RarityKey(item.rarity)));
  return known.has(cat) ? cat : "all";
}

export function filterRor2Items<T extends Ror2Searchable>(
  items: T[],
  query: string,
  rarity: string,
): T[] {
  const scoped =
    !rarity || rarity === "all"
      ? items
      : items.filter((item) => ror2RarityKey(item.rarity) === rarity);
  return filterRor2Entries(scoped, query, "");
}

export function groupRor2ItemsByRarity<T extends { rarity?: string }>(
  items: T[],
): { rarity: string; items: T[] }[] {
  const buckets = new Map<string, T[]>();
  for (const item of items) {
    const key = ror2RarityKey(item.rarity);
    const list = buckets.get(key);
    if (list) list.push(item);
    else buckets.set(key, [item]);
  }
  const preferred = [...PASSIVE_RARITIES, ...ACTIVE_RARITIES];
  const preferredSet = new Set<string>(preferred);
  const keys = [
    ...preferred.filter((key) => buckets.has(key)),
    ...[...buckets.keys()].filter((key) => !preferredSet.has(key)).sort(),
  ];
  return keys.map((rarity) => ({ rarity, items: buckets.get(rarity) || [] }));
}
