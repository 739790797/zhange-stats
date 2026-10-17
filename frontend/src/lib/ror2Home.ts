import {
  filterRor2Entries,
  ror2ItemTableStack,
  ror2Number,
  ror2RarityKey,
  type Ror2Searchable,
} from "@/lib/ror2Catalog";
import { ror2RichTextPlain } from "@/lib/ror2RichText";
import { PLATFORM_ICON_SRC } from "@/lib/platformIcons";

export const ROR2_HOME_PATH = "/guides/ror2";
export const ROR2_ITEMS_PATH = "/guides/ror2/items";
export const ROR2_SURVIVORS_PATH = "/guides/ror2/survivors";

export const ROR2_SECTIONS = [
  { id: "monsters", label: "怪物", path: "/guides/ror2/monsters", unit: "只" },
  { id: "environments", label: "环境", path: "/guides/ror2/environments", unit: "处" },
  { id: "challenges", label: "成就", path: "/guides/ror2/challenges", unit: "项" },
  { id: "interactables", label: "可交互物", path: "/guides/ror2/interactables", unit: "个" },
  { id: "drones", label: "无人机", path: "/guides/ror2/drones", unit: "架" },
  { id: "artifacts", label: "神器", path: "/guides/ror2/artifacts", unit: "件" },
  { id: "newt-altars", label: "纽特祭坛", path: "/guides/ror2/newt-altars", unit: "座" },
] as const;

export type Ror2SectionId = (typeof ROR2_SECTIONS)[number]["id"];

export const ROR2_UNRELEASED_PATH = "/guides/ror2/unreleased";

/** 不进首页内容格。列表页的左侧目录和 Wiki「Unreleased Items」五节一致。 */
export const ROR2_EXTRA_PAGES = [
  { id: "unreleased", label: "Unreleased Items", path: ROR2_UNRELEASED_PATH, unit: "条" },
] as const;

export type Ror2PageSectionId = Ror2SectionId | (typeof ROR2_EXTRA_PAGES)[number]["id"];

export const ROR2_UNRELEASED_GROUPS = [
  { id: "internal-items", label: "Internal Items" },
  { id: "unfinished-items", label: "Unfinished Items" },
  { id: "lore", label: "Lore" },
  { id: "internal-equipment", label: "Internal Equipment" },
  { id: "unfinished-equipment", label: "Unfinished Equipment" },
] as const;

export const ROR2_WIKI_ITEMS = "https://riskofrain2.wiki.gg/wiki/Items";
export const ROR2_LICENSE = "https://creativecommons.org/licenses/by-sa/4.0/";

export type Ror2HomeTile = {
  id: string;
  label: string;
  href?: string;
};

/** 首页内容格。幸存者和物品接到分类列表。 */
export const ROR2_HOME_TILES: Ror2HomeTile[] = [
  { id: "survivors", label: "幸存者", href: ROR2_SURVIVORS_PATH },
  { id: "items", label: "物品", href: ROR2_ITEMS_PATH },
  ...ROR2_SECTIONS.map((section) => ({
    id: section.id,
    label: section.label,
    href: section.path,
  })),
];

export type Ror2SideLink = {
  id: string;
  label: string;
};

/**
 * Expansion 代号 → Wiki 资料片页标题。
 * 模块原文只有代号。中文还没接入，这里不写汉化名。
 * 顺序是发售顺序，只用来把新代号排在已知代号后面。
 */
const ROR2_WIKI_EXPANSIONS: Record<string, string> = {
  SotV: "Survivors of the Void",
  SotS: "Seekers of the Storm",
  AC: "Alloyed Collective",
  HC: "Hallowed Concepts",
};

/** Wiki 用这两个值标未完成或内部条目，不是资料片。 */
const ROR2_NOT_DLCS = new Set(["Junk", "RoR2.Junk"]);

/** 和 Wiki 幸存者模块的出场顺序一致。不在表里的名字排在同组末尾。 */
const ROR2_SURVIVOR_ORDER = [
  "Commando",
  "Huntress",
  "Bandit",
  "MUL-T",
  "Engineer",
  "Artificer",
  "Mercenary",
  "REX",
  "Loader",
  "Acrid",
  "Captain",
  "Heretic",
  "Railgunner",
  "Void Fiend",
  "Seeker",
  "False Son",
  "CHEF",
  "Operator",
  "Drifter",
  "Enforcer",
  "Acolyte",
];

export type Ror2SurvivorSection<T> = {
  id: string;
  label: string;
  title: string;
  survivors: T[];
};

export function ror2SurvivorSections<T extends { name: string; expansion?: string }>(
  survivors: readonly T[],
  scope?: readonly { expansion?: string }[],
): Ror2SurvivorSection<T>[] {
  const buckets = new Map<string, T[]>();
  for (const survivor of survivors) {
    const id = ror2SurvivorExpansionKey(survivor.expansion);
    const rows = buckets.get(id);
    if (rows) rows.push(survivor);
    else buckets.set(id, [survivor]);
  }
  const names = ror2ExpansionNames([...(scope ?? []), ...survivors]);
  const rank = new Map(ROR2_SURVIVOR_ORDER.map((name, index) => [name, index]));
  const sortRows = (rows: T[]) =>
    [...rows].sort((a, b) => {
      const left = rank.get(a.name);
      const right = rank.get(b.name);
      if (left == null && right == null) return 0;
      if (left == null) return 1;
      if (right == null) return -1;
      return left - right;
    });
  const sections: Ror2SurvivorSection<T>[] = [];
  const used = new Set<string>();
  for (const [id, meta] of names) {
    const key = id === "base" ? "" : id;
    const rows = buckets.get(key);
    if (!rows?.length) continue;
    used.add(key);
    sections.push({ id, label: meta.label, title: meta.title, survivors: sortRows(rows) });
  }
  for (const [key, rows] of buckets) {
    if (used.has(key) || !rows.length) continue;
    const label = ror2SurvivorExpansionLabel(key);
    sections.push({ id: key || "base", label, title: label, survivors: sortRows(rows) });
  }
  return sections;
}

