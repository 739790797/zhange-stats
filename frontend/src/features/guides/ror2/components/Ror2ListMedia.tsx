import type { ReactNode } from "react";
import { ror2DlcMark } from "@/features/guides/ror2/model/ror2Home";
import { Ror2ExpansionIcon } from "./Ror2ExpansionIcon";
import styles from "./Ror2ListMedia.module.css";

type MediaProps = {
  expansion?: string;
  imageAvailable?: boolean;
  className?: string;
  children: ReactNode;
};

/** DLC overlay frame used by catalog list rows only; detail headers stay unchanged. */
export function Ror2ListMedia({ expansion, imageAvailable = true, className, children }: MediaProps) {
  const dlc = imageAvailable ? ror2DlcMark(expansion) : null;
  return (
    <span className={[styles.media, className].filter(Boolean).join(" ")}>
      {children}
      {dlc ? (
        <span className={styles.dlcBadge}>
          <Ror2ExpansionIcon src={dlc.iconUrl} label={dlc.label} />
        </span>
      ) : null}
    </span>
  );
}

type SourceMarkProps = { expansion?: string };

/** Inline source fallback for rows that have no usable primary image. */
export function Ror2ListDlcMark({ expansion }: SourceMarkProps) {
  const dlc = ror2DlcMark(expansion);
  if (!dlc) return null;
  return (
    <span className={styles.inlineMark}>
      <Ror2ExpansionIcon src={dlc.iconUrl} label={dlc.label} />
    </span>
  );
}
