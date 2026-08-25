/** 将 FastAPI / axios 错误转为用户可读文案（无 DOM / store 依赖，便于单测）。 */

function detailText(detail: unknown): string | null {
  if (detail == null) return null;
  if (typeof detail === "string") {
    const trimmed = detail.trim();
    if (!trimmed) return null;
    if (trimmed.startsWith("{")) {
      try {
        const parsed = JSON.parse(trimmed) as {
          msg?: unknown;
          message?: unknown;
        };
        const nested = parsed.msg ?? parsed.message;
        if (typeof nested === "string" && nested.trim()) {
          return nested.trim();
        }
      } catch {
        /* 保持原文字 */
      }
    }
    return trimmed;
  }
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        return null;
      })
      .filter(Boolean);
    return parts.length ? parts.join("；") : null;
  }
  return String(detail);
}

/** 区分网络/服务故障与业务错误（如账号密码错误）。 */
export function formatRequestError(
  e: unknown,
  fallback = "请求失败",
): string {
  if (!e || typeof e !== "object") return fallback;
  const err = e as {
    code?: string;
    message?: string;
    response?: { status?: number; data?: { detail?: unknown } };
  };
  const status = err.response?.status;
  const detail = detailText(err.response?.data?.detail);

  if (!err.response) {
    if (err.code === "ECONNABORTED" || /timeout/i.test(err.message || "")) {
      return "连接服务器超时，请稍后重试";
    }
    if (
      "request" in err ||
      err.code === "ERR_NETWORK" ||
      ("isAxiosError" in err &&
        Boolean((err as { isAxiosError?: boolean }).isAxiosError))
    ) {
      return "无法连接服务器，请确认服务已启动";
    }
    if (typeof err.message === "string" && err.message.trim()) {
      return err.message.trim();
    }
    return fallback;
  }
  if (status && status >= 500) {
    return detail || "服务暂时不可用，请稍后重试";
  }
  if (status === 429) {
    return detail || "请求过于频繁，请稍后再试";
  }
  if (status === 422) {
    return detail || "请求参数不正确";
  }
  if (status === 403) {
    return detail || "没有权限或尚未完成验证";
  }
  if (status === 401) {
    return detail || fallback;
  }
  return detail || fallback;
}
