import { Image, Spin, Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovItemDetail } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { tarkovTraderHref, traderPortraitUrl } from "@/lib/tarkovHomeNav";
import { inspectImageUrl, transparentThumbUrl } from "@/lib/tarkovItemImages";
import {
  extractContentLines,
  extractGridPockets,
  extractPlateSlots,
  formatMoney,
  formatPropertyList,
  parseVendorOffers,
  formatOfferPrice,
  itemHasFlea,
  type GridPocket,
  type VendorOffer,
} from "@/lib/tarkovItemFormat";
import { itemHrefFromTypes } from "@/lib/tarkovItemTypes";
import tableStyles from "./TarkovDarkTable.module.css";
import styles from "./TarkovItemDetailPanel.module.css";

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
    const nested = asRecord(row.item) || row;
    const id = String(nested.id || "").trim();
    if (!id) continue;
    const types = Array.isArray(nested.types)
      ? nested.types.map(String)
      : [];
    out.push({
      id,
      name: String(nested.name || nested.shortName || id),
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
export function TarkovItemDetailPanel({ itemId }: Props) {
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-item-detail", itemId],
    queryFn: () => fetchTarkovItemDetail(itemId),
    staleTime: 5 * 60_000,
    retry: 1,
  });

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
    categories: item.categories,
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

  return (
    <div className={styles.stack}>
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

      {sellFor.length || buyFor.length ? (
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

      {showFlea && (Number.isFinite(avg24) || Number.isFinite(lastLow)) ? (
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

      <h2 className={styles.sectionTitle}>属性</h2>
      {propRows.length ? (
        <div className={styles.props}>
          {propRows.map((row) => (
            <div
              key={row.key}
              className={`${styles.prop} ${row.large ? styles.propLarge : ""}`}
            >
              <span className={styles.propKey}>{row.label}</span>
              <span className={styles.propValue}>
                {row.links?.length ? (
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
              </span>
            </div>
          ))}
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
              <div className={styles.contained}>
                {group.plates.map((plate) => (
                  <Link
                    key={plate.id}
                    className={styles.containedLink}
                    to={itemHrefFromTypes(plate.id, plate.types)}
                  >
                    {plate.icon ? (
                      <img
                        className={styles.containedIcon}
                        src={transparentThumbUrl(plate.icon) || plate.icon}
                        alt=""
                      />
                    ) : null}
                    {plate.name}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </>
      ) : null}

      {contained.length ? (
        <>
          <h2 className={styles.sectionTitle}>
            {detail.name ? `${detail.name} 内含物品` : "内含物品"}
          </h2>
          <div className={styles.contained}>
            {contained.map((row) => (
              <Link
                key={row.id}
                className={styles.containedLink}
                to={itemHrefFromTypes(row.id, row.types)}
              >
                {row.icon ? (
                  <img
                    className={styles.containedIcon}
                    src={transparentThumbUrl(row.icon) || row.icon}
                    alt=""
                  />
                ) : null}
                {row.name}
                {row.count > 1 ? ` ×${row.count}` : ""}
              </Link>
            ))}
          </div>
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
    </div>
  );
}

export function useTarkovItemDetailTitle(itemId: string): string {
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-item-detail", itemId],
    queryFn: () => fetchTarkovItemDetail(itemId),
    staleTime: 5 * 60_000,
    retry: 1,
  });
  return detailQuery.data?.name || detailQuery.data?.short_name || "物品详情";
}
