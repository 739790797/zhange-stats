/** 签到状态约定（与后端 checkin_common 对齐）。 */
export const CHECKIN_STATUS = {
  OK: "ok",
  ALREADY: "already",
  ERROR: "error",
  SKIPPED: "skipped",
  PENDING: "pending",
} as const;

export const CHECKIN_STATUS_LABEL: Record<string, string> = {
  ok: "已签",
  already: "已签",
  error: "失败",
  skipped: "跳过",
  pending: "未签",
};

export function isCheckinSuccess(status: string | null | undefined): boolean {
  return status === "ok" || status === "already";
}

export function checkinStatusLabel(
  status: string | null | undefined,
  statusLabel?: string | null
): string {
  if (statusLabel) return statusLabel;
  const key = (status || "").trim();
  return CHECKIN_STATUS_LABEL[key] || key || "-";
}

/** Ant Design Tag color：成功态统一 processing（蓝「已签」） */
export function checkinStatusTagColor(status: string | null | undefined): string {
  if (isCheckinSuccess(status)) return "processing";
  if (status === "error") return "error";
  if (status === "pending") return "default";
  return "default";
}
