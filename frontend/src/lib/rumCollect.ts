/** 浏览器 RUM：接口转圈 + 第三方图。观察很轻；批量 POST，不上平台日志。 */

export type RumKind = "api" | "img";

export type RumEvent = {
  kind: RumKind;
  url: string;
  duration_ms: number;
  status?: number | null;
  method?: string | null;
  transfer_size?: number | null;
};

const SKIP_API_SUBSTR = [
  "/client-rum",
  "/client-errors",
  "/csp-report",
  "/health",
  "/settings/runtime-logs",
  "/settings/runtime-health",
  "/settings/rum",
];

const IMAGE_EXT = /\.(png|jpe?g|webp|gif|svg|avif|ico|bmp)(?:$|\?)/i;
const MAX_BUFFER = 200;
const FLUSH_AT = 40;
const FLUSH_MS = 4000;
const MAX_BATCH = 80;
const MAX_DURATION_MS = 120_000;
const INGEST_PATH = "/api/client-rum";

let enabled = false;
let buffer: RumEvent[] = [];
let timer: number | null = null;
let observer: PerformanceObserver | null = null;

export function shouldCollectApiUrl(pathname: string): boolean {
  const path = String(pathname || "").split("?")[0];
  if (!path) return false;
  return !SKIP_API_SUBSTR.some((part) => path.includes(part));
}

export function axiosRequestPath(config: {
  baseURL?: string;
  url?: string;
}): string {
  const url = String(config.url || "");
  if (/^https?:\/\//i.test(url)) {
    try {
      return new URL(url).pathname;
    } catch {
      return url.split("?")[0];
    }
  }
  const base = String(config.baseURL || "/api");
  const joined = `${base.replace(/\/$/, "")}/${url.replace(/^\//, "")}`;
  try {
    return new URL(joined, "http://rum.invalid").pathname;
  } catch {
    return joined.split("?")[0];
  }
}

export function isImagePath(pathname: string): boolean {
  return IMAGE_EXT.test(pathname || "");
}

export function shouldCollectImageResource(input: {
  name: string;
  initiatorType: string;
  pageOrigin: string;
}): boolean {
  const name = String(input.name || "");
  if (!name || name.startsWith("data:") || name.startsWith("blob:")) return false;
  let url: URL;
  try {
    url = new URL(name);
  } catch {
    return false;
  }
  if (url.origin === input.pageOrigin) return false;
  const type = String(input.initiatorType || "");
  if (
    type === "xmlhttprequest" ||
    type === "fetch" ||
    type === "beacon" ||
    type === "script" ||
    type === "navigation" ||
    type === "video" ||
    type === "audio"
  ) {
    return false;
  }
  if (type === "img" || type === "image" || type === "icon") return true;
  return isImagePath(url.pathname);
}

function scheduleFlush() {
  if (typeof window === "undefined") return;
  if (timer != null) return;
  timer = window.setTimeout(() => {
    timer = null;
    flushRum();
  }, FLUSH_MS);
}

export function enqueueRum(event: RumEvent) {
  if (!enabled || typeof window === "undefined") return;
  if (!Number.isFinite(event.duration_ms)) return;
  const duration = Math.round(
    Math.min(MAX_DURATION_MS, Math.max(0, event.duration_ms)),
  );
  const url = String(event.url || "").slice(0, 512);
  if (!url) return;
  if (event.kind === "api" && !shouldCollectApiUrl(url)) return;
  buffer.push({
    kind: event.kind,
    url,
    duration_ms: duration,
    status: event.status ?? null,
    method: event.method ? String(event.method).slice(0, 16) : null,
    transfer_size:
      event.transfer_size != null && Number.isFinite(event.transfer_size)
        ? Math.max(0, Math.round(event.transfer_size))
        : null,
  });
  if (buffer.length > MAX_BUFFER) {
    buffer.splice(0, buffer.length - MAX_BUFFER);
  }
  if (buffer.length >= FLUSH_AT) flushRum();
  else scheduleFlush();
}

function postBatch(payload: string) {
  // 不走 axios client：避免拦截器自测、访客无 CSRF、卸载时要用 keepalive。
  try {
    void fetch(INGEST_PATH, {
      method: "POST",
      credentials: "same-origin",
      keepalive: true,
      headers: { "Content-Type": "application/json" },
      body: payload,
    }).catch(() => {
      /* 上报失败不打扰用户 */
    });
    return;
  } catch {
    /* 隐私模式等 */
  }
  try {
    if (typeof navigator !== "undefined" && navigator.sendBeacon) {
      const blob = new Blob([payload], { type: "application/json" });
      navigator.sendBeacon(INGEST_PATH, blob);
    }
  } catch {
    /* 忽略 */
  }
}

export function flushRum() {
  if (timer != null) {
    clearTimeout(timer);
    timer = null;
  }
  if (!buffer.length) return;
  const batch = buffer.splice(0, MAX_BATCH);
  const page =
    typeof location !== "undefined" ? String(location.pathname || "").slice(0, 256) : "";
  postBatch(JSON.stringify({ page, events: batch }));
  if (buffer.length) scheduleFlush();
}

function onResourceEntries(entries: PerformanceEntryList) {
  const origin = typeof location !== "undefined" ? location.origin : "";
  for (const entry of entries) {
    if (entry.entryType !== "resource") continue;
    const resource = entry as PerformanceResourceTiming;
    if (
      !shouldCollectImageResource({
        name: resource.name,
        initiatorType: resource.initiatorType,
        pageOrigin: origin,
      })
    ) {
      continue;
    }
    enqueueRum({
      kind: "img",
      url: resource.name,
      duration_ms: resource.duration,
      transfer_size: resource.transferSize || null,
    });
  }
}

function onHidden() {
  flushRum();
}

export function startRum() {
  if (enabled || typeof window === "undefined") return;
  enabled = true;
  if (typeof PerformanceObserver !== "undefined") {
    try {
      observer = new PerformanceObserver((list) => {
        onResourceEntries(list.getEntries());
      });
      try {
        observer.observe({ type: "resource", buffered: true });
      } catch {
        observer.observe({ entryTypes: ["resource"] });
      }
    } catch {
      observer = null;
    }
  }
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") onHidden();
  });
  window.addEventListener("pagehide", onHidden);
}

export function formatRumMs(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}
