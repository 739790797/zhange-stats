import { Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { ReactNode } from "react";
import type { UserCheckinTask } from "@/api/client";
import { CheckinAwardsLine } from "@/components/CheckinAwardsLine";
import { CheckinStatusTag } from "@/components/CheckinStatusTag";
import { formatCheckinTime } from "@/lib/checkinDisplay";
import { isCheckinSuccess } from "@/lib/checkinStatus";

function autoEnabledTag(enabled: boolean | "partial") {
  if (enabled === true) return <Tag color="success">开启</Tag>;
  if (enabled === "partial") return <Tag color="processing">部分开启</Tag>;
  return <Tag>关闭</Tag>;
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
