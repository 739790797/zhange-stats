import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  TARKOV_MAPS,
  tarkovHideoutHref,
  tarkovMapHref,
  tarkovTaskHref,
  tarkovTraderHref,
  tarkovWorkbenchHref,
  traderDisplayName,
} from "@/lib/tarkovHomeNav";
import {
  formatTaskCompare,
  formatTaskExtractLines,
  formatTaskObjectiveExtraLines,
  tarkovObjectiveTypeLabel,
  tarkovObjectiveTypeTone,
  taskRequirementStatusLabel,
} from "@/lib/tarkovTaskObjective";
import { itemDetailHref, itemHrefFromTypes } from "@/lib/tarkovItemTypes";
import { transparentThumbUrl } from "@/lib/tarkovItemImages";
import { collectRaidPrepFailChips } from "@/lib/tarkovRaidPrep";
import { isGunsmithObjectiveType } from "@/lib/tarkovWorkbenchGunsmith";
import type { TarkovTaskDetail } from "@/api/guidesApi";
import type { components } from "@/api/generated/schema";
import taskStyles from "./TarkovTasksPanel.module.css";
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
      <span className={styles.itemTileIconWrap}>
        {thumb ? <img className={styles.itemTileIcon} src={thumb} alt="" /> : null}
        {count && count > 1 ? (
          <span className={styles.objItemCount}>×{count}</span>
        ) : null}
      </span>
      <span className={styles.itemTileName}>{label}</span>
    </>
  );
  if (item.id && (item.types?.length || item.icon_link)) {
    return (
      <Link className={styles.itemTile} to={itemHref(item)} title={label}>
        {body}
      </Link>
    );
  }
  return (
    <span className={styles.itemTile} title={label}>
      {body}
    </span>
  );
}

function splitMetaLine(line: string): { label: string; value: string } {
  const idx = line.indexOf("：");
  if (idx > 0) {
    return { label: line.slice(0, idx), value: line.slice(idx + 1).trim() };
  }
  const match = line.match(/^(\S+)\s+(.+)$/);
  if (match) return { label: match[1], value: match[2] };
  return { label: line, value: "" };
}

function MetaStrip({ lines }: { lines: string[] }) {
  if (!lines.length) return null;
  return (
    <div className={styles.metaStrip}>
      {lines.map((line) => {
        const { label, value } = splitMetaLine(line);
        return (
          <span key={line} className={styles.metaStripItem}>
            {label}
            {value ? (
              <>
                ：<span className={styles.metaStripValue}>{value}</span>
              </>
            ) : null}
          </span>
        );
      })}
    </div>
  );
}

function ItemGrid({
  label,
  children,
}: {
  label?: string;
  children: ReactNode;
}) {
  return (
    <div className={styles.itemGridWrap}>
      {label ? <div className={styles.objGroupLabel}>{label}</div> : null}
      <div className={styles.itemGrid}>{children}</div>
    </div>
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
    <div className={styles.itemGridWrap}>
      <div className={styles.objGroupLabel}>{label}</div>
      <div className={styles.itemGrid}>
        {groups.map((group, index) => (
          <span key={`${label}-${index}`} className={styles.itemGridGroup}>
            {index > 0 ? <span className={styles.itemGridOr}>或</span> : null}
            {group.map((item) => (
              <ObjectiveItem key={item.id || item.name} item={item} />
            ))}
          </span>
        ))}
      </div>
    </div>
  );
}

