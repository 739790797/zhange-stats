import type { SteamNowItem } from "@/api/types";

export type NowPlayingGroup = {
  steam_app_id: string;
  game_name: string;
  icon_url?: string | null;
  players: SteamNowItem[];
};

export function sessionDurationSeconds(
  item: SteamNowItem,
  fetchedAtMs: number,
  nowMs: number,
): number {
  // 以服务端已算好的 UTC 时长为准，再叠加自拉取后的流逝时间，避免本地误解析时区
  const elapsed = Math.max(0, Math.floor((nowMs - fetchedAtMs) / 1000));
  return Math.max(0, item.duration_seconds + elapsed);
}

export function groupNowPlaying(items: SteamNowItem[]): NowPlayingGroup[] {
  const map = new Map<string, NowPlayingGroup>();
  for (const item of items) {
    const key = item.steam_app_id || item.game_name;
    let group = map.get(key);
    if (!group) {
      group = {
        steam_app_id: item.steam_app_id,
        game_name: item.game_name,
        icon_url: item.icon_url,
        players: [],
      };
      map.set(key, group);
    }
    group.players.push(item);
    if (!group.icon_url && item.icon_url) {
      group.icon_url = item.icon_url;
    }
  }
  return Array.from(map.values()).sort((a, b) => {
    const byCount = b.players.length - a.players.length;
    if (byCount !== 0) return byCount;
    return a.game_name.localeCompare(b.game_name, "zh");
  });
}
