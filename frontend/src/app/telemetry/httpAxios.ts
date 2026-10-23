import {
  axiosRequestPath,
  enqueueRum,
  shouldCollectApiUrl,
} from "./rumCollect";

const rumStarts = new WeakMap<object, number>();

export function markAxiosRumStart(config: object) {
  const started = performance.now();
  rumStarts.set(config, started);
  (config as { rumStartedAt?: number }).rumStartedAt = started;
}

function takeRumStart(config: object | undefined): number | null {
  if (!config) return null;
  const fromMap = rumStarts.get(config);
  if (fromMap != null) {
    rumStarts.delete(config);
    return fromMap;
  }
  const marked = (config as { rumStartedAt?: number }).rumStartedAt;
  if (typeof marked === "number") {
    (config as { rumStartedAt?: number }).rumStartedAt = undefined;
    return marked;
  }
  return null;
}

export function recordAxiosRum(
  config: { baseURL?: string; url?: string; method?: string } | undefined,
  status: number,
) {
  if (!config) return;
  const started = takeRumStart(config);
  if (started == null) return;
  const path = axiosRequestPath(config);
  if (!shouldCollectApiUrl(path)) return;
  enqueueRum({
    kind: "api",
    url: path,
    duration_ms: performance.now() - started,
    status,
    method: String(config.method || "GET").toUpperCase(),
  });
}
