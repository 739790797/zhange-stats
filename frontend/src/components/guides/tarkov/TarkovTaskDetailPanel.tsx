import { useEffect, useMemo, useState } from "react";
import { ExportOutlined } from "@ant-design/icons";
import { Alert, Image, Spin } from "antd";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovTaskDetail } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  tarkovMapHref,
  tarkovTaskHref,
  tarkovTraderHref,
  traderDisplayName,
} from "@/lib/tarkovHomeNav";
import { TarkovTaskObjectivesRewards } from "@/components/guides/tarkov/TarkovTaskObjectivesRewards";
import { TarkovTaskDetailSection } from "@/components/guides/tarkov/TarkovTaskDetailSection";
import { TarkovTraderThumb } from "@/components/guides/tarkov/TarkovTraderThumb";
import { useTarkovDocumentTitle } from "@/lib/tarkovDocumentTitle";
import {
  TARKOV_TRADER_LOYALTY_REQ_TYPES,
  TARKOV_TRADER_STANDING_REQ_TYPES,
  formatTaskCompare,
  formatTaskDelay,
  orderObjectiveTypes,
  tarkovObjectiveTypeLabel,
  tarkovObjectiveTypeTone,
  taskRequirementStatusLabel,
  taskUnlockStatusLabel,
} from "@/lib/tarkovTaskObjective";
import { describeTaskMap } from "@/lib/tarkovTaskTree";
import type { components } from "@/api/generated/schema";
import taskStyles from "./TarkovTasksPanel.module.css";
import styles from "./TarkovTaskDetailPanel.module.css";

type Props = {
  taskId: string;
};

type TraderReq = components["schemas"]["TarkovTaskTraderReqOut"];
type TaskReq = components["schemas"]["TarkovTaskRequirementOut"];
type Rewards = components["schemas"]["TarkovTaskFinishRewardsOut"];
type TocItem = { id: string; label: string };

function hasRewardPayload(rewards: Rewards | undefined): boolean {
  if (!rewards) return false;
  return Boolean(
    rewards.items?.length ||
      rewards.trader_standing?.length ||
      rewards.offer_unlock?.length ||
      rewards.skill_level_reward?.length ||
      rewards.trader_unlock?.length ||
      rewards.craft_unlock?.length ||
      rewards.achievement?.length ||
      rewards.customization?.length,
  );
}

function traderReqSubline(
  row: TraderReq,
  fallbackSlug: string,
  fallbackName: string,
): string {
  const english = traderDisplayName(row.slug || fallbackSlug, row.name || fallbackName);
  const type = (row.requirement_type || "").trim();
  const sameTrader = (row.slug || fallbackSlug) === fallbackSlug;
  if (TARKOV_TRADER_LOYALTY_REQ_TYPES.has(type)) {
    return sameTrader ? `LL${row.value}` : `${english} LL${row.value}`;
  }
  const cmp = formatTaskCompare(row.compare_method, row.value);
  if (TARKOV_TRADER_STANDING_REQ_TYPES.has(type)) {
    const bit = `声望 ${cmp || row.value}`;
    return sameTrader ? bit : `${english} ${bit}`;
  }
  const bit = `${type} ${cmp || row.value}`.trim();
  return sameTrader ? bit : `${english} ${bit}`;
}

function traderReqSummary(
  traderSlug: string,
  traderName: string,
  reqs: TraderReq[] | undefined,
): string {
  return (reqs || [])
    .map((row) => traderReqSubline(row, traderSlug, traderName))
    .filter(Boolean)
    .join(" · ");
}

function RelatedList({
  id,
  title,
  rows,
  kind,
}: {
  id: string;
  title: string;
  rows: TaskReq[];
  kind: "prereq" | "unlock";
}) {
  const statusLabel =
    kind === "unlock" ? taskUnlockStatusLabel : taskRequirementStatusLabel;
  const statusClass =
    kind === "unlock" ? styles.relatedStatusNext : styles.relatedStatusNeed;
  return (
    <TarkovTaskDetailSection id={id} title={title} count={rows.length}>
      <div className={styles.relatedBox}>
        {rows.map((row) => {
          const status = (row.status || [])
            .map((item) => statusLabel(item))
            .filter(Boolean)
            .join(" · ");
          const trader = traderDisplayName(row.trader_slug || "", row.trader_name || "");
          return (
            <div key={row.id} className={styles.relatedRow}>
              <div className={styles.relatedLead}>
                <span className={styles.relatedMark} aria-hidden />
                <Link className={styles.relatedName} to={tarkovTaskHref(row.id)}>
                  {row.name || row.id}
                </Link>
                {trader ? (
                  <span className={styles.relatedTrader}>· {trader}</span>
                ) : null}
              </div>
              {status ? <span className={statusClass}>{status}</span> : null}
            </div>
          );
        })}
      </div>
    </TarkovTaskDetailSection>
  );
}

