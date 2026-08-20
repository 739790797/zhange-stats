import { Image, Spin, Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Suspense, lazy } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovItemDetail } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { tarkovTraderHref, traderPortraitUrl } from "@/lib/tarkovHomeNav";
import { useTarkovDocumentTitle } from "@/lib/tarkovDocumentTitle";
import { inspectImageUrl } from "@/lib/tarkovItemImages";
import {
  extractContentLines,
  extractGridPockets,
  extractPlateSlots,
  extractRefItemId,
  formatMoney,
  formatPropertyList,
  isBareTarkovId,
  parseVendorOffers,
  formatOfferPrice,
  itemHasFlea,
  type FormattedPropLink,
  type GridPocket,
  type VendorOffer,
} from "@/lib/tarkovItemFormat";
import { itemHrefFromTypes } from "@/lib/tarkovItemTypes";
import { TarkovItemRefGrid } from "@/components/guides/tarkov/TarkovGuideItemCell";
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

function GridPreview({ pockets }: { pockets: GridPocket[] }) {
  if (!pockets.length) return null;
  return (
    <div className={styles.gridPreview} aria-hidden>
      {pockets.map((pocket, index) => (
        <div
          key={`${pocket.col}-${pocket.row}-${index}`}
          className={styles.gridPocket}
          style={{
            gridTemplateColumns: `repeat(${pocket.width}, 20px)`,
          }}
        >
          {Array.from({ length: pocket.width * pocket.height }, (_, cell) => (
            <span key={cell} className={styles.gridCell} />
          ))}
        </div>
      ))}
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

function vendorIcon(offer: VendorOffer): string {
  const key = offer.vendor;
  if (!key || key === "flea-market" || key === "fleaMarket") return "";
  return traderPortraitUrl(key);
}

function vendorHref(offer: VendorOffer): string | null {
  const key = offer.vendor;
  if (!key || key === "flea-market" || key === "fleaMarket") return null;
  return tarkovTraderHref(key);
}

function OfferCard({
  offer,
  best,
}: {
  offer: VendorOffer;
  best?: boolean;
}) {
  const href = vendorHref(offer);
  const icon = vendorIcon(offer);
  const inner = (
    <>
      <span className={styles.offerIcon}>
        {icon ? (
          <img className={styles.offerImg} src={icon} alt="" />
        ) : (
          <span className={styles.offerFlea}>跳蚤</span>
        )}
        {offer.minLevel ? (
          <span className={styles.offerLevel}>{offer.minLevel}</span>
        ) : null}
      </span>
      <span className={styles.offerPrice}>{formatOfferPrice(offer)}</span>
    </>
  );
  const className = `${styles.offer} ${best ? styles.offerBest : ""}`;
  if (href) {
    return (
      <Link className={className} to={href} title={offer.vendorName}>
        {inner}
      </Link>
    );
  }
  return (
    <span className={className} title={offer.vendorName}>
      {inner}
    </span>
  );
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
        zones,
        class: row.class != null ? String(row.class) : "—",
        durability: String(durability),
      };
    })
    .filter((row): row is ArmorSlotRow => Boolean(row));
}

