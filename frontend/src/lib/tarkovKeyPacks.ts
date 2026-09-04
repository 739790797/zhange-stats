import type { QueryClient } from "@tanstack/react-query";
import {
  TARKOV_BARTERS_PATH,
  TARKOV_CRAFTS_PATH,
  TARKOV_MAPS,
  tarkovHideoutHref,
  tarkovMapSlug,
  tarkovTaskHref,
  traderDisplayName,
} from "@/lib/tarkovHomeNav";
import { formatMoney } from "@/lib/tarkovItemFormat";
import { itemHrefFromTypes } from "@/lib/tarkovItemTypes";

export const TARKOV_KEY_PACKS_STORAGE_KEY = "zhange.guides.tarkov.keyPacks.v1";
export const ALL_PACK_SLUG = "all";
export const UNBOUND_PACK_SLUG = "unbound";
export const COMMUNITY_KEY_HINT = "来源非官方 API（社区百科归包，门锁未收录）";

export type TarkovKeyOwnedFilter = "all" | "missing" | "owned";

export type TarkovKeySourceKind = "barter" | "craft" | "task" | "flea";
export type TarkovKeyTagKind =
  | TarkovKeySourceKind
  | "uses"
  | "access"
  | "lock"
  | "power"
  | "need";

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

export type TarkovKeyUsedInTask = {
  id: string;
  name?: string;
  notes?: string[];
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
  description?: string;
  lock_types?: string[] | null;
  needs_power?: boolean;
  used_in_tasks?: TarkovKeyUsedInTask[] | null;
  sources?: TarkovKeyPackSources | null;
};

const LOCK_TYPE_ZH: Record<string, string> = {
  door: "门",
  opening: "门",
  container: "容器",
  crate: "容器",
  drawer: "抽屉",
  trunk: "后备箱",
  vehicle: "后备箱",
  hatch: "舱口",
  gate: "大门",
  safe: "保险箱",
};

const LOCK_INFER_RULES: Array<{ label: string; pattern: RegExp }> = [
  { label: "保险箱", pattern: /保险箱|保险柜|\bsafe\b/i },
  { label: "后备箱", pattern: /后备箱|行李箱|\btrunk\b/i },
  { label: "抽屉", pattern: /抽屉|\bdrawer\b/i },
  { label: "容器", pattern: /容器|柜子|箱子|\bcontainer\b|\bcrate\b/i },
  { label: "舱口", pattern: /舱口|舱盖|\bhatch\b/i },
  { label: "大门", pattern: /大门|\bgate\b/i },
  { label: "门", pattern: /门|房间|控制室|办公室|宿舍|公寓|\bdoor\b|\broom\b/i },
];

const MAX_NEED_TAGS = 3;

export function lockTypeLabel(raw: string | undefined): string {
  const key = (raw || "").trim();
  if (!key) return "";
  return LOCK_TYPE_ZH[key.toLowerCase()] || key;
}

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

export const TARKOV_KEY_OWNS_QUERY_KEY = ["guides-tarkov-key-owns"] as const;

