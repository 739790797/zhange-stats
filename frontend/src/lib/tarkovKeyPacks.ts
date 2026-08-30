import {
  TARKOV_BARTERS_PATH,
  TARKOV_CRAFTS_PATH,
  TARKOV_MAPS,
  tarkovHideoutHref,
  tarkovMapSlug,
  tarkovTaskHref,
} from "@/lib/tarkovHomeNav";
import { formatMoney } from "@/lib/tarkovItemFormat";
import { itemHrefFromTypes } from "@/lib/tarkovItemTypes";

export const TARKOV_KEY_PACKS_STORAGE_KEY = "zhange.guides.tarkov.keyPacks.v1";
export const UNBOUND_PACK_SLUG = "unbound";
export const COMMUNITY_KEY_HINT = "来源非官方 API（社区百科归包，门锁未收录）";

export type TarkovKeyOwnedFilter = "all" | "missing" | "owned";

export type TarkovKeySourceKind = "barter" | "craft" | "task" | "flea";
export type TarkovKeyTagKind = TarkovKeySourceKind | "uses" | "access";

export type TarkovKeyPackSources = {
  barters?: Array<{
    trader_slug?: string;
    trader_name?: string;
    min_trader_level?: number;
  }>;
  crafts?: Array<{
    station_slug?: string;
    station_name?: string;
    level?: number;
  }>;
  tasks?: Array<{ id: string; name?: string }>;
  flea?: { price?: number | null } | null;
};

export type TarkovKeySourceTag = {
  kind: TarkovKeyTagKind;
  label: string;
  hint: string;
  href?: string;
};

export type TarkovKeyPackKey = {
  id: string;
  name?: string;
  short_name?: string;
  icon_link?: string;
  types?: string[] | null;
  lock_count?: number;
  access?: boolean;
  community?: boolean;
  uses?: number | null;
  sources?: TarkovKeyPackSources | null;
};

export type TarkovKeyPackMap = {
  slug: string;
  name: string;
  english?: string;
  keys?: TarkovKeyPackKey[];
};

export type TarkovKeyPackNavItem = {
  slug: string;
  name: string;
  english: string;
  homeId?: string;
  icon?: string;
  keys: TarkovKeyPackKey[];
};

export type TarkovKeyPackOwnedState = {
  v: 1;
  owned: string[];
  migrated?: boolean;
};

function asIdList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (id): id is string => typeof id === "string" && id.trim().length > 0,
  );
}

export function parseOwnedState(raw: string | null | undefined): string[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as Partial<TarkovKeyPackOwnedState> | string[];
    if (Array.isArray(parsed)) return asIdList(parsed);
    if (parsed && parsed.v === 1) return asIdList(parsed.owned);
  } catch {
    /* ignore */
  }
  return [];
}

export function loadOwnedIds(): string[] {
  try {
    return parseOwnedState(localStorage.getItem(TARKOV_KEY_PACKS_STORAGE_KEY));
  } catch {
    return [];
  }
}

