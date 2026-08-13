import { Link } from "react-router-dom";
import { TARKOV_TOOLS } from "@/lib/tarkovHomeNav";
import styles from "./TarkovHomeView.module.css";

export function TarkovHomeToolRail() {
  return (
    <aside className={styles.tools} aria-label="工具">
      <div className={styles.toolsCard}>
        <div className={styles.toolsHead}>
          <span className={styles.toolsHeadIcon} aria-hidden>
            ⚒
          </span>
          <span>工具</span>
        </div>
        <nav className={styles.toolList}>
          {TARKOV_TOOLS.map((item) => {
            const ready = item.status === "ready";
            return (
              <Link
                key={item.id}
                to={item.href}
                className={`${styles.toolItem} ${ready ? styles.toolReady : ""}`}
              >
                <span className={styles.toolIcon} aria-hidden>
                  {item.icon}
                </span>
                <span className={styles.toolLabel}>{item.label}</span>
                <span className={styles.toolChevron} aria-hidden>
                  ›
                </span>
              </Link>
            );
          })}
        </nav>
      </div>
    </aside>
  );
}
