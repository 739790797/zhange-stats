import type { RumSummaryRow } from "@/api/rumApi";

export const RUM_BAR_LIMIT = 12;

export function rumAtToMs(at: string): number {
  const text = String(at || "").trim();
  if (!text) return Number.NaN;
  const iso = text.includes("T") ? text : text.replace(" ", "T");
  const t = Date.parse(`${iso}+08:00`);
  return Number.isFinite(t) ? t : Number.NaN;
}

export function rumChartLabel(urlKey: string, max = 42): string {
  const text = String(urlKey || "").replace(/^https?:\/\//, "");
  if (text.length <= max) return text;
  return `…${text.slice(1 - max)}`;
}

export type RumTrendPoint = {
  t: number;
  series: string;
  count: number;
  p50: number;
  p95: number;
};

export function rumTrendPoints(
  series:
    | {
        at: string;
        api_count?: number;
        img_count?: number;
        api_p50_ms?: number | null;
        api_p95_ms?: number | null;
        img_p50_ms?: number | null;
        img_p95_ms?: number | null;
      }[]
    | undefined,
): RumTrendPoint[] {
  const out: RumTrendPoint[] = [];
  for (const row of series || []) {
    const t = rumAtToMs(row.at);
    if (!Number.isFinite(t)) continue;
    out.push({
      t,
      series: "接口",
      count: row.api_count ?? 0,
      p50: row.api_p50_ms ?? Number.NaN,
      p95: row.api_p95_ms ?? Number.NaN,
    });
    out.push({
      t,
      series: "第三方图",
      count: row.img_count ?? 0,
      p50: row.img_p50_ms ?? Number.NaN,
      p95: row.img_p95_ms ?? Number.NaN,
    });
  }
  return out;
}

export type RumBarPoint = {
  label: string;
  metric: string;
  ms: number;
};

function uniqueLabel(urlKey: string, used: Set<string>): string {
  const base = rumChartLabel(urlKey);
  if (!used.has(base)) {
    used.add(base);
    return base;
  }
  let i = 2;
  let next = `${base} (${i})`;
  while (used.has(next)) {
    i += 1;
    next = `${base} (${i})`;
  }
  used.add(next);
  return next;
}

export function rumBarPoints(
  rows: RumSummaryRow[] | undefined,
  limit = RUM_BAR_LIMIT,
): RumBarPoint[] {
  const used = new Set<string>();
  const out: RumBarPoint[] = [];
  for (const row of (rows || []).slice(0, limit)) {
    const label = uniqueLabel(row.url_key, used);
    out.push({ label, metric: "p50", ms: row.p50_ms ?? 0 });
    out.push({ label, metric: "p95", ms: row.p95_ms ?? 0 });
  }
  return out;
}

export function rumBarHeight(rowCount: number): number {
  const n = Math.max(1, rowCount);
  return Math.min(480, Math.max(220, n * 36 + 48));
}
