import { Link } from "react-router-dom";
import { isAdminUser } from "@/features/auth/model/isAdminUser";
import { useAuthStore } from "@/features/auth/model/authStore";
import { useServerAppVersion } from "@/shared/hooks/useServerAppVersion";
import { AppVersionText } from "@/shared/ui/AppVersionText";

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

  const admin = isAdminUser(user);
  const tip =
    hasUpdate && latestVersion ? `有新版本 v${latestVersion}` : undefined;
  const wrapStyle = {
    textDecoration: "none" as const,
    display: inline ? ("inline-flex" as const) : ("block" as const),
    alignItems: "center" as const,
    textAlign: (inline ? "start" : "center") as "start" | "center",
  };
  const label = (
    <AppVersionText
      version={version}
      light={light}
      badge={admin}
      hasUpdate={hasUpdate}
      latestVersion={latestVersion}
      inline={inline}
    />
  );

  if (admin) {
    return (
      <Link to="/settings/system" style={wrapStyle} title={tip}>
        {label}
      </Link>
    );
  }

  return <div style={wrapStyle}>{label}</div>;
}
