import { Navigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovMapDetail } from "@/features/guides/tarkov/api/guidesApi";
import { TarkovItemsBreadcrumb } from "@/features/guides/tarkov/components/TarkovItemsBreadcrumb";
import { TarkovMapDetailPanel } from "@/features/guides/tarkov/components/TarkovMapDetailPanel";
import {
  MAPS_HREF,
  TARKOV_HOME_PATH,
  TARKOV_MAPS,
  parseTarkovMaintainMode,
  tarkovMapHref,
  tarkovMapsMaintainHref,
} from "@/features/guides/tarkov/model/tarkovHomeNav";
import { useTarkovGameMode } from "@/features/guides/tarkov/model/tarkovGameMode";
import styles from "@/features/guides/tarkov/components/TarkovItemsPageShell.module.css";

export default function TarkovMapDetailPage() {
  const { mapSlug = "" } = useParams<{ mapSlug: string }>();
  const [searchParams] = useSearchParams();
  const maintain = parseTarkovMaintainMode(searchParams.get("maintain"));
  const gameMode = useTarkovGameMode();
  const known = TARKOV_MAPS.find(
    (item) =>
      item.id === mapSlug ||
      tarkovMapHref(item.id).endsWith(`/${encodeURIComponent(mapSlug)}`),
  );
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-map", gameMode, mapSlug],
    queryFn: () => fetchTarkovMapDetail(mapSlug),
    staleTime: 5 * 60_000,
    retry: 1,
    enabled: Boolean(mapSlug),
  });
  const crumbLabel = detailQuery.data?.name || known?.label || mapSlug;

  if (!mapSlug) {
    return <Navigate to={TARKOV_HOME_PATH} replace />;
  }

  return (
    <div className={`${styles.inner} ${styles.innerFill}`}>
      <TarkovItemsBreadcrumb
        items={[
          { label: "逃离塔科夫", to: TARKOV_HOME_PATH },
          {
            label: maintain ? "地图信息" : "地图",
            to: maintain ? tarkovMapsMaintainHref() : MAPS_HREF,
          },
          { label: crumbLabel },
        ]}
      />
      <TarkovMapDetailPanel slug={mapSlug} />
    </div>
  );
}
