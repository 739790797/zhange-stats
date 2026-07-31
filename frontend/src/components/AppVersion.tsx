import { useQuery } from "@tanstack/react-query";
import { Typography } from "antd";

async function fetchAppVersion(): Promise<string> {
  const res = await fetch("/health", { cache: "no-store" });
  if (!res.ok) return "";
  const data = (await res.json()) as { version?: string };
  const v = (data.version || "").replace(/^v/i, "").trim();
  return v;
}

/** 展示当前运行中的应用版本（来自 /health） */
export function AppVersion({ light = false }: { light?: boolean }) {
  const { data: version } = useQuery({
    queryKey: ["app-version"],
    queryFn: fetchAppVersion,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  if (!version) return null;

  return (
    <Typography.Text
      style={{
        display: "block",
        textAlign: "center",
        fontSize: 12,
        color: light ? "rgba(255,255,255,0.45)" : "rgba(0,0,0,0.35)",
        userSelect: "none",
      }}
    >
      v{version}
    </Typography.Text>
  );
}
