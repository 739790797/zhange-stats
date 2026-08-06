import { Space, Typography } from "antd";
import type { CSSProperties } from "react";

export type CheckinAward = {
  name: string;
  count?: number;
  resource_id?: string | null;
  resource_type?: string | null;
  icon_url?: string | null;
};

const iconStyle: CSSProperties = {
  width: 20,
  height: 20,
  objectFit: "contain",
  verticalAlign: "middle",
  borderRadius: 3,
  background: "rgba(0,0,0,0.04)",
};

/** 签到奖励展示：有 icon_url（方舟）时显示图标+名称×数量，否则回退文案 */
export function CheckinAwardsLine({
  awards,
  awardsText,
  fallback = "-",
}: {
  awards?: CheckinAward[] | null;
  awardsText?: string | null;
  fallback?: string;
}) {
  const list = (awards || []).filter((a) => a?.name);
  if (list.length) {
    return (
      <Space size={10} wrap>
        {list.map((a, idx) => {
          const count = a.count ?? 1;
          const key = `${a.resource_id || a.resource_type || a.name}-${idx}`;
          return (
            <Space key={key} size={4}>
              {a.icon_url ? (
                <img
                  src={a.icon_url}
                  alt={a.name}
                  width={20}
                  height={20}
                  style={iconStyle}
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
