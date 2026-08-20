import { Alert, Image, Spin, Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  fetchTarkovTraderDetail,
  type TarkovTraderOffer,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { TARKOV_TASKS_PATH, tarkovTaskHref } from "@/lib/tarkovHomeNav";
import { useTarkovDocumentTitle } from "@/lib/tarkovDocumentTitle";
import { formatMoney } from "@/lib/tarkovItemFormat";
import { hdPreviewUrl, transparentThumbUrl } from "@/lib/tarkovItemImages";
import { itemHrefFromTypes } from "@/lib/tarkovItemTypes";
import { readAllowedInt, readPositiveInt } from "@/lib/tarkovQueryState";
import tableStyles from "./TarkovDarkTable.module.css";
import catalogStyles from "./TarkovItemCatalogPanel.module.css";
import styles from "./TarkovTraderPanel.module.css";

type Props = {
  slug: string;
};

const PAGE_SIZE_DEFAULT = 50;
const PAGE_SIZE_OPTIONS = [20, 50, 100];
const LOYALTY = [
  { value: 1, label: "I" },
  { value: 2, label: "II" },
  { value: 3, label: "III" },
  { value: 4, label: "IV" },
] as const;

function restockLabel(resetTime: string | undefined, nowMs: number): string {
  const t = Date.parse(resetTime || "");
  if (!Number.isFinite(t)) return "—";
  const ms = t - nowMs;
  if (ms <= 0) return "即将补货";
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return [h, m, sec].map((n) => String(n).padStart(2, "0")).join(":");
}

export function TarkovTraderPanel({ slug }: Props) {
  const [searchParams, setSearchParams] = useSearchParams();
  const levelRaw = Number(searchParams.get("level") || "");
  const level =
    levelRaw === 1 || levelRaw === 2 || levelRaw === 3 || levelRaw === 4
      ? levelRaw
      : undefined;
  const q = (searchParams.get("q") || "").trim();
  const pageNo = readPositiveInt(searchParams.get("page"), 1);
  const pageSize = readAllowedInt(
    searchParams.get("pageSize"),
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_OPTIONS,
  );
  const [keyword, setKeyword] = useState(q);
  const qRef = useRef(q);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [portraitSrc, setPortraitSrc] = useState("");

  useEffect(() => {
    setKeyword(q);
    qRef.current = q;
  }, [q, slug]);

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
    const id = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-trader", slug, level, q, pageNo, pageSize],
    queryFn: () =>
      fetchTarkovTraderDetail(slug, {
        level,
        q,
        page: pageNo,
        pageSize,
      }),
    staleTime: 60_000,
    retry: 1,
    enabled: Boolean(slug),
    placeholderData: (previousData, previousQuery) => {
      if (previousQuery?.queryKey[1] === slug) return previousData;
      return undefined;
    },
  });

  const detail = detailQuery.data;
  useTarkovDocumentTitle(detail?.english || "");
  useEffect(() => {
    setPortraitSrc(detail?.portrait_link || detail?.image_link || "");
  }, [detail?.portrait_link, detail?.image_link, slug]);

  const setLevel = (next: number | undefined) => {
    const params = new URLSearchParams(searchParams);
    if (next) params.set("level", String(next));
    else params.delete("level");
    params.delete("page");
    setSearchParams(params, { replace: true });
  };

  const columns: ColumnsType<TarkovTraderOffer> = [
    {
      title: "名称",
      dataIndex: "name",
      key: "name",
      ellipsis: true,
      render: (_: unknown, row) => {
        const label = row.name || row.short_name || row.item_id;
        const thumb = transparentThumbUrl(row.icon_link);
        const hd = hdPreviewUrl(row.icon_link) || thumb;
        return (
          <span className={catalogStyles.nameCell}>
            {thumb ? (
              <Image
                src={thumb}
                alt=""
                width={36}
                height={36}
                preview={{ src: hd, mask: false }}
                style={{ objectFit: "contain", flex: "0 0 36px" }}
              />
            ) : (
              <span style={{ width: 36, height: 36, flex: "0 0 36px" }} />
            )}
            <Link
              className={catalogStyles.nameLink}
              to={itemHrefFromTypes(row.item_id, row.types)}
            >
              {label}
            </Link>
          </span>
        );
      },
    },
    {
      title: "在跳蚤市场购买",
      key: "flea",
      width: 160,
      align: "right",
      render: (_: unknown, row) =>
        formatMoney(row.last_low_price ?? row.avg24h_price, "RUB"),
    },
    {
      title: "商人报价",
      key: "offer",
      width: 220,
      render: (_: unknown, row) => (
        <div>
          <span className={styles.offerPrice}>
            {formatMoney(row.price, row.currency)}
          </span>
          <span className={styles.offerMeta}>
            {detail?.english || slug} LL{row.min_trader_level}
          </span>
          {row.task_unlock_id ? (
            <Link
              className={styles.unlock}
              to={tarkovTaskHref(row.task_unlock_id)}
            >
              {row.task_unlock_name || "任务解锁"}
            </Link>
          ) : null}
        </div>
      ),
    },
  ];

  if (detailQuery.isLoading && !detail) {
    return (
      <div className={styles.status}>
        <Spin />
      </div>
    );
  }

  if (detailQuery.isError && !detail) {
    return (
      <Alert
        type="error"
        showIcon
        message="商人页加载失败"
        description={apiError(detailQuery.error, "商人页加载失败")}
      />
    );
  }

  if (!detail) return null;

  const rows = detail.items ?? [];
  const total = typeof detail.offer_count === "number" ? detail.offer_count : 0;
  const title = detail.english || slug;

  return (
    <div className={styles.stack}>
      {detailQuery.isError ? (
        <Alert
          type="error"
          showIcon
          message="报价刷新失败"
          description={apiError(detailQuery.error, "报价刷新失败")}
        />
      ) : null}

      <section className={styles.hero}>
        <div>
          <span className={styles.badge}>商人</span>
          <div className={styles.nameRow}>
            <h2 className={styles.name}>{title}</h2>
            {detail.chinese ? (
              <span className={styles.chinese}>（{detail.chinese}）</span>
            ) : null}
            {detail.wiki_link ? (
              <a
                className={styles.wiki}
                href={detail.wiki_link}
                target="_blank"
                rel="noreferrer"
              >
                Wiki
              </a>
            ) : null}
          </div>
          {detail.description ? (
            <p className={styles.desc}>{detail.description}</p>
          ) : null}
        </div>
        <div className={styles.portraitWrap}>
          {portraitSrc ? (
            <img
              className={styles.portrait}
              src={portraitSrc}
              alt=""
              onError={() => {
                if (detail.image_link && portraitSrc !== detail.image_link) {
                  setPortraitSrc(detail.image_link);
                }
              }}
            />
          ) : null}
        </div>
      </section>

      <div className={styles.controls}>
        <div className={styles.restock}>
          补货剩余时间
          <span className={styles.restockTime}>
            {restockLabel(detail.reset_time, nowMs)}
          </span>
        </div>
        <div className={styles.levelRow}>
          {LOYALTY.map((item) => (
            <button
              key={item.value}
              type="button"
              className={`${styles.levelBtn} ${level === item.value ? styles.levelOn : ""}`}
              onClick={() =>
                setLevel(level === item.value ? undefined : item.value)
              }
            >
              {item.label}
            </button>
          ))}
          <Link
            className={styles.taskBtn}
            to={`${TARKOV_TASKS_PATH}?trader=${encodeURIComponent(slug)}`}
          >
            任务
          </Link>
        </div>
        <input
          className={styles.search}
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="按物品筛选"
          aria-label="按物品筛选"
        />
      </div>

      <Table
        className={tableStyles.table}
        rowKey={(row) => `${row.item_id}-${row.min_trader_level}`}
        columns={columns}
        dataSource={rows}
        loading={detailQuery.isFetching}
        pagination={{
          current: pageNo,
          pageSize,
          total,
          showSizeChanger: true,
          pageSizeOptions: PAGE_SIZE_OPTIONS,
          showTotal: (n) => `共 ${n} 条`,
          onChange: (nextPage, nextSize) => {
            const params = new URLSearchParams(searchParams);
            if (nextPage <= 1) params.delete("page");
            else params.set("page", String(nextPage));
            if (nextSize === PAGE_SIZE_DEFAULT) params.delete("pageSize");
            else params.set("pageSize", String(nextSize));
            setSearchParams(params, { replace: true });
          },
        }}
        locale={{ emptyText: "该商人暂无现金报价" }}
      />
    </div>
  );
}
