import { Alert, Spin, Table } from "antd";
import type { ColumnsType, TableProps } from "antd/es/table";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  fetchTarkovTasks,
  type TarkovTaskListItem,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { TARKOV_TRADERS, tarkovTaskHref } from "@/lib/tarkovHomeNav";
import { readAllowedInt, readPositiveInt } from "@/lib/tarkovQueryState";
import {
  orderObjectiveTypes,
  tarkovObjectiveTypeLabel,
  tarkovObjectiveTypeTone,
} from "@/lib/tarkovTaskObjective";
import { TarkovTraderThumb } from "@/components/guides/tarkov/TarkovTraderThumb";
import tableStyles from "./TarkovDarkTable.module.css";
import catalog from "./TarkovItemCatalogPanel.module.css";
import styles from "./TarkovTasksPanel.module.css";

function traderFilterLabel(slug: string, apiName: string): {
  english: string;
  chinese: string;
} {
  const known = TARKOV_TRADERS.find((item) => item.id === slug);
  if (known) return { english: known.english, chinese: known.chinese };
  const match = apiName.match(/^(.*?)\s*[（(](.+?)[）)]\s*$/);
  if (match) {
    return { english: match[1].trim(), chinese: match[2].trim() };
  }
  return { english: apiName, chinese: "" };
}

function factionSuffix(value: string | undefined): string {
  const v = (value || "").trim();
  if (!v || v === "Any") return "";
  return ` (${v})`;
}

const PAGE_SIZE_DEFAULT = 20;
const PAGE_SIZE_OPTIONS = [20, 50, 100];

