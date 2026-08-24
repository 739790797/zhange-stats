import { PLATFORM_NAV } from "@/lib/platformFeatures";

/** 侧栏签到平台顺序（排除 Steam） */
export const CHECKIN_PLATFORM_ORDER: string[] = PLATFORM_NAV.filter(
  (p) => p.icon !== "steam",
).map((p) => p.icon);

export const CHECKIN_PLATFORM_LABELS: Record<string, string> = {
  skland: "森空岛",
  taygedo: "塔吉多",
  exilium: "追放",
  kujiequ: "库街区",
  mihoyo: "米游社",
};

/** 各平台「社区」签到的 game_code，展示时排最前 */
export const COMMUNITY_CHECKIN_GAME_CODES = new Set([
  "app", // 塔吉多
  "kujiequ", // 库街区
  "exilium_bbs", // 追放
  "mihoyo", // 米游社
]);

export function isCommunityCheckinGame(gameCode?: string | null) {
  return COMMUNITY_CHECKIN_GAME_CODES.has(String(gameCode || "").trim());
}

/** 0=社区优先，1=其余游戏 */
export function communityGameRank(gameCode?: string | null) {
  return isCommunityCheckinGame(gameCode) ? 0 : 1;
}

/** 渠道 Tag：历史「社区签到」统一为「社区」 */
export function displayCheckinChannelName(name?: string | null) {
  const n = (name || "").trim();
  if (!n) return null;
  if (n === "社区签到") return "社区";
  return n;
}

export function formatCheckinTime(hour: number, minute: number) {
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

export function platformRank(platform: string) {
  const idx = CHECKIN_PLATFORM_ORDER.indexOf(platform);
  return idx >= 0 ? idx : 99;
}
