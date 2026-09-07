import { isSafeArticleImageSrc } from "./articleImages";

export const ARTICLE_ALIGN = ["left", "center", "right"] as const;
export type ArticleAlign = (typeof ARTICLE_ALIGN)[number];

export const ARTICLE_COLORS = [
  { key: "red", label: "红", value: "#cf1322" },
  { key: "orange", label: "橙", value: "#d46b08" },
  { key: "gold", label: "金", value: "#d48806" },
  { key: "green", label: "绿", value: "#389e0d" },
  { key: "blue", label: "蓝", value: "#1677ff" },
  { key: "purple", label: "紫", value: "#531dab" },
  { key: "gray", label: "灰", value: "#595959" },
] as const;

export const ARTICLE_MARKS = [
  { key: "yellow", label: "黄", value: "#fff1b8" },
  { key: "green", label: "绿", value: "#d9f7be" },
  { key: "red", label: "红", value: "#ffccc7" },
  { key: "blue", label: "蓝", value: "#bae0ff" },
] as const;

export const ARTICLE_INDENT_MAX = 4;

const COLOR_KEYS = new Set(ARTICLE_COLORS.map((row) => row.key));
const MARK_KEYS = new Set(ARTICLE_MARKS.map((row) => row.key));
const COLOR_BY_VALUE = new Map(
  ARTICLE_COLORS.map((row) => [row.value.toLowerCase(), row.key]),
);
const MARK_BY_VALUE = new Map(
  ARTICLE_MARKS.map((row) => [row.value.toLowerCase(), row.key]),
);
const CSS_NAMED_COLORS: Record<string, [number, number, number]> = {
  red: [255, 0, 0],
  orange: [255, 165, 0],
  gold: [255, 215, 0],
  green: [0, 128, 0],
  blue: [0, 0, 255],
  purple: [128, 0, 128],
  gray: [128, 128, 128],
  grey: [128, 128, 128],
  yellow: [255, 255, 0],
};

export function articleAlignClass(align: string | null | undefined): string {
  return align && ARTICLE_ALIGN.includes(align as ArticleAlign)
    ? `article-align-${align}`
    : "";
}

export function articleColorClass(key: string | null | undefined): string {
  return key && COLOR_KEYS.has(key as (typeof ARTICLE_COLORS)[number]["key"])
    ? `article-color-${key}`
    : "";
}

export function articleMarkClass(key: string | null | undefined): string {
  return key && MARK_KEYS.has(key as (typeof ARTICLE_MARKS)[number]["key"])
    ? `article-mark-${key}`
    : "";
}

export function articleIndentClass(level: number | null | undefined): string {
  if (!level || level < 1 || level > ARTICLE_INDENT_MAX) return "";
  return `article-indent-${level}`;
}

export function parseArticleAlign(
  className: string,
  styleAlign?: string,
): ArticleAlign | null {
  const match = /(?:^|\s)article-align-(left|center|right)(?:\s|$)/.exec(
    className || "",
  );
  if (match) return match[1] as ArticleAlign;
  if (
    styleAlign === "left" ||
    styleAlign === "center" ||
    styleAlign === "right"
  ) {
    return styleAlign;
  }
  return null;
}

export function parseCssColor(
  value?: string,
): [number, number, number] | null {
  const text = (value || "").trim().toLowerCase();
  if (!text || text === "transparent" || text === "inherit" || text === "currentcolor") {
    return null;
  }
  const named = CSS_NAMED_COLORS[text];
  if (named) return named;
  const hex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/.exec(text);
  if (hex) {
    const raw =
      hex[1].length === 3
        ? hex[1]
            .split("")
            .map((ch) => ch + ch)
            .join("")
        : hex[1];
    return [
      Number.parseInt(raw.slice(0, 2), 16),
      Number.parseInt(raw.slice(2, 4), 16),
      Number.parseInt(raw.slice(4, 6), 16),
    ];
  }
  const rgb = /^rgba?\(\s*([0-9.]+)(%?)\s*[, ]\s*([0-9.]+)(%?)\s*[, ]\s*([0-9.]+)(%?)(?:\s*[,/]\s*([0-9.]+))?\s*\)$/.exec(
    text,
  );
  if (rgb) {
    const alpha = rgb[7] == null ? 1 : Number(rgb[7]);
    if (Number.isNaN(alpha) || alpha <= 0) return null;
    return [
      channel(rgb[1], rgb[2]),
      channel(rgb[3], rgb[4]),
      channel(rgb[5], rgb[6]),
    ];
  }
  return null;
}

export function classifyArticleColor(
  rgb: [number, number, number],
): (typeof ARTICLE_COLORS)[number]["key"] | null {
  const hex = rgbToHex(rgb);
  const exact = COLOR_BY_VALUE.get(hex);
  if (exact) return exact;
  const [h, s, l] = rgbToHsl(rgb);
  if (l < 0.12 || l > 0.88) return null;
  if (s < 0.12) return "gray";
  if (h < 15 || h >= 345) return "red";
  if (h < 40) return "orange";
  if (h < 65) return "gold";
  if (h < 160) return "green";
  if (h < 260) return "blue";
  return "purple";
}

