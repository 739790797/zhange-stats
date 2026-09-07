import { formatRequestError } from "@/lib/formatRequestError";

/** 业务/页面侧统一取错误文案（网络、5xx、detail 等）。 */
export function apiError(e: unknown, fallback: string): string {
  return formatRequestError(e, fallback);
}

export function apiStatus(e: unknown): number | undefined {
  if (!e || typeof e !== "object") return undefined;
  const status = (e as { response?: { status?: number } }).response?.status;
  return typeof status === "number" ? status : undefined;
}

export function isApiForbidden(e: unknown): boolean {
  return apiStatus(e) === 403;
}