/** 首页杂项格。和内容格同一套按钮，这一轮都不跳转。 */
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

/** Items 页 Untiered 一节点名的条目。其余 Untiered 不进这页。 */
const WIKI_UNTIERED_ITEMS = new Set([
  "Delicate Watch (Broken)",
  "Dio's Best Friend (Consumed)",
  "Dormant Spirit",
  "Dream Crucible (Consumed)",
  "Empty Bottle",
  "Pluripotent Larva (Consumed)",
  "Regenerating Scrap (Consumed)",
  "Sale Star (Consumed)",
  "Tonic Affliction",
  "Unstable Transmitter (Consumed)",
]);

const WIKI_ITEM_RARITIES = new Set<string>([
  ...PASSIVE_RARITIES.filter((rarity) => rarity !== "Untiered"),
  ...ACTIVE_RARITIES,
]);

export function ror2RarityLabel(id: string): string {
  if (id === "Page") return "N'tormat Pages";
  return id;
}

export function ror2WikiListRarity(item: {
  name: string;
  rarity?: string;
  categories?: readonly string[];
  category?: string;
}): string | null {
  if (ror2IsHiddenCategory(item)) return null;
  if (WIKI_UNTIERED_ITEMS.has(item.name)) return "Untiered";
  const rarity = (item.rarity || "").trim();
  return WIKI_ITEM_RARITIES.has(rarity) ? rarity : null;
}

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

export function ror2SurvivorExpansionKey(expansion?: string): string {
  return (expansion || "").trim();
}

export function ror2SurvivorExpansionId(expansion?: string): string {
  return ror2SurvivorExpansionKey(expansion) || "base";
}

export function ror2SurvivorExpansionLabel(expansion?: string): string {
  const id = ror2SurvivorExpansionKey(expansion);
  return ROR2_WIKI_EXPANSIONS[id] ?? (id || "本体");
}

export type Ror2ExpansionName = {
  id: string;
  label: string;
  title: string;
  iconUrl: string | null;
};

/** 图鉴里带资料片字段的条目。序号按整份图鉴排，避免某一页把后面的 DLC 重新编成 1。 */
export function ror2CatalogExpansionRows(catalog: {
  items?: readonly { expansion?: string }[];
  equipment?: readonly { expansion?: string }[];
  survivors?: readonly { expansion?: string }[];
  monsters?: readonly { expansion?: string }[];
  environments?: readonly { expansion?: string }[];
  challenges?: readonly { expansion?: string }[];
  interactables?: readonly { expansion?: string }[];
  artifacts?: readonly { expansion?: string }[];
}): { expansion?: string }[] {
  return [
    ...(catalog.survivors ?? []),
    ...(catalog.items ?? []),
    ...(catalog.equipment ?? []),
    ...(catalog.monsters ?? []),
    ...(catalog.environments ?? []),
    ...(catalog.challenges ?? []),
    ...(catalog.interactables ?? []),
    ...(catalog.artifacts ?? []),
  ];
}

/** 本体在前。已知道的代号按发售顺序，图鉴里多出来的代号接在后面。 */
export function ror2ExpansionOrder(rows: readonly { expansion?: string }[]): string[] {
  const present = new Set(
    rows
      .map((row) => ror2SurvivorExpansionId(row.expansion))
      .filter((id) => id === "base" || !ROR2_NOT_DLCS.has(id)),
  );
  const knownIds = new Set(Object.keys(ROR2_WIKI_EXPANSIONS));
  const known = Object.keys(ROR2_WIKI_EXPANSIONS).filter((id) => present.has(id));
  const rest = [...present].filter((id) => id !== "base" && !knownIds.has(id)).sort();
  const dlcs = [...known, ...rest];
  return present.has("base") ? ["base", ...dlcs] : dlcs;
}

export function ror2ExpansionIconUrl(id: string): string | null {
  if (!id || ROR2_NOT_DLCS.has(id)) return null;
  if (id === "base") return PLATFORM_ICON_SRC.ror2;
  const file = `${id} Icon.png`.replace(/ /g, "_");
  return `https://riskofrain2.wiki.gg/images/${encodeURI(file)}`;
}

/** Wiki 列表只在资料片内容的名字前放图标。本体和内部条目不放。 */
export function ror2DlcMark(expansion?: string): { id: string; label: string; iconUrl: string } | null {
  const id = ror2SurvivorExpansionId(expansion);
  if (!expansion?.trim() || id === "base" || ROR2_NOT_DLCS.has(id)) return null;
  const iconUrl = ror2ExpansionIconUrl(id);
  if (!iconUrl) return null;
  return { id, label: ROR2_WIKI_EXPANSIONS[id] ?? id, iconUrl };
}

export function ror2ExpansionNames(
  rows: readonly { expansion?: string }[],
): Map<string, Ror2ExpansionName> {
  const names = new Map<string, Ror2ExpansionName>();
  for (const id of ror2ExpansionOrder(rows)) {
    if (id === "base") {
      names.set(id, { id, label: "本体", title: "本体", iconUrl: ror2ExpansionIconUrl(id) });
      continue;
    }
    const title = ROR2_WIKI_EXPANSIONS[id] ?? id;
    names.set(id, { id, label: title, title, iconUrl: ror2ExpansionIconUrl(id) });
  }
  return names;
}

export type Ror2SurvivorPack = Ror2ExpansionName & {
  count: number;
};

/** 只列出这份内容里真正有的档。scope 用来排已经知道的资料片，避免某一页把后面的代号排到前面。 */
export function ror2SurvivorPacks<T extends { expansion?: string }>(
  rows: readonly T[],
  scope?: readonly { expansion?: string }[],
): Ror2SurvivorPack[] {
  const names = ror2ExpansionNames([...(scope ?? []), ...rows]);
  const counts = new Map<string, number>();
  for (const row of rows) {
    const id = ror2SurvivorExpansionId(row.expansion);
    counts.set(id, (counts.get(id) ?? 0) + 1);
  }
  const packs: Ror2SurvivorPack[] = [];
  for (const [id, meta] of names) {
    const count = counts.get(id) ?? 0;
    if (count <= 0) continue;
    packs.push({ ...meta, count });
  }
  return packs;
}

