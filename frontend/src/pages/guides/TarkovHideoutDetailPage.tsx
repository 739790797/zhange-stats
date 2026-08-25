import { Navigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovHideoutStation } from "@/api/guidesApi";
import { TarkovItemsBreadcrumb } from "@/components/guides/tarkov/TarkovItemsBreadcrumb";
import { TarkovHideoutPanel } from "@/components/guides/tarkov/TarkovHideoutPanel";
import {
  TARKOV_HIDEOUT_PATH,
  TARKOV_HOME_PATH,
} from "@/lib/tarkovHomeNav";
import styles from "@/components/guides/tarkov/TarkovItemsPageShell.module.css";

export default function TarkovHideoutDetailPage() {
  const { stationSlug = "" } = useParams<{ stationSlug: string }>();
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-hideout-station", stationSlug],
    queryFn: () => fetchTarkovHideoutStation(stationSlug),
    staleTime: 5 * 60_000,
    retry: 1,
    enabled: Boolean(stationSlug),
  });
  const title = detailQuery.data?.name || stationSlug;

  if (!stationSlug) {
    return <Navigate to={TARKOV_HIDEOUT_PATH} replace />;
  }

  return (
    <div className={styles.inner}>
      <TarkovItemsBreadcrumb
        items={[
          { label: "逃离塔科夫", to: TARKOV_HOME_PATH },
          { label: "藏身处", to: TARKOV_HIDEOUT_PATH },
          { label: title },
        ]}
      />
      <TarkovHideoutPanel stationSlug={stationSlug} />
    </div>
  );
}
