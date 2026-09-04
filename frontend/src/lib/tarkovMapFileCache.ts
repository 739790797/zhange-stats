export const TARKOV_MAP_FILE_CACHE_MAX = 64;

export type TarkovMapFileRecord = {
  etag: string;
  body: unknown;
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

/** 超出上限时删掉最旧的 key。 */
export function mapFileKeysToEvict(
  entries: readonly { key: string; savedAt: number }[],
  max = TARKOV_MAP_FILE_CACHE_MAX,
): string[] {
  if (entries.length <= max) return [];
  const sorted = [...entries].sort((a, b) => a.savedAt - b.savedAt);
  return sorted.slice(0, entries.length - max).map((row) => row.key);
}
