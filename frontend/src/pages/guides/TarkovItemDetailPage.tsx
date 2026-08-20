import { ConfigProvider } from "antd";
import { Navigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovItemDetail } from "@/api/guidesApi";
import { TarkovItemDetailPanel } from "@/components/guides/tarkov/TarkovItemDetailPanel";
import { TarkovItemsBreadcrumb } from "@/components/guides/tarkov/TarkovItemsBreadcrumb";
import { TARKOV_ANTD_DARK } from "@/lib/tarkovAntdDark";
import { TARKOV_HOME_PATH } from "@/lib/tarkovHomeNav";
import {
  ITEMS_BASE_PATH,
  handbookHref,
  handbookRootBySlug,
  itemPageBySlug,
  itemTypeHref,
} from "@/lib/tarkovItemTypes";
import styles from "@/components/guides/tarkov/TarkovItemsPageShell.module.css";

export default function TarkovItemDetailPage() {
  const { typeSegment = "", itemId = "" } = useParams<{
    typeSegment: string;
    itemId: string;
  }>();
  const page = itemPageBySlug(typeSegment);
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-item-detail", itemId],
    queryFn: () => fetchTarkovItemDetail(itemId),
    staleTime: 5 * 60_000,
    retry: 1,
    enabled: Boolean(itemId) && Boolean(page),
  });

  if (!page) {
    return <Navigate to={TARKOV_HOME_PATH} replace />;
  }

  const parent = page.parentSlug
    ? handbookRootBySlug(page.parentSlug)
    : undefined;
  const crumbs = [
    { label: "逃离塔科夫", to: TARKOV_HOME_PATH },
    { label: "物品", to: ITEMS_BASE_PATH },
    ...(parent ? [{ label: parent.label, to: handbookHref(parent) }] : []),
    { label: page.label, to: itemTypeHref(page.slug) },
    { label: detailQuery.data?.name || "…" },
  ];

  return (
    <div className={styles.inner}>
      <div className={styles.detailBody}>
        <TarkovItemsBreadcrumb items={crumbs} />
        <ConfigProvider theme={TARKOV_ANTD_DARK}>
          {itemId ? <TarkovItemDetailPanel itemId={itemId} /> : null}
        </ConfigProvider>
      </div>
    </div>
  );
}
