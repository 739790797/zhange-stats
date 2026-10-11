import { normalizeAppVersion } from "@/lib/appVersionCheck";
import { client } from "./http";
import type { components } from "./generated/schema";

export type AppUpdateStatus = components["schemas"]["AppUpdateStatusOut"];
export type AppUpdateCheckResult = components["schemas"]["AppUpdateCheckOut"];
export type AppUpdateDoResult = components["schemas"]["AppUpdateDoOut"];
export type AppUpdateDoIn = components["schemas"]["AppUpdateDoIn"];

export async function fetchAppUpdateStatus() {
  const { data } = await client.get<AppUpdateStatus>("/settings/app-update/status");
  return data;
}

export async function checkAppUpdate() {
  const { data } = await client.post<AppUpdateCheckResult>("/settings/app-update/check");
  return data;
}

export async function doAppUpdate(payload: Partial<AppUpdateDoIn> = {}) {
  const { data } = await client.post<AppUpdateDoResult>(
    "/settings/app-update/do",
    {
      version: payload.version ?? "latest",
      proxy: payload.proxy ?? null,
      reboot: payload.reboot ?? true,
    },
    { timeout: 120_000 },
  );
  return data;
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(signal.reason);
      return;
    }
    const onAbort = () => {
      clearTimeout(timer);
      reject(signal?.reason);
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

/** Poll /health until version matches expected (post-restart). */
export async function waitForHealthVersion(
  expectedVersion: string,
  opts?: {
    timeoutMs?: number;
    intervalMs?: number;
    /** Return early if this throws/returns a string error. */
    shouldAbort?: () => string | null | undefined | Promise<string | null | undefined>;
    /** 离开页面时停止轮询；中止后以 signal.reason 拒绝。 */
    signal?: AbortSignal;
  },
): Promise<string> {
  const timeoutMs = opts?.timeoutMs ?? 600_000;
  const intervalMs = opts?.intervalMs ?? 2000;
  const signal = opts?.signal;
  const want = normalizeAppVersion(expectedVersion);
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    signal?.throwIfAborted();
    if (opts?.shouldAbort) {
      const abortMsg = await opts.shouldAbort();
      signal?.throwIfAborted();
      if (abortMsg) {
        throw new Error(abortMsg);
      }
    }
    try {
      // 重启后探活公开 /health（无 Cookie / CSRF）；不走 *Api
      const res = await fetch("/health", { cache: "no-store", signal });
      const data = (await res.json()) as { version?: string };
      const got = normalizeAppVersion(data.version);
      if (got && got === want) return got;
    } catch {
      // restarting
    }
    await sleep(intervalMs, signal);
  }
  throw new Error("等待服务恢复超时，请手动刷新页面确认版本");
}
