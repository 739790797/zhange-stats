import { Navigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovBossDetail, fetchTarkovBosses } from "@/api/guidesApi";
import { TarkovItemsBreadcrumb } from "@/components/guides/tarkov/TarkovItemsBreadcrumb";
import { TarkovBossPanel } from "@/components/guides/tarkov/TarkovBossPanel";
import {
  bossHubSectionForRow,
  namedBossParentId,
  TARKOV_BOSS_HUB_SECTION_LABELS,
} from "@/lib/tarkovBossKinds";
import {
  TARKOV_BOSSES,
  TARKOV_BOSSES_PATH,
  TARKOV_HOME_PATH,
  tarkovBossHref,
} from "@/lib/tarkovHomeNav";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import styles from "@/components/guides/tarkov/TarkovItemsPageShell.module.css";

export default function TarkovBossPage() {
  const { bossSlug = "" } = useParams<{ bossSlug: string }>();
  const gameMode = useTarkovGameMode();
  const known = TARKOV_BOSSES.find(
    (item) =>
      item.id === bossSlug ||
      tarkovBossHref(item.id).endsWith(`/${encodeURIComponent(bossSlug)}`),
  );
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-boss", gameMode, bossSlug],
    queryFn: () => fetchTarkovBossDetail(bossSlug),
    staleTime: 60_000,
    retry: 1,
    enabled: Boolean(bossSlug),
  });
  const crumbLabel = detailQuery.data?.name || known?.label || bossSlug;
  const hubSection = bossHubSectionForRow(
    detailQuery.data?.id,
    detailQuery.data?.parent_ids,
  );
  const parentId = namedBossParentId(detailQuery.data?.parent_ids);
  const catalogQuery = useQuery({
    queryKey: ["guides-tarkov-bosses", gameMode],
    queryFn: fetchTarkovBosses,
    staleTime: 5 * 60_000,
    enabled: Boolean(parentId),
  });
  const parent = catalogQuery.data?.items.find((item) => item.id === parentId);

  if (!bossSlug) {
    return <Navigate to={TARKOV_HOME_PATH} replace />;
  }

  return (
    <div className={styles.inner}>
      <TarkovItemsBreadcrumb
        items={[
          { label: "逃离塔科夫", to: TARKOV_HOME_PATH },
          { label: TARKOV_BOSS_HUB_SECTION_LABELS[hubSection], to: TARKOV_BOSSES_PATH },
          ...(parent?.slug
            ? [{ label: parent.name || parent.slug, to: tarkovBossHref(parent.slug) }]
            : []),
          { label: crumbLabel },
        ]}
      />
      <TarkovBossPanel slug={bossSlug} />
    </div>
  );
}
