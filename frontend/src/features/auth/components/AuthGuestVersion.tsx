import { Link } from "react-router-dom";
import { useAuthStore } from "@/features/auth/model/authStore";
import { isAdminUser } from "@/features/auth/model/isAdminUser";
import { useServerAppVersion } from "@/shared/hooks/useServerAppVersion";
import { AppVersionText } from "@/shared/ui/AppVersionText";

/** 登录/安装外壳里的版本号；版本获取与显示基元由 shared 提供。 */
export function AuthGuestVersion() {
  const user = useAuthStore((s) => s.user);
  const { data: version } = useServerAppVersion();
  if (!version) return null;

  const admin = isAdminUser(user);
  const wrapStyle = {
    textDecoration: "none" as const,
    display: "block" as const,
    alignItems: "center" as const,
    textAlign: "center" as const,
  };
  const label = <AppVersionText version={version} light badge={admin} />;
  return admin ? (
    <Link to="/settings/system" style={wrapStyle}>
      {label}
    </Link>
  ) : (
    <div style={wrapStyle}>{label}</div>
  );
}
