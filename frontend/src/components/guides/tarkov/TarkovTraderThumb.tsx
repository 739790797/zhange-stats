import { memo } from "react";
import { traderIconUrl, traderPortraitUrl } from "@/lib/tarkovHomeNav";
import styles from "./TarkovTraderThumb.module.css";

type Props = {
  slug: string;
  size?: number;
  title?: string;
};

export const TarkovTraderThumb = memo(function TarkovTraderThumb({
  slug,
  size = 40,
  title,
}: Props) {
  return (
    <span className={styles.wrap} style={{ width: size, height: size }} title={title}>
      <img
        key={slug}
        className={styles.thumb}
        src={traderIconUrl(slug)}
        alt=""
        width={size}
        height={size}
        decoding="async"
        onError={(event) => {
          const img = event.currentTarget;
          if (img.dataset.step !== "portrait") {
            img.dataset.step = "portrait";
            img.src = traderPortraitUrl(slug);
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
