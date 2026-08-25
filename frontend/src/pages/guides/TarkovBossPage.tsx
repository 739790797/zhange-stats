import { Navigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovBossDetail } from "@/api/guidesApi";
import { TarkovItemsBreadcrumb } from "@/components/guides/tarkov/TarkovItemsBreadcrumb";
import { TarkovBossPanel } from "@/components/guides/tarkov/TarkovBossPanel";
import {
  TARKOV_BOSSES,
  TARKOV_BOSSES_PATH,
  TARKOV_HOME_PATH,
  tarkovBossHref,
} from "@/lib/tarkovHomeNav";
import styles from "@/components/guides/tarkov/TarkovItemsPageShell.module.css";

export default function TarkovBossPage() {
  const { bossSlug = "" } = useParams<{ bossSlug: string }>();
  const known = TARKOV_BOSSES.find(
    (item) =>
      item.id === bossSlug ||
      tarkovBossHref(item.id).endsWith(`/${encodeURIComponent(bossSlug)}`),
  );
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-boss", bossSlug],
    queryFn: () => fetchTarkovBossDetail(bossSlug),
    staleTime: 60_000,
    retry: 1,
    enabled: Boolean(bossSlug),
  });
  const crumbLabel = detailQuery.data?.name || known?.label || bossSlug;

  if (!bossSlug) {
    return <Navigate to={TARKOV_HOME_PATH} replace />;
  }

  return (
    <div className={styles.inner}>
      <TarkovItemsBreadcrumb
        items={[
          { label: "逃离塔科夫", to: TARKOV_HOME_PATH },
          { label: "BOSS", to: TARKOV_BOSSES_PATH },
          { label: crumbLabel },
        ]}
      />
      <TarkovBossPanel slug={bossSlug} />
    </div>
  );
}
