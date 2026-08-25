import { useState } from "react";
import { traderIconUrl, traderPortraitUrl } from "@/lib/tarkovHomeNav";
import styles from "./TarkovTraderThumb.module.css";

type Props = {
  slug: string;
  size?: number;
  title?: string;
};

export function TarkovTraderThumb({ slug, size = 40, title }: Props) {
  const [kind, setKind] = useState<"icon" | "portrait" | "none">("icon");
  if (kind === "none") {
    return (
      <span
        className={styles.fallback}
        style={{ width: size, height: size }}
        title={title}
      />
    );
  }
  return (
    <img
      className={styles.thumb}
      src={kind === "icon" ? traderIconUrl(slug) : traderPortraitUrl(slug)}
      alt=""
      width={size}
      height={size}
      title={title}
      style={{ width: size, height: size }}
      onError={() => setKind((prev) => (prev === "icon" ? "portrait" : "none"))}
    />
  );
}
