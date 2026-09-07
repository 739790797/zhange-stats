import { Alert, Image, Spin, Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  fetchTarkovItemCatalog,
  type TarkovCatalogItem,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  CATALOG_COLUMN_LABELS,
  boolProp,
  catalogColumnsForSlug,
  cheapestPrice,
  formatMoney,
  formatPercent,
  formatSigned,
  formatWeight,
  innerSlots,
  itemGridSize,
  numProp,
  propsOf,
  strProp,
  type CatalogColumnId,
  type CatalogPriceRow,
} from "@/lib/tarkovItemFormat";
import { hdPreviewUrl, transparentThumbUrl } from "@/lib/tarkovItemImages";
import {
  findHandbookChild,
  handbookNodeCategoryIds,
  itemDetailHref,
  type TarkovHandbookChild,
  type TarkovItemPage,
} from "@/lib/tarkovItemTypes";
import { readAllowedInt, readPositiveInt } from "@/lib/tarkovQueryState";
import tableStyles from "./TarkovDarkTable.module.css";
import styles from "./TarkovItemCatalogPanel.module.css";

type Props = {
  page: TarkovItemPage;
};

type CatalogRow = TarkovCatalogItem & CatalogPriceRow;

const PAGE_SIZE_DEFAULT = 50;
const PAGE_SIZE_OPTIONS = [20, 50, 100];

function dash(value: string | number | null | undefined): string {
  if (value == null || value === "") return "—";
  return String(value);
}

function cellFor(column: CatalogColumnId, row: CatalogRow): string {
  const props = propsOf(row);
  switch (column) {
    case "grid":
      return itemGridSize(row);
    case "slots":
      return dash(innerSlots(props));
    case "weight":
      return formatWeight(row.weight);
    case "slotRatio": {
      const slots = innerSlots(props);
      const area =
        row.width != null && row.height != null ? row.width * row.height : 0;
      if (!slots || !area) return "—";
      return String(Math.round((slots / area) * 100) / 100);
    }
    case "pricePerSlot": {
      const slots = innerSlots(props);
      const price = cheapestPrice(row);
      if (!slots || price == null) return "—";
      return formatMoney(Math.round(price / slots));
    }
    case "class":
      return dash(numProp(props, "class"));
    case "zones": {
      const zones = props.zones;
      if (Array.isArray(zones)) return zones.map(String).join(" · ") || "—";
      return "—";
    }
    case "durability": {
      const cur = numProp(props, "durability");
      const max = numProp(props, "maxDurability");
      if (cur == null && max == null) return "—";
      if (cur != null && max != null && cur !== max) return `${cur} / ${max}`;
      return dash(cur ?? max);
    }
    case "ricochet":
      return dash(strProp(props, "ricochetY") || numProp(props, "ricochetChance"));
    case "turnPenalty":
      return formatPercent(numProp(props, "turnPenalty"));
    case "blocksHeadset": {
      const blocked = boolProp(props, "blocksHeadset", "blockHeadset");
      if (blocked == null) return "—";
      return blocked ? "是" : "否";
    }
    case "blindness":
      return formatPercent(numProp(props, "blindnessProtection"));
    case "distance":
      return formatSigned(numProp(props, "distanceModifier"));
    case "fuse":
      return dash(numProp(props, "fuse"));
    case "fragments":
      return dash(numProp(props, "fragments"));
    case "radius": {
      const min = numProp(props, "minExplosionDistance");
      const max = numProp(props, "maxExplosionDistance");
      if (min == null && max == null) return "—";
      if (min != null && max != null) return `${min}–${max}`;
      return dash(max ?? min);
    }
    case "grenadeType":
      return dash(strProp(props, "type"));
    case "energy":
      return dash(numProp(props, "energy", "energyImpact"));
    case "hydration":
      return dash(numProp(props, "hydration", "hydrationImpact"));
    case "useTime":
      return dash(numProp(props, "useTime"));
    case "uses":
      return dash(numProp(props, "uses"));
    case "ergo":
      return formatSigned(numProp(props, "ergonomics", "ergoPenalty"));
    case "recoil":
      return formatSigned(numProp(props, "recoilModifier", "recoil"));
    case "loudness":
      return dash(numProp(props, "loudness"));
    case "hp":
      return dash(numProp(props, "hitpoints", "hp"));
    case "slashDamage":
      return dash(numProp(props, "slashDamage"));
    case "stabDamage":
      return dash(numProp(props, "stabDamage"));
    case "price":
      return formatMoney(cheapestPrice(row));
    default:
      return "—";
  }
}

