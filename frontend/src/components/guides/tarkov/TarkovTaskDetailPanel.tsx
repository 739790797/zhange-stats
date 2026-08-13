import {
  EnvironmentOutlined,
  KeyOutlined,
  ShopOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Alert, Spin } from "antd";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovTaskDetail } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import {
  TARKOV_TRADERS,
  tarkovTaskHref,
  traderPortraitUrl,
} from "@/lib/tarkovHomeNav";
import { TarkovTaskProgressSwitch } from "@/components/guides/tarkov/TarkovTaskProgressSwitch";
import { TarkovTaskObjectivesRewards } from "@/components/guides/tarkov/TarkovTaskObjectivesRewards";
import {
  tarkovTaskProgressLabel,
  useTarkovTaskMineMode,
} from "@/lib/tarkovTaskProgress";
import { itemDetailHref, itemHrefFromTypes } from "@/lib/tarkovItemTypes";
import type { components } from "@/api/generated/schema";
import styles from "./TarkovTaskDetailPanel.module.css";

type Props = {
  taskId: string;
};

type NamedRef = components["schemas"]["TarkovTaskNamedRefOut"];
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

function itemHref(item: NamedRef): string {
  if (item.types?.length) return itemHrefFromTypes(item.id, item.types);
  return itemDetailHref("keys", item.id);
}

function KeyLink({ item }: { item: NamedRef }) {
  const label = item.name && item.name !== item.id ? item.name : item.id;
  return (
    <Link className={styles.keyItem} to={itemHref(item)}>
      {item.icon_link ? (
        <img className={styles.keyIcon} src={item.icon_link} alt="" />
      ) : (
        <span className={styles.keyIcon} />
      )}
      {label}
    </Link>
  );
}

export function TarkovTaskDetailPanel({ taskId }: Props) {
  const [mine, setMine] = useTarkovTaskMineMode();
  const detailQuery = useQuery({
    queryKey: ["guides-tarkov-task-detail", taskId, mine],
    queryFn: () => fetchTarkovTaskDetail(taskId, { progress: mine }),
    staleTime: 5 * 60_000,
    retry: 1,
  });

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
    ? traderPortraitUrl(detail.trader_slug)
    : "";
  const reqs = detail.task_requirements || [];
  const nextTasks = detail.successor_tasks || [];
  const keys = detail.needed_keys || [];

  return (
    <div className={styles.stack}>
      <div className={styles.toolbar}>
        <TarkovTaskProgressSwitch enabled={mine} onChange={setMine} />
      </div>
      {mine && !detail.progress_bound ? (
        <Alert
          type="info"
          showIcon
          message="还没绑定 Tarkov Tracker"
          description="打开顶栏「绑定 Token」后，才能显示这任务对你当前账号的状态。"
        />
      ) : null}
      {mine && detail.progress_bound && !detail.progress_ready ? (
        <Alert
          type="warning"
          showIcon
          message="进度明细还没拉下来"
          description="点顶栏等级旁的刷新，把 Tracker 的任务状态同步过来。"
        />
      ) : null}
      <section className={styles.hero}>
        <div>
          <div className={styles.headRow}>
            <span className={styles.badge}>任务</span>
            {mine && detail.progress_status ? (
              <span
                className={`${styles.progressBadge} ${
                  detail.progress_status === "available"
                    ? styles.progressAvailable
                    : detail.progress_status === "complete"
                      ? styles.progressComplete
                      : detail.progress_status === "failed"
                        ? styles.progressFailed
                        : styles.progressLocked
                }`}
              >
                {tarkovTaskProgressLabel(detail.progress_status)}
              </span>
            ) : null}
            <h2 className={styles.name}>{detail.name || detail.id}</h2>
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
                Minimum PMC Level
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
                {traderLevelLabel(
                  detail.trader_slug,
                  detail.trader_name,
                  detail.trader_requirements,
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

          <div className={styles.related}>
            <div className={styles.relatedCol}>
              <h3>前置任务</h3>
              {reqs.length ? (
                <div className={styles.relatedList}>
                  {reqs.map((req) => (
                    <Link
                      key={req.id}
                      className={`${styles.relatedLink} ${
                        mine && req.met === true
                          ? styles.relatedMet
                          : mine && req.met === false
                            ? styles.relatedUnmet
                            : ""
                      }`}
                      to={tarkovTaskHref(req.id)}
                    >
                      {req.name || req.id}
                      {mine && req.met === true
                        ? " · 已满足"
                        : mine && req.met === false
                          ? " · 未完成"
                          : ""}
                    </Link>
                  ))}
                </div>
              ) : (
                <div className={styles.relatedEmpty}>无前置</div>
              )}
            </div>
            <div className={styles.relatedCol}>
              <h3>后续任务</h3>
              {nextTasks.length ? (
                <div className={styles.relatedList}>
                  {nextTasks.map((req) => (
                    <Link
                      key={req.id}
                      className={styles.relatedLink}
                      to={tarkovTaskHref(req.id)}
                    >
                      {req.name || req.id}
                    </Link>
                  ))}
                </div>
              ) : (
                <div className={styles.relatedEmpty}>无后续</div>
              )}
            </div>
          </div>
        </div>

        <div className={styles.posterWrap}>
          {image ? (
            <img className={styles.poster} src={image} alt="" />
          ) : traderSrc ? (
            <img className={styles.poster} src={traderSrc} alt="" />
          ) : null}
          {traderSrc && image ? (
            <img className={styles.traderBadge} src={traderSrc} alt="" />
          ) : null}
        </div>
      </section>

      <TarkovTaskObjectivesRewards detail={detail} />

      {keys.length ? (
        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <KeyOutlined />
            所需钥匙
          </div>
          <div className={styles.keys}>
            {keys.map((row, index) => (
              <div
                key={`${row.map?.id || "map"}-${index}`}
                className={styles.keyGroup}
              >
                <div className={styles.keyMap}>
                  {row.map?.name || row.map?.id || "未知地图"}
                </div>
                {(row.keys || []).map((key) => (
                  <KeyLink key={key.id} item={key} />
                ))}
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
