import { Component, useEffect, useMemo, useState, type ErrorInfo, type ReactNode } from "react";
import { Modal, Popover, Tooltip } from "antd";
import { Link } from "react-router-dom";
import {
  itemDetailHref,
  itemHrefFromTypes,
  itemTypeHrefFromTypes,
} from "@/lib/tarkovItemTypes";
import { inventoryThumbUrl } from "@/lib/tarkovItemImages";
import {
  buildRaidPrepSummary,
  collectRaidPrepBringKit,
  collectRaidPrepCompletedUsers,
  collectRaidPrepSummaryTypeColumns,
  raidPrepTaskIdsForParticipant,
  colorForTaskId,
  colorForUserId,
  expandRaidPrepSummaryItemLines,
  isRaidPrepSummaryBringType,
  isRaidPrepSummaryShootType,
  RAID_PREP_SUMMARY_BRING_GROUP_LABEL,
  RAID_PREP_SUMMARY_BRING_TYPES,
  RAID_PREP_SUMMARY_SHOOT_TYPE,
  raidPrepKeyIsMissing,
  raidPrepSkippedIds,
  raidPrepTaskKeysUnavailable,
  RAID_PREP_UNAVAILABLE_KEY_HINT,
  raidPrepSummaryHasBringTypes,
  raidPrepSummaryHasShootTypes,
  skipMapToObjectiveDones,
  sortRaidPrepSummaryByParticipants,
  tarkovReadableName,
  type RaidPrepNeededItem,
  type RaidPrepObjectiveDoneLike,
  type RaidPrepSkipMap,
  type RaidPrepSummaryShootSlot,
  type RaidPrepTaskLike,
  type RaidPrepTaskSummary,
} from "@/lib/tarkovRaidPrep";
import {
  formatKeyChipHint,
  formatKeyOwnHint,
  formatKeyOwnToggleLabel,
  groupKeyBringsByItem,
  type RaidRoomKeyBringLike,
} from "@/lib/tarkovRaidRooms";
import {
  tarkovObjectiveTypeLabel,
  tarkovObjectiveTypeTone,
} from "@/lib/tarkovTaskObjective";
import { TarkovTraderThumb } from "@/components/guides/tarkov/TarkovTraderThumb";
import { TarkovRaidPrepObjectiveHint } from "@/components/guides/tarkov/TarkovRaidPrepObjectiveHint";
import taskStyles from "./TarkovTasksPanel.module.css";
import styles from "./TarkovRaidPrepPanel.module.css";

class SummaryRenderError extends Component<
  { children: ReactNode },
  { message: string }
> {
  state = { message: "" };

  static getDerivedStateFromError(error: Error) {
    return { message: error.message || "总结表渲染失败" };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("raid prep summary", error, info.componentStack);
  }

  render() {
    if (this.state.message) {
      return (
        <div className={styles.summaryEmpty}>
          总结表打不开：{this.state.message}
        </div>
      );
    }
    return this.props.children;
  }
}

function neededItemHref(item: RaidPrepNeededItem): string {
  if (item.anyOf?.length) {
    const typeHref = itemTypeHrefFromTypes(item.types);
    if (typeHref) return typeHref;
    const first = item.anyOf[0];
    if (first) return itemHrefFromTypes(first.id, first.types);
  }
  if (item.kind === "key") return itemDetailHref("keys", item.id);
  if (item.types.length) return itemHrefFromTypes(item.id, item.types);
  return itemDetailHref("quest-items", item.id);
}

function NeededItemThumb({
  src,
  itemId,
}: {
  src: string;
  itemId: string;
}) {
  const preferred = inventoryThumbUrl(src, itemId);
  const [current, setCurrent] = useState(preferred);
  useEffect(() => {
    setCurrent(preferred);
  }, [preferred]);
  if (!current) return null;
  return (
    <span className={styles.needIcon}>
      <img src={current} alt="" onError={() => setCurrent("")} />
    </span>
  );
}