export function ror2PageTitle(pathname: string): string {
  const path = pathname.replace(/\/+$/, "") || "/";
  if (path === ROR2_ITEMS_PATH) return "雨中冒险2 · 物品";
  if (path === ROR2_SURVIVORS_PATH) return "雨中冒险2 · 幸存者";
  const survivor = ror2SurvivorSlug(path);
  if (survivor) return `雨中冒险2 · ${survivor}`;
  const section = ror2SectionByPath(path);
  if (section) return `雨中冒险2 · ${section.label}`;
  return "雨中冒险2";
}

export type Ror2Crumb = {
  label: string;
  href?: string;
};

/** 顶栏路径。首页由左上标志代替，不进面包屑。 */
export function ror2Crumbs(pathname: string): Ror2Crumb[] {
  const path = pathname.replace(/\/+$/, "") || "/";
  if (path === ROR2_ITEMS_PATH) return [{ label: "物品" }];
  if (path === ROR2_SURVIVORS_PATH) return [{ label: "幸存者列表" }];
  const survivor = ror2SurvivorSlug(path);
  if (survivor) return [{ label: "幸存者列表", href: ROR2_SURVIVORS_PATH }, { label: survivor }];
  const section = ror2SectionByPath(path);
  if (section) return [{ label: section.label }];
  return [];
}

export function ror2SectionByPath(pathname: string) {
  const path = pathname.replace(/\/+$/, "") || "/";
  return (
    ROR2_SECTIONS.find((section) => section.path === path) ??
    ROR2_EXTRA_PAGES.find((section) => section.path === path)
  );
}

export function ror2SectionById(id: string) {
  return (
    ROR2_SECTIONS.find((section) => section.id === id) ??
    ROR2_EXTRA_PAGES.find((section) => section.id === id)
  );
}

export type Ror2Term = { from: string; to: string };

/** 展示用的幸存者中文名。长名字排在前面，避免短名截断长名。 */
export function ror2SurvivorNamePairs(rows: readonly { name: string; name_zh?: string }[]): Ror2Term[] {
  return rows
    .filter((row): row is { name: string; name_zh: string } => Boolean(row.name && row.name_zh && row.name_zh !== row.name))
    .map((row) => ({ from: row.name, to: row.name_zh }))
    .sort((a, b) => b.from.length - a.from.length || a.from.localeCompare(b.from));
}

