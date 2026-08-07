import { Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { CSSProperties, ReactNode } from "react";
import type { UserCheckinTask } from "@/api/client";
import { CheckinAwardsLine } from "@/components/CheckinAwardsLine";
import { CheckinStatusTag } from "@/components/CheckinStatusTag";
import {
  PlatformIcon,
  checkinGameIcon,
  featureIconName,
} from "@/components/PlatformIcon";
import { isCheckinSuccess } from "@/lib/checkinStatus";
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
};

/** 各平台「社区」签到的 game_code，展示时排最前 */
export const COMMUNITY_CHECKIN_GAME_CODES = new Set([
  "app", // 塔吉多
  "kujiequ", // 库街区
  "exilium_bbs", // 追放
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

export function autoEnabledTag(enabled: boolean | "partial") {
  if (enabled === true) return <Tag color="success">开启</Tag>;
  if (enabled === "partial") return <Tag color="processing">部分开启</Tag>;
  return <Tag>关闭</Tag>;
}

const nameLabelStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  minWidth: 0,
};

/** 日常 / 任务调度树：平台、游戏名称前的品牌图标 */
export function CheckinTreeNameLabel(props: {
  kind: "platform" | "game";
  platform: string;
  label: string;
  gameCode?: string | null;
  strong?: boolean;
  type?: "secondary";
  style?: CSSProperties;
}) {
  const { kind, platform, label, gameCode, strong, type, style } = props;
  const platformIcon = featureIconName(platform);
  const iconName =
    kind === "platform"
      ? platformIcon
      : checkinGameIcon(gameCode, platformIcon);

  return (
    <span style={{ ...nameLabelStyle, ...style }}>
      {iconName ? <PlatformIcon name={iconName} size={16} /> : null}
      <Typography.Text strong={strong} type={type} ellipsis>
        {label}
      </Typography.Text>
    </span>
  );
}

/** 角色级任务共用列：启用 / 计划 / 今日签到 / 签到奖励（已签才展示） */
export function buildCheckinTaskScheduleColumns<T>(options: {
  /** 仅叶子行（角色任务）渲染内容 */
  isLeaf: (row: T) => boolean;
  /** 从行取出任务字段；非叶子可不调用 */
  getTask: (row: T) => UserCheckinTask;
}): ColumnsType<T> {
  const { isLeaf, getTask } = options;
  const leaf = (row: T, node: (task: UserCheckinTask) => ReactNode) => {
    if (!isLeaf(row)) return null;
    return node(getTask(row));
  };

  return [
    {
      title: "是否启用",
      key: "auto",
      width: 100,
      align: "center",
      render: (_, row) => leaf(row, (t) => autoEnabledTag(t.auto_checkin)),
    },
    {
      title: "计划时间",
      key: "schedule",
      width: 100,
      render: (_, row) =>
        leaf(row, (t) =>
          t.auto_checkin ? (
            <Typography.Text>
              {formatCheckinTime(t.checkin_hour, t.checkin_minute)}
            </Typography.Text>
          ) : (
            <Typography.Text type="secondary">-</Typography.Text>
          ),
        ),
    },
    {
      title: "今日签到",
      key: "today_status",
      width: 100,
      align: "center",
      render: (_, row) =>
        leaf(row, (t) => (
          <CheckinStatusTag
            status={t.today_status}
            statusLabel={t.today_status_label}
          />
        )),
    },
    {
      title: "签到奖励",
      key: "today_summary",
      ellipsis: true,
      render: (_, row) =>
        leaf(row, (t) =>
          isCheckinSuccess(t.today_status) ? (
            <CheckinAwardsLine
              awards={t.today_awards}
              awardsText={t.today_awards_text}
              fallback="-"
            />
          ) : (
            <Typography.Text type="secondary">-</Typography.Text>
          ),
        ),
    },
  ];
}
