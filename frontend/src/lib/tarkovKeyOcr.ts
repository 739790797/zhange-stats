import {
  compactOcrText,
  normalizeOcrText,
  ocrFuzzyScore,
  ocrHitRank,
} from "@/lib/tarkovOcr";
import type { TarkovOcrWord } from "@/lib/tarkovOcrEngine";
import type { TarkovKeyPackKey, TarkovKeyPackNavItem } from "@/lib/tarkovKeyPacks";

const KEY_OCR_NOISE = new Set(
  [
    "钥匙",
    "钥匙串",
    "钥匙箱",
    "钥匙工具",
    "文件箱",
    "文件",
    "搜索",
    "全部",
    "筛选",
    "已拥有",
    "未拥有",
    "耐久",
    "用途",
    "物品",
    "仓库",
    "装备",
    "key",
    "keys",
    "keytool",
    "docs",
    "docscase",
    "sicc",
  ].map((s) => normalizeOcrText(s)),
);

/** 单独出现时太泛，不当短码。 */
const WEAK_SHORT = new Set([
  "key",
  "keys",
  "钥匙",
  "钥匙串",
  "钥匙卡",
  "工厂",
  "卡",
  "管理员",
]);

const USES_RE = /\d{1,2}\s*\/\s*\d{1,2}/g;
const LATIN_TOKEN_RE = /^[0-9a-z]+$/;

export type TarkovKeyOcrCatalogKey = Pick<
  TarkovKeyPackKey,
  "id" | "name" | "short_name" | "icon_link"
>;

export type TarkovKeyOcrMatch = {
  id: string;
  name: string;
  short_name: string;
  icon_link?: string;
  ocrText: string;
  confidence: "exact" | "fuzzy";
};

type CatalogEntry = {
  id: string;
  name: string;
  short_name: string;
  icon_link: string;
  nameKey: string;
  shortKey: string;
  compactName: string;
  compactShort: string;
  shortAliases: string[];
};

