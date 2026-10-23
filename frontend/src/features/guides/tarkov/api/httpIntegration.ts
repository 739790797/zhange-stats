import type {
  AxiosInstance,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from "axios";
import {
  CATALOG_HTTP_CACHE_MAX,
  catalogBodyKeysToEvict,
  catalogCacheKeyIsMapFile,
  isTarkovCatalogGet,
  isTarkovMapFileUrl,
  tarkovCatalogCacheKey,
} from "@/features/guides/tarkov/model/tarkovCatalogHttp";
import { getTarkovGameMode } from "@/features/guides/tarkov/model/tarkovGameMode";
import {
  loadAllMapFileEtags,
  loadMapFile,
  saveMapFile,
} from "@/features/guides/tarkov/model/tarkovMapFileStore";

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
        for (const [key, etag] of etags) catalogEtags.set(key, etag);
      })
      .catch(() => {
        /* 无 IndexedDB / 隐私模式 */
      });
  }
  return mapFileHydrate;
}

export async function prepareTarkovRequest(
  config: InternalAxiosRequestConfig,
): Promise<InternalAxiosRequestConfig> {
  const url = String(config.url || "");
  if (url.includes("/guides/tarkov")) {
    config.params = { game_mode: getTarkovGameMode(), ...config.params };
  }
  if (isTarkovCatalogGet(config.method, url)) {
    const key = tarkovCatalogCacheKey(url, config.params);
    if (isTarkovMapFileUrl(url)) await hydrateMapFileCache();
    const etag = catalogEtags.get(key);
    if (etag && (catalogBodies.has(key) || isTarkovMapFileUrl(url))) {
      config.headers["If-None-Match"] = etag;
    }
    config.validateStatus = (status) =>
      (status >= 200 && status < 300) || status === 304;
  }
  return config;
}

export async function handleTarkovResponse(
  res: AxiosResponse,
  client: AxiosInstance,
): Promise<AxiosResponse> {
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
        /* IndexedDB 读失败时按缺正文处理 */
      }
    }
    if (cached !== undefined) {
      res.data = cached;
      return res;
    }
    const marked = res.config as { catalogRefetch?: boolean };
    if (marked.catalogRefetch) return res;
    // 本地已没有这份正文（被淘汰或读不出来），304 没法用：去掉条件头整份重拉一次。
    catalogEtags.delete(key);
    res.config.headers.delete("If-None-Match");
    return client.request({ ...res.config, catalogRefetch: true } as typeof res.config);
  }
  const etag = res.headers?.etag || res.headers?.ETag;
  if (etag) catalogEtags.set(key, String(etag));
  rememberCatalogBody(key, res.data);
  if (isTarkovMapFileUrl(url) && etag) {
    void saveMapFile(key, {
      etag: String(etag),
      body: res.data,
      savedAt: Date.now(),
    })
      .then((evicted) => {
        for (const itemKey of evicted) {
          if (!catalogBodies.has(itemKey)) catalogEtags.delete(itemKey);
        }
      })
      .catch(() => {
        /* 配额满则下次再写 */
      });
  }
  return res;
}
