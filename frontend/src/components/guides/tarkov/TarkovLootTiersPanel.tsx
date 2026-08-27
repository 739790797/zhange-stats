import { Alert, Spin, Table } from "antd";
import type { ColumnsType, TableProps } from "antd/es/table";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  fetchTarkovLootTiers,
  type TarkovLootTierItem,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { formatMoney } from "@/lib/tarkovItemFormat";
import { readAllowedInt, readPositiveInt } from "@/lib/tarkovQueryState";
import { TarkovGuideItemCell } from "@/components/guides/tarkov/TarkovGuideItemCell";
import tableStyles from "./TarkovDarkTable.module.css";
import styles from "./TarkovGuideTrade.module.css";
import lootStyles from "./TarkovLootTiersPanel.module.css";

const TIER_CLASS: Record<string, string> = {
  S: lootStyles.tierS,
  A: lootStyles.tierA,
  B: lootStyles.tierB,
  C: lootStyles.tierC,
  D: lootStyles.tierD,
  E: lootStyles.tierE,
};

const TIERS = ["S", "A", "B", "C", "D", "E"] as const;
const PAGE_SIZE_DEFAULT = 50;
const PAGE_SIZE_OPTIONS = [20, 50, 100];

export function TarkovLootTiersPanel() {
  const gameMode = useTarkovGameMode();
  const [searchParams, setSearchParams] = useSearchParams();
  const q = (searchParams.get("q") || "").trim();
  const tier = (searchParams.get("tier") || "").trim().toUpperCase();
  const pageNo = readPositiveInt(searchParams.get("page"), 1);
  const pageSize = readAllowedInt(
    searchParams.get("pageSize"),
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_OPTIONS,
  );
  const [keyword, setKeyword] = useState(q);
  const qRef = useRef(q);

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
    queryKey: ["guides-tarkov-loot-tiers", gameMode, q, tier, pageNo, pageSize],
    queryFn: () =>
      fetchTarkovLootTiers({
        q,
        tier: tier || undefined,
        page: pageNo,
        pageSize,
      }),
    staleTime: 5 * 60_000,
    retry: 1,
    placeholderData: keepPreviousData,
  });

  const setTier = (next: string) => {
    const params = new URLSearchParams(searchParams);
    if (!next) params.delete("tier");
    else params.set("tier", next);
    params.delete("page");
    setSearchParams(params, { replace: true });
  };

  const onTableChange: TableProps<TarkovLootTierItem>["onChange"] = (
    pagination,
  ) => {
    const params = new URLSearchParams(searchParams);
    const nextPage = pagination.current || 1;
    const nextSize = pagination.pageSize || PAGE_SIZE_DEFAULT;
    if (nextPage <= 1) params.delete("page");
    else params.set("page", String(nextPage));
    if (nextSize === PAGE_SIZE_DEFAULT) params.delete("pageSize");
    else params.set("pageSize", String(nextSize));
    setSearchParams(params, { replace: true });
  };

  const rows = catalogQuery.data?.items ?? [];

  const columns: ColumnsType<TarkovLootTierItem> = [
    {
      title: "等级",
      dataIndex: "tier",
      key: "tier",
      width: 72,
      render: (value: string) => (
        <span className={`${lootStyles.tier} ${TIER_CLASS[value] || ""}`}>
          {value}
        </span>
      ),
    },
    {
      title: "物品",
      key: "item",
      render: (_: unknown, row) => (
        <TarkovGuideItemCell
          item={{
            id: row.id,
            name: row.name,
            short_name: row.short_name,
            icon_link: row.icon_link,
            types: row.types,
            count: 1,
          }}
          showCount={false}
        />
      ),
    },
    {
      title: "格数",
      key: "slots",
      width: 90,
      render: (_: unknown, row) => `${row.width}×${row.height}`,
    },
    {
      title: "跳蚤",
      dataIndex: "price",
      key: "price",
      width: 120,
      align: "right",
      render: (value: number) => formatMoney(value),
    },
    {
      title: "每格",
      dataIndex: "price_per_slot",
      key: "pps",
      width: 120,
      align: "right",
      render: (value: number) => formatMoney(value),
    },
  ];

  if (catalogQuery.isLoading && !catalogQuery.data) {
    return (
      <div className={styles.status}>
        <Spin />
      </div>
    );
  }

  if (catalogQuery.isError && !catalogQuery.data) {
    return (
      <Alert
        type="error"
        showIcon
        message="战利品等级加载失败"
        description={apiError(catalogQuery.error, "战利品等级加载失败")}
      />
    );
  }

  const data = catalogQuery.data;

  return (
    <div className={styles.stack}>
      <div className={styles.toolbar}>
        <div className={styles.chipBar}>
          <button
            type="button"
            className={`${styles.chipBtn} ${styles.chipAll} ${
              !tier ? styles.chipOn : ""
            }`}
            onClick={() => setTier("")}
          >
            全部
          </button>
          {TIERS.map((id) => (
            <button
              key={id}
              type="button"
              className={`${styles.chipBtn} ${styles.chipAll} ${
                tier === id ? styles.chipOn : ""
              }`}
              onClick={() => setTier(id)}
            >
              {id}
            </button>
          ))}
        </div>
        <input
          className={styles.search}
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
          placeholder="搜物品"
        />
      </div>
      <div className={styles.meta}>
        按跳蚤每格价分 S–E；当前 {data?.item_count ?? 0} 件有报价物品
      </div>
      <div className={tableStyles.table}>
        <Table
          rowKey={(row) => row.id}
          columns={columns}
          dataSource={rows}
          loading={catalogQuery.isFetching}
          onChange={onTableChange}
          pagination={{
            current: data?.page ?? pageNo,
            pageSize: data?.page_size ?? pageSize,
            total: data?.item_count ?? 0,
            showSizeChanger: true,
            pageSizeOptions: PAGE_SIZE_OPTIONS.map(String),
          }}
          size="small"
        />
      </div>
    </div>
  );
}
