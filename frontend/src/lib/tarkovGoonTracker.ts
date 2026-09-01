import { parseBeijing } from "@/lib/time";

export const GOON_MAP_SLUGS = [
  "woods",
  "shoreline",
  "customs",
  "lighthouse",
] as const;

export type GoonMapSlug = (typeof GOON_MAP_SLUGS)[number];

const GOON_MAP_SET = new Set<string>(GOON_MAP_SLUGS);

export function isGoonMapSlug(slug: string | null | undefined): boolean {
  return GOON_MAP_SET.has(String(slug || "").trim().toLowerCase());
}

export function sameGoonMap(
  mapSlug: string | null | undefined,
  goonSlug: string | null | undefined,
): boolean {
  const left = String(mapSlug || "").trim().toLowerCase();
  const right = String(goonSlug || "").trim().toLowerCase();
  return Boolean(left && right && left === right);
}

/** 「12分钟前」这类相对时间，给选图提示用。 */
export function formatGoonElapsed(
  seenAt: string | null | undefined,
  nowMs = Date.now(),
): string {
  const seen = parseBeijing(seenAt || "");
  if (!seen.isValid()) return "";
  const delta = Math.max(0, nowMs - seen.valueOf());
  const sec = Math.floor(delta / 1000);
  if (sec < 45) return "刚刚";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}分钟前`;
  const hour = Math.floor(min / 60);
  const remMin = min % 60;
  if (hour < 24) {
    return remMin ? `${hour}小时${remMin}分前` : `${hour}小时前`;
  }
  const day = Math.floor(hour / 24);
  return `${day}天前`;
}

export function goonSightingHint(
  seenAt: string | null | undefined,
  nowMs = Date.now(),
): string {
  const elapsed = formatGoonElapsed(seenAt, nowMs);
  if (!elapsed) return "";
  if (elapsed === "刚刚") return "三狗出没（刚刚上报）";
  return `三狗出没（${elapsed}上报）`;
}