export function TarkovItemCatalogPanel({ page }: Props) {
  const gameMode = useTarkovGameMode();
  const [searchParams, setSearchParams] = useSearchParams();
  const childParam = (searchParams.get("child") || "").trim();
  const q = (searchParams.get("q") || "").trim();
  const pageNo = readPositiveInt(searchParams.get("page"), 1);
  const pageSize = readAllowedInt(
    searchParams.get("pageSize"),
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_OPTIONS,
  );
  const [keyword, setKeyword] = useState(q);
  const qRef = useRef(q);

  const activeChild = findHandbookChild(page.children, childParam) || null;

  const categoryIds = activeChild
    ? handbookNodeCategoryIds(activeChild)
    : page.categoryIds;
  const types = page.types || [];
  const canFetch = categoryIds.some(Boolean) || types.some(Boolean);
  const columnIds = catalogColumnsForSlug(page.slug);

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
      "guides-tarkov-catalog",
      gameMode,
      page.slug,
      categoryIds,
      types,
      q,
      pageNo,
      pageSize,
    ],
    queryFn: () =>
      fetchTarkovItemCatalog({
        categoryIds,
        types,
        q,
        page: pageNo,
        pageSize,
      }),
    enabled: canFetch,
    staleTime: 5 * 60_000,
    retry: 1,
    placeholderData: keepPreviousData,
  });

  const setChild = (id: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (id) next.set("child", id);
    else next.delete("child");
    next.delete("page");
    setSearchParams(next, { replace: true });
  };

  const columns = useMemo<ColumnsType<CatalogRow>>(() => {
    return columnIds.map((id) => {
      if (id === "name") {
        return {
          title: CATALOG_COLUMN_LABELS.name,
          dataIndex: "name",
          key: "name",
          ellipsis: true,
          render: (_: unknown, row: CatalogRow) => {
            const label = row.name || row.short_name || row.id;
            const thumb = transparentThumbUrl(row.icon_link);
            const hd = hdPreviewUrl(row.icon_link) || thumb;
            return (
              <span className={styles.nameCell}>
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
                  className={styles.nameLink}
                  to={itemDetailHref(page.slug, row.id)}
                >
                  {label}
                </Link>
              </span>
            );
          },
        };
      }
      const numeric = new Set<CatalogColumnId>([
        "slots",
        "weight",
        "slotRatio",
        "pricePerSlot",
        "class",
        "durability",
        "price",
        "fuse",
        "fragments",
        "energy",
        "hydration",
        "useTime",
        "uses",
        "ergo",
        "recoil",
        "loudness",
        "hp",
        "slashDamage",
        "stabDamage",
      ]);
      return {
        title: CATALOG_COLUMN_LABELS[id],
        key: id,
        width: id === "zones" ? 180 : id === "price" ? 110 : 88,
        align: numeric.has(id) ? "right" : "left",
        render: (_: unknown, row: CatalogRow) => cellFor(id, row),
      };
    });
  }, [columnIds, page.slug]);

  const meta = catalogQuery.data;
  const rows = (meta?.items ?? []) as CatalogRow[];
  const total = typeof meta?.item_count === "number" ? meta.item_count : 0;
  const hasFilter = page.children.length > 0;
  const listBody =
    catalogQuery.isLoading && !catalogQuery.data ? (
      <div className={styles.status}>
        <Spin tip="加载物品…" />
      </div>
    ) : catalogQuery.isError && !catalogQuery.data ? (
      <Alert
        type="error"
        showIcon
        message="物品目录加载失败"
        description={apiError(catalogQuery.error, "物品目录加载失败")}
      />
    ) : (
      <div className={styles.panel}>
        <Table<CatalogRow>
          className={tableStyles.table}
          size="small"
          rowKey="id"
          columns={columns}
          dataSource={rows}
          loading={catalogQuery.isFetching}
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
          scroll={{ x: 720 }}
          locale={{ emptyText: "当前筛选下无物品" }}
        />
      </div>
    );

  const main = (
    <div className={styles.main}>
      {catalogQuery.isError && catalogQuery.data ? (
        <Alert
          type="error"
          showIcon
          message="物品目录加载失败"
          description={apiError(catalogQuery.error, "物品目录加载失败")}
        />
      ) : null}
      <div className={styles.toolbar}>
        <div className={styles.meta}>
          {typeof meta?.item_count === "number" ? `共 ${meta.item_count} 件` : null}
          {activeChild ? ` · ${activeChild.label}` : null}
        </div>
        <input
          className={styles.search}
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="搜索名称 / 短名"
          aria-label="搜索物品"
        />
      </div>
      {listBody}
    </div>
  );

  if (!hasFilter) {
    return <div className={styles.stack}>{main}</div>;
  }

  return (
    <div className={styles.layout}>
      <aside className={styles.sidebar}>
        <CatalogFilterChips
          nodes={page.children}
          activeId={activeChild?.id ?? null}
          onSelect={setChild}
        />
      </aside>
      {main}
    </div>
  );
}

