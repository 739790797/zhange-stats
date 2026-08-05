import { formatRequestError } from "@/lib/formatRequestError";

/** 业务/页面侧统一取错误文案（网络、5xx、detail 等）。 */
export function apiError(e: unknown, fallback: string): string {
  return formatRequestError(e, fallback);
}
