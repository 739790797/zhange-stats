import { Alert, Image, Spin, Table } from "antd";
import type { ColumnsType, TableProps } from "antd/es/table";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  fetchTarkovTasks,
  type TarkovTaskListItem,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import {
  TARKOV_TRADERS,
  traderPortraitUrl,
} from "@/lib/tarkovHomeNav";
import {
  TARKOV_TASK_PROGRESS_FILTERS,
  tarkovTaskProgressLabel,
  useTarkovTaskMineMode,
} from "@/lib/tarkovTaskProgress";
import { TarkovTaskProgressSwitch } from "@/components/guides/tarkov/TarkovTaskProgressSwitch";
import { TarkovTaskExpandBody } from "@/components/guides/tarkov/TarkovTaskObjectivesRewards";
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

function TraderFilterAvatar({ slug }: { slug: string }) {
  const [broken, setBroken] = useState(false);
  if (broken) {
    return <span className={styles.traderAvatarFallback} />;
  }
  return (
    <img
      className={styles.traderAvatar}
      src={traderPortraitUrl(slug)}
      alt=""
      width={72}
      height={72}
      onError={() => setBroken(true)}
    />
  );
}

const PAGE_SIZE_DEFAULT = 20;
const PAGE_SIZE_OPTIONS = [20, 50, 100];

function factionLabel(value: string | undefined): string {
  const v = (value || "").trim();
  if (!v || v === "Any") return "不限";
  return v;
}