export function flattenKeyPackKeys(
  packs: Array<Pick<TarkovKeyPackNavItem, "keys">>,
): TarkovKeyOcrCatalogKey[] {
  const seen = new Set<string>();
  const out: TarkovKeyOcrCatalogKey[] = [];
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

function isWeakShortKey(value: string): boolean {
  const key = normalizeOcrText(value);
  return !key || key.length < 2 || WEAK_SHORT.has(key);
}

/** 只用短名派生别名，不从全名挖房号，避免「西203」带出 203 误打宿舍 203。 */
function shortAliases(shortName: string): string[] {
  const aliases = new Set<string>();
  const shortKey = normalizeOcrText(shortName);
  const compactShort = compactOcrText(shortName);
  if (shortKey && !WEAK_SHORT.has(shortKey)) aliases.add(shortKey);
  if (compactShort && !WEAK_SHORT.has(compactShort)) aliases.add(compactShort);
  const stripped = compactShort.replace(/key$/, "");
  if (stripped && stripped.length >= 2 && !WEAK_SHORT.has(stripped)) {
    aliases.add(stripped);
  }
  return [...aliases];
}

function catalogEntries(keys: TarkovKeyOcrCatalogKey[]): CatalogEntry[] {
  const out: CatalogEntry[] = [];
  for (const key of keys) {
    const id = (key.id || "").trim();
    if (!id) continue;
    const name = (key.name || "").trim();
    const shortName = (key.short_name || "").trim();
    const nameKey = normalizeOcrText(name);
    const shortKey = normalizeOcrText(shortName);
    if (!nameKey && !shortKey) continue;
    out.push({
      id,
      name: name || shortName || id,
      short_name: shortName,
      icon_link: (key.icon_link || "").trim(),
      nameKey,
      shortKey,
      compactName: compactOcrText(name),
      compactShort: compactOcrText(shortName),
      shortAliases: shortAliases(shortName),
    });
  }
  return out;
}

function isKeyOcrNoise(text: string): boolean {
  const key = normalizeOcrText(text);
  if (!key) return true;
  if (KEY_OCR_NOISE.has(key)) return true;
  const trimmed = text.trim();
  if (/^\d+%$/.test(trimmed)) return true;
  if (/^\d+\/\d+$/.test(trimmed)) return true;
  if (/^\d+x\d+$/i.test(key)) return true;
  return false;
}

function isNumericToken(text: string): boolean {
  return /^\d+$/.test(normalizeOcrText(text));
}

/** 宿舍「203钥匙」、东西楼「西301」这类短码，房号数字必须对上。 */
function roomKeyDigits(shortKey: string): string | null {
  const match = shortKey.match(/^(东|西)?(\d{3})(?:钥匙)?$/);
  return match ? match[2] : null;
}

function tokenRoomDigits(needle: string): string | null {
  const match = needle.match(/(?:东|西)?(\d{3})/);
  return match ? match[1] : null;
}

function hasRoomGlyphEvidence(needle: string): boolean {
  return /[\u4e00-\u9fff]/.test(needle);
}

/** 195→105、西399→西309、耐久「220%)」不当房号。 */
function allowRoomKeyScore(
  needle: string,
  entry: CatalogEntry,
  exact: boolean,
): boolean {
  const room = roomKeyDigits(entry.shortKey);
  if (!room) return true;
  const seen = tokenRoomDigits(needle);
  if (seen && seen !== room) return false;
  if (exact) return true;
  return Boolean(seen === room && hasRoomGlyphEvidence(needle));
}

function isShortLatinNeedle(needle: string): boolean {
  return LATIN_TOKEN_RE.test(needle) && needle.length < 3;
}

/** Lion / KIBA 这类短英文词差一字母就会误打 Leon / KIBA内；只接受精确短码。 */
function isPlainLatinWord(needle: string): boolean {
  return /^[a-z]+$/.test(needle) && needle.length <= 5;
}

const COLOR_CARD_REPAIR: Record<string, string> = {
  傅卡: "黑卡",
  墨卡: "黑卡",
  嘿卡: "黑卡",
};

/** 钥匙箱把「绿」「卡」拆成两行；西楼的「西」常被认成「画」。 */
export function repairKeyOcrToken(text: string): string {
  let out = (text || "").replace(/\s+/g, " ").trim();
  out = out.replace(/[|)\]]+$/g, "");
  out = out.replace(/画(?=\d{3})/g, "西");
  out = out.replace(/^w[il]?(\d{3})$/i, "西$1");
  out = out.replace(/^空自$/, "空白");
  out = out.replace(/^[#＃]1sr$/i, "#11SR");
  out = out.replace(/^3区1sr$/i, "#11SR");
  out = out.replace(/^rbav{2,}o$/i, "RB-VO");
  out = out.replace(/^enak\s*13$/i, "Chek. 13");
  out = out.replace(/^管办$/, "主管办");
  out = out.replace(/^蛇卡$/, "红卡");
  out = out.replace(/^生锈.+$/, "生锈钥匙");
  out = out.replace(/^h(\d{3})$/i, "西$1");
  out = out.replace(/^rbz?s?rh$/i, "RB-RH");
  out = out.replace(/^rb[- =]*pk(?:pm|r+)$/i, "RB-PKPM");
  out = out.replace(/^rb[- ]*rssp2$/i, "RB-PSP2");
  out = out.replace(/^管理员[铂铀角旬钼钠是匙]+$/, "管理员钥匙");
  out = out.replace(/^加油关$/, "加油站");
  out = out.replace(/^海关[物移][消流油]$/, "海关物流");
  out = COLOR_CARD_REPAIR[out] || out;
  return out;
}

function stripKeyUses(line: string): string {
  return line.replace(USES_RE, " ").replace(/\s+/g, " ").trim();
}

function isSingleCjk(text: string): boolean {
  return /^[\u4e00-\u9fff]$/.test(text.trim());
}

function joinStackedCjkLines(lines: string[]): string[] {
  const out: string[] = [];
  for (let i = 0; i < lines.length; i += 1) {
    const current = lines[i];
    const next = lines[i + 1];
    if (next && isSingleCjk(current) && isSingleCjk(next)) {
      out.push(`${current.trim()}${next.trim()}`);
      i += 1;
      continue;
    }
    out.push(current);
  }
  return out;
}

function collectKeyOcrLines(...texts: Array<string | undefined | null>): string[] {
  const lines: string[] = [];
  for (const blob of texts) {
    const raw = (blob || "").replace(/\r/g, "\n");
    if (!raw.trim()) continue;
    for (const line of raw.split("\n")) {
      const cleaned = stripKeyUses(line);
      if (cleaned) lines.push(cleaned);
    }
  }
  return joinStackedCjkLines(lines);
}

/** 从整图 OCR 抽出钥匙短码 / 名称候选。 */
export function parseKeyOcrTokens(
  ...texts: Array<string | undefined | null>
): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  const add = (raw: string) => {
    const text = repairKeyOcrToken(raw);
    if (!text || isKeyOcrNoise(text)) return;
    const key = normalizeOcrText(text);
    if (!key || key.length < 2 || seen.has(key)) return;
    if (isShortLatinNeedle(key)) return;
    seen.add(key);
    out.push(text);
  };

  for (const line of collectKeyOcrLines(...texts)) {
    add(line);
    for (const part of line.split(/[\s|/\\,;]+/)) add(part);
    for (const match of line.matchAll(/[A-Za-z]{1,5}[- .]?[A-Za-z0-9]{1,8}/g)) {
      add(match[0]);
    }
  }
  return out;
}

