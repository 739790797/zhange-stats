import { Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import type { ReactNode } from "react";
import type { UserCheckinTask } from "@/api/client";
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

export function lastResultTag(task: Pick<UserCheckinTask, "last_checkin_ok">) {
  if (task.last_checkin_ok === true) {
    return <Tag color="success">成功</Tag>;
  }
  if (task.last_checkin_ok === false) {
    return <Tag color="error">失败</Tag>;
  }
  return <Tag>未执行</Tag>;
}

/** 角色级任务共用列：是否启用 / 计划时间 / 上次执行时间 / 结果 / 摘要 */
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
        leaf(row, (t) => (
          <Typography.Text>
            {formatCheckinTime(t.checkin_hour, t.checkin_minute)}
          </Typography.Text>
        )),
    },
    {
      title: "上次执行时间",
      key: "last_at",
      width: 170,
      render: (_, row) =>
        leaf(row, (t) => (
          <Typography.Text type="secondary">
            {t.last_checkin_at || t.last_checkin_date || "-"}
          </Typography.Text>
        )),
    },
    {
      title: "上次执行结果",
      key: "last_status",
      width: 110,
      align: "center",
      render: (_, row) => leaf(row, (t) => lastResultTag(t)),
    },
    {
      title: "上次摘要",
      key: "last_summary",
      ellipsis: true,
      render: (_, row) =>
        leaf(row, (t) => (
          <Typography.Text type="secondary" ellipsis>
            {t.last_checkin_summary || "-"}
          </Typography.Text>
        )),
    },
  ];
}