/** 账号钥匙拥有写入缓存，并让钥匙管理 / 房间快照一起刷新。 */
export function applyTarkovKeyOwnsCache(
  queryClient: QueryClient,
  ids: string[],
): void {
  markOwnsMigrated(ids);
  queryClient.setQueryData(TARKOV_KEY_OWNS_QUERY_KEY, { item_ids: ids });
  void queryClient.invalidateQueries({ queryKey: ["guides-tarkov-raid-room"] });
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
          const name = traderDisplayName(
            row.trader_slug || "",
            row.trader_name || "",
          );
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

const OBTAIN_LABEL: Record<string, string> = {
  barter: "商人",
  craft: "制作",
  task: "任务",
};

export function isKeySpawnHint(text: string | undefined): boolean {
  const value = (text || "").trim();
  if (!value) return false;
  if (/夹克/.test(value) && /找到|房间/.test(value)) return true;
  if (/刷新于|掉落于|出自/.test(value)) return true;
  return /(?:可以)?在.+?(找到|刷新|掉落)/.test(value);
}

export function splitKeyDescription(description?: string): {
  usage: string;
  spawn: string;
} {
  const text = (description || "").trim();
  if (!text) return { usage: "", spawn: "" };
  const chunks = text
    .split(/(?<=[。！？；;!?\n])/)
    .map((part) => part.trim())
    .filter(Boolean);
  const usage: string[] = [];
  const spawn: string[] = [];
  for (const chunk of chunks.length ? chunks : [text]) {
    if (isKeySpawnHint(chunk)) spawn.push(chunk);
    else usage.push(chunk);
  }
  return { usage: usage.join(""), spawn: spawn.join("") };
}

export function formatKeyUsageText(key: TarkovKeyPackKey): string {
  const { usage } = splitKeyDescription(key.description);
  if (!usage) return "";
  const compact = usage.replace(/[。.\s]/g, "");
  const name = (key.name || "").replace(/[。.\s]/g, "");
  if (name && compact === name) return "";
  return usage;
}

export function formatKeyObtainTags(key: TarkovKeyPackKey): TarkovKeySourceTag[] {
  return formatKeySourceTags(key)
    .filter((tag) => tag.kind !== "flea")
    .map((tag) => ({
      ...tag,
      label: OBTAIN_LABEL[tag.kind] || tag.label,
    }));
}

export function formatKeyFleaTag(
  key: TarkovKeyPackKey,
): TarkovKeySourceTag | null {
  return formatKeySourceTags(key).find((tag) => tag.kind === "flea") || null;
}

export function formatKeyUsageMarks(key: TarkovKeyPackKey): string[] {
  const marks: string[] = [];
  if (key.access) marks.push("入场");
  if (key.needs_power) marks.push("需供电");
  return marks;
}

export function inferLockTypesFromText(
  ...texts: Array<string | undefined>
): string[] {
  const hay = texts.map((part) => part || "").join(" ");
  if (!hay.trim()) return [];
  const out: string[] = [];
  for (const rule of LOCK_INFER_RULES) {
    if (rule.pattern.test(hay) && !out.includes(rule.label)) {
      out.push(rule.label);
    }
  }
  return out;
}

export function formatKeyLockTypes(key: TarkovKeyPackKey): string[] {
  const fromApi: string[] = [];
  for (const raw of key.lock_types || []) {
    const label = lockTypeLabel(raw);
    if (label && !fromApi.includes(label)) fromApi.push(label);
  }
  if (fromApi.length) return fromApi;
  const inferred = inferLockTypesFromText(
    key.description,
    key.name,
    key.short_name,
  );
  if (inferred.length) return inferred;
  if ((key.lock_count || 0) > 0) return ["门"];
  return [];
}

export function formatKeyLockTypeLine(key: TarkovKeyPackKey): string {
  return formatKeyLockTypes(key).join(" · ");
}

export function formatKeyUsageNeedTags(
  key: TarkovKeyPackKey,
): TarkovKeySourceTag[] {
  return formatKeyUsageTags(key).filter((tag) => tag.kind === "need");
}

export function keyUsesSortValue(key: TarkovKeyPackKey): number {
  if (key.uses == null || !Number.isFinite(key.uses) || key.uses < 0) return -1;
  if (key.uses === 0) return Number.POSITIVE_INFINITY;
  return key.uses;
}

export function keyFleaSortValue(key: TarkovKeyPackKey): number {
  const price = key.sources?.flea?.price;
  if (price != null && Number.isFinite(price) && price > 0) return price;
  if (key.sources?.flea) return 0;
  return -1;
}

export function keyLockTypeSortValue(key: TarkovKeyPackKey): string {
  return formatKeyLockTypeLine(key);
}

export function formatKeyUsageTags(key: TarkovKeyPackKey): TarkovKeySourceTag[] {
  const tags: TarkovKeySourceTag[] = [];
  const types = (key.lock_types || [])
    .map((row) => lockTypeLabel(row))
    .filter(Boolean);
  if (types.length) {
    tags.push({ kind: "lock", label: "门锁", hint: uniqueHints(types) });
  }
  if (key.needs_power) {
    tags.push({ kind: "power", label: "需供电", hint: "" });
  }
  const tasks = key.used_in_tasks || [];
  for (const task of tasks.slice(0, MAX_NEED_TAGS)) {
    const notes = (task.notes || []).filter(
      (note) =>
        note.trim() &&
        !isPlaceholderTaskName(note) &&
        !isKeySpawnHint(note),
    );
    tags.push({
      kind: "need",
      label: "任务需要",
      hint: uniqueHints([
        isPlaceholderTaskName(task.name) ? "" : task.name,
        ...notes,
      ]),
      href: task.id ? tarkovTaskHref(task.id) : undefined,
    });
  }
  if (tasks.length > MAX_NEED_TAGS) {
    tags.push({
      kind: "need",
      label: "任务需要",
      hint: `另有 ${tasks.length - MAX_NEED_TAGS} 个任务`,
    });
  }
  return tags;
}

export function keyMatchesQuery(key: TarkovKeyPackKey, q: string): boolean {
  const needle = q.trim().toLowerCase();
  if (!needle) return true;
  const parts: Array<string | undefined> = [
    key.name,
    key.short_name,
    key.id,
    key.description,
  ];
  if (key.access) parts.push("入场");
  if (key.needs_power) parts.push("供电", "需供电");
  for (const label of formatKeyLockTypes(key)) {
    parts.push(label, "门锁");
  }
  for (const task of key.used_in_tasks || []) {
    parts.push(task.name, ...(task.notes || []));
  }
  for (const task of key.sources?.tasks || []) {
    parts.push(task.name);
  }
  const hay = parts
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

export function isAllPackSlug(slug: string | null | undefined): boolean {
  const raw = (slug || "").trim().toLowerCase();
  return !raw || raw === ALL_PACK_SLUG;
}

export function collectPackKeys(
  packs: Array<Pick<TarkovKeyPackNavItem, "keys">>,
): TarkovKeyPackKey[] {
  const seen = new Set<string>();
  const out: TarkovKeyPackKey[] = [];
  for (const pack of packs) {
    for (const key of pack.keys || []) {
      const id = (key.id || "").trim();
      if (!id || seen.has(id)) continue;
      seen.add(id);
      out.push(key);
    }
  }
  return out;
}

export function resolvePackSlug(
  requested: string | null | undefined,
  slugs: string[],
): string {
  const raw = (requested || "").trim().toLowerCase();
  if (!raw || raw === ALL_PACK_SLUG) return ALL_PACK_SLUG;
  if (!slugs.length) return ALL_PACK_SLUG;
  const canon = raw === UNBOUND_PACK_SLUG ? UNBOUND_PACK_SLUG : tarkovMapSlug(raw);
  const hit = slugs.find(
    (slug) =>
      slug === raw || slug === canon || tarkovMapSlug(slug) === canon,
  );
  return hit || ALL_PACK_SLUG;
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
