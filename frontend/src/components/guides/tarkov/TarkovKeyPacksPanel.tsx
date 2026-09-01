import { Alert, Spin, Table, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";
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
import { readAllowedInt, readPositiveInt } from "@/lib/tarkovQueryState";
import {
  ALL_PACK_SLUG,
  COMMUNITY_KEY_HINT,
  UNBOUND_PACK_SLUG,
  buildKeyPackNav,
  collectPackKeys,
  filterPackKeys,
  isAllPackSlug,
  firstPackSlugForQuery,
  formatKeyFleaTag,
  formatKeyLockTypeLine,
  formatKeyObtainTags,
  formatKeyTagLine,
  formatKeyUsageMarks,
  formatKeyUsageNeedTags,
  formatKeyUsageText,
  formatKeyUses,
  isCommunityKeyBind,
  keyFleaSortValue,
  keyLockTypeSortValue,
  keyUsesSortValue,
  applyTarkovKeyOwnsCache,
  loadOwnedIds,
  packOwnedCount,
  readOwnedFilter,
  resolvePackSlug,
  saveOwnedIds,
  takeLocalOwnsForMigrate,
  toggleOwnedId,
  type TarkovKeyOwnedFilter,
  type TarkovKeyPackKey,
  type TarkovKeySourceTag,
} from "@/lib/tarkovKeyPacks";
import trade from "./TarkovGuideTrade.module.css";
import tableStyles from "./TarkovDarkTable.module.css";
import styles from "./TarkovKeyPacksPanel.module.css";

const PAGE_SIZE_DEFAULT = 50;
const PAGE_SIZE_OPTIONS = [20, 50, 100];
const EMPTY_PACK_KEYS: TarkovKeyPackKey[] = [];

const FILTERS: Array<{ id: TarkovKeyOwnedFilter; label: string }> = [
  { id: "owned", label: "已拥有" },
  { id: "missing", label: "未拥有" },
];

/** 首页地图格同款 MDI 路径（viewBox 0 0 24 24）。 */
const ALL_MAP_ICON =
  "M3,3H11V11H3V3M13,3H21V11H13V3M3,13H11V21H3V13M13,13H21V21H13V13Z";
const UNBOUND_MAP_ICON =
  "M7,14A3,3 0 0,1 4,11A3,3 0 0,1 7,8A3,3 0 0,1 10,11A3,3 0 0,1 7,14M12.65,10C11.83,7.67 9.61,6 7,6A5,5 0 0,0 2,11A5,5 0 0,0 7,16C9.61,16 11.83,14.33 12.65,12H17V16H21V12H22V10H12.65Z";

function PackMapIcon({ path }: { path: string }) {
  return (
    <svg
      className={styles.packIcon}
      viewBox="0 0 24 24"
      width="20"
      height="20"
      aria-hidden
    >
      <path d={path} fill="currentColor" />
    </svg>
  );
}

function KeyTagList({ tags }: { tags: TarkovKeySourceTag[] }) {
  if (!tags.length) return <span className={styles.dash}>—</span>;
  return (
    <div className={styles.cellStack}>
      {tags.map((tag, index) => {
        const className = `${styles.tag} ${styles[`tag_${tag.kind}`] || ""}`;
        const line = formatKeyTagLine(tag);
        const reactKey = `${tag.kind}-${tag.label}-${tag.hint}-${tag.href || index}`;
        if (tag.href) {
          return (
            <Link
              key={reactKey}
              className={className}
              to={tag.href}
              title={line}
            >
              {line}
            </Link>
          );
        }
        return (
          <span key={reactKey} className={className} title={line}>
            {line}
          </span>
        );
      })}
    </div>
  );
}

function UsageCell({ row }: { row: TarkovKeyPackKey }) {
  const usage = formatKeyUsageText(row);
  const marks = formatKeyUsageMarks(row);
  const needs = formatKeyUsageNeedTags(row);
  if (!usage && !marks.length && !needs.length) {
    return <span className={styles.dash}>—</span>;
  }
  return (
    <div className={styles.usage}>
      {usage ? <p className={styles.desc}>{usage}</p> : null}
      {marks.length ? (
        <span className={styles.marks}>{marks.join(" · ")}</span>
      ) : null}
      {needs.length ? <KeyTagList tags={needs} /> : null}
    </div>
  );
}

export function TarkovKeyPacksPanel() {
  const gameMode = useTarkovGameMode();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const q = (searchParams.get("q") || "").trim();
  const have = readOwnedFilter(searchParams.get("have"));
  const mapRaw = searchParams.get("map");
  const pageNo = readPositiveInt(searchParams.get("page"), 1);
  const pageSize = readAllowedInt(
    searchParams.get("pageSize"),
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_OPTIONS,
  );
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
      applyTarkovKeyOwnsCache(queryClient, ids);
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
      params.delete("page");
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
  const allKeys = useMemo(() => collectPackKeys(packs), [packs]);
  const activeSlug = resolvePackSlug(mapRaw, slugs);
  const allMaps = isAllPackSlug(activeSlug);
  const active = allMaps
    ? null
    : packs.find((row) => row.slug === activeSlug) || null;
  const activeKeys = allMaps ? allKeys : active?.keys || EMPTY_PACK_KEYS;

  useEffect(() => {
    if (!q || !packs.length || allMaps) return;
    if (filterPackKeys(activeKeys, q, "all", owned).length) return;
    const jump = firstPackSlugForQuery(packs, q);
    if (!jump || jump === activeSlug) return;
    const params = new URLSearchParams(searchParams);
    params.set("map", jump);
    params.delete("page");
    setSearchParams(params, { replace: true });
  }, [q, packs, activeSlug, allMaps, activeKeys, owned, searchParams, setSearchParams]);

  const setMap = (slug: string) => {
    const params = new URLSearchParams(searchParams);
    if (isAllPackSlug(slug)) params.delete("map");
    else params.set("map", slug);
    params.delete("page");
    setSearchParams(params, { replace: true });
  };

  const setHave = (next: TarkovKeyOwnedFilter) => {
    const params = new URLSearchParams(searchParams);
    if (next === "all") params.delete("have");
    else params.set("have", next);
    params.delete("page");
    setSearchParams(params, { replace: true });
  };

  const toggleOwned = useCallback((itemId: string) => {
    const nextHas = !ownedIdsRef.current.includes(itemId);
    const next = toggleOwnedId(ownedIdsRef.current, itemId);
    touchedRef.current = true;
    ownedIdsRef.current = next;
    setOwnedIds(next);
    saveOwnedIds(next, true);
    toggleMut.mutate({ itemId, nextHas });
  }, [toggleMut]);

  const visible = filterPackKeys(activeKeys, q, have, owned);
  const pageCount = Math.max(1, Math.ceil(visible.length / pageSize));
  const currentPage = Math.min(pageNo, pageCount);
  const allCounts = packOwnedCount(allKeys, owned);

  const columns = useMemo<ColumnsType<TarkovKeyPackKey>>(
    () => [
      {
        title: "我有",
        key: "owned",
        width: 56,
        align: "center",
        render: (_: unknown, row) => {
          const haveKey = owned.has(row.id);
          return (
            <button
              type="button"
              className={`${styles.checkBtn}${haveKey ? ` ${styles.checkOn}` : ""}`}
              aria-pressed={haveKey}
              aria-label={
                haveKey
                  ? `取消我有 ${row.name || row.id}`
                  : `标记我有 ${row.name || row.id}`
              }
              onClick={(event) => {
                event.stopPropagation();
                toggleOwned(row.id);
              }}
            >
              {haveKey ? "✓" : ""}
            </button>
          );
        },
      },
      {
        title: "钥匙",
        key: "name",
        width: 240,
        sorter: (a, b) =>
          (a.name || a.short_name || a.id).localeCompare(
            b.name || b.short_name || b.id,
            "zh",
          ),
        render: (_: unknown, row) => (
          <span className={styles.nameCell}>
            <TarkovGuideItemCell
              item={{
                id: row.id,
                name: row.name,
                short_name: row.short_name,
                icon_link: row.icon_link,
                types: row.types,
              }}
              showCount={false}
            />
            {isCommunityKeyBind(row) ? (
              <Tooltip
                title={COMMUNITY_KEY_HINT}
                mouseEnterDelay={0.12}
                mouseLeaveDelay={0.08}
              >
                <span className={styles.communityMark} aria-label={COMMUNITY_KEY_HINT}>
                  ?
                </span>
              </Tooltip>
            ) : null}
          </span>
        ),
      },
      {
        title: "最大耐久",
        key: "uses",
        width: 96,
        align: "right",
        sorter: (a, b) => keyUsesSortValue(a) - keyUsesSortValue(b),
        render: (_: unknown, row) => formatKeyUses(row.uses) || "—",
      },
      {
        title: "跳蚤市场",
        key: "flea",
        width: 120,
        align: "right",
        sorter: (a, b) => keyFleaSortValue(a) - keyFleaSortValue(b),
        render: (_: unknown, row) => {
          const tag = formatKeyFleaTag(row);
          if (!tag) return <span className={styles.dash}>—</span>;
          const line = formatKeyTagLine(tag);
          if (tag.href) {
            return (
              <Link to={tag.href} title={line}>
                {tag.hint || "可上架"}
              </Link>
            );
          }
          return tag.hint || "—";
        },
      },
      {
        title: "制作 / 任务 / 商人",
        key: "obtain",
        width: 220,
        render: (_: unknown, row) => (
          <KeyTagList tags={formatKeyObtainTags(row)} />
        ),
      },
      {
        title: "门锁",
        key: "lock",
        width: 96,
        sorter: (a, b) =>
          keyLockTypeSortValue(a).localeCompare(keyLockTypeSortValue(b), "zh"),
        render: (_: unknown, row) =>
          formatKeyLockTypeLine(row) || <span className={styles.dash}>—</span>,
      },
      {
        title: "用途",
        key: "usage",
        render: (_: unknown, row) => <UsageCell row={row} />,
      },
    ],
    [owned, toggleOwned],
  );

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
      <div className={styles.queryRow}>
        <input
          className={`${trade.search} ${styles.search}`}
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
          placeholder="搜索钥匙、任务或用途"
          aria-label="搜索钥匙、任务或用途"
        />
        <div className={trade.chipBar} role="group" aria-label="拥有筛选">
          {FILTERS.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={have === item.id}
              className={`${trade.chipBtn} ${trade.chipAll}${have === item.id ? ` ${trade.chipOn}` : ""}`}
              onClick={() => setHave(have === item.id ? "all" : item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <div className={styles.rail} role="list" aria-label="地图">
        <button
          type="button"
          role="listitem"
          className={`${styles.packBtn}${allMaps ? ` ${styles.packOn}` : ""}`}
          onClick={() => setMap(ALL_PACK_SLUG)}
        >
          <PackMapIcon path={ALL_MAP_ICON} />
          <span className={styles.packName}>全部</span>
          <span
            className={`${styles.packCount}${
              allCounts.total > 0 && allCounts.have === allCounts.total
                ? ` ${styles.packCountDone}`
                : ""
            }`}
          >
            {allCounts.have}/{allCounts.total}
          </span>
        </button>
        {packs.map((pack) => {
          const count = packOwnedCount(pack.keys, owned);
          const on = !allMaps && pack.slug === activeSlug;
          return (
            <button
              key={pack.slug}
              type="button"
              role="listitem"
              className={`${styles.packBtn}${on ? ` ${styles.packOn}` : ""}`}
              onClick={() => setMap(pack.slug)}
            >
              <PackMapIcon
                path={
                  pack.icon ||
                  (pack.slug === UNBOUND_PACK_SLUG ? UNBOUND_MAP_ICON : ALL_MAP_ICON)
                }
              />
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
      <div className={styles.layout}>
        <div className={styles.main}>
          <Table<TarkovKeyPackKey>
            className={`${tableStyles.table} ${styles.table}`}
            size="small"
            rowKey="id"
            columns={columns}
            dataSource={visible}
            pagination={{
              current: currentPage,
              pageSize,
              total: visible.length,
              showSizeChanger: true,
              pageSizeOptions: PAGE_SIZE_OPTIONS.map(String),
              showTotal: (count, range) => `${range[0]}–${range[1]} / ${count}`,
              onChange: (nextPage, nextSize) => {
                const params = new URLSearchParams(searchParams);
                if (nextPage <= 1) params.delete("page");
                else params.set("page", String(nextPage));
                if (nextSize === PAGE_SIZE_DEFAULT) params.delete("pageSize");
                else params.set("pageSize", String(nextSize));
                setSearchParams(params, { replace: true });
              },
            }}
            loading={catalogQuery.isFetching && !catalogQuery.data}
            scroll={{ x: 1080 }}
            rowClassName={(row) => (owned.has(row.id) ? "owned" : "")}
            onRow={(row) => ({
              onClick: (event) => {
                const target = event.target as HTMLElement;
                if (target.closest("a, button, .ant-image")) return;
                toggleOwned(row.id);
              },
            })}
            locale={{
              emptyText: allMaps
                ? allKeys.length
                  ? "没有符合筛选的钥匙。"
                  : "暂时没有门锁钥匙。"
                : active?.keys.length
                  ? "这一包没有符合筛选的钥匙。"
                  : "这张图暂时没有门锁钥匙。",
            }}
          />
        </div>
      </div>
    </div>
  );
}
