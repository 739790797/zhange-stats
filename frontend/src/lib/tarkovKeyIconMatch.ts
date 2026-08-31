/** RatEye 风格：格子图标模板匹配（NCC + 颜色）。OCR 只用来拆开撞图。 */

export const KEY_ICON_TEMPLATE_SIZE = 24;
export const KEY_ICON_ACCEPT_SCORE = 0.62;
export const KEY_ICON_CLUSTER_SCORE = 0.58;
export const KEY_ICON_FAMILY_NCC = 0.9;
export const KEY_ICON_EMPTY_STD = 7.5;
export const KEY_ICON_COLOR_MAX_DIST = 42;
export const KEY_ICON_COLOR_GAP = 14;

export type TarkovKeyIconSample = {
  gray: Float32Array;
  mean: number;
  std: number;
  r: number;
  g: number;
  b: number;
  chroma: number;
  chromaRatio: number;
};

export type TarkovKeyIconTemplate = TarkovKeyIconSample & {
  id: string;
  short_name?: string;
};

export type TarkovKeyIconIndexItem = {
  id: string;
  gray: string;
  r: number;
  g: number;
  b: number;
  chromaRatio?: number;
};

export type TarkovKeyIconIndexFile = {
  size: number;
  items: TarkovKeyIconIndexItem[];
};

export type TarkovKeyIconHit = {
  id: string;
  score: number;
  ncc: number;
  color: number;
};

export type TarkovKeyIconMatch =
  | { kind: "empty" }
  | { kind: "unique"; hit: TarkovKeyIconHit }
  | { kind: "cluster"; hits: TarkovKeyIconHit[] }
  | { kind: "none"; hits: TarkovKeyIconHit[] };

export function isGreenCheckPixel(r: number, g: number, b: number): boolean {
  return g >= 120 && g >= r + 30 && g >= b + 25 && g - Math.min(r, b) >= 35;
}

/** 格子上的白字 / 耐久橙字，不参与取色。 */
export function isSlotOverlayPixel(r: number, g: number, b: number): boolean {
  if (r > 180 && g > 180 && b > 180 && rgbChroma(r, g, b) < 28) return true;
  return r > 150 && r > g + 25 && r > b + 40 && b < 110;
}

const STANDARD_COLOR_CARDS = new Set(["蓝卡", "黄卡", "绿卡", "红卡", "黑卡", "紫卡"]);

export function rgbChroma(r: number, g: number, b: number): number {
  return Math.max(r, g, b) - Math.min(r, g, b);
}

export function finalizeIconSample(
  gray: Float32Array,
  r: number,
  g: number,
  b: number,
  chromaRatio = 0,
): TarkovKeyIconSample {
  let mean = 0;
  for (let i = 0; i < gray.length; i += 1) mean += gray[i];
  mean /= Math.max(1, gray.length);
  let variance = 0;
  for (let i = 0; i < gray.length; i += 1) {
    const d = gray[i] - mean;
    variance += d * d;
  }
  return {
    gray,
    mean,
    std: Math.sqrt(variance / Math.max(1, gray.length)),
    r,
    g,
    b,
    chroma: rgbChroma(r, g, b),
    chromaRatio,
  };
}

