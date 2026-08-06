/** 签到状态约定（与后端 checkin_common 对齐）。 */
export const CHECKIN_STATUS = {
  OK: "ok",
  ALREADY: "already",
  ERROR: "error",
  SKIPPED: "skipped",
  PENDING: "pending",
  UNKNOWN: "unknown",
} as const;

export const CHECKIN_STATUS_LABEL: Record<string, string> = {
  ok: "已签",
  already: "已签",
  error: "失败",
  skipped: "跳过",
  pending: "未签",
  unknown: "待确认",
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
  if (status === "unknown") return "warning";
  if (status === "pending") return "default";
  return "default";
}

/** 文案是否像凭证/登录失效（弹窗单独提示重新绑定） */
export function isCredentialFailureMessage(text: string | null | undefined): boolean {
  const t = (text || "").trim();
  if (!t) return false;
  return /凭证|登录|登陆|token|授权|重新绑定|已失效|过期|未登录|请重新/.test(t);
}

export type CheckinDialogKind =
  | "success"
  | "already"
  | "failure"
  | "credential"
  | "unknown";

/** 单次签到响应 → 弹窗标题类别 */
export function classifyCheckinDialog(input: {
  skipped?: boolean;
  ok?: boolean | null;
  summary?: string | null;
  status?: string | null;
  message?: string | null;
}): CheckinDialogKind {
  const status = (input.status || "").trim();
  const message = (input.message || input.summary || "").trim();
  if (status === CHECKIN_STATUS.ALREADY || input.skipped) return "already";
  if (status === CHECKIN_STATUS.OK) return "success";
  if (isCredentialFailureMessage(message)) return "credential";
  if (status === CHECKIN_STATUS.ERROR || input.ok === false) return "failure";
  if (isCheckinSuccess(status)) return "success";
  return "unknown";
}

export function checkinDialogTitle(kind: CheckinDialogKind): string {
  switch (kind) {
    case "success":
      return "签到成功";
    case "already":
      return "请勿重复签到";
    case "failure":
    case "credential":
      return "签到失败";
    default:
      return "未知错误";
  }
}
