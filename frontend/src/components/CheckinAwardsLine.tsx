import { Typography } from "antd";
import {
  awardsForDisplay,
  formatAwardsPlainText,
  resolveAwardIconUrl,
  todayAwardsHint,
  type CheckinAward,
  type TodayAwardsInput,
} from "@/lib/checkinAwards";
import styles from "./CheckinAwardsLine.module.css";

export type { CheckinAward };

const DEFAULT_ICON_SIZE = 20;

/** 签到日历弹窗内奖励图标尺寸（`AttendanceCalendarButton` 引用） */
export const CHECKIN_CALENDAR_AWARD_ICON_SIZE = 32;

/** 签到奖励：有真实 icon 才画图，否则 `ABC*1, DEF*2`。日常 / 签到页 / 日历 / 任务表共用。 */
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
  const list = awardsForDisplay(awards, awardsText);
  if (!list.length) {
    return (
      <Typography.Text type="secondary">{fallback}</Typography.Text>
    );
  }
  const withIcons = list.filter((item) => resolveAwardIconUrl(item));
  const withoutIcons = list.filter((item) => !resolveAwardIconUrl(item));
  if (!withIcons.length) {
    return (
      <Typography.Text type="secondary">
        {formatAwardsPlainText(withoutIcons)}
      </Typography.Text>
    );
  }
  return (
    <span className={styles.line}>
      {withIcons.map((item, idx) => {
        const count = item.count ?? 1;
        const key = `${item.resource_id || item.resource_type || item.name}-${idx}`;
        const iconUrl = resolveAwardIconUrl(item);
        return (
          <span key={key} className={styles.item}>
            {iconUrl ? (
              <img
                src={iconUrl}
                alt=""
                width={iconSize}
                height={iconSize}
                className={styles.icon}
                style={{ width: iconSize, height: iconSize }}
                loading="lazy"
                referrerPolicy="no-referrer"
                onError={(event) => {
                  event.currentTarget.style.display = "none";
                }}
              />
            ) : null}
            <Typography.Text type="secondary">
              {item.name}*{count}
            </Typography.Text>
          </span>
        );
      })}
      {withoutIcons.length ? (
        <Typography.Text type="secondary">
          {formatAwardsPlainText(withoutIcons)}
        </Typography.Text>
      ) : null}
    </span>
  );
}

/** 今日签到奖励：日常 / 签到页 / 任务表共用。未签只给提示，不展示历史奖励。 */
export function TodayCheckinAwards({
  status,
  awards,
  awardsText,
  gameCode,
  channelName,
  showLabel = false,
}: TodayAwardsInput & { showLabel?: boolean }) {
  const hint = todayAwardsHint({
    status,
    awards,
    awardsText,
    gameCode,
    channelName,
  });
  if (hint === "") return null;
  const body =
    hint === null ? (
      <CheckinAwardsLine
        awards={awards}
        awardsText={awardsText}
        fallback=""
      />
    ) : (
      <Typography.Text type="secondary">{hint}</Typography.Text>
    );
  if (!showLabel) return body;
  return (
    <>
      <Typography.Text type="secondary">签到奖励：</Typography.Text>
      {body}
    </>
  );
}
