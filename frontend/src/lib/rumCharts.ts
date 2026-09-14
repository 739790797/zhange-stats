import type { RumBizSummary, RumSummaryRow } from "@/api/rumApi";

export const RUM_BAR_LIMIT = 12;

export function rumAtToMs(at: string): number {
  const text = String(at || "").trim();
  if (!text) return Number.NaN;
  const iso = text.includes("T") ? text : text.replace(" ", "T");
  const parsed = /[zZ]|[+-]\d{2}:\d{2}$/.test(iso)
    ? Date.parse(iso)
    : Date.parse(`${iso}+08:00`);
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}

export function rumChartLabel(urlKey: string, max = 42): string {
  const text = String(urlKey || "").replace(/^https?:\/\//, "");
  if (text.length <= max) return text;
  return `…${text.slice(1 - max)}`;
}

export type RumTrendPoint = {
  t: number;
  count: number;
  api_count: number;
  img_count: number;
  api_p95: number | null;
  img_p95: number | null;
};

export function rumTrendDomain(
  series:
    | {
        at: string;
      }[]
    | undefined,
): { min?: number; max?: number } {
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  for (const row of series || []) {
    const t = rumAtToMs(row.at);
    if (!Number.isFinite(t)) continue;
    if (t < min) min = t;
    if (t > max) max = t;
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) return {};
  return { min, max: max > min ? max : min + 1 };
}

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
    const api_count = row.api_count ?? 0;
    const img_count = row.img_count ?? 0;
    if (!api_count && !img_count) continue;
    out.push({
      t,
      count: api_count + img_count,
      api_count,
      img_count,
      api_p95: api_count ? (row.api_p95_ms ?? 0) : null,
      img_p95: img_count ? (row.img_p95_ms ?? 0) : null,
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

export const RUM_BIZ_ALL = "all";

export function rumRowsForBiz(
  rows: RumSummaryRow[] | undefined,
  biz: string,
  limit = RUM_BAR_LIMIT,
): RumSummaryRow[] {
  const list = rows || [];
  const filtered =
    !biz || biz === RUM_BIZ_ALL ? list : list.filter((row) => row.biz === biz);
  return [...filtered]
    .sort(
      (a, b) =>
        (b.p95_ms ?? 0) - (a.p95_ms ?? 0) || (b.count ?? 0) - (a.count ?? 0),
    )
    .slice(0, limit);
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

export function rumBizBarPoints(
  rows: RumBizSummary[] | undefined,
  limit = 16,
): RumBarPoint[] {
  const out: RumBarPoint[] = [];
  for (const row of (rows || []).slice(0, limit)) {
    const label = `${row.label}（${row.count}）`;
    out.push({ label, metric: "p50", ms: row.p50_ms ?? 0 });
    out.push({ label, metric: "p95", ms: row.p95_ms ?? 0 });
  }
  return out;
}

export function rumBizFilterOptions(
  rows: RumBizSummary[] | undefined,
): { label: string; value: string }[] {
  return (rows || []).map((row) => ({
    label: row.label,
    value: row.biz,
  }));
}

export function rumBarHeight(rowCount: number): number {
  const n = Math.max(1, rowCount);
  return Math.min(480, Math.max(220, n * 36 + 48));
}
