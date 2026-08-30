import { Alert, Spin, Tooltip } from "antd";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addTarkovKeyOwn,
  fetchTarkovKeyOwns,
  fetchTarkovKeyPacks,
  mergeTarkovKeyOwns,
  removeTarkovKeyOwn,
} from "@/api/guidesApi";
import { TarkovGuideItemCell } from "@/components/guides/tarkov/TarkovGuideItemCell";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  COMMUNITY_KEY_HINT,
  UNBOUND_PACK_SLUG,
  buildKeyPackNav,
  isCommunityKeyBind,
  filterPackKeys,
  firstPackSlugForQuery,
  formatKeyMetaTags,
  formatKeySourceTags,
  formatKeyTagLine,
  loadOwnedIds,
  markOwnsMigrated,
  packOwnedCount,
  readOwnedFilter,
  resolvePackSlug,
  saveOwnedIds,
  takeLocalOwnsForMigrate,
  toggleOwnedId,
  type TarkovKeyOwnedFilter,
} from "@/lib/tarkovKeyPacks";
import trade from "./TarkovGuideTrade.module.css";
import styles from "./TarkovKeyPacksPanel.module.css";

const FILTERS: Array<{ id: TarkovKeyOwnedFilter; label: string }> = [
  { id: "all", label: "全部" },
  { id: "missing", label: "未拥有" },
  { id: "owned", label: "已拥有" },
];

