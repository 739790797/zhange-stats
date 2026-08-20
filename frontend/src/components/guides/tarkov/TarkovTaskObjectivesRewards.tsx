import {
  GiftOutlined,
  UnorderedListOutlined,
} from "@ant-design/icons";
import { Link } from "react-router-dom";
import { TARKOV_TRADERS } from "@/lib/tarkovHomeNav";
import { formatTaskExtractLines } from "@/lib/tarkovTaskObjective";
import { itemDetailHref, itemHrefFromTypes } from "@/lib/tarkovItemTypes";
import { transparentThumbUrl } from "@/lib/tarkovItemImages";
import type { TarkovTaskDetail } from "@/api/guidesApi";
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
  const label = item.name && item.name !== item.id ? item.name : item.id;
  const body = (
    <>
      {thumb ? (
        <span className={styles.objItemVisual}>
          <img className={styles.objItemIcon} src={thumb} alt="" />
          {count && count > 1 ? (
            <span className={styles.objItemCount}>×{count}</span>
          ) : null}
        </span>
      ) : null}
      <span className={styles.objItemName}>{label}</span>
    </>
  );
  if (item.types?.length) {
    return (
      <Link className={styles.objItem} to={itemHref(item)} title={label}>
        {body}
      </Link>
    );
  }
  return (
    <span className={styles.objItem} title={label}>
      {body}
    </span>
  );
}

function ObjectiveRow({ obj }: { obj: Objective }) {
  const extractLines = formatTaskExtractLines(obj);
  const items = obj.items || [];
  const maps = obj.maps || [];
  const showItems = items.length > 0;
  const showBox = extractLines.length > 0;
  const countForSingle = items.length === 1 ? obj.count : null;
  return (
    <div className={styles.obj}>
      <span className={styles.check} aria-hidden>
        □
      </span>
      <div className={styles.objBody}>
        <div>
          {obj.optional ? <span className={styles.tag}>可选</span> : null}
          {obj.found_in_raid ? (
            <span className={styles.tag}>战局内</span>
          ) : null}
          {obj.description || obj.type || obj.id}
        </div>
        {maps.length ? (
          <div className={styles.objMaps}>
            地图：
            {maps
              .map((map) => map.name || map.slug || map.id)
              .filter(Boolean)
              .join("、")}
          </div>
        ) : null}
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

function KeyLink({ item }: { item: NamedRef }) {
  const label = item.name && item.name !== item.id ? item.name : item.id;
  return (
    <Link className={styles.keyItem} to={itemHref(item)} title={label}>
      {item.icon_link ? (
        <img className={styles.keyIcon} src={item.icon_link} alt="" />
      ) : (
        <span className={styles.keyIcon} />
      )}
      <span className={styles.objItemName}>{label}</span>
    </Link>
  );
}

/** 对齐 tarkov.dev 任务详情：目标（含地图）→ 钥匙 → 完成奖励。 */
export function TarkovTaskObjectivesRewards({
  detail,
}: {
  detail: TarkovTaskDetail;
}) {
  const objectives = detail.objectives || [];
  const rewards = detail.finish_rewards;
  const keys = detail.needed_keys || [];

  return (
    <>
      <section className={styles.section}>
        <h2 className={styles.sectionHead}>
          <UnorderedListOutlined />
          目标
        </h2>
        {objectives.length ? (
          objectives.map((obj) => (
            <ObjectiveRow key={obj.id || obj.description} obj={obj} />
          ))
        ) : (
          <div className={styles.muted}>无目标数据</div>
        )}
      </section>

      {keys.length ? (
        <section className={styles.section}>
          <h2 className={styles.sectionHead}>所需钥匙</h2>
          <div className={styles.keys}>
            {keys.map((row, index) => (
              <div
                key={`${row.map?.id || "map"}-${index}`}
                className={styles.keyGroup}
              >
                <div className={styles.keyMap}>
                  {row.map?.name || row.map?.id || "未知地图"}
                </div>
                <div className={styles.rewardRow}>
                  {(row.keys || []).map((key) => (
                    <KeyLink key={key.id} item={key} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className={styles.section}>
        <h2 className={styles.sectionHead}>
          <GiftOutlined />
          完成奖励
        </h2>
        {detail.experience ||
        rewards?.items?.length ||
        rewards?.trader_standing?.length ? (
          <div className={styles.rewards}>
            {detail.experience ? (
              <div>
                <div className={styles.rewardBlock}>经验</div>
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
                    >
                      {item.icon_link ? (
                        <span className={styles.objItemVisual}>
                          <img
                            className={styles.keyIcon}
                            src={item.icon_link}
                            alt=""
                          />
                          {item.count > 1 ? (
                            <span className={styles.objItemCount}>
                              ×{item.count}
                            </span>
                          ) : null}
                        </span>
                      ) : null}
                      <span className={styles.objItemName}>
                        {item.name && item.name !== item.id ? item.name : item.id}
                      </span>
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
    </>
  );
}
