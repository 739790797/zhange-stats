import { Image, Spin, Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Suspense, lazy } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovItemDetail } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { useTarkovDocumentTitle } from "@/lib/tarkovDocumentTitle";
import { inspectImageUrl } from "@/lib/tarkovItemImages";
import {
  extractContentLines,
  extractPlateSlots,
  extractRefItemId,
  formatPropertyList,
  isBareTarkovId,
  namedTraderOffers,
  numProp,
  parseItemBuyOffers,
  parseItemSellOffers,
  splitVendorOffers,
  type FormattedPropLink,
  type VendorOffer,
} from "@/lib/tarkovItemFormat";
import {
  gridOccupancyCaption,
  resolveItemGridLayout,
  type GridLayoutKind,
  type GridPocket,
} from "@/lib/tarkovItemGrids";
import { itemHrefFromTypes } from "@/lib/tarkovItemTypes";
import { itemKeyLockMaps } from "@/lib/tarkovItemLocks";
import { buildItemFleaQuote } from "@/lib/tarkovItemSources";
import { TarkovItemRefGrid } from "@/components/guides/tarkov/TarkovGuideItemCell";
import { TarkovItemKeyLocks } from "@/components/guides/tarkov/TarkovItemKeyLocks";
import { TarkovItemSources } from "@/components/guides/tarkov/TarkovItemSources";
import { TarkovItemUses } from "@/components/guides/tarkov/TarkovItemUses";
import tableStyles from "./TarkovDarkTable.module.css";
import styles from "./TarkovItemDetailPanel.module.css";

const TarkovAllowedAmmoScatter = lazy(() =>
  import("@/components/guides/tarkov/TarkovAllowedAmmoScatter").then((m) => ({
    default: m.TarkovAllowedAmmoScatter,
  })),
);

function itemRefLinks(links: FormattedPropLink[]) {
  return links
    .filter((link) => Boolean(link.id))
    .map((link) => ({
      id: String(link.id),
      name: link.label,
      icon_link: link.icon,
      types: link.types,
      count: link.count,
      badge: link.badge,
    }));
}

const GRID_CELL = 22;
const GRID_GAP = 2;

function pocketPixels(pocket: GridPocket) {
  return {
    left: pocket.col * (GRID_CELL + GRID_GAP),
    top: pocket.row * (GRID_CELL + GRID_GAP),
    width: pocket.width * GRID_CELL + Math.max(0, pocket.width - 1) * GRID_GAP,
    height: pocket.height * GRID_CELL + Math.max(0, pocket.height - 1) * GRID_GAP,
  };
}

function GridPocketCells({ pocket }: { pocket: GridPocket }) {
  const count = pocket.width * pocket.height;
  return (
    <div
      className={styles.gridPocket}
      style={{ gridTemplateColumns: `repeat(${pocket.width}, ${GRID_CELL}px)` }}
    >
      {Array.from({ length: count }, (_, cell) => (
        <span key={cell} className={styles.gridCellOn} />
      ))}
    </div>
  );
}

function GridPocketsView({
  pockets,
  kind,
  caption,
}: {
  pockets: GridPocket[];
  kind: GridLayoutKind;
  caption: string;
}) {
  if (!pockets.length) return null;
  if (kind === "stacked") {
    return (
      <div className={styles.gridBlock}>
        <div className={styles.gridPockets} role="img" aria-label={caption}>
          {pockets.map((pocket, index) => (
            <GridPocketCells
              key={`${pocket.width}x${pocket.height}-${index}`}
              pocket={pocket}
            />
          ))}
        </div>
        {caption ? <span className={styles.gridCaption}>{caption}</span> : null}
      </div>
    );
  }
  let stageW = 0;
  let stageH = 0;
  const placed = pockets.map((pocket, index) => {
    const box = pocketPixels(pocket);
    stageW = Math.max(stageW, box.left + box.width);
    stageH = Math.max(stageH, box.top + box.height);
    return { pocket, box, index };
  });
  return (
    <div className={styles.gridBlock}>
      <div
        className={styles.gridStage}
        style={{ width: stageW, height: stageH }}
        role="img"
        aria-label={caption}
      >
        {placed.map(({ pocket, box, index }) => (
          <div
            key={`${pocket.col}-${pocket.row}-${index}`}
            className={styles.gridPlaced}
            style={{
              left: box.left,
              top: box.top,
              width: box.width,
              height: box.height,
            }}
          >
            <GridPocketCells pocket={pocket} />
          </div>
        ))}
      </div>
      {caption ? <span className={styles.gridCaption}>{caption}</span> : null}
    </div>
  );
}

