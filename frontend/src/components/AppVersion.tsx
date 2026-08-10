import { useQuery } from "@tanstack/react-query";
import { Typography } from "antd";
import { Link } from "react-router-dom";
import { isAdminUser } from "@/lib/isAdminUser";
import { useAuthStore } from "@/stores/authStore";

async function fetchAppVersion(): Promise<string> {
  const res = await fetch("/health", { cache: "no-store" });
  // degraded 时后端返回 503，仍带 version 字段
  try {
    const data = (await res.json()) as { version?: string };
    return (data.version || "").replace(/^v/i, "").trim();
  } catch {
    return "";
  }
}

/** 展示当前运行中的应用版本（来自 /health） */
export function AppVersion({ light = false }: { light?: boolean }) {
  const user = useAuthStore((s) => s.user);
  const { data: version } = useQuery({
    queryKey: ["app-version"],
    queryFn: fetchAppVersion,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  if (!version) return null;

  const style = {
    display: "block" as const,
    textAlign: "center" as const,
    fontSize: 12,
    color: light ? "rgba(255,255,255,0.45)" : "rgba(0,0,0,0.35)",
    userSelect: "none" as const,
  };

  if (isAdminUser(user)) {
    return (
      <Link to="/settings/system" style={{ textDecoration: "none" }}>
        <Typography.Text style={style}>v{version}</Typography.Text>
      </Link>
    );
  }

  return <Typography.Text style={style}>v{version}</Typography.Text>;
}
