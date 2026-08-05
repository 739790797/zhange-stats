import type { SteamDayData, SteamTimelineRow } from "@/api/types";
import { DAY_SECONDS, GAME_PALETTE } from "@/components/steam/constants";
import { parseBeijing } from "@/lib/time";

export function hashColor(key: string): string {
  let h = 0;
  for (let i = 0; i < key.length; i++) {
    h = (h * 31 + key.charCodeAt(i)) >>> 0;
  }
  return GAME_PALETTE[h % GAME_PALETTE.length];
}

export function segmentColor(status: string, appId?: string | null): string {
  if (status === "offline") return "#d9d9d9";
  if (status === "online") return "#5b8ff9";
  if (status === "playing") return hashColor(appId || "playing");
  return "#bfbfbf";
}

export function steamStoreUrl(appId: string): string {
  return `https://store.steampowered.com/app/${encodeURIComponent(appId)}`;
}

/** 把「自然日×2」的接口结果裁成从中午起的 24 小时窗口（查询仍用 date/end）。 */
export function clipTimelineToNoonWindow(data: SteamDayData): SteamDayData {
  const shift = 12 * 3600;
  const windowEnd = shift + DAY_SECONDS;
  const baseStart = parseBeijing(data.range_start ?? data.date);
  const clippedRows: SteamTimelineRow[] = (data.timeline ?? []).map((row) => ({
    ...row,
    segments: row.segments
      .map((seg) => {
        const start = Math.max(seg.start_sec, shift);
        const end = Math.min(seg.end_sec, windowEnd);
        if (end <= start) return null;
        return {
          ...seg,
          start_sec: start - shift,
          end_sec: end - shift,
        };
      })
      .filter((s): s is NonNullable<typeof s> => s != null),
  }));
  const legend = new Map<string, { game_name: string; icon_url?: string | null }>();
  for (const row of clippedRows) {
    for (const seg of row.segments) {
      if (seg.status === "playing" && seg.steam_app_id) {
        const prev = legend.get(seg.steam_app_id);
        legend.set(seg.steam_app_id, {
          game_name: seg.game_name || prev?.game_name || `App ${seg.steam_app_id}`,
          icon_url: seg.icon_url || prev?.icon_url,
        });
      }
    }
  }
  return {
    ...data,
    range_start: baseStart.add(12, "hour").toISOString(),
    range_end: baseStart.add(36, "hour").toISOString(),
    span_seconds: DAY_SECONDS,
    timeline: clippedRows,
    games_legend: Array.from(legend, ([steam_app_id, meta]) => ({
      steam_app_id,
      game_name: meta.game_name,
      icon_url: meta.icon_url,
    })),
  };
}
