import { useEffect, useMemo, useState } from "react";
import { Modal, Popover, Tooltip } from "antd";
import { Link } from "react-router-dom";
import { itemDetailHref, itemHrefFromTypes } from "@/lib/tarkovItemTypes";
import { inventoryThumbUrl } from "@/lib/tarkovItemImages";
import {
  buildRaidPrepSummary,
  collectRaidPrepSummaryTypeColumns,
  colorForTaskId,
  colorForUserId,
  raidPrepSummaryColumnType,
  sortRaidPrepSummaryByParticipants,
  tarkovReadableName,
  type RaidPrepNeededItem,
  type RaidPrepTaskLike,
  type RaidPrepTaskSummary,
} from "@/lib/tarkovRaidPrep";
import {
  formatKeyBringHint,
  groupKeyBringsByItem,
  type RaidRoomKeyBringLike,
} from "@/lib/tarkovRaidRooms";
import {
  tarkovObjectiveTypeLabel,
  tarkovObjectiveTypeTone,
} from "@/lib/tarkovTaskObjective";
import { TarkovTraderThumb } from "@/components/guides/tarkov/TarkovTraderThumb";
import taskStyles from "./TarkovTasksPanel.module.css";
import styles from "./TarkovRaidPrepPanel.module.css";

function neededItemHref(item: RaidPrepNeededItem): string {
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

type KeyBringControls = {
  byItem: ReadonlyMap<string, { userIds: number[]; names: string[] }>;
  currentUserId?: number | null;
  canToggle: boolean;
  onToggle: (itemId: string) => void;
};

function NeededItemChip({
  item,
  onPeek,
  nativeTitle = true,
  keyBring,
}: {
  item: RaidPrepNeededItem;
  onPeek: (item: RaidPrepNeededItem) => void;
  nativeTitle?: boolean;
  keyBring?: KeyBringControls;
}) {
  const thumb = inventoryThumbUrl(item.icon_link, item.id);
  const count = item.count > 1 ? `×${item.count}` : "";
  const label =
    tarkovReadableName(item.name, item.id) ||
    (item.kind === "key" ? "未知钥匙" : "未知物品");
  const extra = [
    item.found_in_raid ? "战局内" : "",
    item.optional ? "可选" : "",
  ].filter(Boolean);
  const bringEnabled = Boolean(keyBring) && item.kind === "key";
  const group = bringEnabled ? keyBring?.byItem.get(item.id) : undefined;
  const names = group?.names || [];
  const mine = Boolean(
    bringEnabled &&
      keyBring?.currentUserId != null &&
      group?.userIds.includes(keyBring.currentUserId),
  );
  const canToggle = Boolean(bringEnabled && keyBring?.canToggle);
  const hint = bringEnabled
    ? formatKeyBringHint(names, { canToggle })
    : nativeTitle
      ? label
      : undefined;
  const chip = (
    <button
      type="button"
      className={[
        styles.needChip,
        names.length ? styles.needChipBrought : "",
        mine ? styles.needChipMine : "",
      ]
        .filter(Boolean)
        .join(" ")}
      title={bringEnabled ? undefined : nativeTitle ? label : undefined}
      aria-pressed={bringEnabled ? mine : undefined}
      aria-label={bringEnabled ? `${label}。${hint}` : undefined}
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
        {names.length ? (
          <span className={styles.needBringBy}>{names.join("、")}带了</span>
        ) : null}
      </span>
    </button>
  );
  if (!bringEnabled) return chip;
  return (
    <span className={styles.needChipWrap}>
      <Tooltip
        title={hint}
        mouseEnterDelay={0.12}
        mouseLeaveDelay={0.08}
        placement="topLeft"
        zIndex={1200}
      >
        {chip}
      </Tooltip>
    </span>
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

function NeededItemList({
  items,
  onPeek,
  keyBring,
}: {
  items: RaidPrepNeededItem[];
  onPeek: (item: RaidPrepNeededItem) => void;
  keyBring?: KeyBringControls;
}) {
  if (!items.length) return null;
  const chips = items.map((item) => (
    <NeededItemChip
      key={neededItemKey(item)}
      item={item}
      onPeek={onPeek}
      keyBring={keyBring}
    />
  ));
  if (items.length === 1) return chips;
  const rest = items.length - 1;
  return (
    <Popover
      trigger={["hover", "click"]}
      mouseEnterDelay={0.12}
      mouseLeaveDelay={0.18}
      placement="bottomLeft"
      zIndex={1100}
      rootClassName={styles.needMorePopover}
      content={<div className={styles.needMoreList}>{chips}</div>}
    >
      <div className={styles.needCollapsed}>
        <NeededItemChip
          item={items[0]}
          onPeek={onPeek}
          nativeTitle={false}
          keyBring={keyBring}
        />
        <button
          type="button"
          className={styles.needMore}
          aria-label={`其余 ${rest} 项，悬停查看全部`}
        >
          …
        </button>
      </div>
    </Popover>
  );
}

function TypeColumnCell({
  type,
  items,
  hasType,
  onPeek,
}: {
  type: string;
  items: RaidPrepNeededItem[];
  hasType: boolean;
  onPeek: (item: RaidPrepNeededItem) => void;
}) {
  if (items.length) {
    return (
      <div className={styles.needList} role="cell">
        <NeededItemList items={items} onPeek={onPeek} />
      </div>
    );
  }
  if (hasType) {
    return (
      <div className={styles.summaryTypeCell} role="cell">
        <span
          className={taskStyles.typeChip}
          data-tone={tarkovObjectiveTypeTone(type)}
        >
          {tarkovObjectiveTypeLabel(type)}
        </span>
      </div>
    );
  }
  return (
    <div role="cell">
      <span className={styles.summaryNone}>—</span>
    </div>
  );
}

const SUMMARY_FIXED_COLS =
  "minmax(108px, 160px) minmax(160px, 220px) minmax(140px, 200px)";

function summaryGridColumns(typeCount: number): string {
  if (typeCount <= 0) return SUMMARY_FIXED_COLS;
  return `${SUMMARY_FIXED_COLS} repeat(${typeCount}, minmax(148px, 1fr))`;
}

function SummaryList({
  rows,
  typeColumns,
  participantsByTask,
  onPeek,
  keyBring,
}: {
  rows: RaidPrepTaskSummary[];
  typeColumns: string[];
  participantsByTask?: ReadonlyMap<string, readonly RaidPrepParticipant[]>;
  onPeek: (item: RaidPrepNeededItem) => void;
  keyBring?: KeyBringControls;
}) {
  if (!rows.length) {
    return <div className={styles.summaryEmpty}>还没勾选任务</div>;
  }
  const gridTemplateColumns = summaryGridColumns(typeColumns.length);
  const typeSetByTask = new Map(
    rows.map((row) => [row.taskId, new Set(row.types)]),
  );
  return (
    <div className={styles.summaryScroll}>
      <div className={styles.summaryTable} role="table">
        <div
          className={`${styles.summaryRow} ${styles.summaryHead}`}
          role="row"
          style={{ gridTemplateColumns }}
        >
          <div role="columnheader">参与人员</div>
          <div className={styles.summaryTask} role="columnheader">
            任务名称
          </div>
          <div
            role="columnheader"
            title={
              keyBring
                ? "点击钥匙声明我带了，悬停查看谁带了"
                : undefined
            }
          >
            所需钥匙
          </div>
          {typeColumns.map((type) => (
            <div key={type} role="columnheader">
              <span
                className={taskStyles.typeChip}
                data-tone={tarkovObjectiveTypeTone(type)}
              >
                {tarkovObjectiveTypeLabel(type)}
              </span>
            </div>
          ))}
        </div>
        {rows.map((row) => {
          const typeSet = typeSetByTask.get(row.taskId) || new Set<string>();
          return (
            <div
              key={row.taskId}
              className={styles.summaryRow}
              role="row"
              style={{ gridTemplateColumns }}
            >
              <div role="cell">
                <ParticipantChips
                  people={participantsByTask?.get(row.taskId) || []}
                />
              </div>
              <div className={styles.summaryTask} role="cell">
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
                <span className={styles.summaryTaskName}>
                  <Tooltip
                    title={
                      <div className={styles.summaryObjHint}>
                        {row.objectiveLines.length ? (
                          row.objectiveLines.map((line) => (
                            <div key={line} className={styles.summaryObjLine}>
                              {line}
                            </div>
                          ))
                        ) : (
                          <div className={styles.summaryObjLine}>无目标数据</div>
                        )}
                      </div>
                    }
                    mouseEnterDelay={0.12}
                    mouseLeaveDelay={0.08}
                    placement="topLeft"
                    zIndex={1200}
                    rootClassName={styles.summaryObjTooltip}
                    overlayInnerStyle={{ maxWidth: "none" }}
                  >
                    <span className={styles.summaryTaskNameText}>
                      {row.taskName}
                    </span>
                  </Tooltip>
                </span>
              </div>
              <div className={styles.needList} role="cell">
                {row.keys.length ? (
                  <NeededItemList
                    items={row.keys}
                    onPeek={onPeek}
                    keyBring={keyBring}
                  />
                ) : (
                  <span className={styles.summaryNone}>无所需钥匙</span>
                )}
              </div>
              {typeColumns.map((type) => (
                <TypeColumnCell
                  key={type}
                  type={type}
                  items={row.itemsByType[type] || []}
                  hasType={[...typeSet].some(
                    (itemType) => raidPrepSummaryColumnType(itemType) === type,
                  )}
                  onPeek={onPeek}
                />
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function TarkovRaidPrepSummary({
  tasks,
  mapId,
  participantsByTask,
  keyBrings,
  currentUserId,
  canToggleKeyBring = false,
  onToggleKeyBring,
}: {
  tasks: RaidPrepTaskLike[];
  mapId: string;
  participantsByTask?: ReadonlyMap<string, readonly RaidPrepParticipant[]>;
  keyBrings?: readonly RaidRoomKeyBringLike[] | null;
  currentUserId?: number | null;
  canToggleKeyBring?: boolean;
  onToggleKeyBring?: (itemId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [peek, setPeek] = useState<RaidPrepNeededItem | null>(null);
  const rows = useMemo(() => {
    const built = buildRaidPrepSummary(tasks, mapId);
    return sortRaidPrepSummaryByParticipants(built, participantsByTask);
  }, [tasks, mapId, participantsByTask]);
  const typeColumns = useMemo(
    () => collectRaidPrepSummaryTypeColumns(rows),
    [rows],
  );
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
      currentUserId,
      canToggle: Boolean(canToggleKeyBring && onToggleKeyBring),
      onToggle: onToggleKeyBring || (() => undefined),
    };
  }, [keyBrings, currentUserId, canToggleKeyBring, onToggleKeyBring]);
  const itemCount = rows.reduce(
    (sum, row) =>
      sum +
      Object.values(row.itemsByType).reduce(
        (inner, items) => inner + items.length,
        0,
      ),
    0,
  );
  const keyCount = rows.reduce((sum, row) => sum + row.keys.length, 0);
  const meta = rows.length
    ? `已选 ${rows.length} · 物品 ${itemCount} · 钥匙 ${keyCount}`
    : "勾选任务后查看所需物品";

  return (
    <>
      <button
        type="button"
        className={styles.summary}
        onClick={() => setOpen(true)}
      >
        <span className={styles.summaryBtnText}>
          <span className={styles.summaryTitle}>准备内容总结</span>
          <span className={styles.summaryCount}>{meta}</span>
        </span>
        <span className={styles.summaryAction}>查看</span>
      </button>
      <Modal
        title="准备内容总结"
        open={open}
        onCancel={() => setOpen(false)}
        footer={null}
        width="min(1760px, calc(100vw - 32px))"
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
        <SummaryList
          rows={rows}
          typeColumns={typeColumns}
          participantsByTask={participantsByTask}
          onPeek={setPeek}
          keyBring={keyBring}
        />
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
