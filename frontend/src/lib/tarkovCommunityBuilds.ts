import type { TarkovWorkbenchCommunityBuild } from "@/api/guidesApi";

export const COMMUNITY_TAG_ORDER = [
  "meta",
  "budget",
  "cqb",
  "sniper",
  "recoil",
  "ergo",
  "pve",
  "beginner",
  "hybrid",
] as const;

const COMMUNITY_TAG_LABELS: Record<string, string> = {
  featured: "精选",
  meta: "满改",
  budget: "性价比",
  cqb: "CQB",
  sniper: "远距离",
  recoil: "低后座",
  ergo: "高人机",
  pve: "PvE",
  beginner: "新手",
  hybrid: "综合",
};

export function communityTagLabel(tag: string): string {
  return COMMUNITY_TAG_LABELS[tag] || tag;
}

export function communityTagsInList(
  builds: TarkovWorkbenchCommunityBuild[] | undefined,
): string[] {
  const seen = new Set<string>();
  for (const row of builds || []) {
    for (const tag of row.tags || []) {
      if (tag) seen.add(tag);
    }
  }
  const ordered = COMMUNITY_TAG_ORDER.filter((tag) => seen.has(tag));
  const extra = [...seen]
    .filter((tag) => !ordered.includes(tag as (typeof ordered)[number]))
    .sort();
  return [...ordered, ...extra];
}

export function filterCommunityBuilds(
  builds: TarkovWorkbenchCommunityBuild[] | undefined,
  query: string,
  tags: string[],
): TarkovWorkbenchCommunityBuild[] {
  const q = query.trim().toLowerCase();
  const need = tags.filter(Boolean);
  return (builds || []).filter((row) => {
    if (need.length && !need.every((tag) => (row.tags || []).includes(tag))) {
      return false;
    }
    if (!q) return true;
    const hay = `${row.name} ${row.author || ""}`.toLowerCase();
    return hay.includes(q);
  });
}

export function formatCommunityPublishedAt(value: string | null | undefined): string {
  if (!value) return "";
  const day = value.slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(day) ? day : "";
}

export type CommunitySortKey =
  | "published_at"
  | "load_count"
  | "ergonomics"
  | "evo_ergo_delta"
  | "recoil_vertical"
  | "recoil_horizontal"
  | "overswing"
  | "price_rub";

function numericValue(value: number | null | undefined): number {
  return value == null || !Number.isFinite(value) ? Number.NEGATIVE_INFINITY : value;
}

export function compareCommunityBuilds(
  a: TarkovWorkbenchCommunityBuild,
  b: TarkovWorkbenchCommunityBuild,
  key: CommunitySortKey,
): number {
  if (key === "published_at") {
    return (a.published_at || "").localeCompare(b.published_at || "");
  }
  if (key === "load_count") {
    return (a.load_count || 0) - (b.load_count || 0);
  }
  if (key === "overswing") {
    return Number(Boolean(a.preview?.overswing)) - Number(Boolean(b.preview?.overswing));
  }
  const left = a.preview;
  const right = b.preview;
  if (key === "ergonomics") {
    return numericValue(left?.ergonomics) - numericValue(right?.ergonomics);
  }
  if (key === "evo_ergo_delta") {
    return numericValue(left?.evo_ergo_delta) - numericValue(right?.evo_ergo_delta);
  }
  if (key === "recoil_vertical") {
    return numericValue(left?.recoil_vertical) - numericValue(right?.recoil_vertical);
  }
  if (key === "recoil_horizontal") {
    return numericValue(left?.recoil_horizontal) - numericValue(right?.recoil_horizontal);
  }
  return numericValue(left?.price_rub) - numericValue(right?.price_rub);
}

export function formatCommunityErgo(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return String(Math.round(value * 10) / 10);
}

export function formatCommunityEvoDelta(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const n = Math.round(value * 10) / 10;
  const text = n.toFixed(1);
  return n >= 0 ? `+${text}` : text;
}
