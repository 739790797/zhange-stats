import { Badge, Typography } from "antd";

type Props = {
  version: string;
  light?: boolean;
  badge?: boolean;
  hasUpdate?: boolean;
  latestVersion?: string;
  inline?: boolean;
};

/** 版本号的纯展示部分；路由与当前用户权限由 app/auth owner 决定。 */
export function AppVersionText({
  version,
  light = false,
  badge = false,
  hasUpdate = false,
  latestVersion,
  inline = false,
}: Props) {
  const style = {
    display: "inline-block" as const,
    textAlign: (inline ? "start" : "center") as "start" | "center",
    fontSize: 12,
    color: light ? "rgba(255,255,255,0.45)" : "rgba(0,0,0,0.35)",
    userSelect: "none" as const,
  };
  const tip = hasUpdate && latestVersion ? `有新版本 v${latestVersion}` : undefined;
  const text = <Typography.Text style={style}>v{version}</Typography.Text>;
  return badge ? (
    <Badge dot={hasUpdate} offset={[4, 0]} color="#ff4d4f" title={tip}>
      {text}
    </Badge>
  ) : (
    text
  );
}
