import type { Ror2Item, Ror2Survivor } from "@/api/ror2Api";
import { ror2RichTextPlain } from "@/lib/ror2RichText";

const RARITY_ORDER = [
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
  "Equipment",
  "Lunar Equipment",
  "Elite Equipment",
];

const RARITY_COLOR: Record<string, string> = {
  Common: "default",
  Uncommon: "green",
  Legendary: "red",
  Boss: "gold",
  Lunar: "blue",
  "Lunar Equipment": "blue",
  Void: "purple",
  Meal: "orange",
  Hallowed: "magenta",
  Hex: "cyan",
  Page: "geekblue",
  Equipment: "orange",
  "Elite Equipment": "gold",
};

/** 图标描边。色值和 Wiki / 游戏稀有度一致，空稀有度归到 Untiered。 */
const RARITY_ACCENT: Record<string, string> = {
  Common: "#f2f2f2",
  Uncommon: "#6fdb4a",
  Legendary: "#ef5b5b",
  Boss: "#ffeb04",
  Lunar: "#307fff",
  "Lunar Equipment": "#307fff",
  Void: "#ed7fcd",
  Meal: "#f0a04b",
  Hallowed: "#9368f9",
  Hex: "#048501",
  Page: "#6aa8ff",
  Untiered: "#9aa4b2",
  Equipment: "#ff9f43",
  "Elite Equipment": "#ffeb04",
};

export type Ror2Searchable = {
  name: string;
  rarity?: string;
  quote?: string;
  description?: string;
  umbra?: string;
  internal_name?: string;
};

export function ror2RarityColor(rarity: string): string {
  return RARITY_COLOR[rarity] || "default";
}

export function ror2RarityKey(rarity: string | undefined): string {
  const key = (rarity || "").trim();
  return key || "Untiered";
}

export function ror2RarityAccent(rarity: string | undefined): string {
  return RARITY_ACCENT[ror2RarityKey(rarity)] || RARITY_ACCENT.Untiered;
}

export function ror2ItemStackLabel(stats: { stack?: string }[] | undefined): string {
  const values: string[] = [];
  for (const stat of stats ?? []) {
    const stack = (stat.stack || "").trim();
    if (stack && !values.includes(stack)) values.push(stack);
  }
  return values.join(" / ");
}

export function ror2Rarities(entries: { rarity?: string }[]): string[] {
  const present = new Set(entries.map((entry) => entry.rarity).filter((rarity): rarity is string => Boolean(rarity)));
  const known = RARITY_ORDER.filter((rarity) => present.has(rarity));
  const rest = [...present].filter((rarity) => !RARITY_ORDER.includes(rarity)).sort();
  return [...known, ...rest];
}

export function ror2StackText(stack: string, add: string): string {
  if (stack && add) return `${stack} ${add}`;
  return stack || add;
}

export function ror2Number(value: number | null | undefined): string {
  if (value == null) return "";
  return formatNum(value);
}

export function filterRor2Entries<T extends Ror2Searchable>(
  entries: T[],
  query: string,
  rarity: string,
): T[] {
  const needle = query.trim().toLowerCase();
  return entries.filter((entry) => {
    if (rarity && entry.rarity !== rarity) return false;
    if (!needle) return true;
    const haystack = [
      entry.name,
      ror2RichTextPlain(entry.quote ?? ""),
      ror2RichTextPlain(entry.description ?? ""),
      ror2RichTextPlain(entry.umbra ?? ""),
      entry.internal_name,
    ]
      .filter(Boolean)
      .join("\n")
      .toLowerCase();
    return haystack.includes(needle);
  });
}

export function ror2ItemSearchable(item: Ror2Item): Ror2Searchable {
  return item;
}

export function ror2SurvivorSearchable(survivor: Ror2Survivor): Ror2Searchable {
  return survivor;
}

function formatNum(value: number): string {
  if (Number.isInteger(value)) return String(value);
  return String(value);
}