export function sampleIconFromRgba(
  data: Uint8ClampedArray,
  srcW: number,
  srcH: number,
  rect: { x: number; y: number; width: number; height: number },
  size = KEY_ICON_TEMPLATE_SIZE,
): TarkovKeyIconSample | null {
  const x0 = Math.max(0, Math.floor(rect.x));
  const y0 = Math.max(0, Math.floor(rect.y));
  const x1 = Math.min(srcW, Math.ceil(rect.x + rect.width));
  const y1 = Math.min(srcH, Math.ceil(rect.y + rect.height));
  if (x1 - x0 < 6 || y1 - y0 < 6) return null;

  const gray = new Float32Array(size * size);
  let rSum = 0;
  let gSum = 0;
  let bSum = 0;
  let used = 0;
  let chromaR = 0;
  let chromaG = 0;
  let chromaB = 0;
  let chromaN = 0;
  let scanned = 0;
  const cellW = (x1 - x0) / size;
  const cellH = (y1 - y0) / size;
  for (let py = 0; py < size; py += 1) {
    for (let px = 0; px < size; px += 1) {
      const sx0 = x0 + Math.floor(px * cellW);
      const sy0 = y0 + Math.floor(py * cellH);
      const sx1 = Math.max(sx0 + 1, x0 + Math.ceil((px + 1) * cellW));
      const sy1 = Math.max(sy0 + 1, y0 + Math.ceil((py + 1) * cellH));
      let rs = 0;
      let gs = 0;
      let bs = 0;
      let n = 0;
      for (let y = sy0; y < Math.min(srcH, sy1); y += 1) {
        for (let x = sx0; x < Math.min(srcW, sx1); x += 1) {
          const i = (y * srcW + x) * 4;
          const r = data[i];
          const g = data[i + 1];
          const b = data[i + 2];
          const a = data[i + 3];
          if (a < 20 || isGreenCheckPixel(r, g, b)) continue;
          rs += r;
          gs += g;
          bs += b;
          n += 1;
          scanned += 1;
          if (!isSlotOverlayPixel(r, g, b) && rgbChroma(r, g, b) >= 36) {
            chromaR += r;
            chromaG += g;
            chromaB += b;
            chromaN += 1;
          }
        }
      }
      if (!n) {
        gray[py * size + px] = 22;
        continue;
      }
      const r = rs / n;
      const g = gs / n;
      const b = bs / n;
      gray[py * size + px] = 0.299 * r + 0.587 * g + 0.114 * b;
      rSum += r;
      gSum += g;
      bSum += b;
      used += 1;
    }
  }
  if (used < size * size * 0.35) return null;
  const chromaRatio = scanned ? chromaN / scanned : 0;
  const r = chromaN >= 8 ? chromaR / chromaN : rSum / used;
  const g = chromaN >= 8 ? chromaG / chromaN : gSum / used;
  const b = chromaN >= 8 ? chromaB / chromaN : bSum / used;
  return finalizeIconSample(gray, r, g, b, chromaRatio);
}

export function encodeIconGray(gray: Float32Array): string {
  const bytes = new Uint8Array(gray.length);
  for (let i = 0; i < gray.length; i += 1) {
    bytes[i] = Math.max(0, Math.min(255, Math.round(gray[i])));
  }
  if (typeof Buffer !== "undefined") {
    return Buffer.from(bytes).toString("base64");
  }
  let bin = "";
  for (let i = 0; i < bytes.length; i += 1) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}

export function decodeIconGray(raw: string): Float32Array {
  const bytes =
    typeof Buffer !== "undefined"
      ? new Uint8Array(Buffer.from(raw, "base64"))
      : Uint8Array.from(atob(raw), (ch) => ch.charCodeAt(0));
  const gray = new Float32Array(bytes.length);
  for (let i = 0; i < bytes.length; i += 1) gray[i] = bytes[i];
  return gray;
}

export function templateFromIndexItem(
  item: TarkovKeyIconIndexItem,
): TarkovKeyIconTemplate | null {
  const gray = decodeIconGray(item.gray);
  if (gray.length !== KEY_ICON_TEMPLATE_SIZE * KEY_ICON_TEMPLATE_SIZE) return null;
  const sample = finalizeIconSample(gray, item.r, item.g, item.b, item.chromaRatio ?? 0);
  return { id: item.id, ...sample };
}

export function nccScore(a: TarkovKeyIconSample, b: TarkovKeyIconSample): number {
  if (a.std < 1e-3 || b.std < 1e-3 || a.gray.length !== b.gray.length) return 0;
  let sum = 0;
  for (let i = 0; i < a.gray.length; i += 1) {
    sum += (a.gray[i] - a.mean) * (b.gray[i] - b.mean);
  }
  return sum / (a.gray.length * a.std * b.std);
}

