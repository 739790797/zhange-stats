import { Alert, Spin, Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Link } from "react-router-dom";
import { Suspense, lazy, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  fetchTarkovMapDetail,
  type TarkovMapBoss,
  type TarkovMapDetail,
  type TarkovMapExtract,
} from "@/api/guidesApi";
import { useTarkovMapPlaceEditor } from "@/components/guides/tarkov/TarkovMapPlaceEditor";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { useTarkovDocumentTitle } from "@/lib/tarkovDocumentTitle";
import {
  normalizeBossKind,
  TARKOV_BOSS_KIND_LABELS,
} from "@/lib/tarkovBossKinds";
import { tarkovBossHref, tarkovMapHref, tarkovRaidPrepHref } from "@/lib/tarkovHomeNav";
import { normalizeRaidPrepMapId } from "@/lib/tarkovRaidPrep";
import { tarkovExtractStyle } from "@/lib/tarkovMapExtracts";
import { tarkovMapViewerLayerProps } from "@/lib/tarkovMapViewerDetail";
import { PanelFallback } from "@/components/RouteFallback";
import tableStyles from "./TarkovDarkTable.module.css";
import styles from "./TarkovMapsPanel.module.css";

const TarkovMapViewer = lazy(() =>
  import("@/components/guides/tarkov/TarkovMapViewer").then((m) => ({
    default: m.TarkovMapViewer,
  })),
);

type Props = {
  slug: string;
};

export function TarkovMapDetailPanel({ slug }: Props) {
  const gameMode = useTarkovGameMode();
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-map", gameMode, slug],
    queryFn: () => fetchTarkovMapDetail(slug),
    staleTime: 5 * 60_000,
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
        message="地图页加载失败"
        description={apiError(detailQuery.error, "地图页加载失败")}
      />
    );
  }

  const detail = detailQuery.data;
  if (!detail) return null;

  return (
    <TarkovMapDetailReady slug={slug} detail={detail} />
  );
}

function TarkovMapDetailReady({
  slug,
  detail,
}: {
  slug: string;
  detail: TarkovMapDetail;
}) {
  const [floor, setFloor] = useState("");
  const editor = useTarkovMapPlaceEditor({
    slug,
    parentSlug: detail.parent_slug || undefined,
    places: detail.places || [],
    floor,
  });

  const extractColumns: ColumnsType<TarkovMapExtract> = [
    {
      title: "撤离点",
      key: "name",
      render: (_: unknown, row) => {
        const marker = tarkovExtractStyle(row.faction);
        return (
          <span className={styles.extractCell}>
            <img src={marker.iconUrl} alt="" width={18} height={18} />
            <span style={{ color: marker.color }}>{row.name}</span>
          </span>
        );
      },
    },
    { title: "阵营", dataIndex: "faction", key: "faction", width: 100 },
  ];
  const bossColumns: ColumnsType<TarkovMapBoss> = [
    {
      title: "BOSS",
      key: "name",
      render: (_: unknown, row) => {
        const kind = normalizeBossKind(row.kind);
        const name = row.slug ? (
          <Link to={tarkovBossHref(row.slug)}>{row.name}</Link>
        ) : (
          row.name
        );
        if (kind === "boss") return name;
        return (
          <span className={styles.bossNameCell}>
            {name}
            <span
              className={`${styles.kindTag} ${
                kind === "elite" ? styles.kindTagElite : styles.kindTagSoldier
              }`}
            >
              {TARKOV_BOSS_KIND_LABELS[kind]}
            </span>
          </span>
        );
      },
    },
    {
      title: "出生率",
      key: "spawn",
      width: 100,
      render: (_: unknown, row) =>
        row.spawn_chance ? `${row.spawn_chance}%` : "—",
    },
  ];

  return (
    <div className={styles.stack}>
      <section className={styles.hero}>
        <div>
          <div className={styles.headRow}>
            <h1 className={styles.nameTitle}>{detail.name}</h1>
            <Link
              className={styles.wiki}
              to={tarkovRaidPrepHref(
                normalizeRaidPrepMapId(detail.slug) || detail.slug,
              )}
            >
              联机大厅
            </Link>
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
          {detail.english ? (
            <div className={styles.english}>{detail.english}</div>
          ) : null}
          {detail.description ? (
            <p className={styles.desc}>{detail.description}</p>
          ) : null}
          <div className={styles.stats}>
            <div>
              <div className={styles.statLabel}>突袭时长</div>
              <div className={styles.statValue}>
                {detail.raid_duration
                  ? `${detail.raid_duration} 分钟`
                  : "—"}
              </div>
            </div>
            <div>
              <div className={styles.statLabel}>人数</div>
              <div className={styles.statValue}>{detail.players || "—"}</div>
            </div>
            <div>
              <div className={styles.statLabel}>等级</div>
              <div className={styles.statValue}>
                {detail.min_player_level || detail.max_player_level
                  ? `${detail.min_player_level || 1}${
                      detail.max_player_level
                        ? `–${detail.max_player_level}`
                        : "+"
                    }`
                  : "—"}
              </div>
            </div>
          </div>
          {detail.interactive_url ? (
            <a
              className={styles.interactive}
              href={detail.interactive_url}
              target="_blank"
              rel="noreferrer"
            >
              在 tarkov.dev 打开
            </a>
          ) : null}
        </div>
      </section>

      {editor.bar}
      <Suspense fallback={<PanelFallback tip="加载地图…" />}>
        <TarkovMapViewer
          slug={slug}
          {...tarkovMapViewerLayerProps(detail)}
          placeEdit={editor.placeEdit}
          onFloorChange={setFloor}
        />
      </Suspense>
      {editor.modal}

      {detail.variants?.length ? (
        <div>
          <div className={styles.section}>地图变体</div>
          <div className={styles.variants}>
            <Link
              className={`${styles.variant} ${
                !detail.parent_slug ? styles.variantOn : ""
              }`}
              to={tarkovMapHref(detail.parent_slug || detail.slug)}
            >
              常规
            </Link>
            {detail.variants.map((row) => (
              <Link
                key={row.slug}
                className={`${styles.variant} ${
                  row.slug === detail.slug ? styles.variantOn : ""
                }`}
                to={tarkovMapHref(row.slug)}
              >
                {row.name || row.slug}
                {row.raid_duration ? ` · ${row.raid_duration} 分` : ""}
              </Link>
            ))}
          </div>
        </div>
      ) : null}

      {detail.extracts?.length ? (
        <div className={tableStyles.table}>
          <div className={styles.section}>撤离点</div>
          <Table
            rowKey={(row) => row.id || row.name}
            columns={extractColumns}
            dataSource={detail.extracts}
            pagination={false}
            size="small"
          />
        </div>
      ) : null}

      {detail.bosses?.length ? (
        <div className={tableStyles.table}>
          <div className={styles.section}>BOSS</div>
          <Table
            rowKey={(row) => row.id || row.slug}
            columns={bossColumns}
            dataSource={detail.bosses}
            pagination={false}
            size="small"
          />
        </div>
      ) : null}
    </div>
  );
}