function nodeContainsId(node: TarkovHandbookChild, id: string | null): boolean {
  if (!id) return false;
  return Boolean(findHandbookChild([node], id));
}

function CatButton({
  id,
  label,
  active,
  onSelect,
  head,
}: {
  id: string | null;
  label: string;
  active: boolean;
  onSelect: (id: string | null) => void;
  head?: boolean;
}) {
  return (
    <button
      type="button"
      className={`${styles.catBtn}${head ? ` ${styles.catHead}` : ""}${
        active ? ` ${styles.catOn}` : ""
      }`}
      onClick={() => onSelect(id)}
    >
      {label}
    </button>
  );
}

function CatNode({
  node,
  activeId,
  onSelect,
  depth,
}: {
  node: TarkovHandbookChild;
  activeId: string | null;
  onSelect: (id: string | null) => void;
  depth: number;
}) {
  const kids = node.children ?? [];
  const containsActive = nodeContainsId(node, activeId);
  const [open, setOpen] = useState(() => depth === 0 || containsActive);

  useEffect(() => {
    if (containsActive) setOpen(true);
  }, [containsActive]);

  return (
    <div className={styles.treeNode}>
      <div className={styles.catRow}>
        {kids.length ? (
          <button
            type="button"
            className={`${styles.catCaret}${open ? ` ${styles.catCaretOpen}` : ""}`}
            aria-expanded={open}
            aria-label={open ? `收起${node.label}` : `展开${node.label}`}
            onClick={() => setOpen((value) => !value)}
          />
        ) : depth > 0 ? (
          <span className={styles.catCaretSlot} />
        ) : null}
        <CatButton
          id={node.id}
          label={node.label}
          active={activeId === node.id}
          onSelect={onSelect}
          head={depth === 0 && kids.length > 0}
        />
      </div>
      {open && kids.length ? (
        <CatTree
          nodes={kids}
          activeId={activeId}
          onSelect={onSelect}
          depth={depth + 1}
        />
      ) : null}
    </div>
  );
}

function CatTree({
  nodes,
  activeId,
  onSelect,
  depth,
}: {
  nodes: TarkovHandbookChild[];
  activeId: string | null;
  onSelect: (id: string | null) => void;
  depth: number;
}) {
  if (!nodes.length) return null;
  return (
    <div className={depth === 0 ? styles.treeRoots : styles.treeKids}>
      {nodes.map((node) => (
        <CatNode
          key={node.id}
          node={node}
          activeId={activeId}
          onSelect={onSelect}
          depth={depth}
        />
      ))}
    </div>
  );
}

function CatalogFilterChips({
  nodes,
  activeId,
  onSelect,
}: {
  nodes: TarkovHandbookChild[];
  activeId: string | null;
  onSelect: (id: string | null) => void;
}) {
  return (
    <nav className={styles.tree} aria-label="手册分类">
      <CatButton
        id={null}
        label="全部"
        active={!activeId}
        onSelect={onSelect}
      />
      <CatTree
        nodes={nodes}
        activeId={activeId}
        onSelect={onSelect}
        depth={0}
      />
    </nav>
  );
}