export function saveOwnedIds(ids: string[], migrated = false): void {
  const state: TarkovKeyPackOwnedState = {
    v: 1,
    owned: asIdList(ids),
    ...(migrated ? { migrated: true } : {}),
  };
  try {
    localStorage.setItem(TARKOV_KEY_PACKS_STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* ignore quota / private mode */
  }
}

/** 本机勾选尚未迁到账号时取出；已迁过返回 null。 */
export function takeLocalOwnsForMigrate(): string[] | null {
  try {
    const raw = localStorage.getItem(TARKOV_KEY_PACKS_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<TarkovKeyPackOwnedState>;
    if (parsed && parsed.v === 1 && parsed.migrated) return null;
    const ids = parseOwnedState(raw);
    return ids.length ? ids : null;
  } catch {
    return null;
  }
}

export function markOwnsMigrated(ids: string[]): void {
  saveOwnedIds(ids, true);
}

export function toggleOwnedId(owned: string[], itemId: string): string[] {
  const id = itemId.trim();
  if (!id) return [...owned];
  const next = new Set(owned);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return [...next];
}

export function packOwnedCount(
  keys: TarkovKeyPackKey[],
  owned: Set<string>,
): { have: number; total: number } {
  let have = 0;
  for (const key of keys) {
    if (owned.has(key.id)) have += 1;
  }
  return { have, total: keys.length };
}

export function isCommunityKeyBind(
  key: Pick<TarkovKeyPackKey, "community">,
): boolean {
  return key.community === true;
}

export function formatKeyUses(uses: number | null | undefined): string {
  if (uses == null || !Number.isFinite(uses) || uses < 0) return "";
  if (uses === 0) return "无限";
  return String(Math.trunc(uses));
}

export function formatKeyTagLine(tag: Pick<TarkovKeySourceTag, "label" | "hint">): string {
  const hint = (tag.hint || "").trim();
  return hint ? `${tag.label}：${hint}` : tag.label;
}

export function formatKeyMetaTags(key: TarkovKeyPackKey): TarkovKeySourceTag[] {
  const tags: TarkovKeySourceTag[] = [];
  const uses = formatKeyUses(key.uses);
  if (uses) tags.push({ kind: "uses", label: "最大耐久", hint: uses });
  if (key.access) tags.push({ kind: "access", label: "入场", hint: "" });
  return tags;
}

function uniqueHints(values: Array<string | undefined>): string {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of values) {
    const text = (raw || "").trim();
    if (!text || seen.has(text)) continue;
    seen.add(text);
    out.push(text);
  }
  return out.join(" · ");
}

export function isPlaceholderTaskName(name: string | undefined): boolean {
  const text = (name || "").trim();
  if (!text) return true;
  if (/\sname$/i.test(text)) return true;
  return /^[a-f0-9]{24}$/i.test(text);
}

export function formatKeySourceTags(key: TarkovKeyPackKey): TarkovKeySourceTag[] {
  const sources = key.sources;
  const q = encodeURIComponent(key.name || key.short_name || key.id);
  const tags: TarkovKeySourceTag[] = [];
  const barters = sources?.barters || [];
  if (barters.length) {
    tags.push({
      kind: "barter",
      label: "以物易物",
      hint: uniqueHints(
        barters.map((row) => {
          const name = row.trader_name || row.trader_slug || "";
          const level = Number(row.min_trader_level || 0);
          return level > 0 ? `${name} ${level}级` : name;
        }),
      ),
      href: `${TARKOV_BARTERS_PATH}?q=${q}`,
    });
  }
  const crafts = sources?.crafts || [];
  if (crafts.length) {
    const first = crafts[0];
    tags.push({
      kind: "craft",
      label: "藏身处制作",
      hint: uniqueHints(
        crafts.map((row) => {
          const name = row.station_name || row.station_slug || "";
          const level = Number(row.level || 0);
          return level > 0 ? `${name} ${level}级` : name;
        }),
      ),
      href: first?.station_slug
        ? tarkovHideoutHref(first.station_slug)
        : `${TARKOV_CRAFTS_PATH}?q=${q}`,
    });
  }
  const tasks = sources?.tasks || [];
  if (tasks.length) {
    const first = tasks[0];
    tags.push({
      kind: "task",
      label: "任务奖励",
      hint: uniqueHints(
        tasks.map((row) =>
          isPlaceholderTaskName(row.name) ? "" : row.name,
        ),
      ),
      href: first?.id ? tarkovTaskHref(first.id) : undefined,
    });
  }
  if (sources?.flea) {
    const price = sources.flea.price;
    tags.push({
      kind: "flea",
      label: "跳蚤市场",
      hint:
        price != null && Number.isFinite(price) && price > 0
          ? formatMoney(price)
          : "可上架",
      href: itemHrefFromTypes(key.id, key.types || []),
    });
  }
  return tags;
}

export function keyMatchesQuery(key: TarkovKeyPackKey, q: string): boolean {
  const needle = q.trim().toLowerCase();
  if (!needle) return true;
  const hay = [key.name, key.short_name, key.id]
    .map((part) => String(part || "").toLowerCase())
    .join(" ");
  return hay.includes(needle);
}

export function filterPackKeys(
  keys: TarkovKeyPackKey[],
  q: string,
  filter: TarkovKeyOwnedFilter,
  owned: Set<string>,
): TarkovKeyPackKey[] {
  return keys.filter((key) => {
    if (!keyMatchesQuery(key, q)) return false;
    if (filter === "owned") return owned.has(key.id);
    if (filter === "missing") return !owned.has(key.id);
    return true;
  });
}

export function readOwnedFilter(
  raw: string | null | undefined,
): TarkovKeyOwnedFilter {
  if (raw === "owned" || raw === "missing") return raw;
  return "all";
}

export function resolvePackSlug(
  requested: string | null | undefined,
  slugs: string[],
): string {
  if (!slugs.length) return UNBOUND_PACK_SLUG;
  const raw = (requested || "").trim().toLowerCase();
  if (!raw) return slugs[0];
  const canon = raw === UNBOUND_PACK_SLUG ? UNBOUND_PACK_SLUG : tarkovMapSlug(raw);
  const hit = slugs.find(
    (slug) =>
      slug === raw || slug === canon || tarkovMapSlug(slug) === canon,
  );
  return hit || slugs[0];
}

export function firstPackSlugForQuery(
  packs: TarkovKeyPackNavItem[],
  q: string,
): string | null {
  const needle = q.trim();
  if (!needle) return null;
  for (const pack of packs) {
    if (pack.keys.some((key) => keyMatchesQuery(key, needle))) {
      return pack.slug;
    }
  }
  return null;
}

export function buildKeyPackNav(
  maps: TarkovKeyPackMap[],
  unbound: TarkovKeyPackKey[],
): TarkovKeyPackNavItem[] {
  const bySlug = new Map(maps.map((row) => [row.slug, row]));
  const used = new Set<string>();
  const out: TarkovKeyPackNavItem[] = [];

  for (const home of TARKOV_MAPS) {
    if (home.comingSoon || home.status === "soon") continue;
    const slug = tarkovMapSlug(home.id);
    const api = bySlug.get(slug) || bySlug.get(home.id);
    if (api) used.add(api.slug);
    out.push({
      slug,
      name: home.label || api?.name || slug,
      english: home.english,
      homeId: home.id,
      icon: home.icon,
      keys: api?.keys || [],
    });
  }

  for (const row of maps) {
    if (used.has(row.slug)) continue;
    out.push({
      slug: row.slug,
      name: row.name,
      english: row.english || "",
      keys: row.keys || [],
    });
  }

  if (unbound.length) {
    out.push({
      slug: UNBOUND_PACK_SLUG,
      name: "未绑定地图",
      english: "Unbound",
      keys: unbound,
    });
  }
  return out;
}
