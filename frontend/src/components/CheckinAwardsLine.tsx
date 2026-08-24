import { Space, Typography } from "antd";
import type { CSSProperties } from "react";
import { GAME_RES } from "@/components/arknights/constants";

export type CheckinAward = {
  name: string;
  count?: number;
  resource_id?: string | null;
  resource_type?: string | null;
  icon_url?: string | null;
};

const DEFAULT_ICON_SIZE = 20;

/** 签到日历弹窗内奖励图标尺寸（各 *AttendanceCalendar 统一引用） */
export const CHECKIN_CALENDAR_AWARD_ICON_SIZE = 32;

const iconStyle = (size: number): CSSProperties => ({
  width: size,
  height: size,
  objectFit: "contain",
  verticalAlign: "middle",
  borderRadius: 4,
  background: "rgba(0,0,0,0.04)",
  flexShrink: 0,
});

function resolveAwardIconUrl(a: CheckinAward): string | null {
  const direct = (a.icon_url || "").trim();
  if (direct) return direct;
  // 方舟：resource_type 常即 iconId（如 DIAMOND_SHD）；后端未带 icon_url 时前端兜底
  // 追放等平台的 score/exp 等小写类型不是图床 id，勿拼假 URL（破图会把文案顶开）
  const key = String(a.resource_type || "").trim();
  if (!key || key.includes("/") || key.includes("\\") || key.includes("..")) {
    return null;
  }
  if (!/^[A-Z][A-Z0-9_]*$/.test(key)) {
    return null;
  }
  return `${GAME_RES}/item/${key}.png`;
}

/** 签到奖励展示：有 icon_url（或可解析图标）时显示图标+名称×数量，否则回退文案 */
export function CheckinAwardsLine({
  awards,
  awardsText,
  fallback = "-",
  iconSize = DEFAULT_ICON_SIZE,
}: {
  awards?: CheckinAward[] | null;
  awardsText?: string | null;
  fallback?: string;
  /** 奖励图标边长（px）；签到日历请用 CHECKIN_CALENDAR_AWARD_ICON_SIZE */
  iconSize?: number;
}) {
  const list = (awards || []).filter((a) => a?.name);
  if (list.length) {
    const withIcons = list.some((a) => resolveAwardIconUrl(a));
    if (!withIcons) {
      return (
        <Typography.Text type="secondary">
          {list.map((a) => `${a.name}×${a.count ?? 1}`).join(" · ")}
        </Typography.Text>
      );
    }
    return (
      <Space size={iconSize > DEFAULT_ICON_SIZE ? 12 : 10} wrap>
        {list.map((a, idx) => {
          const count = a.count ?? 1;
          const key = `${a.resource_id || a.resource_type || a.name}-${idx}`;
          const iconUrl = resolveAwardIconUrl(a);
          return (
            <Space key={key} size={6} align="center">
              {iconUrl ? (
                <img
                  src={iconUrl}
                  alt={a.name}
                  width={iconSize}
                  height={iconSize}
                  style={iconStyle(iconSize)}
                  loading="lazy"
                  referrerPolicy="no-referrer"
                  onError={(e) => {
                    (e.currentTarget as HTMLImageElement).style.display = "none";
                  }}
                />
              ) : null}
              <Typography.Text type="secondary">
                {a.name}×{count}
              </Typography.Text>
            </Space>
          );
        })}
      </Space>
    );
  }
  const text = (awardsText || "").trim();
  return (
    <Typography.Text type="secondary">{text || fallback}</Typography.Text>
  );
}
