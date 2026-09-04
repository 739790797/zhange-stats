import type { ReactNode } from "react";
import {
  TarkovItemsBreadcrumb,
  type TarkovCrumb,
} from "@/components/guides/tarkov/TarkovItemsBreadcrumb";
import styles from "./TarkovItemsPageShell.module.css";

type Props = {
  /** 当前页标题（面包屑之后）；不传则只留面包屑 */
  title?: string;
  /** 不含分区根（物品/任务）；会自动前置 */
  crumbs: TarkovCrumb[];
  children: ReactNode;
  extra?: ReactNode;
  /** 标题下副文案 */
  subtitle?: ReactNode;
  /** 右侧等宽代码条，如 DATABASE_SEC_AMMO */
  code?: string;
  /** 面包屑分区名，默认「物品」 */
  sectionLabel?: string;
  /** 分区可点回列表时传入 */
  sectionHref?: string;
  /** 不渲染面包屑和大标题（任务列表等自带工具栏时用） */
  hideHead?: boolean;
  /** 吃满攻略壳剩余高度，给地图工作区用 */
  fill?: boolean;
};

export function TarkovItemsPageShell({
  title,
  crumbs,
  children,
  extra,
  subtitle,
  sectionLabel = "物品",
  sectionHref,
  hideHead = false,
  fill = false,
}: Props) {
  const breadcrumbItems: TarkovCrumb[] = [
    { label: "逃离塔科夫", to: "/guides/tarkov" },
    { label: sectionLabel, to: sectionHref },
    ...crumbs,
  ];
  const showHeader = Boolean(title || subtitle || extra);

  return (
    <div className={`${styles.inner}${fill ? ` ${styles.innerFill}` : ""}`}>
      {hideHead ? null : (
        <>
          <TarkovItemsBreadcrumb items={breadcrumbItems} />
          {showHeader ? (
            <div className={styles.headerRow}>
              <div>
                {title ? <h1 className={styles.title}>{title}</h1> : null}
                {subtitle ? <p className={styles.subtitle}>{subtitle}</p> : null}
              </div>
              {extra}
            </div>
          ) : null}
        </>
      )}
      {children}
    </div>
  );
}