export function tokensFromOcrWords(words: TarkovOcrWord[] | undefined): string[] {
  if (!words?.length) return [];
  return parseKeyOcrTokens(words.map((row) => row.text).join("\n"));
}

function aliasHits(entry: CatalogEntry, needle: string, compact: string): boolean {
  if (isShortLatinNeedle(needle)) return false;
  return (
    entry.shortAliases.includes(needle) || entry.shortAliases.includes(compact)
  );
}

function scoreToken(token: string, entry: CatalogEntry): {
  rank: number;
  fuzzy: number;
  exact: boolean;
} {
  const needle = normalizeOcrText(token);
  const compact = compactOcrText(token);
  let exact = aliasHits(entry, needle, compact);
  if (entry.nameKey && (entry.nameKey === needle || entry.compactName === compact)) {
    exact = true;
  }

  const rankRaw = ocrHitRank(
    token,
    entry.name,
    isWeakShortKey(entry.short_name) ? "" : entry.short_name,
    ...entry.shortAliases,
  );
  const rank =
    rankRaw === 0 || (rankRaw === 1 && needle.length >= 5) ? rankRaw : 9;
  let fuzzy = 0;
  if (!isNumericToken(token) && !isPlainLatinWord(needle)) {
    if (entry.shortKey && !isWeakShortKey(entry.short_name) && needle.length >= 4) {
      fuzzy = Math.max(fuzzy, ocrFuzzyScore(entry.shortKey, needle));
      fuzzy = Math.max(fuzzy, ocrFuzzyScore(entry.compactShort, compact));
    }
    if (entry.nameKey && needle.length >= 4) {
      fuzzy = Math.max(fuzzy, ocrFuzzyScore(entry.nameKey, needle));
      fuzzy = Math.max(fuzzy, ocrFuzzyScore(entry.compactName, compact));
    }
  }
  if (!allowRoomKeyScore(needle, entry, exact)) {
    return { rank: 9, fuzzy: 0, exact: false };
  }
  return { rank, fuzzy, exact };
}

/** 218 已勾上时，丢掉「118钥此」这种把 2 认成 1 的宿舍号。 */
function isMisreadDormOne(
  token: string,
  entries: CatalogEntry[],
  usedIds: Set<string>,
): boolean {
  const match = normalizeOcrText(token).match(
    /^1(\d{2})([钥匙铂铀角旬钼钠是此十赤最妇到].*)$/,
  );
  if (!match) return false;
  const twin = `2${match[1]}钥匙`;
  return entries.some((entry) => usedIds.has(entry.id) && entry.shortKey === twin);
}

/** 「314铂是」这类短名头部仍在、后两字糊掉时，只打唯一的「N钥匙」。 */
function tryMarkedRoomFallback(
  token: string,
  entries: CatalogEntry[],
  usedIds: Set<string>,
): CatalogEntry | null {
  const needle = normalizeOcrText(token);
  const match = needle.match(/^(\d{3})(.+)$/);
  if (!match) return null;
  // 「314铂是」后半须像糊掉的「钥匙」；「104便局」这种乱字不走。
  if (!/[钥匙铂铀角旬钼钠是此十赤最妇到]/.test(match[2])) return null;
  const room = match[1];
  const hits = entries.filter((entry) => {
    if (usedIds.has(entry.id)) return false;
    return (
      entry.shortKey === room ||
      entry.shortKey === `${room}钥匙` ||
      entry.compactShort === `${room}钥匙` ||
      entry.shortAliases.includes(room)
    );
  });
  return hits.length === 1 ? hits[0] : null;
}

