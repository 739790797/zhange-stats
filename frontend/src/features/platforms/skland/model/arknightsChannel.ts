/** 方舟 B 服：领取记录为空，无法查询签到奖励。 */
export function isBilibiliArknightsChannel(
  channelName?: string | null,
): boolean {
  const n = (channelName || "").trim().toLowerCase();
  if (!n) return false;
  return (
    n.includes("bilibili") ||
    n.includes("哔哩") ||
    n.includes("b服") ||
    n.includes("b 服")
  );
}