function neededItemKey(item: RaidPrepNeededItem): string {
  return `${item.kind}-${item.id}-${item.objectiveType}-${item.found_in_raid ? "fir" : "stash"}-${item.optional ? "opt" : "req"}`;
}

type KeyNameGroup = { userIds: number[]; names: string[] };

type KeyBringControls = {
  byItem: ReadonlyMap<string, KeyNameGroup>;
  currentUserId?: number | null;
  canToggle: boolean;
  onToggle: (itemId: string) => void;
};

type KeyOwnControls = {
  byItem: ReadonlyMap<string, KeyNameGroup>;
  currentUserId?: number | null;
  canToggle: boolean;
  onToggle: (itemId: string) => void;
};

function NeededItemChip({
  item,
  onPeek,
  nativeTitle = true,
  hideName = false,
  keyBring,
  keyOwn,
}: {
  item: RaidPrepNeededItem;
  onPeek: (item: RaidPrepNeededItem) => void;
  nativeTitle?: boolean;
  hideName?: boolean;
  keyBring?: KeyBringControls;
  keyOwn?: KeyOwnControls;
}) {
  if (item.anyOf?.length) {
    return (
      <AnyOfChip
        item={item}
        onPeek={onPeek}
        hideName={hideName}
        keyBring={keyBring}
        keyOwn={keyOwn}
      />
    );
  }
  const thumb = inventoryThumbUrl(item.icon_link, item.id);
  const count = item.kind === "key" ? "" : item.count > 1 ? `×${item.count}` : "";
  const label =
    tarkovReadableName(item.name, item.id) ||
    (item.kind === "key" ? "未知钥匙" : "未知物品");
  const extra = [
    item.found_in_raid ? "战局内" : "",
    item.optional ? "可选" : "",
  ].filter(Boolean);
  const isKey = item.kind === "key";
  const bringEnabled = Boolean(keyBring) && isKey;
  const group = bringEnabled ? keyBring?.byItem.get(item.id) : undefined;
  const names = group?.names || [];
  const ownNames = isKey ? keyOwn?.byItem.get(item.id)?.names || [] : [];
  const mine = Boolean(
    bringEnabled &&
      keyBring?.currentUserId != null &&
      group?.userIds.includes(keyBring.currentUserId),
  );
  const iOwn = Boolean(
    isKey &&
      keyOwn?.currentUserId != null &&
      keyOwn.byItem.get(item.id)?.userIds.includes(keyOwn.currentUserId),
  );
  const canToggle = Boolean(bringEnabled && keyBring?.canToggle);
  const canToggleOwn = Boolean(isKey && keyOwn?.canToggle);
  const hint = bringEnabled
    ? formatKeyChipHint(ownNames, names, { canToggle })
    : ownNames.length
      ? formatKeyOwnHint(ownNames)
      : nativeTitle
        ? label
        : undefined;
  const missing = isKey && raidPrepKeyIsMissing(ownNames, names);
  const ownLabel = formatKeyOwnToggleLabel(iOwn);
  const chip = (
    <button
      type="button"
      className={[
        styles.needChip,
        ownNames.length ? styles.needChipOwned : "",
        names.length ? styles.needChipBrought : "",
        mine ? styles.needChipMine : "",
        missing ? styles.needChipMissing : "",
        canToggleOwn ? styles.needChipSplit : "",
      ]
        .filter(Boolean)
        .join(" ")}
      title={
        bringEnabled || ownNames.length
          ? undefined
          : nativeTitle
            ? label
            : undefined
      }
      aria-pressed={bringEnabled ? mine : undefined}
      aria-label={
        bringEnabled || ownNames.length ? `${label}。${hint}` : undefined
      }
      onClick={(event) => {
        event.stopPropagation();
        if (bringEnabled && canToggle && keyBring && !event.shiftKey) {
          keyBring.onToggle(item.id);
          return;
        }
        onPeek(item);
      }}
    >
      {thumb ? (
        <NeededItemThumb src={item.icon_link} itemId={item.id} />
      ) : null}
      <span className={styles.needBody}>
        <span className={styles.needName}>
          {label}
          {count ? ` ${count}` : ""}
        </span>
        {extra.length ? (
          <span className={styles.needMeta}>{extra.join(" · ")}</span>
        ) : null}
        {ownNames.length ? (
          <span className={styles.needOwnBy}>{ownNames.join("、")}拥有</span>
        ) : null}
        {names.length ? (
          <span className={styles.needBringBy}>{names.join("、")}带了</span>
        ) : null}
      </span>
    </button>
  );
  const ownBtn = canToggleOwn ? (
    <button
      type="button"
      className={`${styles.needOwnToggle} ${iOwn ? styles.needOwnToggleOn : ""}`}
      aria-pressed={iOwn}
      aria-label={
        iOwn ? "从钥匙管理去掉这把钥匙" : "记到钥匙管理：我有这把钥匙"
      }
      title={iOwn ? "从钥匙管理去掉" : "记到钥匙管理"}
      onClick={(event) => {
        event.stopPropagation();
        keyOwn?.onToggle(item.id);
      }}
    >
      {ownLabel}
    </button>
  ) : null;
  const wrapClass = ownBtn ? styles.needChipCluster : styles.needChipWrap;
  if (!bringEnabled && !ownNames.length && !missing && !ownBtn) return chip;
  if (missing) {
    return (
      <span className={wrapClass}>
        <Tooltip
          title="没人拥有这把钥匙"
          overlayInnerStyle={{ whiteSpace: "pre-line" }}
          mouseEnterDelay={0.12}
          placement="topLeft"
          zIndex={1200}
        >
          {chip}
        </Tooltip>
        {ownBtn}
      </span>
    );
  }
  return (
    <span className={wrapClass}>
      <Tooltip
        title={hint}
        overlayInnerStyle={{ whiteSpace: "pre-line" }}
        mouseEnterDelay={0.12}
        mouseLeaveDelay={0.08}
        placement="topLeft"
        zIndex={1200}
      >
        {chip}
      </Tooltip>
      {ownBtn}
    </span>
  );
}

