import { Alert, Spin, Table } from "antd";
import type { ColumnsType, TableProps } from "antd/es/table";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { fetchTarkovCrafts, type TarkovCraft } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { tarkovHideoutHref } from "@/lib/tarkovHomeNav";
import {
  formatDurationSeconds,
  formatMoney,
} from "@/lib/tarkovItemFormat";
import { readAllowedInt, readPositiveInt } from "@/lib/tarkovQueryState";
import {
  TarkovGuideItemCell,
  TarkovGuideItemStack,
  guideItemFleaCost,
} from "@/components/guides/tarkov/TarkovGuideItemCell";
import tableStyles from "./TarkovDarkTable.module.css";
import styles from "./TarkovGuideTrade.module.css";

const PAGE_SIZE_DEFAULT = 50;
const PAGE_SIZE_OPTIONS = [20, 50, 100];

function profitClass(value: number | null): string {
  if (value == null) return "";
  return value >= 0 ? styles.profitPos : styles.profitNeg;
}

export function TarkovCraftsPanel() {
  const gameMode = useTarkovGameMode();
  const [searchParams, setSearchParams] = useSearchParams();
  const station = (searchParams.get("station") || "").trim();
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
    queryKey: ["guides-tarkov-crafts", gameMode, station, q, pageNo, pageSize],
    queryFn: () =>
      fetchTarkovCrafts({
        q,
        station: station || undefined,
        page: pageNo,
        pageSize,
      }),
    staleTime: 5 * 60_000,
    retry: 1,
    placeholderData: keepPreviousData,
  });

  const setStation = (slug: string) => {
    const params = new URLSearchParams(searchParams);
    if (!slug) params.delete("station");
    else params.set("station", slug);
    params.delete("page");
    setSearchParams(params, { replace: true });
  };

  const onTableChange: TableProps<TarkovCraft>["onChange"] = (pagination) => {
    const params = new URLSearchParams(searchParams);
    const nextPage = pagination.current || 1;
    const nextSize = pagination.pageSize || PAGE_SIZE_DEFAULT;
    if (nextPage <= 1) params.delete("page");
    else params.set("page", String(nextPage));
    if (nextSize === PAGE_SIZE_DEFAULT) params.delete("pageSize");
    else params.set("pageSize", String(nextSize));
    setSearchParams(params, { replace: true });
  };

  const columns: ColumnsType<TarkovCraft> = [
    {
      title: "模块",
      key: "station",
      width: 160,
      render: (_: unknown, row) => (
        <span>
          {row.station_slug ? (
            <Link to={tarkovHideoutHref(row.station_slug)}>
              {row.station_name}
            </Link>
          ) : (
            row.station_name
          )}
          <span className={styles.reqs}> Lv.{row.level}</span>
        </span>
      ),
    },
    {
      title: "材料",
      key: "required",
      render: (_: unknown, row) => (
        <TarkovGuideItemStack items={row.required_items} />
      ),
    },
    {
      title: "产物",
      key: "product",
      render: (_: unknown, row) =>
        row.product_item ? (
          <TarkovGuideItemCell item={row.product_item} showCount />
        ) : (
          "—"
        ),
    },
    {
      title: "时长",
      key: "duration",
      width: 120,
      render: (_: unknown, row) => formatDurationSeconds(row.duration),
    },
    {
      title: "利润",
      key: "profit",
      width: 120,
      align: "right",
      render: (_: unknown, row) => {
        const cost = guideItemFleaCost(row.required_items);
        const sale = row.product_item?.flea_price;
        if (cost == null || sale == null) return "—";
        const profit = sale * Number(row.product_item?.count || 1) - cost;
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
        message="制作列表加载失败"
        description={apiError(catalogQuery.error, "制作列表加载失败")}
      />
    );
  }

  const data = catalogQuery.data;
  const stations = data?.stations ?? [];

  return (
    <div className={styles.stack}>
      <div className={styles.toolbar}>
        <div className={styles.chipBar}>
          <button
            type="button"
            className={`${styles.chipBtn} ${styles.chipAll} ${
              !station ? styles.chipOn : ""
            }`}
            onClick={() => setStation("")}
          >
            全部
          </button>
          {stations.map((row) => (
            <button
              key={row.slug}
              type="button"
              className={`${styles.chipBtn} ${styles.chipAll} ${
                station === row.slug ? styles.chipOn : ""
              }`}
              onClick={() => setStation(row.slug)}
            >
              {row.name}
            </button>
          ))}
        </div>
        <input
          className={styles.search}
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
          placeholder="搜产物或材料"
        />
      </div>
      <div className={styles.meta}>{data?.craft_count ?? data?.total ?? 0} 条制作</div>
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
            total: data?.total ?? data?.craft_count ?? 0,
            showSizeChanger: true,
            pageSizeOptions: PAGE_SIZE_OPTIONS.map(String),
          }}
          size="small"
        />
      </div>
    </div>
  );
}
