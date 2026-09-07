import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  tarkovTraderHref,
  traderDisplayName,
  traderPortraitUrl,
} from "@/lib/tarkovHomeNav";
import {
  formatMoney,
  formatOfferPrice,
  isFleaVendor,
  type VendorOffer,
} from "@/lib/tarkovItemFormat";
import { hasFleaQuote, type ItemFleaQuote } from "@/lib/tarkovItemSources";
import styles from "./TarkovItemSources.module.css";

export function TarkovItemBlock({
  title,
  count,
  extra,
  children,
}: {
  title: string;
  count?: number;
  extra?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className={styles.block}>
      <div className={styles.blockHead}>
        <h3 className={styles.blockTitle}>
          {title}
          {count != null ? (
            <span className={styles.blockCount}>{count}</span>
          ) : null}
        </h3>
        {extra ? <div className={styles.blockExtra}>{extra}</div> : null}
      </div>
      {children}
    </div>
  );
}

function vendorHref(offer: VendorOffer): string | null {
  const key = offer.vendor;
  if (!key || isFleaVendor(key)) return null;
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
  const icon = isFleaVendor(offer.vendor) ? "" : traderPortraitUrl(offer.vendor);
  const label = traderDisplayName(offer.vendor, offer.vendorName);
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
      <span className={styles.offerName}>{label}</span>
      <span className={styles.offerPrice}>{formatOfferPrice(offer)}</span>
    </>
  );
  const className = `${styles.offer} ${best ? styles.offerBest : ""}`;
  if (href) {
    return (
      <Link className={className} to={href} title={label}>
        {inner}
      </Link>
    );
  }
  return (
    <span className={className} title={label}>
      {inner}
    </span>
  );
}

export function TarkovItemOfferRow({
  offers,
  best,
}: {
  offers: VendorOffer[];
  best?: VendorOffer | null;
}) {
  if (!offers.length) return null;
  return (
    <div className={styles.offerPad}>
      <div className={styles.offerRow}>
        {offers.map((offer, index) => (
          <OfferCard
            key={`${offer.vendor}-${index}`}
            offer={offer}
            best={
              best != null &&
              offer.vendor === best.vendor &&
              offer.priceRub === best.priceRub
            }
          />
        ))}
      </div>
    </div>
  );
}

export function TarkovItemFleaQuote({
  flea,
}: {
  flea: ItemFleaQuote | null | undefined;
}) {
  if (!hasFleaQuote(flea) || !flea) return null;
  const change = flea.change48;
  const changeClass =
    change != null && change > 0
      ? styles.fleaUp
      : change != null && change < 0
        ? styles.fleaDown
        : "";
  return (
    <div className={styles.fleaQuote}>
      {flea.lastLow != null && Number.isFinite(flea.lastLow) && flea.lastLow > 0 ? (
        <div className={styles.fleaStat}>
          <span className={styles.fleaLabel}>最近低价</span>
          <span className={styles.fleaValue}>{formatMoney(flea.lastLow)}</span>
        </div>
      ) : null}
      {flea.avg24 != null && Number.isFinite(flea.avg24) && flea.avg24 > 0 ? (
        <div className={styles.fleaStat}>
          <span className={styles.fleaLabel}>24h 均价</span>
          <span className={styles.fleaValue}>{formatMoney(flea.avg24)}</span>
        </div>
      ) : null}
      {change != null && Number.isFinite(change) ? (
        <div className={styles.fleaStat}>
          <span className={styles.fleaLabel}>较昨日</span>
          <span className={`${styles.fleaValue} ${changeClass}`}>
            {change > 0 ? "+" : ""}
            {Math.round(change).toLocaleString("zh-CN")} ₽
            {flea.change48p != null && Number.isFinite(flea.change48p)
              ? ` · ${flea.change48p}%`
              : ""}
          </span>
        </div>
      ) : null}
    </div>
  );
}
