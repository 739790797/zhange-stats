import { Navigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovItemDetail } from "@/features/guides/tarkov/api/guidesApi";
import { TarkovItemDetailPanel } from "@/features/guides/tarkov/components/TarkovItemDetailPanel";
import { TarkovItemsBreadcrumb } from "@/features/guides/tarkov/components/TarkovItemsBreadcrumb";
import { TARKOV_HOME_PATH } from "@/features/guides/tarkov/model/tarkovHomeNav";
import { useTarkovGameMode } from "@/features/guides/tarkov/model/tarkovGameMode";
import { collapsedPresetHref } from "@/features/guides/tarkov/model/tarkovItemPlates";
import {
  ITEMS_BASE_PATH,
  handbookHref,
  handbookRootBySlug,
  itemListingHref,
  itemPageBySlug,
} from "@/features/guides/tarkov/model/tarkovItemTypes";
import styles from "@/features/guides/tarkov/components/TarkovItemsPageShell.module.css";

export default function TarkovItemDetailPage() {
  const gameMode = useTarkovGameMode();
  const { typeSegment = "", itemId = "" } = useParams<{
    typeSegment: string;
    itemId: string;
  }>();
  const page = itemPageBySlug(typeSegment);
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-item-detail", gameMode, itemId],
    queryFn: () => fetchTarkovItemDetail(itemId),
    staleTime: 5 * 60_000,
    retry: 1,
    enabled: Boolean(itemId) && Boolean(page),
  });

  if (!page) {
    return <Navigate to={TARKOV_HOME_PATH} replace />;
  }

  const collapseTo = collapsedPresetHref(detailQuery.data);
  if (collapseTo) {
    return <Navigate to={collapseTo} replace />;
  }

  const parent = page.parentSlug
    ? handbookRootBySlug(page.parentSlug)
    : undefined;
  const crumbs = [
    { label: "逃离塔科夫", to: TARKOV_HOME_PATH },
    { label: "物品", to: ITEMS_BASE_PATH },
    ...(parent ? [{ label: parent.label, to: handbookHref(parent) }] : []),
    { label: page.label, to: itemListingHref(page.slug) },
    { label: detailQuery.data?.name || "…" },
  ];

  return (
    <div className={styles.inner}>
      <div className={styles.detailBody}>
        <TarkovItemsBreadcrumb items={crumbs} />
        {itemId ? <TarkovItemDetailPanel itemId={itemId} /> : null}
      </div>
    </div>
  );
}
