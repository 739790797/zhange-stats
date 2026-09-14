import { memo } from "react";
import { traderIconUrl, traderPortraitUrl } from "@/lib/tarkovHomeNav";
import styles from "./TarkovTraderThumb.module.css";

type Props = {
  slug: string;
  size?: number;
  title?: string;
  variant?: "icon" | "portrait";
};

export const TarkovTraderThumb = memo(function TarkovTraderThumb({
  slug,
  size = 40,
  title,
  variant = "icon",
}: Props) {
  const primary =
    variant === "portrait" ? traderPortraitUrl(slug) : traderIconUrl(slug);
  const fallbackSrc =
    variant === "portrait" ? traderIconUrl(slug) : traderPortraitUrl(slug);
  return (
    <span className={styles.wrap} style={{ width: size, height: size }} title={title}>
      <img
        key={`${slug}-${variant}`}
        className={styles.thumb}
        src={primary}
        alt=""
        width={size}
        height={size}
        decoding="async"
        onError={(event) => {
          const img = event.currentTarget;
          if (img.dataset.step !== "fallback" && fallbackSrc && img.src !== fallbackSrc) {
            img.dataset.step = "fallback";
            img.src = fallbackSrc;
            return;
          }
          img.hidden = true;
          const fallback = img.nextElementSibling;
          if (fallback instanceof HTMLElement) fallback.hidden = false;
        }}
      />
      <span className={styles.fallback} hidden />
    </span>
  );
});