function AnyOfChip({
  item,
  onPeek,
  hideName = false,
  keyBring,
  keyOwn,
}: {
  item: RaidPrepNeededItem;
  onPeek: (item: RaidPrepNeededItem) => void;
  hideName?: boolean;
  keyBring?: KeyBringControls;
  keyOwn?: KeyOwnControls;
}) {
  const options = item.anyOf || [];
  const qty = item.count > 1 ? ` ×${item.count}` : "";
  const extra = [
    item.found_in_raid ? "战局内" : "",
    item.optional ? "可选" : "",
  ].filter(Boolean);
  const label = tarkovReadableName(item.name, item.id) || "物品";
  const chip = (
    <button
      type="button"
      className={`${styles.needChip} ${styles.needAnyOf}`}
      aria-label={`${label}${qty}，共 ${options.length} 种`}
    >
      <span className={styles.needAnyOfIcons}>
        {options.slice(0, 3).map((opt) => (
          <NeededItemThumb
            key={opt.id}
            src={opt.icon_link}
            itemId={opt.id}
          />
        ))}
      </span>
      <span className={styles.needBody}>
        {hideName ? null : (
          <span className={styles.needName}>
            {label}
            {qty}
          </span>
        )}
        <span className={styles.needMeta}>
          {hideName && qty ? `${qty.trim()} · ` : ""}
          {options.length} 种
          {extra.length ? ` · ${extra.join(" · ")}` : ""}
        </span>
      </span>
    </button>
  );
  return (
    <Popover
      trigger={["hover", "click"]}
      mouseEnterDelay={0.12}
      mouseLeaveDelay={0.18}
      placement="bottomLeft"
      zIndex={1100}
      rootClassName={styles.needMorePopover}
      content={
        <div className={styles.needMoreList}>
          {options.map((opt) => (
            <NeededItemChip
              key={neededItemKey(opt)}
              item={opt}
              onPeek={onPeek}
              keyBring={keyBring}
              keyOwn={keyOwn}
            />
          ))}
        </div>
      }
    >
      {chip}
    </Popover>
  );
}

