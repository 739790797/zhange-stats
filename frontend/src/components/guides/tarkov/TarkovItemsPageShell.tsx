import type { ReactNode } from "react";
import {
  TarkovItemsBreadcrumb,
  type TarkovCrumb,
} from "@/components/guides/tarkov/TarkovItemsBreadcrumb";
import styles from "./TarkovItemsPageShell.module.css";

type Props = {
  /** 当前页标题（面包屑之后） */
  title: string;
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
}: Props) {
  const breadcrumbItems: TarkovCrumb[] = [
    { label: "逃离塔科夫", to: "/guides/tarkov" },
    { label: sectionLabel, to: sectionHref },
    ...crumbs,
  ];

  return (
    <div className={styles.inner}>
      {hideHead ? null : (
        <>
          <TarkovItemsBreadcrumb items={breadcrumbItems} />
          <div className={styles.headerRow}>
            <div>
              <h1 className={styles.title}>{title}</h1>
              {subtitle ? <p className={styles.subtitle}>{subtitle}</p> : null}
            </div>
            {extra}
          </div>
        </>
      )}
      {children}
    </div>
  );
}
