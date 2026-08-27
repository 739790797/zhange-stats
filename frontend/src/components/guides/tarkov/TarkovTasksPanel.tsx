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
import {
  TARKOV_TRADERS,
  tarkovTaskHref,
} from "@/lib/tarkovHomeNav";
import {
  readAllowedInt,
  readPositiveInt,
  readTarkovTaskView,
} from "@/lib/tarkovQueryState";
import {
  orderObjectiveTypes,
  tarkovObjectiveTypeLabel,
  tarkovObjectiveTypeTone,
} from "@/lib/tarkovTaskObjective";
import {
  TARKOV_TASK_PROGRESS_FILTERS,
  tarkovTaskProgressLabel,
  useTarkovTaskMineMode,
} from "@/lib/tarkovTaskProgress";
import { TarkovTaskChains } from "@/components/guides/tarkov/TarkovTaskChains";
import { TarkovTaskProgressSwitch } from "@/components/guides/tarkov/TarkovTaskProgressSwitch";
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
  const pstatus = (searchParams.get("pstatus") || "").trim();
  const q = (searchParams.get("q") || "").trim();
  const kappa = searchParams.get("kappa") === "1";
  const view = readTarkovTaskView(searchParams.get("view"));
  const pageNo = readPositiveInt(searchParams.get("page"), 1);
  const pageSize = readAllowedInt(
    searchParams.get("pageSize"),
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_OPTIONS,
  );
  const [mine, setMine] = useTarkovTaskMineMode();
  const [keyword, setKeyword] = useState(q);
  const qRef = useRef(q);
  const statusFilter = mine ? pstatus || "all" : "";

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

  useEffect(() => {
    if (!mine && pstatus) {
      const next = new URLSearchParams(searchParams);
      next.delete("pstatus");
      setSearchParams(next, { replace: true });
    }
  }, [mine, pstatus, searchParams, setSearchParams]);

  const catalogQuery = useQuery({
    queryKey: [
      "guides-tarkov-tasks",
      gameMode,
      trader,
      q,
      pageNo,
      pageSize,
      mine,
      statusFilter,
      kappa,
      view,
    ],
    queryFn: () =>
      fetchTarkovTasks({
        q,
        trader: trader || undefined,
        page: pageNo,
        pageSize,
        kappa: kappa || undefined,
        progress: mine,
        progressStatus:
          mine && statusFilter && statusFilter !== "all"
            ? statusFilter
            : undefined,
        layout: view === "chain" ? "chain" : "table",
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

  const setKappaFilter = (on: boolean) => {
    const next = new URLSearchParams(searchParams);
    if (on) next.set("kappa", "1");
    else next.delete("kappa");
    next.delete("page");
    setSearchParams(next, { replace: true });
  };

  const setStatusFilter = (nextStatus: string) => {
    const next = new URLSearchParams(searchParams);
    if (nextStatus && nextStatus !== "all") next.set("pstatus", nextStatus);
    else next.delete("pstatus");
    next.delete("page");
    setSearchParams(next, { replace: true });
  };

  const setView = (nextView: "chain" | "table") => {
    const next = new URLSearchParams(searchParams);
    if (nextView === "chain") next.set("view", "chain");
    else next.delete("view");
    next.delete("page");
    setSearchParams(next, { replace: true });
  };

  const onTableChange: TableProps<TarkovTaskListItem>["onChange"] = (
    _pagination,
    filters,
    _sorter,
    extra,
  ) => {
    if (extra.action !== "filter") return;
    const values = filters?.progress_status;
    const next =
      Array.isArray(values) && values.length ? String(values[0]) : "all";
    setStatusFilter(next);
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
    ...(mine
      ? [
          {
            title: "状态",
            dataIndex: "progress_status",
            key: "progress_status",
            width: 112,
            filters: TARKOV_TASK_PROGRESS_FILTERS.map((item) => ({
              text: item.label,
              value: item.id,
            })),
            filteredValue:
              statusFilter && statusFilter !== "all" ? [statusFilter] : null,
            filterMultiple: false,
            render: (v: string | null | undefined) => {
              const label = tarkovTaskProgressLabel(v);
              if (!label) return "—";
              const tone =
                v === "available"
                  ? styles.statusAvailable
                  : v === "complete"
                    ? styles.statusComplete
                    : v === "failed"
                      ? styles.statusFailed
                      : styles.statusLocked;
              return (
                <span className={`${styles.statusChip} ${tone}`}>{label}</span>
              );
            },
          } satisfies ColumnsType<TarkovTaskListItem>[number],
        ]
      : []),
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
          row.kappa_required ? "Kappa" : "",
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
          <div className={styles.viewBar} role="radiogroup" aria-label="任务展示">
            <button
              type="button"
              role="radio"
              aria-checked={view === "table"}
              className={`${styles.modeBtn} ${view === "table" ? styles.modeBtnOn : ""}`}
              onClick={() => setView("table")}
            >
              查找
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={view === "chain"}
              className={`${styles.modeBtn} ${view === "chain" ? styles.modeBtnOn : ""}`}
              onClick={() => setView("chain")}
            >
              任务线
            </button>
          </div>
          <div className={styles.toolbarSide}>
            {typeof meta?.task_count === "number" ? (
              <span className={styles.count}>共 {meta.task_count} 条</span>
            ) : null}
            <TarkovTaskProgressSwitch
              enabled={mine}
              onChange={(value) => {
                setMine(value);
                const next = new URLSearchParams(searchParams);
                next.delete("page");
                setSearchParams(next, { replace: true });
              }}
            />
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
          <button
            type="button"
            aria-pressed={kappa}
            className={`${styles.chip} ${kappa ? styles.chipOn : ""}`}
            onClick={() => setKappaFilter(!kappa)}
          >
            Kappa
          </button>
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

        {mine ? (
          <div className={styles.filterRow}>
            <span className={styles.filterLabel}>进度</span>
            <div className={styles.chipBar} role="radiogroup" aria-label="按进度筛选">
              <button
                type="button"
                role="radio"
                aria-checked={!pstatus || pstatus === "all"}
                className={`${styles.chip} ${
                  !pstatus || pstatus === "all" ? styles.chipOn : ""
                }`}
                onClick={() => setStatusFilter("all")}
              >
                全部
              </button>
              {TARKOV_TASK_PROGRESS_FILTERS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  role="radio"
                  aria-checked={pstatus === item.id}
                  className={`${styles.chip} ${
                    pstatus === item.id ? styles.chipOn : ""
                  }`}
                  onClick={() => setStatusFilter(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      {mine && !meta?.progress_bound ? (
        <Alert
          type="info"
          showIcon
          message="还没绑定 Tarkov Tracker"
          description="打开顶栏「绑定 Token」后，才能按完成 / 进行中 / 缺少前置筛选。"
        />
      ) : null}
      {mine && meta?.progress_bound && !meta?.progress_ready ? (
        <Alert
          type="warning"
          showIcon
          message="进度明细还没拉下来"
          description="点顶栏等级旁的刷新，把 Tracker 的任务状态同步过来。"
        />
      ) : null}

      <div className={catalog.panel}>
        {view === "chain" ? (
          <TarkovTaskChains
            items={rows}
            traders={traders.map((item) => ({
              slug: item.slug,
              name: item.name,
            }))}
            mine={mine}
            showTraderHead={allOn}
          />
        ) : (
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
              onChange: (nextPage, nextSize) => {
                const params = new URLSearchParams(searchParams);
                if (nextPage <= 1) params.delete("page");
                else params.set("page", String(nextPage));
                if (nextSize === PAGE_SIZE_DEFAULT) params.delete("pageSize");
                else params.set("pageSize", String(nextSize));
                setSearchParams(params, { replace: true });
              },
            }}
            scroll={{ x: 920 }}
            locale={{
              emptyText: "当前筛选下无任务",
              filterReset: "全部",
              filterConfirm: "筛选",
            }}
          />
        )}
      </div>
    </div>
  );
}