/**
 * 钥匙闭集匹配：短码优先（RatEye shortName），数字码只接受精确命中，避免 114→214。
 */
export function matchKeysFromOcr(opts: {
  tokens?: string[];
  texts?: string[];
  words?: TarkovOcrWord[];
  catalog: TarkovKeyOcrCatalogKey[];
  allowIds?: string[];
}): TarkovKeyOcrMatch[] {
  const allow = opts.allowIds?.length ? new Set(opts.allowIds) : null;
  const entries = catalogEntries(
    allow ? opts.catalog.filter((key) => allow.has(key.id)) : opts.catalog,
  );
  if (!entries.length) return [];

  const tokens = [
    ...(opts.tokens || []).map(repairKeyOcrToken),
    ...parseKeyOcrTokens(...(opts.texts || [])),
    ...tokensFromOcrWords(opts.words),
  ];
  const uniqueTokens: string[] = [];
  const seenToken = new Set<string>();
  for (const token of tokens) {
    const repaired = repairKeyOcrToken(token);
    const key = normalizeOcrText(repaired);
    if (!key || key.length < 2 || seenToken.has(key)) continue;
    if (isShortLatinNeedle(key)) continue;
    seenToken.add(key);
    uniqueTokens.push(repaired);
  }

  const matches: TarkovKeyOcrMatch[] = [];
  const usedIds = new Set<string>();

  const push = (
    entry: CatalogEntry,
    ocrText: string,
    confidence: TarkovKeyOcrMatch["confidence"],
  ) => {
    if (usedIds.has(entry.id)) return;
    usedIds.add(entry.id);
    matches.push({
      id: entry.id,
      name: entry.name,
      short_name: entry.short_name,
      icon_link: entry.icon_link || undefined,
      ocrText,
      confidence,
    });
  };

  for (const token of uniqueTokens) {
    const needle = normalizeOcrText(token);
    if (!needle || needle.length < 2 || WEAK_SHORT.has(needle)) continue;

    const exactShort = entries.filter((entry) =>
      aliasHits(entry, needle, compactOcrText(token)),
    );
    if (exactShort.length === 1) {
      push(exactShort[0], token, "exact");
      continue;
    }
    if (exactShort.length > 1) continue;
    if (isNumericToken(token)) continue;
    // 218 已命中后，不再把「118钥此」当宿舍 118（2 常被认成 1）。
    if (isMisreadDormOne(token, entries, usedIds)) continue;

    const exactName = entries.filter(
      (entry) =>
        entry.nameKey === needle || entry.compactName === compactOcrText(token),
    );
    if (exactName.length === 1) {
      push(exactName[0], token, "exact");
      continue;
    }

    const scored: Array<{
      entry: CatalogEntry;
      rank: number;
      fuzzy: number;
      exact: boolean;
    }> = [];
    for (const entry of entries) {
      if (usedIds.has(entry.id)) continue;
      const { rank, fuzzy, exact } = scoreToken(token, entry);
      const ok = exact || rank === 0 || rank === 1 || fuzzy >= 0.82;
      if (!ok) continue;
      scored.push({ entry, rank, fuzzy, exact });
    }
    scored.sort((a, b) => {
      if (a.exact !== b.exact) return a.exact ? -1 : 1;
      if (a.rank !== b.rank) return a.rank - b.rank;
      return b.fuzzy - a.fuzzy;
    });
    if (!scored.length) {
      const marked = tryMarkedRoomFallback(token, entries, usedIds);
      if (marked) push(marked, token, "fuzzy");
      continue;
    }
    const best = scored[0];
    const second = scored[1];
    if (
      second &&
      !best.exact &&
      best.rank === second.rank &&
      Math.abs(best.fuzzy - second.fuzzy) < 0.06
    ) {
      continue;
    }
    if (!best.exact && best.rank > 1 && best.fuzzy < 0.82) continue;
    push(best.entry, token, best.exact || best.rank === 0 ? "exact" : "fuzzy");
  }

  return matches;
}