/** 对齐 tarkov.dev 物品页：大标题 + 右图 + 买卖价 + 属性卡。 */
export function TarkovItemDetailPanel({
  itemId,
  variant = "full",
}: Props) {
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-item-detail", itemId],
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
  const handbookCats = item.handbookCategories;
  const categoryList =
    Array.isArray(handbookCats) && handbookCats.length
      ? handbookCats
      : item.categories;
  const image = inspectImageUrl(item);
  const wiki = String(item.wikiLink || "").trim();
  const sellFor = parseVendorOffers(item.sellFor ?? item.sell_for);
  const buyFor = parseVendorOffers(item.buyFor ?? item.buy_for);
  const bestSell = sellFor.reduce<VendorOffer | null>((best, offer) => {
    const price = offer.priceRub ?? offer.price ?? 0;
    const current = best?.priceRub ?? best?.price ?? 0;
    if (!best || price > current) return offer;
    return best;
  }, null);
  const avg24 = Number(item.avg24hPrice);
  const lastLow = Number(item.lastLowPrice);
  const change48 = Number(item.changeLast48h);
  const change48p = Number(item.changeLast48hPercent);
  const mergedProps: Record<string, unknown> = {
    weight: item.weight,
    size:
      item.width != null && item.height != null
        ? `${item.width}×${item.height}`
        : undefined,
    categories: categoryList,
    conflictingItems: item.conflictingItems,
    conflictingCategories: item.conflictingCategories,
    ...properties,
    usedOnMaps: properties.usedOnMaps ?? item.usedOnMaps,
  };
  const propRows = formatPropertyList(mergedProps);
  const contained = containedRows(item);
  const armorRows = softArmorRows(properties);
  const plateGroups = extractPlateSlots(properties);
  const pockets = extractGridPockets(properties);
  const contentLines = extractContentLines(properties);
  const showFlea = itemHasFlea(item);
  const armorColumns: ColumnsType<ArmorSlotRow> = [
    { title: "部位", dataIndex: "zones", key: "zones" },
    { title: "等级", dataIndex: "class", key: "class", width: 72 },
    { title: "耐久", dataIndex: "durability", key: "durability", width: 80 },
  ];
  const itemTypes = Array.isArray(item.types)
    ? item.types.map(String)
    : [];
  const receiverId =
    extractRefItemId(properties.baseItem) || extractRefItemId(item.baseItem);
  const showReceiverWiki =
    variant === "full" &&
    itemTypes.includes("preset") &&
    Boolean(receiverId) &&
    receiverId !== itemId;
  const embed = variant === "embed";

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
        </div>
        <div className={styles.visuals}>
          <GridPreview pockets={pockets} />
          {image ? (
            <div className={styles.imageWrap}>
              <Image
                src={image}
                alt=""
                className={styles.image}
                preview={{ mask: false }}
              />
            </div>
          ) : null}
        </div>
      </div>
      )}

      {!embed && (sellFor.length || buyFor.length) ? (
        <div className={styles.traders}>
          {sellFor.length ? (
            <div className={styles.traderCol}>
              <h2 className={styles.sectionTitle}>出售给</h2>
              <div className={styles.offerRow}>
                {sellFor.map((offer, index) => (
                  <OfferCard
                    key={`${offer.vendor}-${index}`}
                    offer={offer}
                    best={
                      bestSell != null &&
                      offer.vendor === bestSell.vendor &&
                      offer.priceRub === bestSell.priceRub
                    }
                  />
                ))}
              </div>
            </div>
          ) : null}
          {buyFor.length ? (
            <div className={styles.traderColBuy}>
              <h2 className={styles.sectionTitle}>购买自</h2>
              <div className={`${styles.offerRow} ${styles.offerRowBuy}`}>
                {buyFor.map((offer, index) => (
                  <OfferCard key={`${offer.vendor}-${index}`} offer={offer} />
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {!embed && showFlea && (Number.isFinite(avg24) || Number.isFinite(lastLow)) ? (
        <div className={styles.fleaMeta}>
          {Number.isFinite(lastLow) ? (
            <span>最近低价 {formatMoney(lastLow)}</span>
          ) : null}
          {Number.isFinite(avg24) ? (
            <span>24h 均价 {formatMoney(avg24)}</span>
          ) : null}
          {Number.isFinite(change48) ? (
            <span>
              较昨日 {change48 > 0 ? "+" : ""}
              {Math.round(change48).toLocaleString("zh-CN")} ₽
              {Number.isFinite(change48p) ? ` / ${change48p}%` : ""}
            </span>
          ) : null}
        </div>
      ) : null}

      {embed ? null : <h2 className={styles.sectionTitle}>属性</h2>}
      {propRows.length ? (
        <div className={styles.props}>
          {propRows.map((row) => {
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
                  <>
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
                  </>
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
      ) : (
        <div className={styles.fleaMeta}>暂无属性</div>
      )}

      {armorRows.length ? (
        <>
          <h2 className={styles.sectionTitle}>软甲槽</h2>
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
          <h2 className={styles.sectionTitle}>兼容护甲板</h2>
          {plateGroups.map((group) => (
            <div key={group.key} className={styles.plateGroup}>
              <h3 className={styles.plateHead}>{group.name}</h3>
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
          <h2 className={styles.sectionTitle}>
            {detail.name ? `${detail.name} 内含物品` : "内含物品"}
          </h2>
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
          <h2 className={styles.sectionTitle}>内容</h2>
          <div className={styles.contentBox}>
            {contentLines.map((line) => (
              <p key={line}>{line}</p>
            ))}
          </div>
        </>
      ) : null}

      {detail.description ? (
        <p className={styles.desc}>{detail.description}</p>
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
