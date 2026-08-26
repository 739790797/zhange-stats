import { Typography } from "antd";
import type { CSSProperties } from "react";
import { PlatformIcon } from "@/components/PlatformIcon";
import { checkinGameIcon, featureIconName } from "@/lib/platformIcons";

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
  iconSize?: number;
}) {
  const { kind, platform, label, gameCode, strong, type, style, iconSize = 16 } = props;
  const platformIcon = featureIconName(platform);
  const iconName =
    kind === "platform"
      ? platformIcon
      : checkinGameIcon(gameCode, platformIcon);

  return (
    <span style={{ ...nameLabelStyle, ...style }}>
      {iconName ? <PlatformIcon name={iconName} size={iconSize} /> : null}
      <Typography.Text strong={strong} type={type} ellipsis>
        {label}
      </Typography.Text>
    </span>
  );
}