type Props = {
  itemId: string;
  /** embed：作为机匣 wiki 嵌在预设页下方，不再套一层 */
  variant?: "full" | "embed";
};

type ArmorSlotRow = {
  key: string;
  zones: string;
  class: string;
  durability: string;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function containedRows(item: Record<string, unknown>): Array<{
  id: string;
  name: string;
  count: number;
  icon: string;
  types: string[];
}> {
  const raw = item.containsItems;
  if (!Array.isArray(raw)) return [];
  const out: Array<{
    id: string;
    name: string;
    count: number;
    icon: string;
    types: string[];
  }> = [];
  for (const entry of raw) {
    const row = asRecord(entry);
    if (!row) continue;
    const nested =
      asRecord(row.item) ||
      (typeof row.item === "string" ? { id: row.item } : row);
    const id = String(nested.id || "").trim();
    if (!id) continue;
    const name = String(nested.name || nested.shortName || "").trim();
    if (!name || isBareTarkovId(name)) continue;
    const types = Array.isArray(nested.types)
      ? nested.types.map(String)
      : [];
    out.push({
      id,
      name,
      count: Number(row.count) || 1,
      icon: String(nested.iconLink || nested.baseImageLink || ""),
      types,
    });
  }
  return out;
}

function softArmorRows(props: Record<string, unknown>): ArmorSlotRow[] {
  const slots = props.armorSlots;
  if (!Array.isArray(slots)) return [];
  return slots
    .map((slot, index) => {
      const row = asRecord(slot);
      if (!row) return null;
      const durability = Number(row.durability);
      if (!Number.isFinite(durability) || durability <= 0) return null;
      const zones = Array.isArray(row.zones)
        ? row.zones.map(String).join(" · ")
        : String(row.name || "—");
      return {
        key: `${index}-${zones}`,
        class: row.class != null ? String(row.class) : "—",
        durability: String(durability),
        zones,
      };
    })
    .filter((row): row is ArmorSlotRow => Boolean(row));
}

function bestTraderOffer(offers: VendorOffer[]): VendorOffer | null {
  return offers.reduce<VendorOffer | null>((best, offer) => {
    const price = offer.priceRub ?? offer.price ?? 0;
    const current = best?.priceRub ?? best?.price ?? 0;
    if (!best || price > current) return offer;
    return best;
  }, null);
}

/** 常规排版：基础信息 → 属性 → 来源 → 用途；机匣是关联物品，放在四段之后。 */
export function TarkovItemDetailPanel({
  itemId,
  variant = "full",
}: Props) {
  const gameMode = useTarkovGameMode();
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-item-detail", gameMode, itemId],
    queryFn: () => fetchTarkovItemDetail(itemId),
    staleTime: 5 * 60_000,
    retry: 1,
  });
  useTarkovDocumentTitle(
    variant === "embed" ? "" : detailQuery.data?.name || "",
  );

  if (detailQuery.isLoading) {
    return (
      <div className={styles.status}>
        <Spin tip="加载详情…" />
      </div>
    );
  }

  if (detailQuery.isError) {
    return (
      <div className={styles.error}>
        {apiError(detailQuery.error, "物品详情加载失败")}
      </div>
    );
  }

  const detail = detailQuery.data;
  if (!detail) return null;

  const item = (detail.item || {}) as Record<string, unknown>;
  const properties = (detail.properties || {}) as Record<string, unknown>;
  const { baseItem: baseItemProp, ...restProperties } = properties;
  const handbookCats = item.handbookCategories;
  const categoryList =
    Array.isArray(handbookCats) && handbookCats.length
      ? handbookCats
      : item.categories;
  const image = inspectImageUrl(item, detail.id);
  const wiki = String(item.wikiLink || "").trim();
  const description =
    (detail.description || "").trim() ||
    String(item.description || "").trim();
  const buyOffers = parseItemBuyOffers(item);
  const sellOffers = parseItemSellOffers(item);
  const buySplit = splitVendorOffers(buyOffers);
  const sellSplit = splitVendorOffers(sellOffers);
  const traderBuys = namedTraderOffers(buyOffers);
  const traderSells = namedTraderOffers(sellOffers);
  const bestSell = bestTraderOffer(traderSells);
  const fleaBuy = buildItemFleaQuote(item, { fallbackOffers: buySplit.flea });
  const fleaSell = buildItemFleaQuote(item, {
    withChange: true,
    fallbackOffers: sellSplit.flea,
  });
  const lockMaps = itemKeyLockMaps(detail);
  const itemTypes = Array.isArray(item.types)
    ? item.types.map(String)
    : [];
  const receiverId =
    extractRefItemId(baseItemProp) || extractRefItemId(item.baseItem);
  const embed = variant === "embed";
  const showReceiverWiki =
    !embed &&
    itemTypes.includes("preset") &&
    Boolean(receiverId) &&
    receiverId !== itemId;
  const mergedProps: Record<string, unknown> = {
    weight: item.weight,
    size:
      item.width != null && item.height != null
        ? `${item.width}×${item.height}`
        : undefined,
    categories: categoryList,
    conflictingItems: item.conflictingItems,
    conflictingCategories: item.conflictingCategories,
    ...restProperties,
    ...(showReceiverWiki ? {} : { baseItem: baseItemProp ?? item.baseItem }),
    usedOnMaps: lockMaps.length
      ? undefined
      : restProperties.usedOnMaps ?? item.usedOnMaps,
  };
  const propRows = formatPropertyList(mergedProps);
  const contained = containedRows(item);
  const armorRows = softArmorRows(properties);
  const plateGroups = extractPlateSlots(properties);
  const gridLayout = resolveItemGridLayout(properties, detail.id);
  const pockets = gridLayout.pockets;
  const hasGrid = pockets.length > 0;
  const gridCaption = hasGrid
    ? gridOccupancyCaption(pockets, numProp(properties, "capacity"))
    : "";
  const contentLines = extractContentLines(properties);
  const armorColumns: ColumnsType<ArmorSlotRow> = [
    { title: "部位", dataIndex: "zones", key: "zones" },
    { title: "等级", dataIndex: "class", key: "class", width: 72 },
    { title: "耐久", dataIndex: "durability", key: "durability", width: 80 },
  ];
  const hasAttrCards = propRows.length > 0 || hasGrid;
  const hasAttrExtras = Boolean(
    lockMaps.length ||
      armorRows.length ||
      plateGroups.length ||
      contained.length ||
      contentLines.length,
  );
  const showAttrs = hasAttrCards || hasAttrExtras;
  const gridVisual = hasGrid ? (
    <div className={`${styles.prop} ${styles.propLarge}`}>
      <span className={styles.propKey}>格仓</span>
      <GridPocketsView
        pockets={pockets}
        kind={gridLayout.kind}
        caption={gridCaption}
      />
    </div>
  ) : null;
  const otherPropRows = hasGrid
    ? propRows.filter((row) => row.key !== "grids")
    : propRows;

  const attrCards = hasAttrCards ? (
    <div className={styles.props}>
      {gridVisual}
      {otherPropRows.map((row) => {
        const chips = row.links ? itemRefLinks(row.links) : [];
        const isAllowedAmmo = row.key === "allowedAmmo";
        const ammoIds = isAllowedAmmo
          ? chips.map((chip) => chip.id).filter(Boolean)
          : [];
        const defaultAmmoId = isAllowedAmmo
          ? chips.find((chip) => chip.badge === "默认")?.id
          : undefined;
        return (
          <div
            key={row.key}
            className={`${styles.prop} ${row.large ? styles.propLarge : ""}`}
          >
            <span className={styles.propKey}>{row.label}</span>
            {isAllowedAmmo && ammoIds.length ? (
              <Suspense
                fallback={
                  <div className={styles.ammoScatterFallback}>
                    <Spin size="small" />
                  </div>
                }
              >
                <TarkovAllowedAmmoScatter
                  ammoIds={ammoIds}
                  defaultAmmoId={defaultAmmoId}
                  fallbackItems={chips}
                  note={row.note}
                />
              </Suspense>
            ) : (
              <span className={styles.propValue}>
                {chips.length ? (
                  <TarkovItemRefGrid items={chips} />
                ) : row.links?.length ? (
                  row.links.map((link, index) => (
                    <span key={`${link.href}-${index}`}>
                      {index ? " · " : null}
                      <Link className={styles.propLink} to={link.href}>
                        {link.label}
                      </Link>
                    </span>
                  ))
                ) : (
                  row.value
                )}
                {row.note ? (
                  <span className={styles.propNote}>{row.note}</span>
                ) : null}
              </span>
            )}
          </div>
        );
      })}
    </div>
  ) : embed && !hasAttrExtras ? (
    <div className={styles.fleaMeta}>暂无属性</div>
  ) : null;

  return (
    <div className={embed ? styles.embedStack : styles.stack}>
      {embed ? (
        <div className={styles.embedHead}>
          <h2 className={styles.embedName}>
            <Link to={itemHrefFromTypes(itemId, itemTypes)}>
              {detail.name}
            </Link>
          </h2>
          {detail.short_name ? (
            <cite className={styles.shortName}>{detail.short_name}</cite>
          ) : null}
        </div>
      ) : (
        <div className={styles.hero}>
          <div className={styles.copy}>
            <h1 className={styles.name}>{detail.name}</h1>
            {detail.short_name ? (
              <cite className={styles.shortName}>{detail.short_name}</cite>
            ) : null}
            {wiki ? (
              <a
                className={styles.wiki}
                href={wiki}
                target="_blank"
                rel="noreferrer"
              >
                Wiki
              </a>
            ) : null}
            {description ? (
              <p className={styles.heroDesc}>{description}</p>
            ) : null}
          </div>
          {image ? (
            <div className={styles.visuals}>
              <div className={styles.imageWrap}>
                <Image
                  src={image}
                  alt={detail.name}
                  className={styles.image}
                  preview={{ mask: false }}
                />
              </div>
            </div>
          ) : null}
        </div>
      )}

      {showAttrs ? (
        <section className={styles.attrs}>
          {embed ? null : <h2 className={styles.sectionTitle}>属性</h2>}
          {attrCards}

          {lockMaps.length ? <TarkovItemKeyLocks detail={detail} /> : null}

          {armorRows.length ? (
            <>
              <h3 className={styles.attrSub}>软甲槽</h3>
              <Table<ArmorSlotRow>
                className={tableStyles.table}
                size="small"
                rowKey="key"
                columns={armorColumns}
                dataSource={armorRows}
                pagination={false}
              />
            </>
          ) : null}

          {plateGroups.length ? (
            <>
              <h3 className={styles.attrSub}>兼容护甲板</h3>
              {plateGroups.map((group) => (
                <div key={group.key} className={styles.plateGroup}>
                  <h4 className={styles.plateHead}>{group.name}</h4>
                  <TarkovItemRefGrid
                    items={group.plates.map((plate) => ({
                      id: plate.id,
                      name: plate.name,
                      icon_link: plate.icon,
                      types: plate.types,
                    }))}
                  />
                </div>
              ))}
            </>
          ) : null}

          {contained.length ? (
            <>
              <h3 className={styles.attrSub}>内含物品</h3>
              <TarkovItemRefGrid
                showCount
                items={contained.map((row) => ({
                  id: row.id,
                  name: row.name,
                  icon_link: row.icon,
                  types: row.types,
                  count: row.count,
                }))}
              />
            </>
          ) : null}

          {contentLines.length ? (
            <>
              <h3 className={styles.attrSub}>内容</h3>
              <div className={styles.contentBox}>
                {contentLines.map((line) => (
                  <p key={line}>{line}</p>
                ))}
              </div>
            </>
          ) : null}
        </section>
      ) : null}

      {!embed ? (
        <TarkovItemSources
          detail={detail}
          flea={fleaBuy}
          traderBuys={traderBuys}
        />
      ) : null}
      {!embed ? (
        <TarkovItemUses
          detail={detail}
          flea={fleaSell}
          traderSells={traderSells}
          bestSell={bestSell}
        />
      ) : null}

      {showReceiverWiki ? (
        <section className={styles.embedWiki}>
          <h2 className={styles.sectionTitle}>机匣</h2>
          <p className={styles.embedWikiNote}>
            口径、可用弹药和射击数据属于机匣，本配置及其他预设共用。
          </p>
          <TarkovItemDetailPanel itemId={receiverId} variant="embed" />
        </section>
      ) : null}
    </div>
  );
}