export function colorScore(a: TarkovKeyIconSample, b: TarkovKeyIconSample): number {
  const dist = Math.hypot(a.r - b.r, a.g - b.g, a.b - b.b);
  return 1 - Math.min(1, dist / 200);
}

export function colorDistance(a: TarkovKeyIconSample, b: TarkovKeyIconSample): number {
  return Math.hypot(a.r - b.r, a.g - b.g, a.b - b.b);
}

export function combinedIconScore(
  ncc: number,
  color: number,
  sample: TarkovKeyIconSample,
  tmpl: TarkovKeyIconSample,
): number {
  const n = Math.max(0, ncc);
  const colorful = sample.chroma > 40 && tmpl.chroma > 40;
  return colorful ? n * 0.5 + color * 0.5 : n * 0.78 + color * 0.22;
}

export function iconFamilyIds(
  winnerId: string,
  templates: TarkovKeyIconTemplate[],
  threshold = KEY_ICON_FAMILY_NCC,
): string[] {
  const winner = templates.find((row) => row.id === winnerId);
  if (!winner) return [winnerId];
  return templates
    .filter((row) => nccScore(winner, row) >= threshold)
    .map((row) => row.id);
}

export function matchKeyIcon(
  sample: TarkovKeyIconSample | null,
  templates: TarkovKeyIconTemplate[],
): TarkovKeyIconMatch {
  if (!sample || sample.std < KEY_ICON_EMPTY_STD) return { kind: "empty" };
  if (!templates.length) return { kind: "none", hits: [] };

  if (sample.chroma >= 40 && sample.chromaRatio >= 0.06) {
    const colored = templates
      .filter((tmpl) => {
        const name = (tmpl.short_name || "").trim();
        return STANDARD_COLOR_CARDS.has(name) || name.startsWith("A.P.");
      })
      .map((tmpl) => ({
        id: tmpl.id,
        ncc: nccScore(sample, tmpl),
        color: colorScore(sample, tmpl),
        score: colorScore(sample, tmpl),
        dist: colorDistance(sample, tmpl),
      }))
      .sort((a, b) => a.dist - b.dist);
    const best = colored[0];
    const next = colored[1];
    const bestName = (templates.find((row) => row.id === best?.id)?.short_name || "").trim();
    const nextName = (templates.find((row) => row.id === next?.id)?.short_name || "").trim();
    const standardOverAp =
      !!best && STANDARD_COLOR_CARDS.has(bestName) && nextName.startsWith("A.P.");
    if (
      best &&
      STANDARD_COLOR_CARDS.has(bestName) &&
      best.dist <= KEY_ICON_COLOR_MAX_DIST &&
      (!next || next.dist - best.dist >= KEY_ICON_COLOR_GAP || standardOverAp)
    ) {
      return {
        kind: "unique",
        hit: { id: best.id, score: best.color, ncc: best.ncc, color: best.color },
      };
    }
  }

  const hits: TarkovKeyIconHit[] = templates.map((tmpl) => {
    const ncc = nccScore(sample, tmpl);
    const color = colorScore(sample, tmpl);
    return {
      id: tmpl.id,
      ncc,
      color,
      score: combinedIconScore(ncc, color, sample, tmpl),
    };
  });
  hits.sort((a, b) => b.score - a.score || b.ncc - a.ncc);
  const top = hits[0];
  if (!top || top.score < KEY_ICON_CLUSTER_SCORE) {
    return { kind: "none", hits: hits.slice(0, 8) };
  }
  const family = new Set(iconFamilyIds(top.id, templates));
  const cluster = hits.filter((hit) => family.has(hit.id));
  if (top.score >= KEY_ICON_ACCEPT_SCORE && cluster.length === 1) {
    return { kind: "unique", hit: top };
  }
  if (cluster.length >= 2) {
    return { kind: "cluster", hits: cluster };
  }
  if (top.score >= KEY_ICON_ACCEPT_SCORE) {
    return { kind: "unique", hit: top };
  }
  return { kind: "none", hits: hits.slice(0, 8) };
}
