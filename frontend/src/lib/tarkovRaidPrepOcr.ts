import { RAID_PREP_MAX_SELECTED } from "@/lib/tarkovRaidPrep";

/** 游戏任务页表格区相对全屏裁切（16:9，含「任务」列与行文本）。 */
export const RAID_PREP_OCR_LIST_CROP = {
  x: 0.1,
  y: 0.17,
  w: 0.58,
  h: 0.78,
} as const;

/** 裁切后放大倍数；与 {@link RAID_PREP_OCR_DPI} 对齐供 Tesseract 估算字高。 */
export const RAID_PREP_OCR_SCALE = 2;

/** Tesseract `user_defined_dpi`；未设时易按低分辨率误估导致漏行。 */
export const RAID_PREP_OCR_DPI = 200;

/** 优先支持的分辨率（同 16:9，裁切比例可复用）。 */
export const RAID_PREP_OCR_PREFERRED_SIZES = [
  { width: 1920, height: 1080 },
  { width: 2560, height: 1440 },
] as const;

/** UI 噪词：不像任务名，直接丢掉。 */
const OCR_NOISE_EXACT = new Set(
  [
    "任务",
    "任务列表",
    "商人",
    "类型",
    "分类",
    "接受",
    "完成",
    "进行中",
    "已完成",
    "失败",
    "可用",
    "锁定",
    "每日",
    "每周",
    "行动任务",
    "角色",
    "藏身处",
    "技能",
    "地图",
    "商人处",
    "目标",
    "奖励",
    "状态",
    "地点",
    "进度",
    "全部",
    "筛选",
    "搜索",
    "主线任务",
    "支线任务",
    "进行中!",
  ].map((s) => normalizeOcrText(s)),
);

/** 行尾地点 / 状态词，解析任务名时剥掉。 */
const OCR_LINE_TAIL_WORDS = [
  "任意地点",
  "塔科夫街区",
  "塔科夫",
  "海岸线",
  "储备站",
  "海关",
  "工厂",
  "灯塔",
  "街区",
  "进行中!",
  "进行中",
  "已完成",
  "失败",
  "进行",
  "进行:",
  "进行*",
] as const;

const OCR_TOKEN_RE = /[0-9a-zA-Z]+|[\u4e00-\u9fff]+/g;
const OCR_COMPACT_RE = /[\s\-_.·•]+/g;

export type RaidPrepOcrCatalogTask = {
  id: string;
  name?: string | null;
  normalized_name?: string | null;
  map_name?: string | null;
  trader_slug?: string | null;
  trader_name?: string | null;
};

export type RaidPrepOcrMatch = {
  id: string;
  name: string;
  ocrText: string;
  trader_slug?: string;
  trader_name?: string;
};

export type RaidPrepOcrCropRect = {
  x: number;
  y: number;
  width: number;
  height: number;
};

/** 与后端 search.compact_text 对齐，便于 OCR「医疗隐私-5」对目录「医疗隐私 - Part 5」。 */
export function compactOcrText(text: string): string {
  return (text || "")
    .trim()
    .toLowerCase()
    .replace(OCR_COMPACT_RE, "")
    .replace(/part/g, "");
}

export function ocrSearchTokens(text: string): string[] {
  const out: string[] = [];
  for (const match of (text || "").matchAll(OCR_TOKEN_RE)) {
    out.push(match[0].toLowerCase());
  }
  return out;
}

/** 越小越靠前；null 表示未命中。 */
export function ocrHitRank(needle: string, ...fields: string[]): number | null {
  const compactQ = compactOcrText(needle);
  const tokens = ocrSearchTokens(needle);
  if (!compactQ && !tokens.length) return null;
  let best: number | null = null;
  for (const field of fields) {
    const hay = String(field || "");
    if (!hay) continue;
    const compactH = compactOcrText(hay);
    const lowerH = hay.toLowerCase();
    if (compactQ && compactH === compactQ) return 0;
    if (compactQ && compactH.startsWith(compactQ)) {
      best = best === null ? 1 : Math.min(best, 1);
      continue;
    }
    if (compactQ && compactH.includes(compactQ)) {
      const ratio = compactQ.length / Math.max(compactH.length, 1);
      if (compactQ.length >= 4 || ratio >= 0.55) {
        best = best === null ? 2 : Math.min(best, 2);
      }
      continue;
    }
    if (compactQ && compactQ.includes(compactH) && compactH.length >= 4) {
      best = best === null ? 2 : Math.min(best, 2);
      continue;
    }
    if (
      tokens.length &&
      tokens.every((t) => lowerH.includes(t) || compactH.includes(t))
    ) {
      best = best === null ? 3 : Math.min(best, 3);
    }
  }
  return best;
}

