import { Tag, Tooltip, Typography } from "antd";
import {
  CHECKIN_STATUS,
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
  const tag = (
    <Tag color={checkinStatusTagColor(status)}>
      {checkinStatusLabel(status, statusLabel)}
    </Tag>
  );
  if (status === CHECKIN_STATUS.UNKNOWN) {
    return (
      <Tooltip title="上游未返回明确状态，可手动点签到确认">
        {tag}
      </Tooltip>
    );
  }
  return tag;
}
