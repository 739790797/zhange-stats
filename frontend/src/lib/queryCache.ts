/** 本站接口（features / me / profile），非外部上游。 */
export const LOCAL_QUERY_STALE_MS = 30_000;

export const QUERY_PERSIST_KEY = "zhange-query-persist";

/** sessionStorage 里只留半小时，刷新后可先画签到状态再 force 回源。 */
export const QUERY_PERSIST_MAX_AGE_MS = 30 * 60 * 1000;

const PERSIST_QUERY_HEADS = new Set([
  "skland-status",
  "taygedo-status",
  "exilium-status",
  "kujiequ-status",
  "mihoyo-status",
  "platform-features-effective",
]);

export function shouldPersistQueryKey(queryKey: readonly unknown[]): boolean {
  const head = queryKey[0];
  return typeof head === "string" && PERSIST_QUERY_HEADS.has(head);
}

export function shouldDehydratePersistedQuery(query: {
  queryKey: readonly unknown[];
  state: { status: string };
}): boolean {
  return (
    query.state.status === "success" && shouldPersistQueryKey(query.queryKey)
  );
}

/** 无缓存的首次请求才挡整块 UI；有 persist / 内存数据时走 isFetching。 */
export function isInitialQueryPending(query: {
  data: unknown;
  isPending: boolean;
}): boolean {
  return query.data == null && query.isPending;
}
