import type { RuntimeHealthService } from "@/api/runtimeHealthApi";

/** 本机依赖探活，画在运行环境表单标签旁。 */
export const RUNTIME_STATUS_IDS = ["database", "redis"] as const;

export const HEALTH_TAG: Record<string, { color: string; label: string }> = {
  ok: { color: "success", label: "正常" },
  degraded: { color: "warning", label: "降级" },
  error: { color: "error", label: "异常" },
  offline: { color: "error", label: "离线" },
  skipped: { color: "default", label: "未启用" },
};

export function healthMeta(status: string) {
  return HEALTH_TAG[status] ?? { color: "default", label: status || "—" };
}

export function healthHint(
  item: Pick<RuntimeHealthService, "detail" | "latency_ms">,
): string {
  const latency =
    item.latency_ms != null && Number.isFinite(item.latency_ms)
      ? `${Math.round(item.latency_ms)}ms`
      : "";
  return [item.detail, latency].filter(Boolean).join(" · ");
}

export function healthById(
  services: readonly RuntimeHealthService[] | undefined,
  id: string,
): RuntimeHealthService | undefined {
  return services?.find((item) => item.id === id);
}

export function pickHealthServices(
  services: readonly RuntimeHealthService[] | undefined,
  ids: readonly string[],
): RuntimeHealthService[] {
  if (!services?.length) return [];
  const byId = new Map(services.map((item) => [item.id, item]));
  return ids.flatMap((id) => {
    const item = byId.get(id);
    return item ? [item] : [];
  });
}
