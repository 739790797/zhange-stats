import type { ReactNode } from "react";
import styles from "./TarkovTaskDetailPanel.module.css";

type Props = {
  id?: string;
  title: string;
  icon?: ReactNode;
  empty?: boolean;
  count?: number;
  children?: ReactNode;
  className?: string;
};

export function TarkovTaskDetailSection({
  id,
  title,
  icon,
  empty = false,
  count,
  children,
  className,
}: Props) {
  return (
    <section
      id={id}
      className={[styles.section, className].filter(Boolean).join(" ")}
    >
      <h2 className={styles.sectionHead}>
        {icon}
        {title}
        {count != null ? (
          <span className={styles.sectionCount}>{count}</span>
        ) : null}
        <span className={styles.sectionRule} aria-hidden />
      </h2>
      {empty ? <div className={styles.muted}>无</div> : children}
    </section>
  );
}
