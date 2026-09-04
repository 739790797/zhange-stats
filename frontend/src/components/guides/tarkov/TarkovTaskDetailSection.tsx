import type { ReactNode } from "react";
import styles from "./TarkovTaskDetailPanel.module.css";

type Props = {
  title: string;
  icon?: ReactNode;
  empty?: boolean;
  children?: ReactNode;
  className?: string;
};

export function TarkovTaskDetailSection({
  title,
  icon,
  empty = false,
  children,
  className,
}: Props) {
  return (
    <section
      className={[styles.railCard, className].filter(Boolean).join(" ")}
    >
      <h2 className={styles.sectionHead}>
        {icon}
        {title}
      </h2>
      {empty ? <div className={styles.muted}>无</div> : children}
    </section>
  );
}