export function TarkovTasksPanel() {
  const [searchParams, setSearchParams] = useSearchParams();
  const trader = (searchParams.get("trader") || "").trim();
  const pstatus = (searchParams.get("pstatus") || "").trim();
  const [mine, setMine] = useTarkovTaskMineMode();
  const [keyword, setKeyword] = useState("");
  const [q, setQ] = useState("");
  const qRef = useRef(q);
  const [pageNo, setPageNo] = useState(1);
  const [pageSize, setPageSize] = useState(PAGE_SIZE_DEFAULT);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const statusFilter = mine ? pstatus || "all" : "";

  useEffect(() => {
    const handle = window.setTimeout(() => {
      const next = keyword.trim();
      if (qRef.current === next) return;
      qRef.current = next;
      setQ(next);
      setPageNo(1);
    }, 300);
    return () => window.clearTimeout(handle);
  }, [keyword]);

  useEffect(() => {
    if (!mine && pstatus) {
      const next = new URLSearchParams(searchParams);
      next.delete("pstatus");
      setSearchParams(next, { replace: true });
    }
  }, [mine, pstatus, searchParams, setSearchParams]);

  useEffect(() => {
    setExpandedId(null);
  }, [trader, q, pageNo, pageSize, mine, statusFilter]);

  const catalogQuery = useQuery({
    queryKey: [
      "guides-tarkov-tasks",
      trader,
      q,
      pageNo,
      pageSize,
      mine,
      statusFilter,
    ],
    queryFn: () =>
      fetchTarkovTasks({
        q,
        trader: trader || undefined,
        page: pageNo,
        pageSize,
        progress: mine,
        progressStatus:
          mine && statusFilter && statusFilter !== "all"
            ? statusFilter
            : undefined,
      }),
    staleTime: 5 * 60_000,
    retry: 1,
    placeholderData: keepPreviousData,
  });

  const allOn = !trader;

  const setTraderFilter = (nextTrader: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (nextTrader) next.set("trader", nextTrader);
    else next.delete("trader");
    next.delete("kappa");
    setPageNo(1);
    setSearchParams(next, { replace: true });
  };

  const setStatusFilter = (nextStatus: string) => {
    const next = new URLSearchParams(searchParams);
    if (nextStatus && nextStatus !== "all") next.set("pstatus", nextStatus);
    else next.delete("pstatus");
    setPageNo(1);
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
      title: "名称",
      dataIndex: "name",
      key: "name",
      width: 280,
      ellipsis: true,
      render: (_: unknown, row) => {
        const label = row.name || row.normalized_name || row.id;
        const thumb = (row.task_image_link || "").trim();
        return (
          <span className={catalog.nameCell}>
            {thumb ? (
              <Image
                src={thumb}
                alt=""
                width={48}
                height={28}
                preview={{ src: thumb, mask: false }}
                onClick={(e) => e.stopPropagation()}
                style={{ objectFit: "cover", flex: "0 0 48px" }}
              />
            ) : (
              <span style={{ width: 48, height: 28, flex: "0 0 48px" }} />
            )}
            <span className={styles.taskName}>{label}</span>
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
      title: "商人",
      dataIndex: "trader_name",
      key: "trader_name",
      width: 120,
      ellipsis: true,
      render: (v: string) => v || "—",
    },
    {
      title: "地图",
      dataIndex: "map_name",
      key: "map_name",
      width: 100,
      ellipsis: true,
      render: (v: string) => v || "—",
    },
    {
      title: "等级",
      dataIndex: "min_player_level",
      key: "min_player_level",
      width: 64,
      align: "right",
      render: (v: number) => (v ? v : "—"),
    },
    {
      title: "经验",
      dataIndex: "experience",
      key: "experience",
      width: 80,
      align: "right",
      render: (v: number) =>
        v ? v.toLocaleString("zh-CN") : "—",
    },
    {
      title: "阵营",
      dataIndex: "faction_name",
      key: "faction_name",
      width: 72,
      render: (v: string) => factionLabel(v),
    },
    {
      title: "目标",
      dataIndex: "objective_count",
      key: "objective_count",
      width: 56,
      align: "right",
    },
    {
      title: "卡帕",
      dataIndex: "kappa_required",
      key: "kappa_required",
      width: 72,
      render: (v: boolean) => (v ? "需要" : "—"),
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

      <div className={catalog.toolbar}>
        <div className={catalog.meta}>
          {typeof meta?.task_count === "number" ? `共 ${meta.task_count} 条` : null}
        </div>
        <div className={styles.toolbarRight}>
          <TarkovTaskProgressSwitch
            enabled={mine}
            onChange={(value) => {
              setMine(value);
              setPageNo(1);
            }}
          />
          <input
            className={catalog.search}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="搜索名称 / 商人 / 地图"
            aria-label="搜索任务"
          />
        </div>
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

      <div className={styles.traderGrid} role="radiogroup" aria-label="按商人筛选">
        <button
          type="button"
          role="radio"
          aria-checked={allOn}
          className={`${styles.traderCard} ${allOn ? styles.traderCardOn : ""}`}
          onClick={() => setTraderFilter(null)}
        >
          <span className={styles.traderAvatarFallback}>全部</span>
          <div className={styles.traderEnglish}>All</div>
          <div className={styles.traderChinese}>全部商人</div>
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
              className={`${styles.traderCard} ${selected ? styles.traderCardOn : ""}`}
              onClick={() => setTraderFilter(item.slug)}
            >
              <TraderFilterAvatar slug={item.slug} />
              <div className={styles.traderEnglish}>{english}</div>
              {chinese ? (
                <div className={styles.traderChinese}>{chinese}</div>
              ) : null}
            </button>
          );
        })}
      </div>

      <div className={catalog.panel}>
        <Table<TarkovTaskListItem>
          className={`${tableStyles.table} ${styles.clickableRows}`}
          size="small"
          rowKey="id"
          columns={columns}
          dataSource={rows}
          loading={catalogQuery.isFetching}
          onChange={onTableChange}
          expandable={{
            expandedRowKeys: expandedId ? [expandedId] : [],
            onExpand: (expanded, record) => {
              setExpandedId(expanded ? record.id : null);
            },
            expandedRowRender: (row) => (
              <TarkovTaskExpandBody taskId={row.id} />
            ),
            expandRowByClick: true,
            columnWidth: 36,
          }}
          pagination={{
            current: pageNo,
            pageSize,
            total,
            showSizeChanger: true,
            pageSizeOptions: PAGE_SIZE_OPTIONS.map(String),
            showTotal: (count, range) => `${range[0]}–${range[1]} / ${count}`,
            onChange: (nextPage, nextSize) => {
              setPageNo(nextPage);
              setPageSize(nextSize);
            },
          }}
          scroll={{ x: 960 }}
          locale={{
            emptyText: "当前筛选下无任务",
            filterReset: "全部",
            filterConfirm: "筛选",
          }}
        />
      </div>
    </div>
  );
}