export type RaidPrepParticipant = {
  name: string;
  userId?: number;
};

function ParticipantChips({
  people,
}: {
  people: readonly RaidPrepParticipant[];
}) {
  if (!people.length) {
    return <span className={styles.summaryNone}>—</span>;
  }
  return (
    <div className={styles.summaryPeople}>
      {people.map((person, index) => (
        <span
          key={`${person.userId ?? person.name}-${index}`}
          className={styles.summaryPerson}
          title={person.name}
        >
          <span
            className={styles.memberDot}
            style={{
              background:
                person.userId != null
                  ? colorForUserId(person.userId)
                  : colorForTaskId(person.name),
            }}
          />
          <span className={styles.summaryPersonName}>{person.name}</span>
        </span>
      ))}
    </div>
  );
}

function TypeChip({ type }: { type: string }) {
  return (
    <span
      className={taskStyles.typeChip}
      data-tone={tarkovObjectiveTypeTone(type)}
    >
      {tarkovObjectiveTypeLabel(type)}
    </span>
  );
}

function typeHead(type: string) {
  return <TypeChip type={type} />;
}

function BringTypesHead() {
  return (
    <span className={styles.summaryBringTypeHead}>
      {RAID_PREP_SUMMARY_BRING_TYPES.map((type, index) => (
        <span key={type} className={styles.summaryBringTypeHeadItem}>
          {index > 0 ? (
            <span className={styles.summaryBringSlash} aria-hidden="true">
              /
            </span>
          ) : null}
          {typeHead(type)}
        </span>
      ))}
    </span>
  );
}

function BringSlotCell({
  slot,
  onPeek,
  className,
}: {
  slot: { type: string; item?: RaidPrepNeededItem } | null;
  onPeek: (item: RaidPrepNeededItem) => void;
  className?: string;
}) {
  if (slot?.item) {
    return (
      <td className={className}>
        <span className={styles.bringItem}>
          {typeHead(slot.type)}
          <NeededItemChip item={slot.item} onPeek={onPeek} />
        </span>
      </td>
    );
  }
  if (slot) {
    return (
      <td className={className}>
        <div className={styles.summaryTypeCell}>{typeHead(slot.type)}</div>
      </td>
    );
  }
  return (
    <td className={className}>
      <span className={styles.summaryNone}>—</span>
    </td>
  );
}

function ShootSlotCell({
  slot,
  onPeek,
}: {
  slot: RaidPrepSummaryShootSlot | null;
  onPeek: (item: RaidPrepNeededItem) => void;
}) {
  if (!slot) {
    return (
      <td className={styles.summaryShootCol}>
        <span className={styles.summaryNone}>—</span>
      </td>
    );
  }
  const chips = slot.items.filter((item) => !item.anyOf);
  return (
    <td className={styles.summaryShootCol}>
      <div className={styles.summaryShootSlot}>
        {chips.length ? (
          <div className={styles.summaryShootItems}>
            {chips.map((item) => (
              <NeededItemChip
                key={neededItemKey(item)}
                item={item}
                onPeek={onPeek}
              />
            ))}
          </div>
        ) : null}
        <span className={styles.summaryShootText}>
          {slot.text}
          {slot.count > 1 ? (
            <span className={styles.summaryShootCount}> ×{slot.count}</span>
          ) : null}
        </span>
      </div>
    </td>
  );
}