function RequiredKeyGroups({ groups }: { groups: NamedRef[][] | undefined }) {
  if (!groups?.length) return null;
  return (
    <>
      {groups.map((group, index) => (
        <ItemGrid
          key={`rk-${index}`}
          label={groups.length > 1 ? `钥匙 ${index + 1}` : "所需钥匙"}
        >
          {group.map((item, itemIndex) => (
            <span key={item.id || `${index}-${itemIndex}`} className={styles.itemGridGroup}>
              {itemIndex > 0 ? <span className={styles.itemGridOr}>或</span> : null}
              <ObjectiveItem item={item} />
            </span>
          ))}
        </ItemGrid>
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

function ObjectiveRow({ obj, taskId }: { obj: Objective; taskId?: string }) {
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
    <div className={styles.objCard} data-tone={tarkovObjectiveTypeTone(obj.type || "")}>
      <span className={styles.check} aria-hidden />
      <div className={styles.objBody}>
        <div className={styles.objTitle}>
          {obj.optional ? <span className={styles.tag}>可选</span> : null}
          {obj.found_in_raid ? (
            <span className={styles.tag}>战局内</span>
          ) : null}
          {typeLabel ? (
            <span
              className={`${taskStyles.typeChip} ${styles.objTypeChip}`}
              data-tone={tarkovObjectiveTypeTone(obj.type || "")}
            >
              {typeLabel}
            </span>
          ) : null}
          <span className={styles.objDesc}>{obj.description || obj.type || obj.id}</span>
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
          <ItemGrid>
            {items.map((item) => (
              <ObjectiveItem key={item.id} item={item} count={countForSingle} />
            ))}
          </ItemGrid>
        ) : null}
        {(obj.using_weapon || []).length ? (
          <ItemGrid label="使用武器">
            {(obj.using_weapon || []).map((item) => (
              <ObjectiveItem key={item.id} item={item} />
            ))}
          </ItemGrid>
        ) : null}
        <ItemGroup label="使用配件" groups={obj.using_weapon_mods} />
        <ItemGroup label="穿着" groups={obj.wearing} />
        {(obj.not_wearing || []).length ? (
          <ItemGrid label="禁止穿着">
            {(obj.not_wearing || []).map((item) => (
              <ObjectiveItem key={item.id} item={item} />
            ))}
          </ItemGrid>
        ) : null}
        {(obj.use_any || []).length ? (
          <ItemGrid label="使用任一">
            {(obj.use_any || []).map((item) => (
              <ObjectiveItem key={item.id} item={item} />
            ))}
          </ItemGrid>
        ) : null}
        {(obj.contains_all || []).length ? (
          <ItemGrid label="必须包含">
            {(obj.contains_all || []).map((item) => (
              <ObjectiveItem key={item.id} item={item} />
            ))}
          </ItemGrid>
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
        {isGunsmithObjectiveType(obj.type) && taskId ? (
          <div className={styles.objMaps}>
            <Link
              className={styles.inlineLink}
              to={tarkovWorkbenchHref(undefined, {
                taskId,
                objectiveId: obj.id,
              })}
            >
              去工作台求解
            </Link>
          </div>
        ) : null}
        {boxLines.length ? <MetaStrip lines={boxLines} /> : null}
      </div>
    </div>
  );
}

function KeyLink({ item }: { item: NamedRef }) {
  return <ObjectiveItem item={item} />;
}

function leftoverFailConditions(conditions: FailCondition[]): FailCondition[] {
  return conditions.filter((row) => {
    const type = (row.type || "").trim();
    if (!type) return Boolean((row.description || "").trim());
    return !["taskStatus", "extract", "useItem", "traderStanding", "shoot"].includes(
      type,
    );
  });
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

function RewardCard({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className={styles.rewardCard}>
      <div className={styles.rewardCardHead}>{title}</div>
      <div className={styles.rewardCardBody}>{children}</div>
    </div>
  );
}

function RewardLine({
  href,
  icon,
  name,
  value,
  accent,
}: {
  href?: string;
  icon?: string | null;
  name: ReactNode;
  value?: ReactNode;
  accent?: boolean;
}) {
  const inner = (
    <>
      {icon ? <img className={styles.rewardLineIcon} src={icon} alt="" /> : null}
      <span className={styles.rewardLineName}>{name}</span>
      {value != null ? (
        <span className={accent ? styles.rewardGold : styles.rewardLineValue}>
          {value}
        </span>
      ) : null}
    </>
  );
  if (href) {
    return (
      <Link className={styles.rewardLine} to={href}>
        {inner}
      </Link>
    );
  }
  return <div className={styles.rewardLine}>{inner}</div>;
}

function RewardsBlock({
  id,
  title,
  rewards,
  experience,
}: {
  id?: string;
  title: string;
  rewards: Rewards | undefined;
  experience?: number;
}) {
  const hasXp = Boolean(experience);
  if (!hasXp && !rewardsHaveContent(rewards)) {
    return (
      <section id={id} className={styles.section}>
        <h2 className={styles.sectionHead}>
          {title}
          <span className={styles.sectionRule} aria-hidden />
        </h2>
        <div className={styles.muted}>无奖励数据</div>
      </section>
    );
  }
  return (
    <section id={id} className={styles.section}>
      <h2 className={styles.sectionHead}>
        {title}
        <span className={styles.sectionRule} aria-hidden />
      </h2>
      <div className={styles.rewardGrid}>
        {hasXp ? (
          <RewardCard title="经验">
            <RewardLine
              name="完成经验"
              value={`+${Number(experience).toLocaleString("zh-CN")} EXP`}
              accent
            />
          </RewardCard>
        ) : null}
        {rewards?.trader_standing?.length ? (
          <RewardCard title="商人声望">
            {rewards.trader_standing.map((row) => (
              <RewardLine
                key={`st-${row.id}`}
                href={row.slug ? tarkovTraderHref(row.slug) : undefined}
                name={traderDisplayName(row.slug, row.name || row.id)}
                value={`${row.standing > 0 ? "+" : ""}${row.standing}`}
                accent={row.standing > 0}
              />
            ))}
          </RewardCard>
        ) : null}
        {rewards?.items?.length ? (
          <RewardCard title="物品奖励">
            {rewards.items.map((item) => (
              <RewardLine
                key={`${item.id}-${item.count}`}
                href={itemHref(item)}
                icon={item.icon_link}
                name={namedLabel(item)}
                value={`×${item.count}`}
                accent={item.count > 1}
              />
            ))}
          </RewardCard>
        ) : null}
        {rewards?.offer_unlock?.length ? (
          <RewardCard title="解锁报价">
            {rewards.offer_unlock.map((row) => {
              const trader = row.trader;
              const item = row.item;
              const traderName = trader
                ? `${traderDisplayName(trader.slug, trader.name || trader.id)}${
                    row.level ? ` LL${row.level}` : ""
                  }`
                : "";
              return (
                <RewardLine
                  key={row.id || item?.id}
                  href={item ? itemHref(item) : trader?.slug ? tarkovTraderHref(trader.slug) : undefined}
                  icon={item?.icon_link}
                  name={
                    <>
                      {traderName}
                      {traderName && item ? " · " : ""}
                      {item ? namedLabel(item) : ""}
                    </>
                  }
                />
              );
            })}
          </RewardCard>
        ) : null}
        {rewards?.craft_unlock?.length ? (
          <RewardCard title="解锁制作">
            {rewards.craft_unlock.map((row) => {
              const station = row.station;
              const href = station?.slug ? tarkovHideoutHref(station.slug) : "";
              const stationName = namedLabel(station);
              return (
                <RewardLine
                  key={row.id || station?.id}
                  href={href || (row.item ? itemHref(row.item) : undefined)}
                  icon={row.item?.icon_link}
                  name={
                    <>
                      {stationName}
                      {row.level ? ` ${row.level} 级` : ""}
                      {stationName && row.item ? " · " : ""}
                      {row.item ? namedLabel(row.item) : ""}
                    </>
                  }
                />
              );
            })}
          </RewardCard>
        ) : null}
        {rewards?.trader_unlock?.length ? (
          <RewardCard title="解锁商人">
            {rewards.trader_unlock.map((row) => (
              <RewardLine
                key={row.id}
                href={row.slug ? tarkovTraderHref(row.slug) : undefined}
                name={
                  row.slug
                    ? traderDisplayName(row.slug, row.name || row.id)
                    : namedLabel(row)
                }
              />
            ))}
          </RewardCard>
        ) : null}
        {rewards?.skill_level_reward?.length ? (
          <RewardCard title="技能">
            {rewards.skill_level_reward.map((row) => (
              <RewardLine
                key={`${row.name}-${row.level}`}
                name={row.name}
                value={row.level ? `${row.level} 级` : undefined}
              />
            ))}
          </RewardCard>
        ) : null}
        {rewards?.achievement?.length ? (
          <RewardCard title="成就">
            {rewards.achievement.map((row) => (
              <RewardLine
                key={row.id}
                icon={row.image_link}
                name={namedLabel(row)}
              />
            ))}
          </RewardCard>
        ) : null}
        {rewards?.customization?.length ? (
          <RewardCard title="外观">
            {rewards.customization.map((row) => (
              <RewardLine
                key={row.id}
                icon={row.image_link}
                name={
                  <>
                    {namedLabel(row)}
                    {row.customization_type ? `（${row.customization_type}）` : ""}
                  </>
                }
              />
            ))}
          </RewardCard>
        ) : null}
      </div>
    </section>
  );
}

function FailSection({
  id,
  conditions,
  restartable,
}: {
  id?: string;
  conditions: FailCondition[];
  restartable: boolean;
}) {
  const chips = collectRaidPrepFailChips(conditions);
  const leftover = leftoverFailConditions(conditions);
  if (!chips.length && !leftover.length && !restartable) return null;
  return (
    <section id={id} className={styles.section}>
      <h2 className={styles.sectionHead}>
        失败条件
        <span className={styles.sectionRule} aria-hidden />
      </h2>
      <div className={styles.failBox}>
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
      </div>
    </section>
  );
}

/** 目标 → 关联任务 → 钥匙 / 奖励 / 失败，纵向铺在主栏。 */
export function TarkovTaskObjectivesRewards({
  detail,
  afterObjectives,
}: {
  detail: TarkovTaskDetail;
  afterObjectives?: ReactNode;
}) {
  const objectives = detail.objectives || [];
  const keys = detail.needed_keys || [];
  const start = detail.start_rewards;
  const showStart = rewardsHaveContent(start);

  return (
    <>
      <section id="task-objectives" className={styles.section}>
        <h2 className={styles.sectionHead}>
          目标
          {objectives.length ? (
            <span className={styles.sectionCount}>{objectives.length}</span>
          ) : null}
          <span className={styles.sectionRule} aria-hidden />
        </h2>
        {objectives.length ? (
          <div className={styles.objList}>
            {objectives.map((obj) => (
              <ObjectiveRow
                key={obj.id || obj.description}
                obj={obj}
                taskId={detail.id}
              />
            ))}
          </div>
        ) : (
          <div className={styles.muted}>无目标数据</div>
        )}
      </section>
      {afterObjectives}
      {keys.length ? (
        <section id="task-keys" className={styles.section}>
          <h2 className={styles.sectionHead}>
            所需钥匙
            <span className={styles.sectionRule} aria-hidden />
          </h2>
          <div className={styles.keys}>
            {keys.map((row, index) => (
              <div
                key={`${row.map?.id || "map"}-${index}`}
                className={styles.keyGroup}
              >
                <div className={styles.keyMap}>
                  <MapNameLink slug={row.map?.slug} name={row.map?.name} />
                </div>
                <div className={styles.itemGrid}>
                  {(row.keys || []).map((key) => (
                    <KeyLink key={key.id} item={key} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}
      {showStart ? (
        <RewardsBlock id="task-start-rewards" title="接取奖励" rewards={start} />
      ) : null}
      <RewardsBlock
        id="task-finish-rewards"
        title="完成奖励"
        rewards={detail.finish_rewards}
        experience={detail.experience}
      />
      {rewardsHaveContent(detail.fail_rewards) ? (
        <RewardsBlock
          id="task-fail-rewards"
          title="失败惩罚"
          rewards={detail.fail_rewards}
        />
      ) : null}
      <FailSection
        id="task-fail"
        conditions={detail.fail_conditions || []}
        restartable={Boolean(detail.restartable)}
      />
    </>
  );
}
