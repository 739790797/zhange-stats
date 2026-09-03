import { Alert, Image, Spin } from "antd";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovTaskDetail } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  TARKOV_MAPS,
  TARKOV_TRADERS,
  tarkovMapHref,
  tarkovTaskHref,
  tarkovTraderHref,
  traderIconUrl,
  traderPortraitUrl,
} from "@/lib/tarkovHomeNav";
import { TarkovTaskObjectivesRewards } from "@/components/guides/tarkov/TarkovTaskObjectivesRewards";
import { useTarkovDocumentTitle } from "@/lib/tarkovDocumentTitle";
import {
  formatTaskCompare,
  formatTaskDelay,
  taskRequirementStatusLabel,
  taskUnlockStatusLabel,
} from "@/lib/tarkovTaskObjective";
import { factionTaskSuffix } from "@/lib/tarkovTaskTree";
import type { components } from "@/api/generated/schema";
import styles from "./TarkovTaskDetailPanel.module.css";

type Props = {
  taskId: string;
};

type TraderReq = components["schemas"]["TarkovTaskTraderReqOut"];
type TaskReq = components["schemas"]["TarkovTaskRequirementOut"];

function traderEnglish(slug: string, fallback: string): string {
  const known = TARKOV_TRADERS.find((item) => item.id === slug);
  if (known) return known.english;
  return fallback.replace(/（.+）$/, "").trim() || fallback;
}

function traderReqLine(row: TraderReq, fallbackSlug: string, fallbackName: string): string {
  const english = traderEnglish(row.slug || fallbackSlug, row.name || fallbackName);
  const type = (row.requirement_type || "").trim();
  if (
    type === "level" ||
    type === "loyaltyLevel" ||
    type === "loyalty" ||
    type === ""
  ) {
    return `${english} LL${row.value}`;
  }
  const cmp = formatTaskCompare(row.compare_method, row.value);
  if (type === "reputation" || type === "standing") {
    return `${english} 声望 ${cmp || row.value}`;
  }
  return `${english} ${type} ${cmp || row.value}`.trim();
}

function traderLevelLabel(
  traderSlug: string,
  traderName: string,
  reqs: TraderReq[] | undefined,
): string {
  const english = traderEnglish(traderSlug, traderName);
  if (!(reqs || []).length) return english || "—";
  return (reqs || [])
    .map((row) => traderReqLine(row, traderSlug, traderName))
    .join("、");
}

function mapHref(slug: string): string | null {
  const key = slug.trim().toLowerCase();
  if (!key) return null;
  const known = TARKOV_MAPS.find((row) => row.id === key);
  return known ? tarkovMapHref(known.id) : null;
}

function RelatedList({
  title,
  rows,
  kind,
}: {
  title: string;
  rows: TaskReq[];
  kind: "prereq" | "unlock";
}) {
  const statusLabel =
    kind === "unlock" ? taskUnlockStatusLabel : taskRequirementStatusLabel;
  return (
    <div className={styles.relatedCol}>
      <h3>{title}</h3>
      {rows.length ? (
        <div className={styles.relatedList}>
          {rows.map((row) => {
            const status = (row.status || [])
              .map((item) => statusLabel(item))
              .filter(Boolean)
              .join(" · ");
            return (
              <Link
                key={row.id}
                className={styles.relatedLink}
                to={tarkovTaskHref(row.id)}
              >
                {row.name || row.id}
                {row.trader_slug || row.trader_name
                  ? ` · ${traderEnglish(row.trader_slug || "", row.trader_name || "")}`
                  : ""}
                {status ? `（${status}）` : ""}
              </Link>
            );
          })}
        </div>
      ) : (
        <div className={styles.relatedEmpty}>无</div>
      )}
    </div>
  );
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
  const mapLink = mapHref(detail.map_slug || "");
  const delay = formatTaskDelay(
    detail.available_delay_seconds_min,
    detail.available_delay_seconds_max,
  );
  const prestige = detail.required_prestige;
  const prestigeLabel = prestige
    ? prestige.name ||
      (prestige.prestige_level ? `声望 ${prestige.prestige_level}` : "")
    : "";
  const prereqs = detail.task_requirements || [];
  const unlocks = detail.unlocks || [];

  const poster = image ? (
    <div className={styles.posterWrap}>
      <Image
        className={styles.poster}
        src={image}
        alt={detail.name || ""}
        preview={{ src: image }}
      />
      {traderSrc ? (
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
  ) : null;
  const related =
    prereqs.length || unlocks.length ? (
      <div className={styles.railCard}>
        {prereqs.length ? (
          <RelatedList title="前置任务" rows={prereqs} kind="prereq" />
        ) : null}
        {unlocks.length ? (
          <RelatedList title="后续任务" rows={unlocks} kind="unlock" />
        ) : null}
      </div>
    ) : null;

  return (
    <div className={styles.stack}>
      <header className={styles.hero}>
        <div className={styles.headRow}>
          <span className={styles.badge}>任务</span>
          {detail.kappa_required ? (
            <span className={styles.endgameChip}>Kappa</span>
          ) : null}
          {detail.lightkeeper_required ? (
            <span className={styles.endgameChip}>灯塔商人</span>
          ) : null}
          {detail.restartable ? (
            <span className={styles.progressBadge}>可重开</span>
          ) : null}
        </div>
        <div className={styles.titleBar}>
          {traderSrc ? (
            traderHref ? (
              <Link to={traderHref}>
                <img
                  className={styles.titleTrader}
                  src={traderSrc}
                  alt={detail.trader_name || ""}
                />
              </Link>
            ) : (
              <img
                className={styles.titleTrader}
                src={traderSrc}
                alt={detail.trader_name || ""}
              />
            )
          ) : traderFallback ? (
            <img className={styles.titleTrader} src={traderFallback} alt="" />
          ) : null}
          <h1 className={styles.name}>
            {detail.name || detail.id}
            {factionTaskSuffix(detail.faction_name)}
          </h1>
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

        <div className={styles.metaBar}>
          <span className={styles.metaItem}>
            <span className={styles.metaLabel}>PMC</span>
            {detail.min_player_level || "—"}
          </span>
          <span className={styles.metaItem}>
            <span className={styles.metaLabel}>商人</span>
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
          </span>
          <span className={styles.metaItem}>
            <span className={styles.metaLabel}>地图</span>
            {detail.map_name ? (
              mapLink ? (
                <Link className={styles.inlineLink} to={mapLink}>
                  {detail.map_name}
                </Link>
              ) : (
                detail.map_name
              )
            ) : (
              "—"
            )}
          </span>
          {prestigeLabel ? (
            <span className={styles.prestige}>
              {prestige?.image_link ? (
                <img
                  className={styles.prestigeIcon}
                  src={prestige.image_link}
                  alt=""
                />
              ) : null}
              需要{prestigeLabel}
            </span>
          ) : null}
          {delay ? <span>{delay}</span> : null}
        </div>
      </header>

      <TarkovTaskObjectivesRewards
        detail={detail}
        railLead={
          <>
            {poster}
            {related}
          </>
        }
      />
    </div>
  );
}
