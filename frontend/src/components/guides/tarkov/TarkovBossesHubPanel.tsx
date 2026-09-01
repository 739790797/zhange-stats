import { useMemo } from "react";
import { Alert, Spin } from "antd";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovBosses } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import {
  selectTopLevelNamedBosses,
  TARKOV_BOSS_HUB_SECTION_LABELS,
  TARKOV_BOSS_HUB_SECTIONS,
} from "@/lib/tarkovBossKinds";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { selectIndependentOtherBosses } from "@/lib/tarkovBossHubRows";
import { buildBossPortraitIndex } from "@/lib/tarkovBossHeatmap";
import catalogStyles from "./TarkovItemCatalogPanel.module.css";
import styles from "./TarkovBossPanel.module.css";
import { TarkovBossHeatmap } from "./TarkovBossHeatmap";

export function TarkovBossesHubPanel() {
  const gameMode = useTarkovGameMode();
  const catalogQuery = useQuery({
    queryKey: ["guides-tarkov-bosses", gameMode],
    queryFn: fetchTarkovBosses,
    staleTime: 5 * 60_000,
    retry: 1,
  });
  const items = catalogQuery.data?.items;
  const named = useMemo(
    () => selectTopLevelNamedBosses(items ?? []),
    [items],
  );
  const others = useMemo(
    () => selectIndependentOtherBosses(items ?? []),
    [items],
  );
  const portraits = useMemo(() => buildBossPortraitIndex(items ?? []), [items]);

  if (catalogQuery.isLoading) {
    return (
      <div className={styles.status}>
        <Spin />
      </div>
    );
  }

  if (catalogQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="BOSS 列表加载失败"
        description={apiError(catalogQuery.error, "BOSS 列表加载失败")}
      />
    );
  }

  const sections = TARKOV_BOSS_HUB_SECTIONS.filter((key) =>
    key === "boss" ? named.length : others.length,
  );

  return (
    <div className={catalogStyles.stack}>
      {sections.length ? (
        sections.map((key) => {
          const list = key === "boss" ? named : others;
          return (
            <section key={key} className={catalogStyles.panel}>
              <div className={styles.listSection}>
                <h2 className={styles.listSectionHead}>
                  {TARKOV_BOSS_HUB_SECTION_LABELS[key]}
                  <span className={styles.listSectionCount}>{list.length}</span>
                </h2>
                <TarkovBossHeatmap
                  key={`${gameMode}-${key}`}
                  bosses={list}
                  portraits={portraits}
                />
              </div>
            </section>
          );
        })
      ) : (
        <div className={catalogStyles.panel}>暂无 BOSS 数据</div>
      )}
    </div>
  );
}