function ItemOrEmptyCell({
  item,
  onPeek,
  className,
  empty,
  keyBring,
  keyOwn,
}: {
  item: RaidPrepNeededItem | null;
  onPeek: (item: RaidPrepNeededItem) => void;
  className?: string;
  empty?: string;
  keyBring?: KeyBringControls;
  keyOwn?: KeyOwnControls;
}) {
  if (item) {
    return (
      <td className={className}>
        <NeededItemChip
          item={item}
          onPeek={onPeek}
          keyBring={keyBring}
          keyOwn={keyOwn}
        />
      </td>
    );
  }
  return (
    <td className={className}>
      <span className={styles.summaryNone}>{empty || "—"}</span>
    </td>
  );
}

function bringColClass(index: number, count: number): string {
  return [
    styles.summaryBringCol,
    index === 0 ? styles.summaryBringColFirst : "",
    index === count - 1 ? styles.summaryBringColLast : "",
  ]
    .filter(Boolean)
    .join(" ");
}

function SummaryList({
  rows,
  typeColumns,
  participantsByTask,
  completedByTask,
  onPeek,
  keyBring,
  keyOwn,
  skippedByTask,
  doneTaskIds,
  onToggleObjective,
  onTitle,
  viewerId,
}: {
  rows: RaidPrepTaskSummary[];
  typeColumns: string[];
  participantsByTask?: ReadonlyMap<string, readonly RaidPrepParticipant[]>;
  completedByTask?: ReadonlyMap<string, readonly RaidPrepParticipant[]>;
  onPeek: (item: RaidPrepNeededItem) => void;
  keyBring?: KeyBringControls;
  keyOwn?: KeyOwnControls;
  skippedByTask?: RaidPrepSkipMap;
  doneTaskIds?: ReadonlySet<string> | readonly string[] | null;
  onToggleObjective?: (taskId: string, objectiveId: string) => void;
  onTitle?: (taskId: string) => void;
  viewerId?: number | null;
}) {
  const doneIdSet = doneTaskIds instanceof Set ? doneTaskIds : new Set(doneTaskIds || []);
  const bringKit = collectRaidPrepBringKit(
    rows,
    raidPrepTaskIdsForParticipant(participantsByTask, viewerId),
  );
  if (!rows.length) {
    return <div className={styles.summaryEmpty}>还没勾选任务</div>;
  }
  const restTypeColumns = typeColumns.filter(
    (type) =>
      !isRaidPrepSummaryBringType(type) && !isRaidPrepSummaryShootType(type),
  );
  const showBringTypes = raidPrepSummaryHasBringTypes(rows, typeColumns);
  const showShootTypes = raidPrepSummaryHasShootTypes(rows);
  const bringSpan = 1 + (showBringTypes ? 1 : 0);
  const availableKeyIds = new Set<string>();
  if (keyOwn) {
    for (const [id, group] of keyOwn.byItem) {
      if (group.names.length) availableKeyIds.add(id);
    }
  }
  if (keyBring) {
    for (const [id, group] of keyBring.byItem) {
      if (group.names.length) availableKeyIds.add(id);
    }
  }
  return (
    <div className={styles.summaryBody}>
      <div className={styles.summaryKit}>
        <span className={styles.summaryKitLabel}>你要准备的东西：</span>
        {bringKit.length ? (
          <div className={styles.summaryKitList}>
            {bringKit.map((item) => (
              <NeededItemChip
                key={neededItemKey(item)}
                item={item}
                onPeek={onPeek}
                nativeTitle={false}
                hideName={Boolean(item.anyOf?.length)}
              />
            ))}
          </div>
        ) : (
          <span className={styles.summaryKitEmpty}>
            没有要带进战局的藏匿 / 标记 / 使用物
          </span>
        )}
      </div>
      <div className={styles.summaryScroll}>
      <table className={styles.summaryTable}>
        <thead>
          <tr>
            <th rowSpan={2}>参与人员</th>
            <th rowSpan={2}>任务名称</th>
            <th
              className={styles.summaryBringGroup}
              colSpan={bringSpan}
              title="钥匙、藏匿物、标记物、使用物：从保险箱带进战局"
            >
              {RAID_PREP_SUMMARY_BRING_GROUP_LABEL}
            </th>
            {restTypeColumns.map((type) => (
              <th key={type} rowSpan={2}>
                {typeHead(type)}
              </th>
            ))}
            {showShootTypes ? (
              <th rowSpan={2}>{typeHead(RAID_PREP_SUMMARY_SHOOT_TYPE)}</th>
            ) : null}
            <th
              rowSpan={2}
              title="必做步骤全部勾完的人（逐步进度见悬停任务名）"
            >
              已完成
            </th>
          </tr>
          <tr>
            <th
              className={`${styles.summaryBringHead} ${bringColClass(0, bringSpan)}`}
              title={
                keyBring
                  ? "点击钥匙声明我带了；总结会提示谁拥有、谁带了"
                  : "悬停查看谁拥有这把钥匙"
              }
            >
              <span className={taskStyles.typeChip} data-tone="key">
                钥匙
              </span>
            </th>
            {showBringTypes ? (
              <th
                className={`${styles.summaryBringHead} ${bringColClass(1, bringSpan)}`}
              >
                <BringTypesHead />
              </th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {rows.flatMap((row) => {
            const grid = expandRaidPrepSummaryItemLines(
              row,
              restTypeColumns,
              showBringTypes,
              showShootTypes,
            );
            const noKeys = !(row.keys || []).length;
            const unavailable = raidPrepTaskKeysUnavailable(
              row.keys,
              availableKeyIds,
            );
            return grid.lines.map((line, index) => (
              <tr
                key={`${row.taskId}-${index}`}
                className={
                  index < grid.lines.length - 1
                    ? styles.summaryTaskCont
                    : undefined
                }
              >
                <td>
                  {index === 0 ? (
                    <ParticipantChips
                      people={participantsByTask?.get(row.taskId) || []}
                    />
                  ) : (
                    <span className={styles.summaryNone}> </span>
                  )}
                </td>
                <td>
                  {index === 0 ? (
                    <div className={styles.summaryTask}>
                      <span
                        className={styles.swatch}
                        style={{ background: colorForTaskId(row.taskId) }}
                      />
                      {row.traderSlug ? (
                        <TarkovTraderThumb
                          slug={row.traderSlug}
                          size={22}
                          title={row.traderName || row.traderSlug}
                        />
                      ) : null}
                      <span
                        className={`${styles.summaryTaskName}${
                          row.mapComplete ? ` ${styles.summaryTaskNameDone}` : ""
                        }`}
                      >
                        <TarkovRaidPrepObjectiveHint
                          taskName={row.taskName}
                          traderSlug={row.traderSlug}
                          traderName={row.traderName}
                          objectives={row.objectives || []}
                          otherMapGroups={row.otherMapGroups}
                          skipped={raidPrepSkippedIds(skippedByTask, row.taskId)}
                          taskDone={doneIdSet.has(row.taskId)}
                          onToggle={
                            onToggleObjective
                              ? (objectiveId) =>
                                  onToggleObjective(row.taskId, objectiveId)
                              : undefined
                          }
                          placement="topLeft"
                          trigger={onTitle ? ["hover"] : ["hover", "click"]}
                        >
                          {onTitle ? (
                            <button
                              type="button"
                              className={styles.summaryTaskNameText}
                              onClick={(event) => {
                                event.stopPropagation();
                                onTitle(row.taskId);
                              }}
                            >
                              {row.taskName}
                            </button>
                          ) : (
                            <span className={styles.summaryTaskNameText}>
                              {row.taskName}
                            </span>
                          )}
                        </TarkovRaidPrepObjectiveHint>
                        {unavailable ? (
                          <Tooltip
                            title={RAID_PREP_UNAVAILABLE_KEY_HINT}
                            mouseEnterDelay={0.12}
                            placement="top"
                            zIndex={1200}
                          >
                            <button
                              type="button"
                              className={styles.summaryKeyWhy}
                              aria-label={RAID_PREP_UNAVAILABLE_KEY_HINT}
                              onClick={(event) => event.stopPropagation()}
                            >
                              ?
                            </button>
                          </Tooltip>
                        ) : null}
                      </span>
                    </div>
                  ) : (
                    <span className={styles.summaryNone}> </span>
                  )}
                </td>
                <ItemOrEmptyCell
                  item={line.key}
                  onPeek={onPeek}
                  keyBring={keyBring}
                  keyOwn={keyOwn}
                  empty={index === 0 && noKeys ? "无所需钥匙" : "—"}
                  className={bringColClass(0, bringSpan)}
                />
                {showBringTypes ? (
                  <BringSlotCell
                    slot={line.bring}
                    onPeek={onPeek}
                    className={bringColClass(1, bringSpan)}
                  />
                ) : null}
                {restTypeColumns.map((type) => (
                  <ItemOrEmptyCell
                    key={type}
                    item={line.rest[type] ?? null}
                    onPeek={onPeek}
                  />
                ))}
                {showShootTypes ? (
                  <ShootSlotCell slot={line.shoot} onPeek={onPeek} />
                ) : null}
                <td>
                  {index === 0 ? (
                    <ParticipantChips
                      people={completedByTask?.get(row.taskId) || []}
                    />
                  ) : (
                    <span className={styles.summaryNone}> </span>
                  )}
                </td>
              </tr>
            ));
          })}
        </tbody>
      </table>
      </div>
    </div>
  );
}

export function TarkovRaidPrepSummary({
  tasks,
  mapId,
  participantsByTask,
  keyBrings,
  keyOwns,
  currentUserId,
  canToggleKeyBring = false,
  onToggleKeyBring,
  canToggleKeyOwn = false,
  onToggleKeyOwn,
  skippedByTask,
  doneTaskIds,
  objectiveDones,
  currentUser,
  onToggleObjective,
  onTitle,
}: {
  tasks: RaidPrepTaskLike[];
  mapId: string;
  participantsByTask?: ReadonlyMap<string, readonly RaidPrepParticipant[]>;
  keyBrings?: readonly RaidRoomKeyBringLike[] | null;
  keyOwns?: readonly RaidRoomKeyBringLike[] | null;
  currentUserId?: number | null;
  canToggleKeyBring?: boolean;
  onToggleKeyBring?: (itemId: string) => void;
  canToggleKeyOwn?: boolean;
  onToggleKeyOwn?: (itemId: string) => void;
  skippedByTask?: RaidPrepSkipMap;
  doneTaskIds?: ReadonlySet<string> | readonly string[] | null;
  objectiveDones?: readonly RaidPrepObjectiveDoneLike[] | null;
  currentUser?: { userId: number; name: string } | null;
  onToggleObjective?: (taskId: string, objectiveId: string) => void;
  onTitle?: (taskId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [peek, setPeek] = useState<RaidPrepNeededItem | null>(null);
  const rows = useMemo(() => {
    if (!open) return [];
    const built = buildRaidPrepSummary(tasks, mapId, skippedByTask);
    return sortRaidPrepSummaryByParticipants(built, participantsByTask);
  }, [open, tasks, mapId, participantsByTask, skippedByTask]);
  const completedByTask = useMemo(() => {
    if (!open) return new Map();
    const dones =
      objectiveDones ??
      (currentUser
        ? skipMapToObjectiveDones(skippedByTask, currentUser)
        : []);
    return collectRaidPrepCompletedUsers(tasks, mapId, dones);
  }, [open, tasks, mapId, objectiveDones, skippedByTask, currentUser]);
  const typeColumns = useMemo(
    () => (open ? collectRaidPrepSummaryTypeColumns(rows) : []),
    [open, rows],
  );
  const viewerId = currentUserId ?? currentUser?.userId ?? null;
  const keyBring = useMemo<KeyBringControls | undefined>(() => {
    if (!onToggleKeyBring && !keyBrings?.length) return undefined;
    const byItem = new Map<string, { userIds: number[]; names: string[] }>();
    for (const group of groupKeyBringsByItem(keyBrings)) {
      byItem.set(group.itemId, {
        userIds: group.userIds,
        names: group.names,
      });
    }
    return {
      byItem,
      currentUserId: viewerId,
      canToggle: Boolean(canToggleKeyBring && onToggleKeyBring),
      onToggle: onToggleKeyBring || (() => undefined),
    };
  }, [keyBrings, viewerId, canToggleKeyBring, onToggleKeyBring]);
  const keyOwn = useMemo<KeyOwnControls | undefined>(() => {
    if (!onToggleKeyOwn && !keyOwns?.length) return undefined;
    const byItem = new Map<string, KeyNameGroup>();
    for (const group of groupKeyBringsByItem(keyOwns)) {
      byItem.set(group.itemId, {
        userIds: group.userIds,
        names: group.names,
      });
    }
    return {
      byItem,
      currentUserId: viewerId,
      canToggle: Boolean(canToggleKeyOwn && onToggleKeyOwn),
      onToggle: onToggleKeyOwn || (() => undefined),
    };
  }, [keyOwns, viewerId, canToggleKeyOwn, onToggleKeyOwn]);
  return (
    <>
      <button
        type="button"
        className={styles.summary}
        onClick={() => setOpen(true)}
      >
        <span className={styles.summaryBtnText}>
          <span className={styles.summaryTitle}>准备内容总结</span>
          {tasks.length ? null : (
            <span className={styles.summaryCount}>勾选任务后查看所需物品</span>
          )}
        </span>
        <span className={styles.summaryAction}>查看</span>
      </button>
      <Modal
        title="准备内容总结"
        open={open}
        onCancel={() => setOpen(false)}
        footer={null}
        width="fit-content"
        centered
        className={styles.summaryModal}
        classNames={{
          body: styles.summaryModalBody,
          content: styles.summaryModalContent,
          wrapper: styles.summaryModalWrap,
        }}
        styles={{
          wrapper: { overflow: "hidden" },
          body: { maxHeight: "none", paddingTop: 0 },
        }}
      >
        <SummaryRenderError>
          <SummaryList
            rows={rows}
            typeColumns={typeColumns}
            participantsByTask={participantsByTask}
            completedByTask={completedByTask}
            onPeek={setPeek}
            keyBring={keyBring}
            keyOwn={keyOwn}
            skippedByTask={skippedByTask}
            doneTaskIds={doneTaskIds}
            onToggleObjective={onToggleObjective}
            onTitle={
              onTitle
                ? (taskId) => {
                    setOpen(false);
                    onTitle(taskId);
                  }
                : undefined
            }
            viewerId={viewerId}
          />
        </SummaryRenderError>
      </Modal>
      <Modal
        title={
          peek
            ? tarkovReadableName(peek.name, peek.id) ||
              (peek.kind === "key" ? "钥匙" : "物品")
            : "物品"
        }
        open={Boolean(peek)}
        onCancel={() => setPeek(null)}
        footer={
          peek ? (
            <Link className={styles.needChip} to={neededItemHref(peek)}>
              在图鉴打开
            </Link>
          ) : null
        }
        width={420}
      >
        {peek ? (
          <p className={styles.summaryModalLead}>
            {[
              peek.count > 1 ? `数量 ${peek.count}` : "",
              peek.found_in_raid ? "战局内找到" : "",
              peek.optional ? "可选" : "",
            ]
              .filter(Boolean)
              .join(" · ") || "点下方按钮打开图鉴详情。"}
          </p>
        ) : null}
      </Modal>
    </>
  );
}