function scrollToSection(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
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

  const detail = detailQuery.data;
  const intro = (detail?.dialogue?.description || "").trim();
  const startTalk = (detail?.dialogue?.start || "").trim();
  const successTalk = (detail?.dialogue?.success || "").trim();
  const failTalk = (detail?.dialogue?.fail || "").trim();
  const hasDialogue = Boolean(startTalk || successTalk || failTalk);
  const prereqs = detail?.task_requirements || [];
  const unlocks = detail?.unlocks || [];
  const keys = detail?.needed_keys || [];
  const typeKeys = orderObjectiveTypes(detail?.objective_types);
  const toc = useMemo(() => {
    if (!detail) return [] as TocItem[];
    const items: TocItem[] = [];
    items.push({ id: "task-objectives", label: "目标" });
    if (prereqs.length) items.push({ id: "task-prereqs", label: "前置任务" });
    if (unlocks.length) items.push({ id: "task-unlocks", label: "后续任务" });
    if (keys.length) items.push({ id: "task-keys", label: "所需钥匙" });
    if (hasRewardPayload(detail.start_rewards)) {
      items.push({ id: "task-start-rewards", label: "接取奖励" });
    }
    items.push({ id: "task-finish-rewards", label: "完成奖励" });
    if (hasRewardPayload(detail.fail_rewards)) {
      items.push({ id: "task-fail-rewards", label: "失败惩罚" });
    }
    if (detail.restartable || (detail.fail_conditions || []).length) {
      items.push({ id: "task-fail", label: "失败条件" });
    }
    if (hasDialogue) items.push({ id: "task-dialogue", label: "任务对话" });
    return items;
  }, [detail, hasDialogue, keys.length, prereqs.length, unlocks.length]);
  const [activeId, setActiveId] = useState("");

  useEffect(() => {
    setActiveId(toc[0]?.id || "");
  }, [toc]);

  useEffect(() => {
    const ids = toc.map((item) => item.id);
    if (!ids.length) return;
    const root = document.getElementById("tarkov-main");
    const observer = new IntersectionObserver(
      (entries) => {
        const hit = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (hit?.target.id) setActiveId(hit.target.id);
      },
      { root, rootMargin: "0px 0px -65% 0px", threshold: 0 },
    );
    for (const id of ids) {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, [toc]);

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

  if (!detail) return null;

  const image = (detail.task_image_link || "").trim();
  const traderHref = detail.trader_slug
    ? tarkovTraderHref(detail.trader_slug)
    : "";
  const traderEnglish = traderDisplayName(
    detail.trader_slug || "",
    detail.trader_name || "",
  );
  const mapMark = describeTaskMap(detail);
  const mapLink = mapMark ? tarkovMapHref(mapMark.id) : "";
  const delay = formatTaskDelay(
    detail.available_delay_seconds_min,
    detail.available_delay_seconds_max,
  );
  const delayValue = delay.replace(/^完成后等待\s*/, "");
  const prestige = detail.required_prestige;
  const prestigeLabel = prestige
    ? prestige.name ||
      (prestige.prestige_level ? `声望 ${prestige.prestige_level}` : "")
    : "";
  const traderSub = traderReqSummary(
    detail.trader_slug || "",
    traderEnglish,
    detail.trader_requirements,
  );
  const factionLabel = (detail.faction_name || "").trim() || "—";
  const related = (
    <>
      {prereqs.length ? (
        <RelatedList
          id="task-prereqs"
          title="前置任务"
          rows={prereqs}
          kind="prereq"
        />
      ) : null}
      {unlocks.length ? (
        <RelatedList
          id="task-unlocks"
          title="后续任务"
          rows={unlocks}
          kind="unlock"
        />
      ) : null}
    </>
  );

  return (
    <div className={styles.stack}>
      <header className={styles.hero}>
        <div className={styles.heroPoster}>
          {image ? (
            <Image
              className={styles.heroPosterImg}
              src={image}
              alt={detail.name || ""}
              preview={{ src: image }}
            />
          ) : (
            <div className={styles.posterEmpty} />
          )}
          <span className={styles.posterBadge}>任务</span>
        </div>
        <div className={styles.heroCopy}>
          {detail.kappa_required ||
          detail.lightkeeper_required ||
          detail.prestige_cycle ||
          detail.restartable ||
          detail.wiki_link ? (
            <div className={styles.heroTop}>
              <div className={styles.headRow}>
                {detail.kappa_required ? (
                  <span className={styles.endgameChip}>Kappa</span>
                ) : null}
                {detail.lightkeeper_required ? (
                  <span className={styles.endgameChip}>Lightkeeper</span>
                ) : null}
                {detail.prestige_cycle ? (
                  <span className={styles.endgameChip}>转生</span>
                ) : null}
                {detail.restartable ? (
                  <span className={styles.progressBadge}>可重开</span>
                ) : null}
              </div>
              {detail.wiki_link ? (
                <a
                  className={styles.wiki}
                  href={detail.wiki_link}
                  target="_blank"
                  rel="noreferrer"
                >
                  Wiki
                  <ExportOutlined />
                </a>
              ) : null}
            </div>
          ) : null}
          <h1 className={styles.name}>{detail.name || detail.id}</h1>
          <div className={styles.metaBar}>
            <span className={styles.metaItem}>
              <span className={styles.metaLabel}>PMC</span>
              <span className={styles.metaAccent}>
                {detail.min_player_level || "—"}
              </span>
            </span>
            {delayValue ? (
              <>
                <span className={styles.metaDot} aria-hidden>
                  ·
                </span>
                <span className={styles.metaItem}>
                  <span className={styles.metaLabel}>完成后等待</span>
                  <span>{delayValue}</span>
                </span>
              </>
            ) : null}
            {prestigeLabel ? (
              <>
                <span className={styles.metaDot} aria-hidden>
                  ·
                </span>
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
              </>
            ) : null}
          </div>
        </div>
      </header>

      <div className={styles.stats}>
        <div className={styles.statCard}>
          <div className={styles.statLabel}>商人</div>
          <div className={styles.statValueRow}>
            {detail.trader_slug ? (
              <span className={styles.statAvatar}>
                <TarkovTraderThumb
                  slug={detail.trader_slug}
                  size={28}
                  title={traderEnglish}
                />
              </span>
            ) : null}
            <div className={styles.statCopy}>
              {traderHref ? (
                <Link className={styles.statNameLink} to={traderHref}>
                  {traderEnglish || "—"}
                </Link>
              ) : (
                <span className={styles.statValue}>{traderEnglish || "—"}</span>
              )}
              {traderSub ? <div className={styles.statSub}>{traderSub}</div> : null}
            </div>
          </div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statLabel}>地图</div>
          {mapMark ? (
            <Link
              className={styles.mapTile}
              to={mapLink}
              title={
                mapMark.english
                  ? `${mapMark.label}（${mapMark.english}）`
                  : mapMark.label
              }
            >
              {mapMark.icon ? (
                <svg
                  className={styles.mapTileIcon}
                  viewBox="0 0 24 24"
                  width="18"
                  height="18"
                  aria-hidden
                >
                  <path d={mapMark.icon} fill="currentColor" />
                </svg>
              ) : null}
              <span className={styles.mapTileName}>{mapMark.label}</span>
            </Link>
          ) : (
            <div className={styles.statValue}>—</div>
          )}
        </div>
        <div className={styles.statCard}>
          <div className={styles.statLabel}>任务类型</div>
          {typeKeys.length ? (
            <div className={taskStyles.typeList}>
              {typeKeys.map((type) => (
                <span
                  key={type}
                  className={taskStyles.typeChip}
                  data-tone={tarkovObjectiveTypeTone(type)}
                >
                  {tarkovObjectiveTypeLabel(type)}
                </span>
              ))}
            </div>
          ) : (
            <div className={styles.statValue}>—</div>
          )}
        </div>
        <div className={styles.statCard}>
          <div className={styles.statLabel}>阵营</div>
          <div className={styles.statValue}>{factionLabel}</div>
        </div>
      </div>

      <div className={styles.body}>
        <div className={styles.mainCol}>
          {intro ? <div className={styles.intro}>{intro}</div> : null}
          <TarkovTaskObjectivesRewards
            detail={detail}
            afterObjectives={related}
          />
          {hasDialogue ? (
            <section id="task-dialogue" className={styles.section}>
              <h2 className={styles.sectionHead}>
                任务对话
                <span className={styles.sectionRule} aria-hidden />
              </h2>
              <div className={styles.dialogueList}>
                {startTalk ? (
                  <div>
                    <div className={styles.dialogueLabel}>接取</div>
                    <div className={styles.intro}>{startTalk}</div>
                  </div>
                ) : null}
                {successTalk ? (
                  <div>
                    <div className={styles.dialogueLabel}>完成</div>
                    <div className={styles.intro}>{successTalk}</div>
                  </div>
                ) : null}
                {failTalk ? (
                  <div>
                    <div className={styles.dialogueLabel}>失败</div>
                    <div className={styles.intro}>{failTalk}</div>
                  </div>
                ) : null}
              </div>
            </section>
          ) : null}
        </div>
        {toc.length ? (
          <nav className={styles.toc} aria-label="本页内容">
            <div className={styles.tocTitle}>本页内容</div>
            {toc.map((item) => (
              <a
                key={item.id}
                className={
                  item.id === activeId
                    ? `${styles.tocLink} ${styles.tocLinkActive}`
                    : styles.tocLink
                }
                href={`#${item.id}`}
                onClick={(event) => {
                  event.preventDefault();
                  setActiveId(item.id);
                  scrollToSection(item.id);
                }}
              >
                {item.label}
              </a>
            ))}
          </nav>
        ) : null}
      </div>
    </div>
  );
}
