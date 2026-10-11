import { Badge, Typography } from "antd";
import { Link } from "react-router-dom";
import { useServerAppVersion } from "@/hooks/useServerAppVersion";
import { isAdminUser } from "@/lib/isAdminUser";
import { useAuthStore } from "@/stores/authStore";

/** 展示当前运行中的应用版本（来自 /health） */
export function AppVersion({
  light = false,
  hasUpdate = false,
  latestVersion,
  inline = false,
}: {
  light?: boolean;
  hasUpdate?: boolean;
  latestVersion?: string;
  /** 侧栏顶栏等行内排版，不要独占一行居中 */
  inline?: boolean;
}) {
  const user = useAuthStore((s) => s.user);
  const { data: version } = useServerAppVersion();

  if (!version) return null;

  const style = {
    display: "inline-block" as const,
    textAlign: (inline ? "start" : "center") as "start" | "center",
    fontSize: 12,
    color: light ? "rgba(255,255,255,0.45)" : "rgba(0,0,0,0.35)",
    userSelect: "none" as const,
  };

  const tip =
    hasUpdate && latestVersion ? `有新版本 v${latestVersion}` : undefined;
  const wrapStyle = {
    textDecoration: "none" as const,
    display: inline ? ("inline-flex" as const) : ("block" as const),
    alignItems: "center" as const,
    textAlign: (inline ? "start" : "center") as "start" | "center",
  };

  if (isAdminUser(user)) {
    return (
      <Link to="/settings/system" style={wrapStyle} title={tip}>
        <Badge dot={hasUpdate} offset={[4, 0]} color="#ff4d4f" title={tip}>
          <Typography.Text style={style}>v{version}</Typography.Text>
        </Badge>
      </Link>
    );
  }

  return (
    <div style={wrapStyle}>
      <Typography.Text style={style}>v{version}</Typography.Text>
    </div>
  );
}
