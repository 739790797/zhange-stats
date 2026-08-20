import { Image } from "antd";
import { Link } from "react-router-dom";
import { formatMoney } from "@/lib/tarkovItemFormat";
import { hdPreviewUrl, transparentThumbUrl } from "@/lib/tarkovItemImages";
import { itemHrefFromTypes } from "@/lib/tarkovItemTypes";
import catalog from "./TarkovItemCatalogPanel.module.css";
import styles from "./TarkovGuideItemCell.module.css";

export type TarkovGuideItemRef = {
  id: string;
  name?: string;
  short_name?: string;
  icon_link?: string;
  types?: string[] | null;
  count?: number;
  found_in_raid?: boolean;
  flea_price?: number | null;
  badge?: string;
};

export function guideItemFleaCost(
  items: TarkovGuideItemRef[] | undefined,
): number | null {
  if (!items?.length) return 0;
  let sum = 0;
  for (const item of items) {
    const price = item.flea_price;
    if (price == null || !Number.isFinite(price) || price <= 0) return null;
    sum += price * Number(item.count || 1);
  }
  return sum;
}

export function TarkovGuideItemCell({
  item,
  showCount = true,
  showPrice = false,
}: {
  item: TarkovGuideItemRef;
  showCount?: boolean;
  showPrice?: boolean;
}) {
  const label = item.name || item.short_name || item.id;
  const thumb = transparentThumbUrl(item.icon_link);
  const hd = hdPreviewUrl(item.icon_link) || thumb;
  const count = Number(item.count || 1);
  return (
    <span className={catalog.nameCell}>
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
      <span className={styles.body}>
        <Link
          className={catalog.nameLink}
          to={itemHrefFromTypes(item.id, item.types || [])}
        >
          {showCount && count !== 1 ? `${count}× ${label}` : label}
        </Link>
        {item.found_in_raid ? (
          <span className={styles.fir}>战局内找到</span>
        ) : null}
        {showPrice ? (
          <span className={styles.price}>
            {formatMoney(item.flea_price)}
          </span>
        ) : null}
      </span>
    </span>
  );
}

export function TarkovItemRefGrid({
  items,
  showCount = false,
}: {
  items: TarkovGuideItemRef[];
  showCount?: boolean;
}) {
  if (!items.length) return null;
  return (
    <div className={styles.grid}>
      {items.map((item, index) => {
        const label = item.name || item.short_name || item.id;
        const thumb = transparentThumbUrl(item.icon_link) || item.icon_link;
        const count = Number(item.count || 1);
        const text =
          showCount && count > 1 ? `${count}× ${label}` : label;
        return (
          <Link
            key={`${item.id}-${index}`}
            className={`${styles.chip} ${item.badge ? styles.chipMarked : ""}`}
            to={itemHrefFromTypes(item.id, item.types || [])}
            title={item.badge ? `${item.badge} · ${text}` : text}
          >
            {item.badge ? (
              <span className={styles.chipBadge}>{item.badge}</span>
            ) : null}
            <span className={styles.chipIcon}>
              {thumb ? <img src={thumb} alt="" /> : null}
            </span>
            <span className={styles.chipName}>{text}</span>
          </Link>
        );
      })}
    </div>
  );
}

export function TarkovGuideItemStack({
  items,
}: {
  items: TarkovGuideItemRef[] | undefined;
}) {
  if (!items?.length) return <span>—</span>;
  return (
    <div className={styles.stack}>
      {items.map((item, index) => (
        <TarkovGuideItemCell
          key={`${item.id}-${index}`}
          item={item}
          showCount
        />
      ))}
    </div>
  );
}
