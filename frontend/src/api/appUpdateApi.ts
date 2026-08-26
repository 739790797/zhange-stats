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
  // 接口会立刻返回并在后台执行；仍给足超时以防预检/拉 Release 较慢
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

/** Poll /health until version matches expected (post-restart). */
export async function waitForHealthVersion(
  expectedVersion: string,
  opts?: {
    timeoutMs?: number;
    intervalMs?: number;
    /** Return early if this throws/returns a string error. */
    shouldAbort?: () => string | null | undefined | Promise<string | null | undefined>;
  },
): Promise<string> {
  const timeoutMs = opts?.timeoutMs ?? 600_000;
  const intervalMs = opts?.intervalMs ?? 2000;
  const want = expectedVersion.replace(/^v/i, "").trim();
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (opts?.shouldAbort) {
      const abortMsg = await opts.shouldAbort();
      if (abortMsg) {
        throw new Error(abortMsg);
      }
    }
    try {
      const res = await fetch("/health", { cache: "no-store" });
      const data = (await res.json()) as { version?: string };
      const got = (data.version || "").replace(/^v/i, "").trim();
      if (got && got === want) return got;
    } catch {
      // restarting
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error("等待服务恢复超时，请手动刷新页面确认版本");
}
