import type { ReactNode } from "react";
import { GiftOutlined, UnorderedListOutlined, WarningOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import {
  TARKOV_MAPS,
  tarkovHideoutHref,
  tarkovMapHref,
  tarkovTaskHref,
  tarkovTraderHref,
  traderDisplayName,
} from "@/lib/tarkovHomeNav";
import {
  formatTaskCompare,
  formatTaskExtractLines,
  formatTaskObjectiveExtraLines,
  tarkovObjectiveTypeLabel,
  taskRequirementStatusLabel,
} from "@/lib/tarkovTaskObjective";
import { itemDetailHref, itemHrefFromTypes } from "@/lib/tarkovItemTypes";
import { transparentThumbUrl } from "@/lib/tarkovItemImages";
import { collectRaidPrepFailChips } from "@/lib/tarkovRaidPrep";
import type { TarkovTaskDetail } from "@/api/guidesApi";
import type { components } from "@/api/generated/schema";
import styles from "./TarkovTaskDetailPanel.module.css";

type NamedRef = components["schemas"]["TarkovTaskNamedRefOut"];
type Objective = components["schemas"]["TarkovTaskObjectiveOut"];
type Rewards = components["schemas"]["TarkovTaskFinishRewardsOut"];
type FailCondition = components["schemas"]["TarkovTaskFailConditionOut"];

function itemHref(item: NamedRef): string {
  if (item.types?.length) return itemHrefFromTypes(item.id, item.types);
  return itemDetailHref("keys", item.id);
}

function mapHref(slug: string): string | null {
  const key = slug.trim().toLowerCase();
  if (!key) return null;
  const known = TARKOV_MAPS.find((row) => row.id === key);
  return known ? tarkovMapHref(known.id) : null;
}

function MapNameLink({
  slug,
  name,
  fallback = "未知地图",
}: {
  slug?: string | null;
  name?: string | null;
  fallback?: string;
}) {
  const label = (name || "").trim() || fallback;
  const href = mapHref(slug || "");
  if (href) {
    return (
      <Link className={styles.inlineLink} to={href}>
        {label}
      </Link>
    );
  }
  return <>{label}</>;
}

function namedLabel(item: { id?: string | null; name?: string | null } | null | undefined): string {
  const ident = (item?.id || "").trim();
  const name = (item?.name || "").trim();
  if (name && name !== ident) return name;
  return name || ident;
}

function ObjectiveItem({
  item,
  count,
}: {
  item: NamedRef;
  count?: number | null;
}) {
  const thumb = transparentThumbUrl(item.icon_link) || item.icon_link;
  const label = namedLabel(item);
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
  if (item.id && (item.types?.length || item.icon_link)) {
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

function ItemGroup({
  label,
  groups,
}: {
  label: string;
  groups: NamedRef[][] | undefined;
}) {
  if (!groups?.length) return null;
  return (
    <div className={styles.objItems}>
      <span className={styles.objGroupLabel}>{label}</span>
      {groups.map((group, index) => (
        <span key={`${label}-${index}`} className={styles.objOrGroup}>
          {index > 0 ? <span className={styles.objOr}>或</span> : null}
          {group.map((item) => (
            <ObjectiveItem key={item.id || item.name} item={item} />
          ))}
        </span>
      ))}
    </div>
  );
}

function RequiredKeyGroups({ groups }: { groups: NamedRef[][] | undefined }) {
  if (!groups?.length) return null;
  return (
    <>
      {groups.map((group, index) => (
        <div key={`rk-${index}`} className={styles.objItems}>
          <span className={styles.objGroupLabel}>
            {groups.length > 1 ? `钥匙 ${index + 1}` : "所需钥匙"}
          </span>
          {group.map((item, itemIndex) => (
            <span key={item.id || `${index}-${itemIndex}`} className={styles.objOrGroup}>
              {itemIndex > 0 ? <span className={styles.objOr}>或</span> : null}
              <ObjectiveItem item={item} />
            </span>
          ))}
        </div>
      ))}
    </>
  );
}

function objectivePinHref(obj: Objective): string | null {
  for (const map of obj.maps || []) {
    const href = mapHref(map.slug || "");
    if (href) return href;
  }
  for (const zone of obj.zones || []) {
    const href = mapHref(zone.map_slug || "");
    if (href) return href;
  }
  for (const loc of obj.possible_locations || []) {
    const href = mapHref(loc.map_slug || "");
    if (href) return href;
  }
  return null;
}

function objectivePinCount(obj: Objective): number {
  const zones = (obj.zones || []).length;
  const spots = (obj.possible_locations || []).reduce(
    (sum, loc) => sum + (loc.positions || []).length,
    0,
  );
  return zones + spots;
}

function ObjectiveRow({ obj }: { obj: Objective }) {
  const extractLines = formatTaskExtractLines(obj);
  const items = obj.items || [];
  const maps = obj.maps || [];
  const showItems = items.length > 0;
  const extraLines = formatTaskObjectiveExtraLines({
    ...obj,
    count:
      items.length === 1 || extractLines.length ? null : obj.count,
  });
  const boxLines = [...extractLines, ...extraLines];
  const countForSingle = items.length === 1 ? obj.count : null;
  const station = obj.hideout_station;
  const stationHref = station?.slug ? tarkovHideoutHref(station.slug) : "";
  const typeLabel = tarkovObjectiveTypeLabel(obj.type || "");
  const standing = formatTaskCompare(obj.standing?.compare_method, obj.standing?.value);
  const relatedStatus = (obj.related_status || [])
    .map((item) => taskRequirementStatusLabel(item))
    .filter(Boolean)
    .join(" · ");
  const pinCount = objectivePinCount(obj);
  const pinHref = pinCount ? objectivePinHref(obj) : null;
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
          {typeLabel ? <span className={styles.tag}>{typeLabel}</span> : null}
          {obj.description || obj.type || obj.id}
        </div>
        {maps.length ? (
          <div className={styles.objMaps}>
            地图：
            {maps.map((map, index) => {
              const label = map.name || map.slug || map.id;
              const href = mapHref(map.slug || "");
              return (
                <span key={map.id || `${label}-${index}`}>
                  {index > 0 ? "、" : null}
                  {href ? (
                    <Link className={styles.inlineLink} to={href}>
                      {label}
                    </Link>
                  ) : (
                    label
                  )}
                </span>
              );
            })}
          </div>
        ) : null}
        {showItems ? (
          <div className={styles.objItems}>
            {items.map((item) => (
              <ObjectiveItem key={item.id} item={item} count={countForSingle} />
            ))}
          </div>
        ) : null}
        {(obj.using_weapon || []).length ? (
          <div className={styles.objItems}>
            <span className={styles.objGroupLabel}>使用武器</span>
            {(obj.using_weapon || []).map((item) => (
              <ObjectiveItem key={item.id} item={item} />
            ))}
          </div>
        ) : null}
        <ItemGroup label="使用配件" groups={obj.using_weapon_mods} />
        <ItemGroup label="穿着" groups={obj.wearing} />
        {(obj.not_wearing || []).length ? (
          <div className={styles.objItems}>
            <span className={styles.objGroupLabel}>禁止穿着</span>
            {(obj.not_wearing || []).map((item) => (
              <ObjectiveItem key={item.id} item={item} />
            ))}
          </div>
        ) : null}
        {(obj.use_any || []).length ? (
          <div className={styles.objItems}>
            <span className={styles.objGroupLabel}>使用任一</span>
            {(obj.use_any || []).map((item) => (
              <ObjectiveItem key={item.id} item={item} />
            ))}
          </div>
        ) : null}
        {(obj.contains_all || []).length ? (
          <div className={styles.objItems}>
            <span className={styles.objGroupLabel}>必须包含</span>
            {(obj.contains_all || []).map((item) => (
              <ObjectiveItem key={item.id} item={item} />
            ))}
          </div>
        ) : null}
        <RequiredKeyGroups groups={obj.required_keys} />
        {(obj.related_tasks || []).length ? (
          <div className={styles.objMaps}>
            关联任务：
            {(obj.related_tasks || []).map((task, index) => (
              <span key={task.id}>
                {index > 0 ? "、" : null}
                <Link className={styles.inlineLink} to={tarkovTaskHref(task.id)}>
                  {namedLabel(task)}
                </Link>
              </span>
            ))}
            {relatedStatus ? `（${relatedStatus}）` : ""}
          </div>
        ) : null}
        {station && namedLabel(station) ? (
          <div className={styles.objMaps}>
            藏身处：
            {stationHref ? (
              <Link className={styles.inlineLink} to={stationHref}>
                {namedLabel(station)}
                {obj.station_level != null ? ` ${obj.station_level} 级` : ""}
              </Link>
            ) : (
              <>
                {namedLabel(station)}
                {obj.station_level != null ? ` ${obj.station_level} 级` : ""}
              </>
            )}
          </div>
        ) : null}
        {obj.trader?.slug || standing ? (
          <div className={styles.objMaps}>
            商人：
            {obj.trader?.slug ? (
              <Link className={styles.inlineLink} to={tarkovTraderHref(obj.trader.slug)}>
                {traderDisplayName(obj.trader.slug, obj.trader.name || obj.trader.id)}
                {obj.trader_level != null ? ` LL${obj.trader_level}` : ""}
              </Link>
            ) : null}
            {standing ? ` 声望 ${standing}` : ""}
          </div>
        ) : null}
        {pinCount ? (
          <div className={styles.objMaps}>
            {pinHref ? (
              <Link className={styles.inlineLink} to={pinHref}>
                互动地图可查看标点（{pinCount} 处）
              </Link>
            ) : (
              `有 ${pinCount} 处标点`
            )}
          </div>
        ) : null}
        {boxLines.length ? (
          <div className={styles.objBox}>
            {boxLines.map((line) => (
              <div key={line}>{line}</div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function KeyLink({ item }: { item: NamedRef }) {
  const label = namedLabel(item);
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

function rewardsHaveContent(rewards: Rewards | undefined): boolean {
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

function RewardsBlock({
  title,
  rewards,
  experience,
}: {
  title: string;
  rewards: Rewards | undefined;
  experience?: number;
}) {
  const hasXp = Boolean(experience);
  if (!hasXp && !rewardsHaveContent(rewards)) {
    return (
      <section className={styles.railCard}>
        <h2 className={styles.sectionHead}>
          <GiftOutlined />
          {title}
        </h2>
        <div className={styles.muted}>无奖励数据</div>
      </section>
    );
  }
  return (
    <section className={styles.railCard}>
      <h2 className={styles.sectionHead}>
        <GiftOutlined />
        {title}
      </h2>
      <div className={styles.rewards}>
        {hasXp ? (
          <div>
            <div className={styles.rewardBlock}>经验</div>
            <div className={styles.xp}>
              +{Number(experience).toLocaleString("zh-CN")}
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
                      <img className={styles.keyIcon} src={item.icon_link} alt="" />
                      {item.count > 1 ? (
                        <span className={styles.objItemCount}>×{item.count}</span>
                      ) : null}
                    </span>
                  ) : null}
                  <span className={styles.objItemName}>{namedLabel(item)}</span>
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
                  {row.slug ? (
                    <Link className={styles.inlineLink} to={tarkovTraderHref(row.slug)}>
                      {traderDisplayName(row.slug, row.name || row.id)}
                    </Link>
                  ) : (
                    traderDisplayName(row.slug, row.name || row.id)
                  )}{" "}
                  {row.standing > 0 ? "+" : ""}
                  {row.standing}
                </span>
              ))}
            </div>
          </div>
        ) : null}
        {rewards?.offer_unlock?.length ? (
          <div>
            <div className={styles.rewardBlock}>解锁报价</div>
            <div className={styles.rewardRow}>
              {rewards.offer_unlock.map((row) => {
                const trader = row.trader;
                const item = row.item;
                return (
                  <span key={row.id || item?.id} className={styles.rewardUnlock}>
                    {trader?.slug ? (
                      <Link className={styles.inlineLink} to={tarkovTraderHref(trader.slug)}>
                        {traderDisplayName(trader.slug, trader.name || trader.id)}
                        {row.level ? ` LL${row.level}` : ""}
                      </Link>
                    ) : null}
                    {item ? <ObjectiveItem item={item} /> : null}
                  </span>
                );
              })}
            </div>
          </div>
        ) : null}
        {rewards?.craft_unlock?.length ? (
          <div>
            <div className={styles.rewardBlock}>解锁制作</div>
            <div className={styles.rewardRow}>
              {rewards.craft_unlock.map((row) => {
                const station = row.station;
                const href = station?.slug ? tarkovHideoutHref(station.slug) : "";
                return (
                  <span key={row.id || station?.id} className={styles.rewardUnlock}>
                    {href ? (
                      <Link className={styles.inlineLink} to={href}>
                        {namedLabel(station)}
                        {row.level ? ` ${row.level} 级` : ""}
                      </Link>
                    ) : namedLabel(station) ? (
                      <span>
                        {namedLabel(station)}
                        {row.level ? ` ${row.level} 级` : ""}
                      </span>
                    ) : null}
                    {row.item ? <ObjectiveItem item={row.item} /> : null}
                  </span>
                );
              })}
            </div>
          </div>
        ) : null}
        {rewards?.trader_unlock?.length ? (
          <div>
            <div className={styles.rewardBlock}>解锁商人</div>
            <div className={styles.rewardRow}>
              {rewards.trader_unlock.map((row) =>
                row.slug ? (
                  <Link key={row.id} className={styles.inlineLink} to={tarkovTraderHref(row.slug)}>
                    {traderDisplayName(row.slug, row.name || row.id)}
                  </Link>
                ) : (
                  <span key={row.id}>{namedLabel(row)}</span>
                ),
              )}
            </div>
          </div>
        ) : null}
        {rewards?.skill_level_reward?.length ? (
          <div>
            <div className={styles.rewardBlock}>技能</div>
            <div className={styles.rewardRow}>
              {rewards.skill_level_reward.map((row) => (
                <span key={`${row.name}-${row.level}`}>
                  {row.name}
                  {row.level ? ` ${row.level} 级` : ""}
                </span>
              ))}
            </div>
          </div>
        ) : null}
        {rewards?.achievement?.length ? (
          <div>
            <div className={styles.rewardBlock}>成就</div>
            <div className={styles.rewardRow}>
              {rewards.achievement.map((row) => (
                <span key={row.id} className={styles.rewardUnlock}>
                  {row.image_link ? (
                    <img className={styles.keyIcon} src={row.image_link} alt="" />
                  ) : null}
                  <span>{namedLabel(row)}</span>
                </span>
              ))}
            </div>
          </div>
        ) : null}
        {rewards?.customization?.length ? (
          <div>
            <div className={styles.rewardBlock}>外观</div>
            <div className={styles.rewardRow}>
              {rewards.customization.map((row) => (
                <span key={row.id} className={styles.rewardUnlock}>
                  {row.image_link ? (
                    <img className={styles.keyIcon} src={row.image_link} alt="" />
                  ) : null}
                  <span>
                    {namedLabel(row)}
                    {row.customization_type
                      ? `（${row.customization_type}）`
                      : ""}
                  </span>
                </span>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function FailSection({
  conditions,
  restartable,
}: {
  conditions: FailCondition[];
  restartable: boolean;
}) {
  const chips = collectRaidPrepFailChips(conditions);
  const leftover = conditions.filter((row) => {
    const type = (row.type || "").trim();
    if (!type) return Boolean((row.description || "").trim());
    return !["taskStatus", "extract", "useItem", "traderStanding", "shoot"].includes(type);
  });
  if (!chips.length && !leftover.length && !restartable) return null;
  return (
    <section className={styles.railCard}>
      <h2 className={styles.sectionHead}>
        <WarningOutlined />
        失败条件
      </h2>
      {restartable ? (
        <div className={styles.muted}>失败后可重新接取。</div>
      ) : null}
      {chips.length ? (
        <div className={styles.failList}>
          {chips.map((chip) => (
            <div key={`${chip.type}-${chip.text}`} className={styles.failRow}>
              {chip.tasks?.length ? (
                <>
                  完成该任务会使
                  {chip.tasks.map((task, index) => (
                    <span key={task.id}>
                      {index > 0 ? "、" : ""}
                      <Link className={styles.inlineLink} to={tarkovTaskHref(task.id)}>
                        {task.name}
                      </Link>
                    </span>
                  ))}
                  失败
                </>
              ) : (
                chip.text
              )}
            </div>
          ))}
        </div>
      ) : null}
      {leftover.map((row) => (
        <div key={row.id || row.description} className={styles.failRow}>
          {row.description || row.type}
        </div>
      ))}
    </section>
  );
}

/** 左栏海报 / 钥匙 / 奖励，右栏目标。 */
export function TarkovTaskObjectivesRewards({
  detail,
  railLead,
}: {
  detail: TarkovTaskDetail;
  railLead?: ReactNode;
}) {
  const objectives = detail.objectives || [];
  const keys = detail.needed_keys || [];
  const start = detail.start_rewards;
  const showStart = rewardsHaveContent(start);

  return (
    <div className={styles.body}>
      <aside className={styles.rail}>
        {railLead}
        {showStart ? <RewardsBlock title="接取奖励" rewards={start} /> : null}
        {keys.length ? (
          <section className={styles.railCard}>
            <h2 className={styles.sectionHead}>所需钥匙</h2>
            <div className={styles.keys}>
              {keys.map((row, index) => (
                <div
                  key={`${row.map?.id || "map"}-${index}`}
                  className={styles.keyGroup}
                >
                  <div className={styles.keyMap}>
                    <MapNameLink slug={row.map?.slug} name={row.map?.name} />
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
        <RewardsBlock
          title="完成奖励"
          rewards={detail.finish_rewards}
          experience={detail.experience}
        />
        {rewardsHaveContent(detail.fail_rewards) ? (
          <RewardsBlock title="失败惩罚" rewards={detail.fail_rewards} />
        ) : null}
        <FailSection
          conditions={detail.fail_conditions || []}
          restartable={Boolean(detail.restartable)}
        />
      </aside>

      <div className={styles.mainCol}>
        <section className={`${styles.section} ${styles.objectivePanel}`}>
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
      </div>
    </div>
  );
}
