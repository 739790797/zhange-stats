import { Tag, Typography } from "antd";
import {
  checkinStatusLabel,
  checkinStatusTagColor,
} from "@/lib/checkinStatus";

/** 签到状态 Tag：统一中文文案（已签 / 失败 / 跳过 / 未签） */
export function CheckinStatusTag({
  status,
  statusLabel,
}: {
  status?: string | null;
  statusLabel?: string | null;
}) {
  if (!status && !statusLabel) {
    return <Typography.Text type="secondary">-</Typography.Text>;
  }
  return (
    <Tag color={checkinStatusTagColor(status)}>
      {checkinStatusLabel(status, statusLabel)}
    </Tag>
  );
}
