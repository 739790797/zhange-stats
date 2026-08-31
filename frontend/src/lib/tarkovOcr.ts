/** 塔科夫截图识别：文本归一化、模糊打分、进度文案。匹配规则按闭集宁缺毋滥。 */

const OCR_TOKEN_RE = /[0-9a-zA-Z]+|[\u4e00-\u9fff]+/g;
const OCR_COMPACT_RE = /[\s\-_.·•]+/g;

export function formatOcrProgress(status: string, progress?: number): string {
  const key = (status || "").toLowerCase();
  if (key.includes("core")) return "正在加载识别引擎…";
  if (key.includes("language") || key.includes("traineddata")) {
    return "正在加载识别模型…";
  }
  if (key.includes("initializ")) return "正在初始化识别器…";
  if (key.includes("icon")) {
    const pct =
      typeof progress === "number" && progress > 0
        ? ` ${Math.round(progress * 100)}%`
        : "";
    return `正在比对钥匙图标…${pct}`;
  }
  if (key.includes("recogniz")) {
    const pct =
      typeof progress === "number" && progress > 0
        ? ` ${Math.round(progress * 100)}%`
        : "";
    return `正在识别文字…${pct}`;
  }
  return "识别中…";
}

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

export function ocrLevenshtein(a: string, b: string): number {
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

export function ocrFuzzyScore(a: string, b: string): number {
  if (!a || !b) return 0;
  if (a === b) return 1;
  const dist = ocrLevenshtein(a, b);
  const minLen = Math.min(a.length, b.length);
  let fuzzy = 1 - dist / Math.max(a.length, b.length);
  if (dist <= 1 && minLen >= 2) fuzzy = Math.max(fuzzy, 0.82);
  else if (dist <= 2 && minLen >= 3) fuzzy = Math.max(fuzzy, 0.78);
  else if (dist <= 3 && minLen >= 5) fuzzy = Math.max(fuzzy, 0.72);
  return fuzzy;
}

/** 放大后最长边不超过 maxEdge，避免整仓 2x 撑爆内存。 */
export function ocrOutputScale(
  srcWidth: number,
  srcHeight: number,
  want: number,
  maxEdge = 1920,
): number {
  const edge = Math.max(srcWidth, srcHeight);
  if (edge <= 0) return 1;
  const scaled = edge * want;
  if (scaled <= maxEdge) return want;
  return maxEdge / edge;
}

/** 合并进已有勾选，去重并截断上限。 */
export function mergeOcrSelection(
  existingIds: string[],
  confirmedIds: string[],
  max = Number.POSITIVE_INFINITY,
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
export function newOcrIds(
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
