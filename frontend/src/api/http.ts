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
import {
  loadAllMapFileEtags,
  loadMapFile,
  saveMapFile,
} from "@/lib/tarkovMapFileStore";
import { useAuthStore } from "@/stores/authStore";

export const client = axios.create({
  baseURL: "/api",
  timeout: 15000,
});

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
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
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
    const url = String(error.config?.url || "");
    const isLoginAttempt = url.includes("/auth/login");
    const status = error.response?.status;
    const code = error.response?.data?.code;
    if (status === 503 && code === "SETUP_REQUIRED") {
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/setup")) {
        window.location.assign("/setup");
      }
      return Promise.reject(error);
    }
    if (status === 401 && !isLoginAttempt) {
      useAuthStore.getState().logout();
    }
    return Promise.reject(error);
  },
);
