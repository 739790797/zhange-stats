export const TARKOV_MAP_FILE_CACHE_MAX = 64;

export type TarkovMapFileRecord = {
  etag: string;
  body: unknown;
  savedAt: number;
};

export type TarkovMapFileEtagRecord = {
  etag: string;
  savedAt: number;
};

export function localMapFileMatchesRemote(
  localEtag: string | undefined,
  remoteEtag: string | undefined,
): boolean {
  const local = (localEtag || "").trim();
  const remote = (remoteEtag || "").trim();
  return Boolean(local) && local === remote;
}

/**
 * 正文表里每个 key 配上 etags 表里的保存时间。etags 表缺的行（旧版遗留）按最旧算，先被淘汰；
 * 刚写入的那条以传入的时间为准。
 */
export function mapFileEvictionEntries(
  fileKeys: readonly IDBValidKey[],
  etagKeys: readonly IDBValidKey[],
  etagRecords: readonly (TarkovMapFileEtagRecord | undefined)[],
  saved: { key: string; savedAt: number },
): { key: string; savedAt: number }[] {
  const savedAt = new Map<string, number>();
  etagKeys.forEach((key, index) => {
    if (typeof key === "string") savedAt.set(key, etagRecords[index]?.savedAt || 0);
  });
  savedAt.set(saved.key, saved.savedAt);
  return fileKeys
    .filter((key): key is string => typeof key === "string")
    .map((key) => ({ key, savedAt: savedAt.get(key) ?? 0 }));
}

/** 超出上限时删掉最旧的 key。 */
export function mapFileKeysToEvict(
  entries: readonly { key: string; savedAt: number }[],
  max = TARKOV_MAP_FILE_CACHE_MAX,
): string[] {
  if (entries.length <= max) return [];
  const sorted = [...entries].sort((a, b) => a.savedAt - b.savedAt);
  return sorted.slice(0, entries.length - max).map((row) => row.key);
}
