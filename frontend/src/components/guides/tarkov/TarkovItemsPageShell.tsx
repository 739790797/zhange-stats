import type { ReactNode } from "react";
import { PageHeader } from "@/components/PageHeader";
import {
  TarkovItemsBreadcrumb,
  type TarkovCrumb,
} from "@/components/guides/tarkov/TarkovItemsBreadcrumb";
import { ITEMS_BASE_PATH } from "@/lib/tarkovItemTypes";

type Props = {
  /** 当前页标题（面包屑之后） */
  title: string;
  /** 不含「物品」根；会自动前置 */
  crumbs: TarkovCrumb[];
  children: ReactNode;
  extra?: ReactNode;
  /** 标题下副文案 */
  subtitle?: ReactNode;
};

export function TarkovItemsPageShell({
  title,
  crumbs,
  children,
  extra,
  subtitle,
}: Props) {
  const breadcrumbItems: TarkovCrumb[] = [
    { label: "物品", to: crumbs.length ? ITEMS_BASE_PATH : undefined },
    ...crumbs,
  ];

  return (
    <div>
      <TarkovItemsBreadcrumb items={breadcrumbItems} />
      <PageHeader title={title} subtitle={subtitle} extra={extra} />
      {children}
    </div>
  );
}
