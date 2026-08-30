import { EnvironmentOutlined, ShopOutlined, UserOutlined } from "@ant-design/icons";
import { Alert, Image, Spin } from "antd";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovTaskDetail } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  TARKOV_TRADERS,
  tarkovTraderHref,
  traderIconUrl,
  traderPortraitUrl,
} from "@/lib/tarkovHomeNav";
import { TarkovTaskObjectivesRewards } from "@/components/guides/tarkov/TarkovTaskObjectivesRewards";
import { useTarkovDocumentTitle } from "@/lib/tarkovDocumentTitle";
import type { components } from "@/api/generated/schema";
import styles from "./TarkovTaskDetailPanel.module.css";

type Props = {
  taskId: string;
};

type TraderReq = components["schemas"]["TarkovTaskTraderReqOut"];

function traderEnglish(slug: string, fallback: string): string {
  const known = TARKOV_TRADERS.find((item) => item.id === slug);
  if (known) return known.english;
  return fallback.replace(/（.+）$/, "").trim() || fallback;
}

function traderLevelLabel(
  traderSlug: string,
  traderName: string,
  reqs: TraderReq[] | undefined,
): string {
  const english = traderEnglish(traderSlug, traderName);
  const levels = (reqs || []).filter(
    (row) =>
      row.requirement_type === "level" ||
      row.requirement_type === "loyaltyLevel",
  );
  if (!levels.length) return english || "—";
  return levels
    .map((row) => {
      const name = traderEnglish(row.slug, row.name || english);
      return `${name} LL${row.value}`;
    })
    .join("、");
}

export function TarkovTaskDetailPanel({ taskId }: Props) {
  const gameMode = useTarkovGameMode();
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-task-detail", gameMode, taskId],
    queryFn: () => fetchTarkovTaskDetail(taskId),
    staleTime: 5 * 60_000,
    retry: 1,
  });
  useTarkovDocumentTitle(detailQuery.data?.name || "");

  if (detailQuery.isLoading) {
    return (
      <div className={styles.status}>
        <Spin tip="加载任务…" />
      </div>
    );
  }

  if (detailQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="任务详情加载失败"
        description={apiError(detailQuery.error, "任务详情加载失败")}
      />
    );
  }

  const detail = detailQuery.data;
  if (!detail) return null;

  const image = (detail.task_image_link || "").trim();
  const traderSrc = detail.trader_slug
    ? traderIconUrl(detail.trader_slug)
    : "";
  const traderFallback = detail.trader_slug
    ? traderPortraitUrl(detail.trader_slug)
    : "";
  const traderHref = detail.trader_slug
    ? tarkovTraderHref(detail.trader_slug)
    : "";

  return (
    <div className={styles.stack}>
      <section className={styles.hero}>
        <div>
          <div className={styles.headRow}>
            <span className={styles.badge}>任务</span>
            {detail.lightkeeper_required ? (
              <span className={styles.endgameChip}>灯塔商人</span>
            ) : null}
          </div>
          <div className={styles.titleBar}>
            <h1 className={styles.name}>{detail.name || detail.id}</h1>
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

          <div className={styles.stats}>
            <div>
              <div className={styles.statLabel}>
                <UserOutlined className={styles.statIcon} />
                最低 PMC 等级
              </div>
              <div className={styles.statValue}>
                {detail.min_player_level || "—"}
              </div>
            </div>
            <div>
              <div className={styles.statLabel}>
                <ShopOutlined className={styles.statIcon} />
                商人等级
              </div>
              <div className={styles.statValue}>
                {traderHref ? (
                  <Link className={styles.inlineLink} to={traderHref}>
                    {traderLevelLabel(
                      detail.trader_slug,
                      detail.trader_name,
                      detail.trader_requirements,
                    )}
                  </Link>
                ) : (
                  traderLevelLabel(
                    detail.trader_slug,
                    detail.trader_name,
                    detail.trader_requirements,
                  )
                )}
              </div>
            </div>
            <div>
              <div className={styles.statLabel}>
                <EnvironmentOutlined className={styles.statIcon} />
                地图
              </div>
              <div className={styles.statValue}>
                {detail.map_name || "—"}
              </div>
            </div>
          </div>
        </div>

        <div className={styles.posterWrap}>
          {image ? (
            <Image
              className={styles.poster}
              src={image}
              alt={detail.name || ""}
              preview={{ src: image }}
            />
          ) : traderFallback ? (
            <img className={styles.poster} src={traderFallback} alt="" />
          ) : null}
          {traderSrc && image ? (
            traderHref ? (
              <Link className={styles.traderBadgeLink} to={traderHref}>
                <img
                  className={styles.traderBadge}
                  src={traderSrc}
                  alt={detail.trader_name || ""}
                />
              </Link>
            ) : (
              <img className={styles.traderBadge} src={traderSrc} alt="" />
            )
          ) : null}
        </div>
      </section>

      <TarkovTaskObjectivesRewards detail={detail} />
    </div>
  );
}
