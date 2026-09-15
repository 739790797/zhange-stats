/** 塔科夫截图识别：模糊打分、进度文案。匹配规则按闭集宁缺毋滥。 */

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

const KEY_OCR_ENGINE_LABELS: Record<string, string> = {
  paddle: "熊猫 OCR",
  easyocr: "EasyOCR",
};

export function formatKeyOcrEngines(engines?: string[] | null): string {
  const names = (engines || [])
    .map((id) => KEY_OCR_ENGINE_LABELS[id] || id.trim())
    .filter(Boolean);
  return [...new Set(names)].join(" / ");
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
