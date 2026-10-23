import { Link } from "react-router-dom";
import styles from "./TarkovItemsPageShell.module.css";

export type TarkovCrumb = {
  label: string;
  /** 有 to 则可点击跳转；最后一级通常不传 */
  to?: string;
};

type Props = {
  items: TarkovCrumb[];
};

/** 物品区路径：物品 > 弹药 > …，任一段可点回对应页 */
export function TarkovItemsBreadcrumb({ items }: Props) {
  return (
    <nav className={styles.crumbs} aria-label="面包屑">
      {items.map((item, index) => (
        <span key={`${index}-${item.label}`}>
          {index > 0 ? <span className={styles.crumbSep}>/</span> : null}
          {item.to ? (
            <Link to={item.to} className={styles.crumbLink}>
              {item.label}
            </Link>
          ) : (
            <span className={styles.crumbCurrent}>{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}
