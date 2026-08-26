import { isBilibiliArknightsChannel } from "@/lib/arknightsChannel";
import { CHECKIN_STATUS, isCheckinSuccess } from "@/lib/checkinStatus";

/** 签到奖励展示：图标解析、状态文案过滤。签到页 / 日常 / 日历共用。 */

export type CheckinAward = {
  name: string;
  count?: number;
  resource_id?: string | null;
  resource_type?: string | null;
  icon_url?: string | null;
};

/** 与 `components/arknights/constants.ts` GAME_RES 同源 */
export const ARKNIGHTS_ITEM_ICON_BASE =
  "https://raw.githubusercontent.com/yuanyan3060/ArknightsGameResource/main/item";

const STATUS_AWARDS_TEXT =
  /^(今日已签到|签到成功|签到奖励已发放|讨论区今日已签到|B服不支持查询)(。)?$/;

export function isStatusAwardsText(text: string): boolean {
  return STATUS_AWARDS_TEXT.test(text.trim());
}

function arknightsItemIcon(resourceType?: string | null): string | null {
  const key = String(resourceType || "").trim();
  if (!key || key.includes("/") || key.includes("\\") || key.includes("..")) {
    return null;
  }
  if (!/^[A-Z][A-Z0-9_]*$/.test(key)) {
    return null;
  }
  return `${ARKNIGHTS_ITEM_ICON_BASE}/${key}.png`;
}

/** 仅真实图：上游 icon_url 或方可拼出的方舟物品图。无图返回 null，走纯文本。 */
export function resolveAwardIconUrl(award: CheckinAward): string | null {
  const direct = (award.icon_url || "").trim();
  if (direct) return direct;
  return arknightsItemIcon(award.resource_type);
}

/** 无图标时的奖励文案：`情报拼图*10, 经验*55` */
export function formatAwardsPlainText(awards: CheckinAward[]): string {
  return awards
    .filter((item) => item?.name)
    .map((item) => `${item.name}*${item.count ?? 1}`)
    .join(", ");
}

/** 把「情报拼图×10 · 经验×55」一类文案拆成结构化条目。 */
export function parseAwardsText(text: string): CheckinAward[] {
  const raw = text.trim();
  if (!raw || isStatusAwardsText(raw)) return [];
  const parts = raw
    .split(/[·，,、/]/)
    .map((part) => part.trim())
    .filter(Boolean);
  const out: CheckinAward[] = [];
  for (const part of parts) {
    if (isStatusAwardsText(part)) continue;
    const matched = part.match(
      /^(?<name>.+?)\s*[×xX*＊＋+]\s*(?<count>\d+)\s*$/,
    );
    if (matched?.groups?.name) {
      out.push({
        name: matched.groups.name.trim(),
        count: Number(matched.groups.count),
      });
      continue;
    }
    out.push({ name: part, count: 1 });
  }
  return out;
}

export function awardsForDisplay(
  awards?: CheckinAward[] | null,
  awardsText?: string | null,
): CheckinAward[] {
  const list = (awards || []).filter((item) => item?.name);
  if (list.length) return list;
  const text = (awardsText || "").trim();
  if (!text) return [];
  return parseAwardsText(text);
}

export type TodayAwardsInput = {
  status?: string | null;
  awards?: CheckinAward[] | null;
  awardsText?: string | null;
  gameCode?: string | null;
  channelName?: string | null;
};

/**
 * 今日奖励列：已签且有条目 → null（画奖励）；
 * 未签/失败等 → 提示文案；已签但无条目 → 空串（不占位）。
 */
export function todayAwardsHint(input: TodayAwardsInput): string | null {
  if (!isCheckinSuccess(input.status)) {
    const status = (input.status || "").trim();
    if (status === CHECKIN_STATUS.ERROR) return "签到失败";
    if (status === CHECKIN_STATUS.UNKNOWN) return "待确认";
    if (status === CHECKIN_STATUS.SKIPPED) return "已跳过";
    return "今日未签到";
  }
  if (awardsForDisplay(input.awards, input.awardsText).length) return null;
  if (
    input.gameCode === "arknights" &&
    isBilibiliArknightsChannel(input.channelName)
  ) {
    return "B服不支持查询";
  }
  return "";
}
