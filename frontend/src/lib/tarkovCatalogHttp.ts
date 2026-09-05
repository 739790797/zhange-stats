export const CATALOG_HTTP_CACHE_MAX = 80;

const SKIP_SUBSTRINGS = [
  "/raid-rooms",
  "/goons",
  "/search",
  "/key-owns",
  "/collection-owns",
  "/collection-layout",
  "/task-dones",
  "/raid-logs",
  "/raid-prep/state",
];

export function isTarkovCatalogGet(
  method: string | undefined,
  url: string,
): boolean {
  const verb = (method || "get").toLowerCase();
  if (verb !== "get") return false;
  if (!url.includes("/guides/tarkov")) return false;
  return !SKIP_SUBSTRINGS.some((part) => url.includes(part));
}

export function tarkovCatalogCacheKey(url: string, params: unknown): string {
  return `${url}::${JSON.stringify(params || {})}`;
}

/** 地图目录 / 详情 / 散落物图层 JSON（不含 places 写接口）。 */
export function isTarkovMapFileUrl(url: string): boolean {
  const path = (url.split("?")[0] || "").replace(/\/+$/, "");
  if (path.endsWith("/guides/tarkov/maps")) return true;
  if (/\/guides\/tarkov\/maps\/[^/]+\/loot$/.test(path)) return true;
  return /\/guides\/tarkov\/maps\/[^/]+$/.test(path);
}

export function catalogCacheKeyIsMapFile(cacheKey: string): boolean {
  const url = cacheKey.split("::")[0] || "";
  return isTarkovMapFileUrl(url);
}

/** 超出上限时删掉最旧的 key（keys 按插入顺序，最旧在前）。 */
export function catalogBodyKeysToEvict(
  keysOldestFirst: readonly string[],
  max = CATALOG_HTTP_CACHE_MAX,
): string[] {
  if (keysOldestFirst.length <= max) return [];
  return keysOldestFirst.slice(0, keysOldestFirst.length - max);
}
