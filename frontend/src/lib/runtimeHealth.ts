import type { RuntimeHealthService } from "@/api/runtimeHealthApi";

/** 会探活的依赖，画成状态卡片。 */
export const RUNTIME_STATUS_IDS = [
  "mysql",
  "redis",
  "scheduler",
  "smtp",
] as const;

/** 部署核对项，只做说明，不伪装成服务。 */
export const RUNTIME_NOTE_IDS = ["app_env", "xff"] as const;

export const RUNTIME_NOTE_LABELS: Record<string, string> = {
  app_env: "运行环境",
  xff: "访客 IP",
};

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

export function runtimeNoteLabel(item: RuntimeHealthService): string {
  return RUNTIME_NOTE_LABELS[item.id] || item.name;
}
