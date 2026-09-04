import { Alert, Spin, Table } from "antd";
import type { ColumnsType, TableProps } from "antd/es/table";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  fetchTarkovBarters,
  type TarkovBarter,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { TARKOV_TRADERS, tarkovTaskHref, traderDisplayName, traderIconUrl } from "@/lib/tarkovHomeNav";
import { formatMoney } from "@/lib/tarkovItemFormat";
import { readAllowedInt, readPositiveInt } from "@/lib/tarkovQueryState";
import { guideItemFleaCost } from "@/lib/tarkovGuideItemCost";
import {
  TarkovGuideItemCell,
  TarkovGuideItemStack,
} from "@/components/guides/tarkov/TarkovGuideItemCell";
import tableStyles from "./TarkovDarkTable.module.css";
import styles from "./TarkovGuideTrade.module.css";

const PAGE_SIZE_DEFAULT = 50;
const PAGE_SIZE_OPTIONS = [20, 50, 100];

function profitClass(value: number | null): string {
  if (value == null) return "";
  return value >= 0 ? styles.profitPos : styles.profitNeg;
}

export function TarkovBartersPanel() {
  const gameMode = useTarkovGameMode();
  const [searchParams, setSearchParams] = useSearchParams();
  const trader = (searchParams.get("trader") || "").trim();
  const q = (searchParams.get("q") || "").trim();
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
    queryKey: ["guides-tarkov-barters", gameMode, trader, q, pageNo, pageSize],
    queryFn: () =>
      fetchTarkovBarters({
        q,
        trader: trader || undefined,
        page: pageNo,
        pageSize,
      }),
    staleTime: 5 * 60_000,
    retry: 1,
    placeholderData: keepPreviousData,
  });

  const setTrader = (slug: string) => {
    const params = new URLSearchParams(searchParams);
    if (!slug) params.delete("trader");
    else params.set("trader", slug);
    params.delete("page");
    setSearchParams(params, { replace: true });
  };

  const onTableChange: TableProps<TarkovBarter>["onChange"] = (pagination) => {
    const params = new URLSearchParams(searchParams);
    const nextPage = pagination.current || 1;
    const nextSize = pagination.pageSize || PAGE_SIZE_DEFAULT;
    if (nextPage <= 1) params.delete("page");
    else params.set("page", String(nextPage));
    if (nextSize === PAGE_SIZE_DEFAULT) params.delete("pageSize");
    else params.set("pageSize", String(nextSize));
    setSearchParams(params, { replace: true });
  };

  const traders = catalogQuery.data?.traders?.length
    ? catalogQuery.data.traders
    : TARKOV_TRADERS.map((row) => ({ slug: row.id, name: row.english }));

  const columns: ColumnsType<TarkovBarter> = [
    {
      title: "商人",
      key: "trader",
      width: 140,
      render: (_: unknown, row) => (
        <span className={styles.reqs}>
          {traderDisplayName(row.trader_slug, row.trader_name || row.trader_slug)} LL{row.min_trader_level}
          {row.task_unlock ? (
            <>
              <br />
              <Link to={tarkovTaskHref(row.task_unlock)}>任务解锁</Link>
            </>
          ) : null}
        </span>
      ),
    },
    {
      title: "给出",
      key: "required",
      render: (_: unknown, row) => (
        <TarkovGuideItemStack items={row.required_items} />
      ),
    },
    {
      title: "得到",
      key: "offered",
      render: (_: unknown, row) =>
        row.offered_item ? (
          <TarkovGuideItemCell item={row.offered_item} showCount />
        ) : (
          "—"
        ),
    },
    {
      title: "成本",
      key: "cost",
      width: 120,
      align: "right",
      render: (_: unknown, row) => formatMoney(guideItemFleaCost(row.required_items)),
    },
    {
      title: "利润",
      key: "profit",
      width: 120,
      align: "right",
      render: (_: unknown, row) => {
        const cost = guideItemFleaCost(row.required_items);
        const sale = row.offered_item?.flea_price;
        if (cost == null || sale == null) return "—";
        const profit = sale * Number(row.offered_item?.count || 1) - cost;
        return (
          <span className={profitClass(profit)}>{formatMoney(profit)}</span>
        );
      },
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
        message="以物易物加载失败"
        description={apiError(catalogQuery.error, "以物易物加载失败")}
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
              !trader ? styles.chipOn : ""
            }`}
            onClick={() => setTrader("")}
          >
            全部
          </button>
          {traders.map((row) => (
            <button
              key={row.slug}
              type="button"
              className={`${styles.chipBtn} ${
                trader === row.slug ? styles.chipOn : ""
              }`}
              title={row.name}
              onClick={() => setTrader(row.slug)}
            >
              <img src={traderIconUrl(row.slug)} alt="" />
            </button>
          ))}
        </div>
        <input
          className={styles.search}
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
          placeholder="搜物品或商人"
        />
      </div>
      <div className={styles.meta}>
        {data?.barter_count ?? data?.total ?? 0} 条以物易物
      </div>
      <div className={tableStyles.table}>
        <Table
          rowKey={(row) => row.id}
          columns={columns}
          dataSource={data?.items ?? []}
          loading={catalogQuery.isFetching}
          onChange={onTableChange}
          pagination={{
            current: data?.page ?? pageNo,
            pageSize: data?.page_size ?? pageSize,
            total: data?.total ?? data?.barter_count ?? 0,
            showSizeChanger: true,
            pageSizeOptions: PAGE_SIZE_OPTIONS.map(String),
          }}
          size="small"
        />
      </div>
    </div>
  );
}