export function TarkovKeyPacksPanel() {
  const gameMode = useTarkovGameMode();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const q = (searchParams.get("q") || "").trim();
  const have = readOwnedFilter(searchParams.get("have"));
  const mapRaw = searchParams.get("map");
  const [keyword, setKeyword] = useState(q);
  const qRef = useRef(q);
  const migratedRef = useRef(false);
  const [ownedIds, setOwnedIds] = useState<string[]>(() => loadOwnedIds());
  const owned = useMemo(() => new Set(ownedIds), [ownedIds]);
  const ownedIdsRef = useRef(ownedIds);
  ownedIdsRef.current = ownedIds;
  const touchedRef = useRef(false);

  const applyOwns = useCallback(
    (ids: string[]) => {
      ownedIdsRef.current = ids;
      setOwnedIds(ids);
      markOwnsMigrated(ids);
      queryClient.setQueryData(["guides-tarkov-key-owns"], { item_ids: ids });
      void queryClient.invalidateQueries({ queryKey: ["guides-tarkov-raid-room"] });
    },
    [queryClient],
  );

  const ownsQuery = useQuery({
    queryKey: ["guides-tarkov-key-owns"],
    queryFn: fetchTarkovKeyOwns,
    staleTime: 60_000,
  });

  const mergeMut = useMutation({
    mutationFn: mergeTarkovKeyOwns,
    onSuccess: (data) => applyOwns(data.item_ids || []),
  });

  const toggleMut = useMutation({
    mutationFn: async ({
      itemId,
      nextHas,
    }: {
      itemId: string;
      nextHas: boolean;
    }) => (nextHas ? addTarkovKeyOwn(itemId) : removeTarkovKeyOwn(itemId)),
    onSuccess: (data) => applyOwns(data.item_ids || []),
    onError: async () => {
      const result = await ownsQuery.refetch();
      applyOwns(result.data?.item_ids || []);
    },
  });

  useEffect(() => {
    const server = ownsQuery.data?.item_ids;
    if (!ownsQuery.isSuccess || server == null || migratedRef.current) return;
    migratedRef.current = true;
    if (touchedRef.current) return;
    const local = takeLocalOwnsForMigrate();
    if (local?.length && !server.length) {
      mergeMut.mutate(local);
      return;
    }
    applyOwns(server);
  }, [ownsQuery.isSuccess, ownsQuery.data, mergeMut, applyOwns]);

  useEffect(() => {
    setKeyword(q);
    qRef.current = q;
  }, [q]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      const next = keyword.trim();
      if (qRef.current === next) return;
      qRef.current = next;
      const params = new URLSearchParams(searchParams);
      if (next) params.set("q", next);
      else params.delete("q");
      setSearchParams(params, { replace: true });
    }, 300);
    return () => window.clearTimeout(handle);
  }, [keyword, searchParams, setSearchParams]);

  const catalogQuery = useQuery({
    queryKey: ["guides-tarkov-key-packs", gameMode],
    queryFn: fetchTarkovKeyPacks,
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const packs = useMemo(
    () =>
      buildKeyPackNav(
        catalogQuery.data?.maps ?? [],
        catalogQuery.data?.unbound ?? [],
      ),
    [catalogQuery.data],
  );
  const slugs = useMemo(() => packs.map((row) => row.slug), [packs]);
  const activeSlug = resolvePackSlug(mapRaw, slugs);
  const active = packs.find((row) => row.slug === activeSlug) || packs[0];

  useEffect(() => {
    if (!q || !packs.length) return;
    const current = packs.find((row) => row.slug === activeSlug);
    if (current && filterPackKeys(current.keys, q, "all", owned).length) {
      return;
    }
    const jump = firstPackSlugForQuery(packs, q);
    if (!jump || jump === activeSlug) return;
    const params = new URLSearchParams(searchParams);
    params.set("map", jump);
    setSearchParams(params, { replace: true });
  }, [q, packs, activeSlug, owned, searchParams, setSearchParams]);

  const setMap = (slug: string) => {
    const params = new URLSearchParams(searchParams);
    if (slug && slug !== slugs[0]) params.set("map", slug);
    else params.delete("map");
    setSearchParams(params, { replace: true });
  };

  const setHave = (next: TarkovKeyOwnedFilter) => {
    const params = new URLSearchParams(searchParams);
    if (next === "all") params.delete("have");
    else params.set("have", next);
    setSearchParams(params, { replace: true });
  };

  const toggleOwned = (itemId: string) => {
    const nextHas = !ownedIdsRef.current.includes(itemId);
    const next = toggleOwnedId(ownedIdsRef.current, itemId);
    touchedRef.current = true;
    ownedIdsRef.current = next;
    setOwnedIds(next);
    saveOwnedIds(next, true);
    toggleMut.mutate({ itemId, nextHas });
  };

  const visible = active
    ? filterPackKeys(active.keys, q, have, owned)
    : [];
  const counts = active ? packOwnedCount(active.keys, owned) : { have: 0, total: 0 };

  if (catalogQuery.isLoading && !catalogQuery.data) {
    return (
      <div className={trade.status}>
        <Spin />
      </div>
    );
  }

  if (catalogQuery.isError && !catalogQuery.data) {
    return (
      <Alert
        type="error"
        showIcon
        message="钥匙分类加载失败"
        description={apiError(catalogQuery.error, "钥匙分类加载失败")}
      />
    );
  }

  return (
    <div className={trade.stack}>
      <div className={trade.toolbar}>
        <input
          className={trade.search}
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
          placeholder="搜索钥匙名"
          aria-label="搜索钥匙"
        />
        <div className={trade.chipBar} role="group" aria-label="拥有筛选">
          {FILTERS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`${trade.chipBtn} ${trade.chipAll}${have === item.id ? ` ${trade.chipOn}` : ""}`}
              onClick={() => setHave(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <div className={styles.rail} role="list" aria-label="地图">
        {packs.map((pack) => {
          const count = packOwnedCount(pack.keys, owned);
          const on = pack.slug === activeSlug;
          return (
            <button
              key={pack.slug}
              type="button"
              role="listitem"
              className={`${styles.packBtn}${on ? ` ${styles.packOn}` : ""}`}
              onClick={() => setMap(pack.slug)}
            >
              <span className={styles.packName}>{pack.name}</span>
              <span
                className={`${styles.packCount}${count.total > 0 && count.have === count.total ? ` ${styles.packCountDone}` : ""}`}
              >
                {count.have}/{count.total}
              </span>
            </button>
          );
        })}
      </div>
      <div className={trade.meta}>
        按门锁把钥匙分到每张地图，对着清单装箱。勾选「我有」记在账号上，准备总结会提示谁拥有。
      </div>
      <div className={styles.layout}>
        <div className={styles.main}>
          <div className={styles.mainHead}>
            <h2 className={styles.mainTitle}>
              {active?.name || "钥匙包"}
              {active?.english ? ` · ${active.english}` : ""}
            </h2>
            <span className={styles.mainMeta}>
              {active?.slug === UNBOUND_PACK_SLUG
                ? "手册有、门锁对不上的钥匙"
                : `我有 ${counts.have} / 共 ${counts.total}`}
            </span>
          </div>
          {visible.length ? (
            <div className={styles.grid}>
              {visible.map((key) => {
                const haveKey = owned.has(key.id);
                const tags = [
                  ...formatKeyMetaTags(key),
                  ...formatKeySourceTags(key),
                ];
                return (
                  <div
                    key={key.id}
                    className={`${styles.card}${haveKey ? ` ${styles.cardOwned}` : ""}`}
                    role="button"
                    tabIndex={0}
                    aria-pressed={haveKey}
                    aria-label={haveKey ? `取消我有 ${key.name || key.id}` : `标记我有 ${key.name || key.id}`}
                    onClick={() => toggleOwned(key.id)}
                    onKeyDown={(event) => {
                      if (event.key !== "Enter" && event.key !== " ") return;
                      event.preventDefault();
                      toggleOwned(key.id);
                    }}
                  >
                    <span
                      className={styles.check}
                      aria-hidden
                    >
                      {haveKey ? "✓" : ""}
                    </span>
                    <div
                      className={styles.cardBody}
                      onClick={(event) => {
                        if ((event.target as HTMLElement).closest("a")) {
                          event.stopPropagation();
                        }
                      }}
                    >
                      <div className={styles.itemHead}>
                        <div className={styles.item}>
                          <TarkovGuideItemCell
                            item={{
                              id: key.id,
                              name: key.name,
                              short_name: key.short_name,
                              icon_link: key.icon_link,
                              types: key.types,
                            }}
                            showCount={false}
                          />
                        </div>
                        {isCommunityKeyBind(key) ? (
                          <Tooltip
                            title={COMMUNITY_KEY_HINT}
                            mouseEnterDelay={0.12}
                            mouseLeaveDelay={0.08}
                          >
                            <span
                              className={styles.communityMark}
                              aria-label={COMMUNITY_KEY_HINT}
                              onClick={(event) => event.stopPropagation()}
                            >
                              ?
                            </span>
                          </Tooltip>
                        ) : null}
                      </div>
                      {tags.length ? (
                        <div className={styles.tags} aria-label="钥匙信息">
                          {tags.map((tag) => {
                            const className = `${styles.tag} ${styles[`tag_${tag.kind}`] || ""}`;
                            const line = formatKeyTagLine(tag);
                            if (tag.href) {
                              return (
                                <Link
                                  key={tag.kind}
                                  className={className}
                                  to={tag.href}
                                  title={line}
                                  onClick={(event) => event.stopPropagation()}
                                >
                                  {line}
                                </Link>
                              );
                            }
                            return (
                              <span
                                key={tag.kind}
                                className={className}
                                title={line}
                              >
                                {line}
                              </span>
                            );
                          })}
                        </div>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className={styles.empty}>
              {active?.keys.length
                ? "这一包没有符合筛选的钥匙。"
                : "这张图暂时没有门锁钥匙。"}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