export function ror2ReplaceTerms(text: string, terms: readonly Ror2Term[]): string {
  if (!text || terms.length === 0) return text;
  let out = text;
  for (const term of terms) {
    const pattern = new RegExp(`(?<![A-Za-z0-9])${escapeRegExp(term.from)}(?![A-Za-z0-9])`, "g");
    out = out.replace(pattern, term.to);
  }
  return out;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function ror2SurvivorHref(name: string): string {
  return `${ROR2_SURVIVORS_PATH}/${encodeURIComponent(name)}`;
}

export function ror2SurvivorSlug(pathname: string): string | null {
  const path = pathname.replace(/\/+$/, "") || "/";
  const prefix = `${ROR2_SURVIVORS_PATH}/`;
  if (!path.startsWith(prefix)) return null;
  const slug = path.slice(prefix.length);
  if (!slug || slug.includes("/")) return null;
  try {
    return decodeURIComponent(slug);
  } catch {
    return slug;
  }
}

/** Wiki 信息框：细雨 1.5 倍回复，暴雨原值，季风 0.6 倍。缺省加速度按模块写成 80，0 仍是 0。 */
export function ror2TierValue(value: number | null | undefined, factor: number): number | null {
  if (value == null) return null;
  return Math.round(value * factor * 10000) / 10000;
}

export function ror2InfoboxAcceleration(value: number | null | undefined): number {
  return value == null ? 80 : value;
}

export function ror2DrizzleArmor(armor: number | null | undefined): number {
  return (armor ?? 0) + 70;
}

export function ror2PerLevel(value: number | null | undefined): string {
  if (value == null) return "";
  const text = ror2Number(value);
  return value > 0 ? `+${text}` : text;
}

export function ror2SurvivorsHref(expansion = "", query = ""): string {
  const params = new URLSearchParams();
  const cat = expansion.trim();
  const q = query.trim();
  if (cat && cat !== "all") params.set("cat", cat);
  if (q) params.set("q", q);
  const qs = params.toString();
  return qs ? `${ROR2_SURVIVORS_PATH}?${qs}` : ROR2_SURVIVORS_PATH;
}

export function ror2ActiveExpansion(
  raw: string | null | undefined,
  survivors: { expansion?: string }[],
): string {
  const cat = (raw || "").trim();
  if (!cat || cat === "all") return "all";
  const known = new Set(survivors.map((row) => ror2SurvivorExpansionId(row.expansion)));
  return known.has(cat) ? cat : "all";
}

export function filterRor2Survivors<
  T extends Ror2Searchable & { expansion?: string; name_zh?: string },
>(survivors: T[], query: string, expansion: string, zh = false): T[] {
  const scoped =
    !expansion || expansion === "all"
      ? survivors
      : survivors.filter((row) => ror2SurvivorExpansionId(row.expansion) === expansion);
  if (!zh) return filterRor2Entries(scoped, query, "");
  const needle = query.trim().toLowerCase();
  if (!needle) return scoped;
  return scoped.filter((row) =>
    [row.name, row.name_zh, ror2RichTextPlain(row.description ?? ""), ror2RichTextPlain(row.umbra ?? "")]
      .filter(Boolean)
      .join("\n")
      .toLowerCase()
      .includes(needle),
  );
}

export function ror2SurvivorStatLine(survivor: {
  health?: number | null;
  health_per_level?: number | null;
  damage?: number | null;
  damage_per_level?: number | null;
  regen?: number | null;
  regen_per_level?: number | null;
  speed?: number | null;
  armor?: number | null;
}): string {
  const parts: string[] = [];
  const health = growthText(survivor.health, survivor.health_per_level);
  const damage = growthText(survivor.damage, survivor.damage_per_level);
  const regen = growthText(survivor.regen, survivor.regen_per_level);
  if (health) parts.push(`生命 ${health}`);
  if (damage) parts.push(`伤害 ${damage}`);
  if (regen) parts.push(`回复 ${regen}`);
  if (survivor.speed != null) parts.push(`移速 ${ror2Number(survivor.speed)}`);
  if (survivor.armor) parts.push(`护甲 ${ror2Number(survivor.armor)}`);
  return parts.join(" · ");
}

function growthText(base: number | null | undefined, per: number | null | undefined): string {
  if (base == null) return "";
  if (per == null || per === 0) return ror2Number(base);
  const sign = per > 0 ? "+" : "";
  return `${ror2Number(base)} (${sign}${ror2Number(per)})`;
}

const ROR2_STAT_MISSING = "—";

/** Wiki 幸存者表把缺省和 0 都画成 80。 */
export function ror2SurvivorAcceleration(value: number | null | undefined): number {
  return value ? value : 80;
}

export type Ror2SurvivorTableCells = {
  health: string;
  healthGrowth: string;
  regen: string;
  regenGrowth: string;
  damage: string;
  damageGrowth: string;
  speed: string;
  acceleration: string;
  mass: string;
  armor: string;
};

type Ror2SurvivorTableSource = {
  health?: number | null;
  health_per_level?: number | null;
  damage?: number | null;
  damage_per_level?: number | null;
  regen?: number | null;
  regen_per_level?: number | null;
  speed?: number | null;
  acceleration?: number | null;
  mass?: number | null;
  armor?: number | null;
};

/** 和 Wiki 幸存者对照表同一套写法：基础值，成长值另起一段。 */
export function ror2SurvivorTableCells(survivor: Ror2SurvivorTableSource): Ror2SurvivorTableCells {
  return {
    health: survivor.health == null ? ROR2_STAT_MISSING : ror2Number(survivor.health),
    healthGrowth: survivor.health == null ? "" : plusGrowth(survivor.health_per_level),
    regen: survivor.regen == null ? ROR2_STAT_MISSING : `${ror2Number(survivor.regen)}/s`,
    regenGrowth: survivor.regen == null ? "" : rateGrowth(survivor.regen_per_level),
    damage: survivor.damage == null ? ROR2_STAT_MISSING : ror2Number(survivor.damage),
    damageGrowth: survivor.damage == null ? "" : plusGrowth(survivor.damage_per_level),
    speed: survivor.speed == null ? ROR2_STAT_MISSING : `${ror2Number(survivor.speed)} m/s`,
    acceleration: ror2Number(ror2SurvivorAcceleration(survivor.acceleration)),
    mass: survivor.mass == null ? ROR2_STAT_MISSING : ror2Number(survivor.mass),
    armor: survivor.armor == null ? ROR2_STAT_MISSING : ror2Number(survivor.armor),
  };
}

function plusGrowth(per: number | null | undefined): string {
  if (per == null) return "";
  const sign = per < 0 ? "" : "+";
  return `(${sign}${ror2Number(per)})`;
}

function rateGrowth(per: number | null | undefined): string {
  if (per == null) return "";
  const sign = per > 0 ? "+" : "";
  return `(${sign}${ror2Number(per)}/s)`;
}

export const ROR2_SURVIVOR_SORT_KEYS = [
  "image",
  "name",
  "health",
  "regen",
  "damage",
  "speed",
  "acceleration",
  "mass",
  "armor",
] as const;

export type Ror2SurvivorSortKey = (typeof ROR2_SURVIVOR_SORT_KEYS)[number];

type Ror2SurvivorSortable = Ror2SurvivorTableSource & { name: string; name_zh?: string };

export function sortRor2Survivors<T extends Ror2SurvivorSortable>(
  rows: readonly T[],
  key: Ror2SurvivorSortKey,
  direction: "asc" | "desc",
): T[] {
  const sign = direction === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => compareSurvivor(a, b, key, sign));
}

function compareSurvivor(
  a: Ror2SurvivorSortable,
  b: Ror2SurvivorSortable,
  key: Ror2SurvivorSortKey,
  sign: number,
): number {
  const byName = compareNames(survivorDisplayName(a), survivorDisplayName(b));
  if (key === "name" || key === "image") return byName * sign;
  const left = survivorSortNumber(a, key);
  const right = survivorSortNumber(b, key);
  if (left == null && right == null) return byName;
  if (left == null) return 1;
  if (right == null) return -1;
  const diff = (left - right) * sign;
  return diff === 0 ? byName : diff;
}

function survivorDisplayName(row: { name: string; name_zh?: string }): string {
  return row.name_zh || row.name;
}

function compareNames(a: string, b: string): number {
  if (a === b) return 0;
  return a < b ? -1 : 1;
}