export function TarkovTasksPanel() {
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
    queryKey: [
      "guides-tarkov-tasks",
      gameMode,
      trader,
      q,
      pageNo,
      pageSize,
    ],
    queryFn: () =>
      fetchTarkovTasks({
        q,
        trader: trader || undefined,
        page: pageNo,
        pageSize,
      }),
    staleTime: 5 * 60_000,
    retry: 1,
    placeholderData: keepPreviousData,
  });

  const allOn = !trader;

  const setTraderFilter = (nextTrader: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (!nextTrader) next.delete("trader");
    else next.set("trader", nextTrader);
    next.delete("page");
    setSearchParams(next, { replace: true });
  };

  const onTableChange: TableProps<TarkovTaskListItem>["onChange"] = (
    pagination,
  ) => {
    const nextPage = pagination.current ?? 1;
    const nextSize = pagination.pageSize ?? PAGE_SIZE_DEFAULT;
    const params = new URLSearchParams(searchParams);
    if (nextPage <= 1) params.delete("page");
    else params.set("page", String(nextPage));
    if (nextSize === PAGE_SIZE_DEFAULT) params.delete("pageSize");
    else params.set("pageSize", String(nextSize));
    setSearchParams(params, { replace: true });
  };

  const columns: ColumnsType<TarkovTaskListItem> = [
    {
      title: "任务",
      dataIndex: "name",
      key: "name",
      ellipsis: true,
      render: (_: unknown, row) => {
        const label = row.name || row.normalized_name || row.id;
        const traderName = row.trader_name || row.trader_slug;
        return (
          <span className={styles.taskCell}>
            {row.trader_slug ? (
              <TarkovTraderThumb slug={row.trader_slug} size={40} title={traderName} />
            ) : (
              <span className={styles.traderThumbFallback} />
            )}
            <Link className={styles.taskName} to={tarkovTaskHref(row.id)}>
              {label}
              {factionSuffix(row.faction_name)}
            </Link>
          </span>
        );
      },
    },
    {
      title: "目标",
      key: "objective_types",
      width: 248,
      render: (_: unknown, row) => {
        const types = orderObjectiveTypes(row.objective_types);
        if (!types.length) return "";
        return (
          <span className={styles.typeList}>
            {types.map((type) => (
              <span
                key={type}
                className={styles.typeChip}
                data-tone={tarkovObjectiveTypeTone(type)}
                title={type}
              >
                {tarkovObjectiveTypeLabel(type)}
              </span>
            ))}
          </span>
        );
      },
    },
    {
      title: "最低等级",
      dataIndex: "min_player_level",
      key: "min_player_level",
      width: 96,
      align: "center",
      render: (v: number) => (v ? v : ""),
    },
    {
      title: "经验",
      dataIndex: "experience",
      key: "experience",
      width: 96,
      align: "right",
      render: (v: number) => (v ? v.toLocaleString("zh-CN") : ""),
    },
    {
      title: "终局",
      key: "endgame",
      width: 120,
      render: (_: unknown, row) => {
        const marks = [
          row.lightkeeper_required ? "灯塔商人" : "",
        ].filter(Boolean);
        if (!marks.length) return "";
        return <span className={styles.endgame}>{marks.join(" · ")}</span>;
      },
    },
  ];

  if (catalogQuery.isLoading && !catalogQuery.data) {
    return (
      <div className={catalog.status}>
        <Spin tip="加载任务…" />
      </div>
    );
  }

  if (catalogQuery.isError && !catalogQuery.data) {
    return (
      <Alert
        type="error"
        showIcon
        message="任务列表加载失败"
        description={apiError(catalogQuery.error, "任务列表加载失败")}
      />
    );
  }

  const meta = catalogQuery.data;
  const rows = meta?.items ?? [];
  const total = typeof meta?.task_count === "number" ? meta.task_count : 0;
  const traders = meta?.traders ?? [];

  return (
    <div className={catalog.stack}>
      {catalogQuery.isError ? (
        <Alert
          type="error"
          showIcon
          message="任务列表加载失败"
          description={apiError(catalogQuery.error, "任务列表加载失败")}
        />
      ) : null}

      <div className={styles.toolbar}>
        <div className={styles.toolbarTop}>
          <div className={styles.toolbarSide}>
            {typeof meta?.task_count === "number" ? (
              <span className={styles.count}>共 {meta.task_count} 条</span>
            ) : null}
          </div>
        </div>

        <div className={styles.queryRow}>
          <input
            className={styles.search}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="按任务名称筛选"
            aria-label="搜索任务"
          />
        </div>

        <div className={styles.filterRow}>
          <span className={styles.filterLabel}>商人</span>
          <div className={styles.traderBar} role="radiogroup" aria-label="按商人筛选">
            <button
              type="button"
              role="radio"
              aria-checked={allOn}
              className={`${styles.traderBtn} ${styles.traderBtnAll} ${allOn ? styles.traderBtnOn : ""}`}
              onClick={() => setTraderFilter(null)}
            >
              全部
            </button>
            {traders.map((item) => {
              const { english, chinese } = traderFilterLabel(item.slug, item.name);
              const selected = trader === item.slug;
              return (
                <button
                  key={item.slug || item.id}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  aria-label={chinese ? `${english}（${chinese}）` : english}
                  title={chinese ? `${english}（${chinese}）` : english}
                  className={`${styles.traderBtn} ${selected ? styles.traderBtnOn : ""}`}
                  onClick={() => setTraderFilter(item.slug)}
                >
                  <TarkovTraderThumb slug={item.slug} size={40} />
                  <span className={styles.traderCaption}>
                    {chinese || english}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className={catalog.panel}>
        <Table<TarkovTaskListItem>
          className={tableStyles.table}
          size="small"
          rowKey="id"
          columns={columns}
          dataSource={rows}
          loading={catalogQuery.isFetching}
          onChange={onTableChange}
          pagination={{
            current: pageNo,
            pageSize,
            total,
            showSizeChanger: true,
            pageSizeOptions: PAGE_SIZE_OPTIONS.map(String),
            showTotal: (count, range) => `${range[0]}–${range[1]} / ${count}`,
          }}
          scroll={{ x: 920 }}
          locale={{
            emptyText: "当前筛选下无任务",
          }}
        />
      </div>
    </div>
  );
}