/** 去空白、标点、全角，便于比对。 */
export function normalizeOcrText(value: string): string {
  return (value || "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[\s\u3000]+/g, "")
    .replace(
      /[·•・．.。,，、:：;；!！?？"'“”‘’（）()【】[\]<>《》\-_—–−_/\\|]+/g,
      "",
    )
    .replace(/…+/g, "");
}

export function isPreferredRaidPrepOcrSize(
  width: number,
  height: number,
): boolean {
  return RAID_PREP_OCR_PREFERRED_SIZES.some(
    (size) => size.width === width && size.height === height,
  );
}

/** 是否接近 16:9（允许轻微黑边误差）。 */
export function isNearWidescreen(width: number, height: number): boolean {
  if (width < 800 || height < 450) return false;
  const ratio = width / height;
  return ratio >= 1.7 && ratio <= 1.85;
}

export function raidPrepOcrListCropRect(
  width: number,
  height: number,
): RaidPrepOcrCropRect {
  const ratio = width / height;
  const crop = {
    x: RAID_PREP_OCR_LIST_CROP.x,
    y: RAID_PREP_OCR_LIST_CROP.y,
    w: RAID_PREP_OCR_LIST_CROP.w,
    h: RAID_PREP_OCR_LIST_CROP.h as number,
  };
  // 窗口偏高（非 16:9）时任务列表下沿更低，需向下多裁一些
  if (ratio < 1.75) {
    crop.h = Math.min(0.84, crop.h + (1.75 - ratio) * 0.28);
  }
  return {
    x: Math.round(width * crop.x),
    y: Math.round(height * crop.y),
    width: Math.max(1, Math.round(width * crop.w)),
    height: Math.max(1, Math.round(height * crop.h)),
  };
}

/** 合并多次 OCR 原文，去重后解析为任务名行。 */
export function mergeOcrRawTexts(...texts: string[]): string[] {
  return parseOcrTaskLines(texts.filter(Boolean).join("\n"));
}

/** 目录名去掉「 - Part N」等后缀，便于「宕教」对「邪教 - Part 1」。 */
export function ocrCatalogShortName(name: string): string {
  const head = (name || "").split(/\s*-\s*/)[0]?.trim() || "";
  return normalizeOcrText(head);
}

/** 目录里的 Part 序号（「 - Part 3」→ `"3"`）。 */
export function ocrCatalogPartNumber(name: string): string | null {
  const m = (name || "").match(/part\s*(\d+)/i);
  return m?.[1] ?? null;
}

export function ocrGuessPartInfo(nameGuess: string): {
  base: string;
  part: string | null;
} {
  const trimmed = (nameGuess || "").trim();
  const partMatch = trimmed.match(/(?:-\s*|[\s"'"'·•]+)(\d+)\s*$/);
  const part = partMatch?.[1] ?? null;
  let base = trimmed;
  if (partMatch && partMatch.index !== undefined) {
    base = trimmed.slice(0, partMatch.index).replace(/[\s\-·•"'""'']+$/, "");
  }
  base = base.replace(/^[^\u4e00-\u9fffA-Za-z0-9]+/, "").trim();
  return { base: normalizeOcrText(base), part };
}

/** 把 OCR 全文拆成候选任务名行。 */
export function parseOcrTaskLines(text: string): string[] {
  const raw = (text || "")
    .replace(/\r/g, "\n")
    .split("\n")
    .map((line) => line.replace(/\s+/g, " ").trim())
    .filter(Boolean);

  const out: string[] = [];
  const seen = new Set<string>();
  for (const line of raw) {
    const cleaned = extractTaskNameFromOcrLine(line);
    if (!cleaned) continue;
    if (isLikelyLocationOrStatusLine(cleaned)) continue;
    const key = normalizeOcrText(cleaned);
    if (!key || seen.has(key)) continue;
    if (OCR_NOISE_EXACT.has(key)) continue;
    if (key.length < 2) continue;
    // 纯数字 / 进度条残渣
    if (/^[\d.%／/ea]+$/i.test(cleaned)) continue;
    seen.add(key);
    out.push(cleaned);
  }
  return out;
}

/** 剥掉商人图标列 OCR 噪点（加 。 / 除 契。渤。），保留「各而 - 1」类任务名。 */
function stripMerchantPrefix(text: string): string {
  let out = text;
  while (/^[\u4e00-\u9fff]{1,2}\s*[。．.、]/.test(out)) {
    out = out.replace(/^[\u4e00-\u9fff]{1,2}\s*[。．.、]+\s*/, "");
  }
  out = out.replace(
    /^[\u4e00-\u9fff]{1}\s+(?=[\u4e00-\u9fff]{1,2}\s*[。．.、])/,
    "",
  );
  while (/^[\u4e00-\u9fff]{1,2}\s*[。．.、]/.test(out)) {
    out = out.replace(/^[\u4e00-\u9fff]{1,2}\s*[。．.、]+\s*/, "");
  }
  // 国 酌 士 → 隐士：无标点单行图标 + 两字任务名
  out = out.replace(
    /^[\u4e00-\u9fff]\s+([\u4e00-\u9fff]\s+[\u4e00-\u9fff])\s*$/,
    "$1",
  );
  return out.trim();
}

/** 从表格整行 OCR 文本里抽出任务名列。 */
export function extractTaskNameFromOcrLine(line: string): string {
  let text = line.replace(/\s+/g, " ").trim();
  text = text.replace(/\d+%/g, " ").replace(/[%ea]/gi, " ");
  for (const word of OCR_LINE_TAIL_WORDS) {
    const idx = text.indexOf(word);
    if (idx > 2) text = text.slice(0, idx).trim();
  }
  text = text.replace(/^[^\u4e00-\u9fffA-Za-z0-9]+/, "");
  text = stripMerchantPrefix(text);
  const match = text.match(
    /[\u4e00-\u9fff][\u4e00-\u9fffA-Za-z0-9\s\-·•"'""'']{1,48}/,
  );
  if (match) {
    text = match[0].replace(/\s+/g, " ").trim();
  }
  text = text.replace(/["'"'·•]+(\d+)\s*$/, " - $1");
  if (!/\d/.test(text)) {
    const partTail = line.match(
      /[\u4e00-\u9fff][\s\-·•"'""'']{0,4}(\d+)(?:\s*%|\s|$)/,
    );
    if (partTail) {
      text = `${text.replace(/[\s\-·•"'""'']+$/, "")} - ${partTail[1]}`;
    }
  }
  text = text.replace(/\s+[A-Za-z]{1,3}$/, "").trim();
  return text;
}

/** 单列 OCR 模式下，地点列 / 状态 / 进度会单独成行，需滤掉。 */
export function isLikelyLocationOrStatusLine(text: string): boolean {
  const t = text.trim();
  if (!t) return true;
  if (/^进行中!?$/i.test(t)) return true;
  if (/^[\d.%@/\\\[\]TtFf]+$/i.test(t)) return true;
  if (
    /^(任意地点|中心区|工厂|灯塔|海关|海岸线|储备站|街区|海找玉|海央线)$/.test(
      t,
    )
  ) {
    return true;
  }
  if (/科夫街区$/.test(t)) return true;
  if (/^塔科夫街区$/.test(t)) return true;
  if (t.length <= 2 && !/^[\u4e00-\u9fff]{2,}$/.test(t)) return true;
  return false;
}

function levenshtein(a: string, b: string): number {
  if (a === b) return 0;
  if (!a.length) return b.length;
  if (!b.length) return a.length;
  const prev = new Array<number>(b.length + 1);
  const curr = new Array<number>(b.length + 1);
  for (let j = 0; j <= b.length; j += 1) prev[j] = j;
  for (let i = 1; i <= a.length; i += 1) {
    curr[0] = i;
    for (let j = 1; j <= b.length; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      curr[j] = Math.min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost);
    }
    for (let j = 0; j <= b.length; j += 1) prev[j] = curr[j];
  }
  return prev[b.length];
}

function isSuffixFragment(guessBase: string, catalogShort: string): boolean {
  return (
    catalogShort.endsWith(guessBase) &&
    !catalogShort.startsWith(guessBase) &&
    guessBase.length < catalogShort.length * 0.75
  );
}

function hasExplicitPartSuffix(nameGuess: string): boolean {
  const t = nameGuess.trim();
  if (/-\s*\d+\s*$/.test(t) || /["'"']\d+\s*$/.test(t)) return true;
  const compact = normalizeOcrText(t);
  return /[\u4e00-\u9fff]+\d+$/.test(compact) && compact.length >= 3;
}

function scoreLineAgainstEntry(
  nameGuess: string,
  needleKey: string,
  entry: CatalogEntry,
): { rank: number; fuzzy: number } {
  const rank = ocrHitRank(nameGuess, entry.name, entry.normalizedKey);
  let fuzzy = 0;
  for (const catalogKey of [entry.key, entry.shortKey].filter(Boolean)) {
    fuzzy = Math.max(fuzzy, fuzzyScore(catalogKey, needleKey));
  }
  fuzzy = Math.max(fuzzy, scorePartNumberMatch(nameGuess, entry.name));
  return { rank: rank ?? 9, fuzzy };
}

function tryWeakPartFallback(
  nameGuess: string,
  entries: CatalogEntry[],
  usedIds: Set<string>,
): CatalogEntry | null {
  if (!hasExplicitPartSuffix(nameGuess)) return null;
  const guess = ocrGuessPartInfo(nameGuess);
  if (!guess.part || !guess.base || guess.base.length < 2) return null;

  const candidates = entries.filter((entry) => {
    if (usedIds.has(entry.id)) return false;
    const part = ocrCatalogPartNumber(entry.name);
    if (part !== guess.part) return false;
    const shortKey = entry.shortKey;
    if (!shortKey || shortKey.length > 3) return false;
    if (isSuffixFragment(guess.base, shortKey)) return false;
    return true;
  });
  return candidates.length === 1 ? candidates[0] : null;
}

function fuzzyScore(a: string, b: string): number {
  if (!a || !b) return 0;
  if (a === b) return 1;
  const dist = levenshtein(a, b);
  const minLen = Math.min(a.length, b.length);
  let fuzzy = 1 - dist / Math.max(a.length, b.length);
  if (dist <= 1 && minLen >= 2) fuzzy = Math.max(fuzzy, 0.82);
  else if (dist <= 2 && minLen >= 3) fuzzy = Math.max(fuzzy, 0.78);
  else if (dist <= 3 && minLen >= 5) fuzzy = Math.max(fuzzy, 0.72);
  return fuzzy;
}

/** Part 序号一致时，比较主名；拒绝「之力」误碰「平衡之力」类后缀匹配。 */
function scorePartNumberMatch(
  nameGuess: string,
  entryName: string,
): number {
  const guess = ocrGuessPartInfo(nameGuess);
  const part = ocrCatalogPartNumber(entryName);
  if (!guess.part || !part || guess.part !== part || !guess.base) return 0;

  let best = 0;
  for (const catBase of [
    ocrCatalogShortName(entryName),
    compactOcrText(entryName).replace(/\d+.*$/, ""),
  ].filter(Boolean)) {
    if (
      catBase.endsWith(guess.base) &&
      !catBase.startsWith(guess.base) &&
      guess.base.length < catBase.length * 0.75
    ) {
      continue;
    }
    if (catBase.startsWith(guess.base) && guess.base.length >= 1) {
      best = Math.max(best, 0.55 + (guess.base.length / catBase.length) * 0.35);
    }
    best = Math.max(best, fuzzyScore(catBase, guess.base));
  }
  return best;
}

type CatalogEntry = {
  id: string;
  name: string;
  key: string;
  shortKey: string;
  normalizedKey: string;
  trader_slug: string;
  trader_name: string;
};

function catalogEntries(tasks: RaidPrepOcrCatalogTask[]): CatalogEntry[] {
  const out: CatalogEntry[] = [];
  for (const task of tasks) {
    const id = (task.id || "").trim();
    if (!id) continue;
    const name = (task.name || "").trim();
    const key = normalizeOcrText(name);
    const normalizedKey = normalizeOcrText(task.normalized_name || "");
    if (!key && !normalizedKey) continue;
    out.push({
      id,
      name: name || task.normalized_name || id,
      key,
      shortKey: ocrCatalogShortName(name),
      normalizedKey,
      trader_slug: (task.trader_slug || "").trim(),
      trader_name: (task.trader_name || "").trim(),
    });
  }
  return out;
}

/**
 * 宁缺毋滥：优先 compact 命中；OCR 误字时用模糊匹配，歧义行丢弃。
 */
export function matchRaidPrepTasksFromOcr(opts: {
  lines: string[];
  catalog: RaidPrepOcrCatalogTask[];
}): RaidPrepOcrMatch[] {
  const entries = catalogEntries(opts.catalog);
  if (!entries.length) return [];

  const matches: RaidPrepOcrMatch[] = [];
  const usedIds = new Set<string>();

  const pushMatch = (entry: CatalogEntry, ocrText: string) => {
    if (usedIds.has(entry.id)) return false;
    usedIds.add(entry.id);
    matches.push({
      id: entry.id,
      name: entry.name,
      ocrText,
      trader_slug: entry.trader_slug || undefined,
      trader_name: entry.trader_name || undefined,
    });
    return true;
  };

  for (const line of opts.lines) {
    const nameGuess = extractTaskNameFromOcrLine(line);
    if (!nameGuess) continue;
    const needleKey = normalizeOcrText(nameGuess);
    if (!needleKey || needleKey.length < 2) continue;

    const scored: Array<{ entry: CatalogEntry; rank: number; fuzzy: number }> =
      [];
    for (const entry of entries) {
      if (usedIds.has(entry.id)) continue;
      const { rank, fuzzy } = scoreLineAgainstEntry(
        nameGuess,
        needleKey,
        entry,
      );
      const ok = rank <= 3 || fuzzy >= 0.76;
      if (!ok) continue;
      scored.push({ entry, rank, fuzzy });
    }

    scored.sort((a, b) => {
      if (a.rank !== b.rank) return a.rank - b.rank;
      return b.fuzzy - a.fuzzy;
    });
    if (!scored.length) {
      const weak = tryWeakPartFallback(nameGuess, entries, usedIds);
      if (weak) pushMatch(weak, nameGuess);
      continue;
    }
    const best = scored[0];
    const second = scored[1];
    if (
      second &&
      best.rank === second.rank &&
      best.rank >= 2 &&
      Math.abs(best.fuzzy - second.fuzzy) < 0.06
    ) {
      const weak = tryWeakPartFallback(nameGuess, entries, usedIds);
      if (weak) pushMatch(weak, nameGuess);
      continue;
    }
    if (best.rank > 3 && best.fuzzy < 0.76) {
      const weak = tryWeakPartFallback(nameGuess, entries, usedIds);
      if (weak) pushMatch(weak, nameGuess);
      continue;
    }

    pushMatch(best.entry, nameGuess);
  }

  return matches;
}

/** 合并进已有勾选，去重并截断上限。 */
export function mergeRaidPrepOcrSelection(
  existingIds: string[],
  confirmedIds: string[],
  max = RAID_PREP_MAX_SELECTED,
): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const id of [...existingIds, ...confirmedIds]) {
    const key = (id || "").trim();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(key);
    if (out.length >= max) break;
  }
  return out;
}

/** 本次确认里真正新增的 id（已存在的不算）。 */
export function newRaidPrepOcrIds(
  existingIds: string[],
  confirmedIds: string[],
): string[] {
  const have = new Set(existingIds.map((id) => id.trim()).filter(Boolean));
  const out: string[] = [];
  const seen = new Set<string>();
  for (const id of confirmedIds) {
    const key = (id || "").trim();
    if (!key || have.has(key) || seen.has(key)) continue;
    seen.add(key);
    out.push(key);
  }
  return out;
}
