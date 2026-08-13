import {
  BorderOutlined,
  GiftOutlined,
  UnorderedListOutlined,
} from "@ant-design/icons";
import { Alert, Spin } from "antd";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  fetchTarkovTaskDetail,
  type TarkovTaskDetail,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { TARKOV_TRADERS } from "@/lib/tarkovHomeNav";
import { useTarkovTaskMineMode } from "@/lib/tarkovTaskProgress";
import { formatTaskExtractLines } from "@/lib/tarkovTaskObjective";
import { itemDetailHref, itemHrefFromTypes } from "@/lib/tarkovItemTypes";
import { transparentThumbUrl } from "@/lib/tarkovItemImages";
import type { components } from "@/api/generated/schema";
import styles from "./TarkovTaskDetailPanel.module.css";

type NamedRef = components["schemas"]["TarkovTaskNamedRefOut"];
type Objective = components["schemas"]["TarkovTaskObjectiveOut"];

function traderEnglish(slug: string, fallback: string): string {
  const known = TARKOV_TRADERS.find((item) => item.id === slug);
  if (known) return known.english;
  return fallback.replace(/（.+）$/, "").trim() || fallback;
}

function itemHref(item: NamedRef): string {
  if (item.types?.length) return itemHrefFromTypes(item.id, item.types);
  return itemDetailHref("keys", item.id);
}

function ObjectiveItem({
  item,
  count,
}: {
  item: NamedRef;
  count?: number | null;
}) {
  const thumb = transparentThumbUrl(item.icon_link) || item.icon_link;
  const label = item.name && item.name !== item.id ? item.name : "";
  const body = (
    <>
      {thumb ? (
        <img className={styles.objItemIcon} src={thumb} alt="" />
      ) : null}
      {count && count > 1 ? (
        <span className={styles.objItemCount}>×{count}</span>
      ) : null}
      {!thumb && label ? label : null}
    </>
  );
  if (item.types?.length) {
    return (
      <Link
        className={styles.objItem}
        to={itemHref(item)}
        onClick={(e) => e.stopPropagation()}
        title={label || item.id}
      >
        {body}
      </Link>
    );
  }
  return (
    <span className={styles.objItem} title={label || item.id}>
      {body}
    </span>
  );
}

function ObjectiveRow({ obj }: { obj: Objective }) {
  const extractLines = formatTaskExtractLines(obj);
  const items = obj.items || [];
  const showItems = items.length > 0;
  const showBox = extractLines.length > 0;
  const countForSingle = items.length === 1 ? obj.count : null;
  return (
    <div className={styles.obj}>
      <BorderOutlined className={styles.check} />
      <div className={styles.objBody}>
        <div>
          {obj.optional ? <span className={styles.tag}>可选</span> : null}
          {obj.found_in_raid ? (
            <span className={styles.tag}>战局内</span>
          ) : null}
          {obj.description || obj.type || obj.id}
        </div>
        {showItems ? (
          <div className={styles.objItems}>
            {items.map((item) => (
              <ObjectiveItem key={item.id} item={item} count={countForSingle} />
            ))}
          </div>
        ) : null}
        {showBox ? (
          <div className={styles.objBox}>
            {extractLines.map((line) => (
              <div key={line}>{line}</div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

type RewardsProps = {
  detail: TarkovTaskDetail;
  compact?: boolean;
};

/** 游戏任务卡同款：目标清单 + 完成奖励（不含目标下的地图标签）。 */
export function TarkovTaskObjectivesRewards({
  detail,
  compact = false,
}: RewardsProps) {
  const objectives = detail.objectives || [];
  const rewards = detail.finish_rewards;
  const sectionClass = compact ? styles.sectionFlush : styles.section;

  return (
    <div className={compact ? styles.expandStack : undefined}>
      <section className={sectionClass}>
        <div className={styles.sectionHead}>
          <UnorderedListOutlined />
          目标
        </div>
        {objectives.length ? (
          objectives.map((obj) => (
            <ObjectiveRow key={obj.id || obj.description} obj={obj} />
          ))
        ) : (
          <div className={styles.muted}>无目标数据</div>
        )}
      </section>

      <section className={sectionClass}>
        <div className={styles.sectionHead}>
          <GiftOutlined />
          Completion Rewards
        </div>
        {detail.experience ||
        rewards?.items?.length ||
        rewards?.trader_standing?.length ? (
          <div className={styles.rewards}>
            {detail.experience ? (
              <div>
                <div className={styles.rewardBlock}>XP</div>
                <div className={styles.xp}>
                  +{detail.experience.toLocaleString("zh-CN")}
                </div>
              </div>
            ) : null}
            {rewards?.items?.length ? (
              <div>
                <div className={styles.rewardBlock}>物品</div>
                <div className={styles.rewardRow}>
                  {rewards.items.map((item) => (
                    <Link
                      key={`${item.id}-${item.count}`}
                      className={styles.rewardItem}
                      to={itemHref(item)}
                      onClick={(e) => e.stopPropagation()}
                    >
                      {item.icon_link ? (
                        <img
                          className={styles.keyIcon}
                          src={item.icon_link}
                          alt=""
                        />
                      ) : null}
                      {item.name && item.name !== item.id ? item.name : item.id}
                      {item.count > 1 ? ` ×${item.count}` : ""}
                    </Link>
                  ))}
                </div>
              </div>
            ) : null}
            {rewards?.trader_standing?.length ? (
              <div>
                <div className={styles.rewardBlock}>商人声望</div>
                <div className={styles.rewardRow}>
                  {rewards.trader_standing.map((row) => (
                    <span key={`st-${row.id}`}>
                      {traderEnglish(row.slug, row.name || row.id)}{" "}
                      {row.standing > 0 ? "+" : ""}
                      {row.standing}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : (
          <div className={styles.muted}>无奖励数据</div>
        )}
      </section>
    </div>
  );
}

export function TarkovTaskExpandBody({ taskId }: { taskId: string }) {
  const [mine] = useTarkovTaskMineMode();
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-task-detail", taskId, mine],
    queryFn: () => fetchTarkovTaskDetail(taskId, { progress: mine }),
    staleTime: 5 * 60_000,
    retry: 1,
  });

  if (detailQuery.isLoading) {
    return (
      <div className={styles.expandStatus}>
        <Spin size="small" tip="加载目标与奖励…" />
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

  if (!detailQuery.data) return null;
  return <TarkovTaskObjectivesRewards detail={detailQuery.data} compact />;
}
