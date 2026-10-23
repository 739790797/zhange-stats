import { recordAxiosRum } from "@/app/telemetry/httpAxios";
import { notifyUnauthorized } from "@/features/auth/api/httpInterceptors";
import {
  isUpstreamRepoNotSyncedError,
  UPSTREAM_REPO_NOT_SYNCED_EVENT,
} from "./upstreamRepoSyncPrompt";

type HttpErrorLike = {
  config?: { url?: string; baseURL?: string; method?: string };
  response?: {
    headers?: Record<string, string | undefined>;
    status?: number;
    data?: { code?: unknown };
  };
};

export function handleHttpError(error: unknown): Promise<never> {
  const details = (error && typeof error === "object" ? error : {}) as HttpErrorLike;
  recordAxiosRum(details.config, Number(details.response?.status || 0));
  const headers = details.response?.headers;
  const rid = headers?.["x-request-id"] || headers?.["X-Request-ID"];
  if (rid && error && typeof error === "object") {
    (error as { requestId?: string }).requestId = String(rid);
  }
  const url = String(details.config?.url || "");
  const status = details.response?.status;
  const code = details.response?.data?.code;
  if (isUpstreamRepoNotSyncedError(error) && typeof window !== "undefined") {
    window.dispatchEvent(new Event(UPSTREAM_REPO_NOT_SYNCED_EVENT));
  }
  if (status === 503 && code === "SETUP_REQUIRED") {
    if (
      typeof window !== "undefined" &&
      !window.location.pathname.startsWith("/setup")
    ) {
      window.location.assign("/setup");
    }
    return Promise.reject(error);
  }
  notifyUnauthorized(Number(status || 0), url);
  return Promise.reject(error);
}
