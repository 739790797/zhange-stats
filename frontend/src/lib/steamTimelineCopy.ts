/** Steam 时间轴空态 / 隐私提示（展示层）。 */

export type SteamVisibilityHintInput = {
  hint?: string | null;
  steam_bound?: boolean;
  visible_member_count?: number;
} | null | undefined;

export function steamTimelineEmptyText(input: {
  rowCount: number;
  visibleMemberCount?: number | null;
}): string {
  if (input.rowCount > 0) return "";
  if (!input.visibleMemberCount) {
    return "暂无绑定 Steam 的圈子成员";
  }
  return "该时段暂无游玩记录";
}

export function steamPrivacySkipHint(
  meta: SteamVisibilityHintInput,
  rowCount: number,
): string | null {
  const fromApi = (meta?.hint || "").trim();
  if (fromApi) return fromApi;
  if (!meta?.steam_bound) return null;
  if (rowCount > 0) return null;
  return "若应有数据却为空，请确认 Steam「游戏详情」已设为公开；隐私过严时本轮状态可能被跳过。";
}