export function classifyArticleMark(
  rgb: [number, number, number],
): (typeof ARTICLE_MARKS)[number]["key"] | null {
  const hex = rgbToHex(rgb);
  const exact = MARK_BY_VALUE.get(hex);
  if (exact) return exact;
  const [h, s, l] = rgbToHsl(rgb);
  if (s < 0.12 || l > 0.97 || l < 0.35) return null;
  if (h < 20 || h >= 340) return "red";
  if (h < 80) return "yellow";
  if (h < 160) return "green";
  return "blue";
}

export function parseArticleColor(
  className: string,
  styleColor?: string,
): string | null {
  const match = /(?:^|\s)article-color-([a-z]+)(?:\s|$)/.exec(className || "");
  if (match && COLOR_KEYS.has(match[1] as (typeof ARTICLE_COLORS)[number]["key"])) {
    return match[1];
  }
  const rgb = parseCssColor(styleColor);
  return rgb ? classifyArticleColor(rgb) : null;
}

export function cssStyleProp(style: string, name: string): string {
  const match = new RegExp(`(?:^|;)\\s*${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*:\\s*([^;]+)`, "i").exec(
    style || "",
  );
  return match ? match[1].trim() : "";
}

export function parseArticleMark(
  className: string,
  styleBackground?: string,
): string | null {
  const match = /(?:^|\s)article-mark-([a-z]+)(?:\s|$)/.exec(className || "");
  if (match && MARK_KEYS.has(match[1] as (typeof ARTICLE_MARKS)[number]["key"])) {
    return match[1];
  }
  const rgb = parseCssColor(styleBackground);
  return rgb ? classifyArticleMark(rgb) : null;
}

export function parseArticleIndent(className: string): number | null {
  const match = /(?:^|\s)article-indent-([1-4])(?:\s|$)/.exec(className || "");
  return match ? Number(match[1]) : null;
}

export function isAllowedArticleClass(name: string): boolean {
  const token = (name || "").trim();
  if (!token) return false;
  if (/^article-align-(left|center|right)$/.test(token)) return true;
  if (/^article-indent-[1-4]$/.test(token)) return true;
  if (/^article-color-[a-z]+$/.test(token)) {
    return COLOR_KEYS.has(token.slice("article-color-".length) as never);
  }
  if (/^article-mark-[a-z]+$/.test(token)) {
    return MARK_KEYS.has(token.slice("article-mark-".length) as never);
  }
  if (/^language-[\w-]+$/.test(token)) return true;
  if (token === "article-math" || token === "article-math-block") return true;
  return false;
}

export function filterArticleClasses(className: string): string {
  return (className || "")
    .split(/\s+/)
    .filter(isAllowedArticleClass)
    .join(" ");
}

export function isSafeArticleHref(href: string): boolean {
  const text = (href || "").trim();
  if (!text || text.startsWith("//")) return false;
  if (text.startsWith("#")) return !text.includes(":");
  if (text.startsWith("/")) {
    const path = text.split("?", 1)[0].split("#", 1)[0];
    return !path.includes("..") && !path.includes("\\") && !path.includes(":");
  }
  try {
    const parsed = new URL(text);
    return (
      parsed.protocol === "http:" ||
      parsed.protocol === "https:" ||
      parsed.protocol === "mailto:"
    );
  } catch {
    return false;
  }
}

export function isSafeArticleImageUrl(src: string): boolean {
  return isSafeArticleImageSrc(src);
}

export const ARTICLE_HTML_TAGS = [
  "p",
  "br",
  "hr",
  "span",
  "div",
  "strong",
  "b",
  "em",
  "i",
  "u",
  "s",
  "del",
  "mark",
  "code",
  "pre",
  "blockquote",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "ul",
  "ol",
  "li",
  "a",
  "img",
  "figure",
  "figcaption",
  "table",
  "thead",
  "tbody",
  "tr",
  "th",
  "td",
];

export const ARTICLE_HTML_ATTRS = [
  "href",
  "title",
  "target",
  "rel",
  "src",
  "alt",
  "width",
  "height",
  "class",
  "colspan",
  "rowspan",
];

function channel(raw: string, percent: string): number {
  const n = Number(raw);
  if (Number.isNaN(n)) return 0;
  if (percent) return Math.max(0, Math.min(255, Math.round((n / 100) * 255)));
  return Math.max(0, Math.min(255, Math.round(n)));
}

function rgbToHex(rgb: [number, number, number]): string {
  return `#${rgb
    .map((n) => n.toString(16).padStart(2, "0"))
    .join("")}`;
}

function rgbToHsl(rgb: [number, number, number]): [number, number, number] {
  const r = rgb[0] / 255;
  const g = rgb[1] / 255;
  const b = rgb[2] / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  if (max === min) return [0, 0, l];
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let h = 0;
  if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
  else if (max === g) h = (b - r) / d + 2;
  else h = (r - g) / d + 4;
  return [h * 60, s, l];
}

export type TextChunk = { pos: number; text: string };

export function findTextRanges(
  chunks: TextChunk[],
  query: string,
): { from: number; to: number }[] {
  const needle = query || "";
  if (!needle) return [];
  const out: { from: number; to: number }[] = [];
  for (const chunk of chunks) {
    let from = 0;
    while (from < chunk.text.length) {
      const at = chunk.text.indexOf(needle, from);
      if (at < 0) break;
      out.push({ from: chunk.pos + at, to: chunk.pos + at + needle.length });
      from = at + needle.length;
    }
  }
  return out;
}
