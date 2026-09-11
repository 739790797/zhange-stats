import axios from "axios";
import {
  CATALOG_HTTP_CACHE_MAX,
  catalogBodyKeysToEvict,
  catalogCacheKeyIsMapFile,
  isTarkovCatalogGet,
  isTarkovMapFileUrl,
  tarkovCatalogCacheKey,
} from "@/lib/tarkovCatalogHttp";
import { getTarkovGameMode } from "@/lib/tarkovGameMode";
import { isUnsafeHttpMethod, readCsrfToken } from "@/lib/csrfCookie";
import {
  axiosRequestPath,
  enqueueRum,
  shouldCollectApiUrl,
} from "@/lib/rumCollect";
import {
  resetLogoutOnce,
  shouldLogoutOn401,
  takeLogoutOnce,
} from "@/lib/shouldLogoutOn401";
import {
  loadAllMapFileEtags,
  loadMapFile,
  saveMapFile,
} from "@/lib/tarkovMapFileStore";
import { useAuthStore } from "@/stores/authStore";

export const client = axios.create({
  baseURL: "/api",
  timeout: 15000,
  withCredentials: true,
});

const rumStarts = new WeakMap<object, number>();

function markRumStart(config: object) {
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

function recordAxiosRum(config: { baseURL?: string; url?: string; method?: string } | undefined, status: number) {
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

/** fetch 流式接口与 axios 拦截器共用：已登录业务 401 只登出一次。 */
export function notifyUnauthorized(status: number, url: string) {
  const hasSession = Boolean(useAuthStore.getState().user);
  if (
    shouldLogoutOn401({
      status,
      url,
      hasSession,
    }) &&
    takeLogoutOnce()
  ) {
    void import("./authApi")
      .then((m) => m.logoutRequest())
      .catch(() => {
        /* 会话已失效时 logout 仍可能 401/403，本地照样清掉 */
      })
      .finally(() => {
        useAuthStore.getState().logout();
      });
    window.setTimeout(() => resetLogoutOnce(), 1500);
  }
}

const catalogBodies = new Map<string, unknown>();
const catalogEtags = new Map<string, string>();

let mapFileHydrate: Promise<void> | null = null;

function rememberCatalogBody(key: string, body: unknown) {
  catalogBodies.delete(key);
  catalogBodies.set(key, body);
  for (const evict of catalogBodyKeysToEvict(
    [...catalogBodies.keys()],
    CATALOG_HTTP_CACHE_MAX,
  )) {
    catalogBodies.delete(evict);
    if (!catalogCacheKeyIsMapFile(evict)) catalogEtags.delete(evict);
  }
}

function hydrateMapFileCache(): Promise<void> {
  if (!mapFileHydrate) {
    mapFileHydrate = loadAllMapFileEtags()
      .then((etags) => {
        for (const [key, etag] of etags) {
          catalogEtags.set(key, etag);
        }
      })
      .catch(() => {
        /* 无 IndexedDB / 隐私模式 */
      });
  }
  return mapFileHydrate;
}

client.interceptors.request.use(async (config) => {
  markRumStart(config);
  if (isUnsafeHttpMethod(config.method)) {
    const csrf = readCsrfToken();
    if (csrf) {
      config.headers["X-CSRF-Token"] = csrf;
    }
  }
  const url = String(config.url || "");
  if (url.includes("/guides/tarkov")) {
    config.params = { game_mode: getTarkovGameMode(), ...config.params };
  }
  if (isTarkovCatalogGet(config.method, url)) {
    const key = tarkovCatalogCacheKey(url, config.params);
    if (isTarkovMapFileUrl(url)) {
      await hydrateMapFileCache();
      if (!catalogBodies.has(key)) {
        try {
          const rec = await loadMapFile(key);
          if (rec?.etag) {
            catalogEtags.set(key, rec.etag);
          } else {
            catalogEtags.delete(key);
          }
        } catch {
          catalogEtags.delete(key);
        }
      }
    }
    const etag = catalogEtags.get(key);
    if (etag && (catalogBodies.has(key) || isTarkovMapFileUrl(url))) {
      config.headers["If-None-Match"] = etag;
    }
    config.validateStatus = (status) =>
      (status >= 200 && status < 300) || status === 304;
  }
  return config;
});

client.interceptors.response.use(
  async (res) => {
    recordAxiosRum(res.config, res.status);
    const url = String(res.config.url || "");
    if (!isTarkovCatalogGet(res.config.method, url)) return res;
    const key = tarkovCatalogCacheKey(url, res.config.params);
    if (res.status === 304) {
      let cached = catalogBodies.get(key);
      if (cached === undefined && isTarkovMapFileUrl(url)) {
        try {
          const rec = await loadMapFile(key);
          if (rec && rec.body !== undefined) {
            cached = rec.body;
            rememberCatalogBody(key, rec.body);
          }
        } catch {
          /* IndexedDB 读失败则保持空 body */
        }
      }
      if (cached !== undefined) {
        res.data = cached;
      }
      return res;
    }
    const etag = res.headers?.etag || res.headers?.ETag;
    if (etag) catalogEtags.set(key, String(etag));
    rememberCatalogBody(key, res.data);
    if (isTarkovMapFileUrl(url) && etag) {
      void saveMapFile(key, {
        etag: String(etag),
        body: res.data,
        savedAt: Date.now(),
      }).catch(() => {
        /* 配额满则下次再写 */
      });
    }
    return res;
  },
  (error) => {
    recordAxiosRum(error.config, Number(error.response?.status || 0));
    const headers = error.response?.headers as
      | Record<string, string | undefined>
      | undefined;
    const rid = headers?.["x-request-id"] || headers?.["X-Request-ID"];
    if (rid && error && typeof error === "object") {
      (error as { requestId?: string }).requestId = String(rid);
    }
    const url = String(error.config?.url || "");
    const status = error.response?.status;
    const code = error.response?.data?.code;
    if (status === 503 && code === "SETUP_REQUIRED") {
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/setup")) {
        window.location.assign("/setup");
      }
      return Promise.reject(error);
    }
    notifyUnauthorized(Number(status || 0), url);
    return Promise.reject(error);
  },
);
