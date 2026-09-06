import {
  EnvironmentOutlined,
  EyeOutlined,
  HeartOutlined,
  LineChartOutlined,
} from "@ant-design/icons";
import { Alert, Spin } from "antd";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovBossDetail } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { useTarkovDocumentTitle } from "@/lib/tarkovDocumentTitle";
import { normalizeBossKind, TARKOV_BOSS_KIND_LABELS } from "@/lib/tarkovBossKinds";
import { resolveBossSpawnGroups, spawnGroupComboNumbers } from "@/lib/tarkovBossSpawnGroups";
import styles from "./TarkovBossPanel.module.css";
import {
  TarkovBossEscortChips,
  TarkovBossLocationChips,
  TarkovBossMapChips,
} from "./TarkovBossSpawnChips";
import { TarkovBossEquipment } from "./TarkovBossEquipment";
import { TarkovBossSpawnMap } from "./TarkovBossSpawnMap";

type Props = {
  slug: string;
};

export function TarkovBossPanel({ slug }: Props) {
  const gameMode = useTarkovGameMode();
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-boss", gameMode, slug],
    queryFn: () => fetchTarkovBossDetail(slug),
    staleTime: 60_000,
    retry: 1,
    enabled: Boolean(slug),
  });
  useTarkovDocumentTitle(detailQuery.data?.name || "");

  if (detailQuery.isLoading) {
    return (
      <div className={styles.status}>
        <Spin />
      </div>
    );
  }

  if (detailQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="BOSS 页加载失败"
        description={apiError(detailQuery.error, "BOSS 页加载失败")}
      />
    );
  }

  const detail = detailQuery.data;
  if (!detail) return null;

  const spawnGroups = resolveBossSpawnGroups(detail);
  const comboNumbers = spawnGroupComboNumbers(spawnGroups);

  return (
    <div className={styles.stack}>
      <section className={styles.hero}>
        <div className={styles.heroTop}>
          <div>
            <div className={styles.headRow}>
              <span className={styles.badge}>
                {TARKOV_BOSS_KIND_LABELS[normalizeBossKind(detail.kind)]}
              </span>
              <h2 className={styles.name}>{detail.name}</h2>
              {detail.wiki_link ? (
                <a
                  className={styles.wiki}
                  href={detail.wiki_link}
                  target="_blank"
                  rel="noreferrer"
                >
                  Wiki
                </a>
              ) : null}
            </div>
          {detail.bio ? <p className={styles.bio}>{detail.bio}</p> : null}
          {detail.description ? (
            <>
              <span className={styles.sectionLabel}>行为</span>
              <p className={styles.desc}>{detail.description}</p>
            </>
          ) : null}
          <div className={styles.stats}>
            <div>
              <div className={styles.statLabel}>
                <EyeOutlined className={styles.statIcon} />
                行为
              </div>
              <div className={styles.statValue}>{detail.behavior_zh || "—"}</div>
            </div>
            <div>
              <div className={styles.statLabel}>
                <EnvironmentOutlined className={styles.statIcon} />
                地图
              </div>
              <div className={styles.statValue}>{detail.maps_label || "—"}</div>
            </div>
            <div>
              <div className={styles.statLabel}>
                <LineChartOutlined className={styles.statIcon} />
                刷新概率
              </div>
              <div className={styles.statValue}>{detail.spawn_label || "—"}</div>
            </div>
            <div>
              <div className={styles.statLabel}>
                <HeartOutlined className={styles.statIcon} />
                生命值
              </div>
              <div className={styles.statValue}>
                <div className={styles.healthTotal}>
                  {detail.health_total || "—"}
                </div>
                {detail.health?.length ? (
                  <div className={styles.healthParts}>
                    {detail.health
                      .map((part) => `${part.name} ${part.max}`)
                      .join(" · ")}
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </div>
        <div className={styles.posterWrap}>
          {detail.poster_link || detail.portrait_link ? (
            <img
              className={styles.poster}
              src={detail.poster_link || detail.portrait_link}
              alt=""
            />
          ) : null}
        </div>
        </div>
        <TarkovBossSpawnMap detail={detail} />
      </section>

      <TarkovBossEquipment slots={detail.equipment_slots ?? []} />

      {spawnGroups.length ? (
        <section className={styles.section}>
          <div className={styles.lootHead}>刷新</div>
          <div className={styles.spawnGroups}>
            {spawnGroups.map((group, index) => (
              <article
                key={group.maps.map((row) => row.slug || row.name).join("|") + index}
                className={styles.spawnGroup}
              >
                {comboNumbers[index] ? (
                  <div className={styles.spawnCombo}>组合{comboNumbers[index]}</div>
                ) : null}
                <div className={styles.spawnMaps}>
                  <TarkovBossMapChips group={group} />
                </div>
                {group.landLabel ? (
                  <div className={styles.spawnRow}>
                    <div className={styles.spawnRowLabel}>落地</div>
                    <div className={styles.landValue}>{group.landLabel}</div>
                  </div>
                ) : null}
                {group.locations.length ? (
                  <div className={styles.spawnRow}>
                    <div className={styles.spawnRowLabel}>区域</div>
                    <TarkovBossLocationChips group={group} />
                  </div>
                ) : null}
                {group.escorts.length ? (
                  <div className={styles.spawnRow}>
                    <div className={styles.spawnRowLabel}>随从</div>
                    <TarkovBossEscortChips group={group} />
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
