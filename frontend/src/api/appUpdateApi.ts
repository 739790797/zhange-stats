import { client } from "./http";
import type { components } from "./generated/schema";

export type AppUpdateStatus = components["schemas"]["AppUpdateStatusOut"];
export type AppUpdateRelease = components["schemas"]["AppUpdateReleaseOut"];
export type AppUpdateCheckResult = components["schemas"]["AppUpdateCheckOut"];
export type AppUpdateDoResult = components["schemas"]["AppUpdateDoOut"];
export type AppUpdateDoIn = components["schemas"]["AppUpdateDoIn"];

export async function fetchAppUpdateStatus() {
  const { data } = await client.get<AppUpdateStatus>("/settings/app-update/status");
  return data;
}

export async function fetchAppUpdateReleases() {
  const { data } = await client.get<AppUpdateRelease[]>("/settings/app-update/releases");
  return data;
}

export async function checkAppUpdate() {
  const { data } = await client.post<AppUpdateCheckResult>("/settings/app-update/check");
  return data;
}

export async function doAppUpdate(payload: Partial<AppUpdateDoIn> = {}) {
  const { data } = await client.post<AppUpdateDoResult>("/settings/app-update/do", {
    version: payload.version ?? "latest",
    proxy: payload.proxy ?? null,
    reboot: payload.reboot ?? true,
  });
  return data;
}

/** Poll /health until version matches expected (post-restart). */
export async function waitForHealthVersion(
  expectedVersion: string,
  opts?: { timeoutMs?: number; intervalMs?: number },
): Promise<string> {
  const timeoutMs = opts?.timeoutMs ?? 120_000;
  const intervalMs = opts?.intervalMs ?? 1500;
  const want = expectedVersion.replace(/^v/i, "").trim();
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
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