function survivorSortNumber(row: Ror2SurvivorSortable, key: Ror2SurvivorSortKey): number | null {
  if (key === "health") return row.health ?? null;
  if (key === "regen") return row.regen ?? null;
  if (key === "damage") return row.damage ?? null;
  if (key === "speed") return row.speed ?? null;
  if (key === "acceleration") return ror2SurvivorAcceleration(row.acceleration);
  if (key === "mass") return row.mass ?? null;
  if (key === "armor") return row.armor ?? null;
  return null;
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

export function ror2IsHiddenCategory(row: { categories?: readonly string[]; category?: string }): boolean {
  if ((row.category || "").trim().toLowerCase() === "hidden") return true;
  return (row.categories ?? []).some((item) => item.trim().toLowerCase() === "hidden");
}

export function ror2CatalogItems<T extends { name: string; rarity?: string; categories?: readonly string[]; category?: string }>(catalog: {
  items: readonly T[];
  equipment: readonly T[];
}): T[] {
  return [...catalog.items, ...catalog.equipment].filter((row) => ror2WikiListRarity(row));
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
        return { id, label: ror2RarityLabel(id), count: counts.get(id) || 0 };
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
      rarities: rest.map((id) => ({ id, label: ror2RarityLabel(id), count: counts.get(id) || 0 })),
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

export function ror2ItemSource(
  raw: string | null | undefined,
  items: { expansion?: string }[],
): string {
  const id = (raw || "").trim();
  if (!id || id === "all") return "all";
  const known = new Set(items.map((item) => ror2SurvivorExpansionId(item.expansion)));
  return known.has(id) ? id : "all";
}

export function filterRor2Items<T extends Ror2Searchable & { expansion?: string }>(
  items: T[],
  query: string,
  rarity: string,
  source = "",
  zh = false,
): T[] {
  const bySource =
    !source || source === "all"
      ? items
      : items.filter((item) => ror2SurvivorExpansionId(item.expansion) === source);
  const byRarity =
    !rarity || rarity === "all"
      ? bySource
      : bySource.filter((item) => ror2RarityKey(item.rarity) === rarity);
  if (!zh) return filterRor2Entries(byRarity, query, "");
  const needle = query.trim().toLowerCase();
  if (!needle) return byRarity;
  return byRarity.filter((item) => zhHaystack(item).includes(needle));
}

function zhHaystack(item: Ror2Searchable & { name_zh?: string; description_zh?: string }): string {
  return [
    item.name,
    item.name_zh,
    ror2RichTextPlain(item.quote ?? ""),
    ror2RichTextPlain(item.description ?? ""),
    ror2RichTextPlain(item.description_zh ?? ""),
    ror2RichTextPlain(item.umbra ?? ""),
    item.internal_name,
  ]
    .filter(Boolean)
    .join("\n")
    .toLowerCase();
}

export type Ror2ItemSortKey = "name" | "description" | "stack" | "cooldown";

export function ror2ItemRarityIsActive(rarity: string): boolean {
  return (ACTIVE_RARITIES as readonly string[]).includes(rarity);
}

/** Wiki 主动物品表把冷却画成 20s、0.1s。空值不补单位。 */
export function ror2ItemCooldownText(value?: string | null): string {
  const text = (value || "").trim();
  if (!text) return "";
  if (/^\d+(\.\d+)?$/.test(text)) return `${text}s`;
  return text;
}

export function sortRor2Items<
  T extends Ror2Searchable & { stats?: { stack?: string }[]; cooldown?: string | null },
>(
  items: readonly T[],
  key: Ror2ItemSortKey,
  direction: "asc" | "desc",
): T[] {
  const sign = direction === "asc" ? 1 : -1;
  return [...items].sort((a, b) => {
    if (key === "cooldown") {
      const diff = compareCooldown(a.cooldown, b.cooldown);
      if (diff !== 0) return diff * sign;
      return compareNames(a.name, b.name);
    }
    const diff = compareNames(itemSortText(a, key), itemSortText(b, key));
    if (diff !== 0) return diff * sign;
    return compareNames(a.name, b.name);
  });
}

function compareCooldown(left?: string | null, right?: string | null): number {
  const a = cooldownSeconds(left);
  const b = cooldownSeconds(right);
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  return a - b;
}

function cooldownSeconds(value?: string | null): number | null {
  const text = (value || "").trim();
  if (!/^\d+(\.\d+)?$/.test(text)) return null;
  return Number(text);
}

function itemSortText(
  item: Ror2Searchable & { stats?: { stack?: string }[]; name_zh?: string; description_zh?: string },
  key: Ror2ItemSortKey,
): string {
  if (key === "description") return ror2RichTextPlain(item.description_zh || item.description || "");
  if (key === "stack") return ror2ItemTableStack(item.stats);
  return item.name_zh || item.name;
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

export type Ror2DirectoryRow = Ror2Searchable & {
  group: string;
  note: string;
  imageUrl: string | null;
  dlcIconUrl?: string | null;
  dlcLabel?: string;
  quote_zh?: string;
  unlocks?: { name: string; name_zh?: string; imageUrl: string }[];
  coins?: string;
};

type CombatFields = {
  health?: number | null;
  health_per_level?: number | null;
  damage?: number | null;
  damage_per_level?: number | null;
  regen?: number | null;
  regen_per_level?: number | null;
  speed?: number | null;
  armor?: number | null;
};

const WIKI_MONSTER_KINDS = ["Normal", "Boss", "Special", "Special Boss"] as const;
const WIKI_DRONE_ORIGINS = ["Interactable", "Survivor", "Item"] as const;
const WIKI_INTERACTABLE_CATEGORIES = [
  "Chests",
  "Shrines",
  "Drones",
  "Duplicators",
  "Misc",
  "Environment Specific",
  "Charging Zones",
  "Portals",
  "Skill Related",
] as const;
const PILLAR_LINK = "Commencement#Releasing the Rescue Ship";

const WIKI_ENVIRONMENTS: { id: string; names: readonly string[] }[] = [
  { id: "first", names: ["Distant Roost", "Titanic Plains", "Siphoned Forest", "Verdant Falls", "Viscous Falls", "Shattered Abodes", "Disturbed Impact"] },
  { id: "second", names: ["Abandoned Aqueduct", "Wetland Aspect", "Aphelian Sanctuary", "Pretender's Precipice", "Reformed Altar"] },
  { id: "third", names: ["Rallypoint Delta", "Scorched Acres", "Sulfur Pools", "Iron Alluvium", "Iron Auroras", "Damp Caverns", "Tenebrous Quagmire", "Treeborn Colony", "Golden Dieback"] },
  { id: "fourth", names: ["Abyssal Depths", "Siren's Call", "Sundered Grove", "Repurposed Crater", "Lurid Basilica", "Conduit Canyon"] },
  { id: "fifth", names: ["Sky Meadow", "Helminth Hatchery"] },
  { id: "final", names: ["Commencement"] },
  { id: "loop", names: ["Viscous Falls", "Disturbed Impact", "Iron Auroras", "Golden Dieback"] },
  { id: "colossus", names: ["Reformed Altar", "Treeborn Colony", "Prime Meridian"] },
  { id: "void-ending", names: ["Void Fields", "Void Locus", "The Planetarium"] },
  { id: "decompile", names: ["Conduit Canyon", "Solutional Haunt", "Computational Exchange", "Neural Sanctum"] },
  { id: "soulbound", names: ["Soulbound Threshold", "Terminal Lucidity"] },
  { id: "hidden-realms", names: ["A Moment, Fractured", "A Moment, Whole", "Bazaar Between Time", "Bulwark's Ambry", "Gilded Coast", "Void Fields", "Void Locus", "The Planetarium", "The Simulacrum", "Computational Exchange", "Neural Sanctum", "Soulbound Threshold", "Terminal Lucidity"] },
];

const NEWT_STAGES = [
  "Titanic Plains",
  "Distant Roost",
  "Siphoned Forest",
  "Verdant Falls",
  "Viscous Falls",
  "Shattered Abodes",
  "Disturbed Impact",
  "Abandoned Aqueduct",
  "Wetland Aspect",
  "Aphelian Sanctuary",
  "Pretender's Precipice",
  "Rallypoint Delta",
  "Scorched Acres",
  "Sulfur Pools",
  "Iron Alluvium",
  "Iron Auroras",
  "Damp Caverns",
  "Tenebrous Quagmire",
  "Abyssal Depths",
  "Siren's Call",
  "Sundered Grove",
  "Repurposed Crater",
  "Lurid Basilica",
  "Sky Meadow",
  "Helminth Hatchery",
  "Reformed Altar",
  "Treeborn Colony",
  "Golden Dieback",
] as const;

const CHALLENGE_ORDER = ["Survivors", "Items", "Equipment", "Skills", "Skins", "Artifacts"] as const;

const GROUP_LABEL: Record<string, string> = {
  Normal: "Regular Monsters",
  Boss: "Bosses",
  Special: "Special Monsters",
  "Special Boss": "Special Bosses",
  Survivors: "Survivors",
  Items: "Items",
  Equipment: "Equipment",
  Skills: "Skills",
  Skins: "Skins",
  Artifacts: "Artifacts",
  Chests: "Chests",
  Drones: "Drones",
  Shrines: "Shrines",
  Duplicators: "Printer",
  Misc: "Misc",
  "Environment Specific": "Environment Specific",
  "Charging Zones": "Charging Zones",
  Portals: "Portals",
  "Skill Related": "Skill Related",
  Interactable: "Interactable Drones & Turrets",
  Survivor: "Survivor Drones & Turrets",
  Item: "Item Drones & Turrets",
  first: "First Stages",
  second: "Second Stages",
  third: "Third Stages",
  fourth: "Fourth Stages",
  fifth: "Fifth Stages",
  final: "Final Stage",
  loop: "Loop Exclusive",
  colossus: "Path of the Colossus",
  "void-ending": "Void Ending Route",
  decompile: "Decompile Ending Route",
  soulbound: "Soulbound Threshold and Terminal Lucidity",
  "hidden-realms": "Hidden Realms",
  "internal-items": "Internal Items",
  "unfinished-items": "Unfinished Items",
  lore: "Lore",
  "internal-equipment": "Internal Equipment",
  "unfinished-equipment": "Unfinished Equipment",
};

export function ror2GroupLabel(id: string): string {
  if (/^\d+$/.test(id)) return `阶段 ${id}`;
  if (!id) return "本体";
  return GROUP_LABEL[id] ?? ror2SurvivorExpansionLabel(id);
}

export function ror2DirectoryGroups<T extends { group: string }>(
  rows: readonly T[],
  order: readonly string[],
): { id: string; label: string; rows: T[] }[] {
  const buckets = new Map<string, T[]>();
  for (const row of rows) {
    const key = row.group;
    const list = buckets.get(key);
    if (list) list.push(row);
    else buckets.set(key, [row]);
  }
  const known = new Set<string>(order);
  const keys = [
    ...order.filter((key) => buckets.has(key)),
    ...[...buckets.keys()].filter((key) => !known.has(key)).sort(),
  ];
  return keys.map((id) => ({ id, label: ror2GroupLabel(id), rows: buckets.get(id) ?? [] }));
}

export function ror2SectionGroupOrder(section: Ror2PageSectionId): readonly string[] {
  if (section === "unreleased") return ROR2_UNRELEASED_GROUPS.map((group) => group.id);
  if (section === "monsters") return WIKI_MONSTER_KINDS;
  if (section === "drones") return WIKI_DRONE_ORIGINS;
  if (section === "environments") return WIKI_ENVIRONMENTS.map((group) => group.id);
  if (section === "challenges") return CHALLENGE_ORDER;
  if (section === "artifacts") return ["Artifacts"];
  if (section === "newt-altars") return NEWT_STAGES;
  return WIKI_INTERACTABLE_CATEGORIES;
}

export function filterRor2Directory<T extends Ror2Searchable & { group: string; quote_zh?: string }>(
  rows: readonly T[],
  query: string,
  group: string,
): T[] {
  const scoped = !group || group === "all" ? [...rows] : rows.filter((row) => row.group === group);
  const needle = query.trim().toLowerCase();
  if (!needle) return scoped;
  return scoped.filter((row) =>
    [
      row.name,
      row.name_zh,
      ror2RichTextPlain(row.quote ?? ""),
      ror2RichTextPlain(row.quote_zh ?? ""),
      ror2RichTextPlain(row.description ?? ""),
      ror2RichTextPlain(row.description_zh ?? ""),
    ]
      .filter(Boolean)
      .join("\n")
      .toLowerCase()
      .includes(needle),
  );
}

export function ror2ActiveGroup(raw: string | null | undefined, rows: { group: string }[]): string {
  const cat = (raw || "").trim();
  if (!cat || cat === "all") return "all";
  return rows.some((row) => row.group === cat) ? cat : "all";
}

export function ror2SectionHref(path: string, group = "", query = ""): string {
  const params = new URLSearchParams();
  const cat = group.trim();
  const q = query.trim();
  if (cat && cat !== "all") params.set("cat", cat);
  if (q) params.set("q", q);
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

function dlcFields(expansion?: string): { dlcIconUrl: string | null; dlcLabel: string } {
  const mark = ror2DlcMark(expansion);
  return { dlcIconUrl: mark?.iconUrl ?? null, dlcLabel: mark?.label ?? "" };
}

export type Ror2DirectoryCatalog = {
  monsters: (CombatFields & {
    name: string;
    name_zh?: string;
    boss_name_zh?: string;
    kind?: string;
    role?: string;
    expansion?: string;
    boss_name?: string;
    categories?: string[];
    is_ally?: boolean;
    do_not_count?: boolean;
    is_subtype?: boolean;
    image_url?: string | null;
  })[];
  drones: (CombatFields & {
    name: string;
    name_zh?: string;
    kind?: string;
    quote?: string;
    quote_zh?: string;
    description?: string;
    description_zh?: string;
    rarity?: string;
    cost?: string;
    categories?: string[];
    type2?: string;
    image_url?: string | null;
  })[];
  environments: {
    name: string;
    name_zh?: string;
    stage?: string;
    subtitle?: string;
    subtitle_zh?: string;
    description?: string;
    description_zh?: string;
    soundtrack?: string;
    expansion?: string;
    categories?: string[];
    image_url?: string | null;
  }[];
  challenges: {
    name: string;
    name_zh?: string;
    kind?: string;
    description?: string;
    description_zh?: string;
    unlock?: string[];
    coins?: string;
    expansion?: string;
  }[];
  items?: { name: string; expansion?: string; image_url?: string | null }[];
  equipment?: { name: string; expansion?: string; image_url?: string | null }[];
  survivors?: { name: string; expansion?: string; image_url?: string | null }[];
  interactables: {
    name: string;
    name_zh?: string;
    category?: string;
    effect?: string;
    effect_zh?: string;
    expansion?: string;
    cost?: string;
    location?: string[];
    wiki_url?: string;
    link?: string;
    image_url?: string | null;
    categories?: string[];
  }[];
  artifacts: {
    name: string;
    name_zh?: string;
    description?: string;
    description_zh?: string;
    code?: string[];
    expansion?: string;
    unlock?: string;
    unlock_zh?: string;
    image_url?: string | null;
  }[];
};

/** 数据模块没有图。Wiki 画页面时用短名拼 Artifact_of_名字.png。 */
export function ror2UnlockIcon(
  name: string,
  sources: readonly { name: string; image_url?: string | null }[],
): string {
  const found = sources.find((row) => row.name === name);
  if (found?.image_url) return found.image_url;
  const file = `${name.trim()}.png`.replace(/ /g, "_");
  return `https://riskofrain2.wiki.gg/images/${encodeURI(file)}`;
}

/** 数据模块没有图。Wiki 画页面时用短名拼 Artifact_of_名字.png。 */
export function ror2ArtifactIconUrl(name: string): string {
  const file = `Artifact_of_${name.trim()}.png`.replace(/ /g, "_");
  return `https://riskofrain2.wiki.gg/images/${encodeURI(file)}`;
}

export function ror2WikiInteractables<T extends { category?: string; link?: string; name: string }>(
  rows: readonly T[],
): T[] {
  const keep = new Set<string>(WIKI_INTERACTABLE_CATEGORIES);
  const seen = new Set<string>();
  const out: T[] = [];
  for (const row of rows) {
    const category = row.category || "";
    if (!keep.has(category)) continue;
    const link = row.link || row.name;
    if (link !== PILLAR_LINK && seen.has(link)) continue;
    if (link !== PILLAR_LINK) seen.add(link);
    out.push(row);
  }
  return out;
}

export function ror2SectionRows(
  section: Ror2SectionId,
  catalog: Partial<Ror2DirectoryCatalog>,
): Ror2DirectoryRow[] {
  const monsters = (catalog.monsters ?? []).filter(
    (row) =>
      !row.is_ally &&
      !row.do_not_count &&
      !row.is_subtype &&
      WIKI_MONSTER_KINDS.includes((row.kind || "") as (typeof WIKI_MONSTER_KINDS)[number]),
  );
  const drones = (catalog.drones ?? []).filter((row) =>
    WIKI_DRONE_ORIGINS.includes((row.type2 || "") as (typeof WIKI_DRONE_ORIGINS)[number]),
  );
  const challenges = catalog.challenges ?? [];
  const artifacts = catalog.artifacts ?? [];
  const interactables = (catalog.interactables ?? []).filter((row) => !ror2IsHiddenCategory(row));
  if (section === "monsters") {
    return monsters.map((row) => ({
      name: row.name,
      name_zh: row.name_zh,
      group: row.kind || "未分类",
      quote: row.boss_name || row.role || "",
      quote_zh: row.boss_name_zh,
      description: ror2SurvivorStatLine(row),
      note: "",
      imageUrl: row.image_url ?? null,
      ...dlcFields(row.expansion),
    }));
  }
  if (section === "drones") {
    return drones.map((row) => ({
      name: row.name,
      name_zh: row.name_zh,
      group: row.type2 || "未分类",
      quote: row.quote || "",
      quote_zh: row.quote_zh,
      description: row.description || "",
      description_zh: row.description_zh,
      note: [row.cost, ror2SurvivorStatLine(row)].filter(Boolean).join(" · "),
      imageUrl: row.image_url ?? null,
    }));
  }
  if (section === "environments") {
    const byName = new Map((catalog.environments ?? []).map((row) => [row.name, row]));
    return WIKI_ENVIRONMENTS.flatMap((group) =>
      group.names.map((name) => {
        const row = byName.get(name);
        return {
          name,
          name_zh: row?.name_zh,
          group: group.id,
          quote: row?.subtitle || "",
          quote_zh: row?.subtitle_zh,
          description: row?.description || "",
          description_zh: row?.description_zh,
          note: row?.stage ? `Stage ${row.stage}` : "",
          imageUrl: row?.image_url ?? null,
          ...dlcFields(row?.expansion),
        };
      }),
    );
  }
  if (section === "challenges") {
    const icons = [...(catalog.survivors ?? []), ...(catalog.items ?? []), ...(catalog.equipment ?? []), ...(catalog.artifacts ?? [])];
    return challenges.map((row) => ({
      name: row.name,
      name_zh: row.name_zh,
      group: row.kind || "未分类",
      quote: "",
      description: row.description || "",
      description_zh: row.description_zh,
      note: "",
      imageUrl: null,
      coins: row.coins || "",
      ...dlcFields(row.expansion),
      unlocks: (row.unlock ?? []).map((name) => ({
        name,
        imageUrl: ror2UnlockIcon(name, icons),
      })),
    }));
  }
  if (section === "artifacts") {
    return artifacts.map((row) => ({
      name: row.name,
      name_zh: row.name_zh,
      group: "Artifacts",
      quote: (row.code ?? []).join(" "),
      description: row.description || "",
      description_zh: row.description_zh,
      note: row.unlock_zh || row.unlock || "",
      imageUrl: row.image_url || ror2ArtifactIconUrl(row.name),
      ...dlcFields(row.expansion),
    }));
  }
  const listed = ror2WikiInteractables(interactables);
  if (section === "newt-altars") {
    const byName = new Map((catalog.environments ?? []).map((row) => [row.name, row]));
    return NEWT_STAGES.map((name) => {
      const row = byName.get(name);
      return {
        name,
        name_zh: row?.name_zh,
        group: name,
        quote: row?.subtitle || "",
        quote_zh: row?.subtitle_zh,
        description: row?.description || "",
        description_zh: row?.description_zh,
        note: "",
        imageUrl: row?.image_url ?? null,
        ...dlcFields(row?.expansion),
      };
    });
  }
  const source = listed;
  return source.map((row) => ({
    name: row.name,
    name_zh: row.name_zh,
    group: row.category || "未分类",
    quote: row.effect || "",
    quote_zh: row.effect_zh,
    description: [row.cost, (row.location ?? []).join("、")].filter(Boolean).join(" · "),
    note: "",
    imageUrl: row.image_url ?? null,
    ...dlcFields(row.expansion),
  }));
}

type UnreleasedSource = {
  name: string;
  name_zh?: string;
  code?: string;
  description?: string;
  description_zh?: string;
  quote?: string;
  rarity?: string;
  expansion?: string;
  image_url?: string | null;
};

/** Wiki「Unreleased Items」表格里的内部名，顺序与页面一致。 */
const UNRELEASED_CODES = {
  "internal-items": [
    "AdaptiveArmor",
    "BoostAttackSpeed",
    "BoostDamage",
    "BoostEquipmentRecharge",
    "BoostHp",
    "ConvertCritChanceToCritDamage",
    "CutHp",
    "DrizzlePlayerHelper",
    "DroneWeaponsBoost",
    "DroneWeaponsDisplay1",
    "DroneWeaponsDisplay2",
    "Ghost",
    "GummyCloneIdentifier",
    "HealthDecay",
    "InvadingDoppelganger",
    "LevelBonus",
    "MinHealthPercentage",
    "MinionLeash",
    "MonsoonPlayerHelper",
    "SummonedEcho",
    "TeamSizeDamageBonus",
    "TeleportWhenOob",
    "UseAmbientLevel",
    "Voidman passiveItem",
  ],
  "unfinished-items": [
    "AACannon",
    "BurnNearby",
    "CooldownOnCrit",
    "CrippleWardOnLevel",
    "CritHeal",
    "EmpowerAlways",
    "Incubator",
    "LunarWings",
    "MageAttunement",
    "PlantOnHit",
    "PlasmaCore",
    "ScrapGreenSuppressed",
    "ScrapRedSuppressed",
    "ScrapWhiteSuppressed",
    "SkullCounter",
    "TempestOnKill",
    "WarCryOnCombat",
  ],
  "internal-equipment": ["EliteVoidEquipment"],
  "unfinished-equipment": [
    "EliteEchoEquipment",
    "EliteGoldEquipment",
    "EliteSecretSpeedEquipment",
    "EliteYellowEquipment",
    "Enigma",
    "GhostGun",
    "IrradiatingLaser",
    "LunarPortalOnUse",
    "LunarPotion",
    "OrbOnUse",
    "OrbitalLaser",
    "SoulCorruptor",
    "SoulJar",
  ],
} as const;

const UNRELEASED_LORE = [
  "Ancestral Incubator",
  "Strange Scrap, White",
  "Strange Scrap, Green",
  "Strange Scrap, Red",
  "Blessings of Terafirmae",
  "Overloading Excavator",
  "Elegy of Extinction",
  "Faulty Conductor (Equipment)",
  "G-Force Accelerator",
] as const;

function unreleasedEntry(rows: readonly UnreleasedSource[], code: string): UnreleasedSource | undefined {
  const hits = rows.filter((row) => (row.code || "").toLowerCase() === code.toLowerCase());
  return hits.find((row) => row.name.toLowerCase() === code.toLowerCase()) ?? hits[0];
}

function unreleasedRow(group: string, label: string, entry: UnreleasedSource | undefined): Ror2DirectoryRow {
  const name = entry?.name || label;
  return {
    name,
    name_zh: entry?.name_zh,
    group,
    quote: entry?.code && entry.name !== label ? entry.code : "",
    description: entry?.description || entry?.quote || "",
    description_zh: entry?.description_zh,
    note: entry?.rarity || "",
    imageUrl: entry?.image_url ?? null,
    ...dlcFields(entry?.expansion),
  };
}

export function ror2UnreleasedRows(catalog: {
  items?: readonly UnreleasedSource[];
  equipment?: readonly UnreleasedSource[];
}): Ror2DirectoryRow[] {
  const pool = [...(catalog.items ?? []), ...(catalog.equipment ?? [])];
  const rows: Ror2DirectoryRow[] = [];
  for (const group of ROR2_UNRELEASED_GROUPS) {
    if (group.id === "lore") {
      for (const name of UNRELEASED_LORE) {
        const entry = pool.find((row) => row.name === name);
        rows.push(unreleasedRow(group.id, name, entry));
      }
      continue;
    }
    const codes = UNRELEASED_CODES[group.id];
    for (const code of codes) {
      rows.push(unreleasedRow(group.id, code, unreleasedEntry(pool, code)));
    }
  }
  return rows;
}
