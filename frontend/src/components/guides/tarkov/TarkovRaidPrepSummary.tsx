import { useEffect, useMemo, useState } from "react";
import { Modal } from "antd";
import { Link } from "react-router-dom";
import { tarkovTaskHref } from "@/lib/tarkovHomeNav";
import { itemDetailHref, itemHrefFromTypes } from "@/lib/tarkovItemTypes";
import { inventoryThumbUrl } from "@/lib/tarkovItemImages";
import {
  buildRaidPrepSummary,
  colorForTaskId,
  colorForUserId,
  sortRaidPrepSummaryByParticipants,
  tarkovReadableName,
  type RaidPrepNeededItem,
  type RaidPrepTaskLike,
  type RaidPrepTaskSummary,
} from "@/lib/tarkovRaidPrep";
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

function NeededItemChip({ item }: { item: RaidPrepNeededItem }) {
  const thumb = inventoryThumbUrl(item.icon_link, item.id);
  const count = item.count > 1 ? `×${item.count}` : "";
  const label =
    tarkovReadableName(item.name, item.id) ||
    (item.kind === "key" ? "未知钥匙" : "未知物品");
  const extra = [
    item.found_in_raid ? "战局内" : "",
    item.optional ? "可选" : "",
  ].filter(Boolean);
  return (
    <Link
      className={styles.needChip}
      to={neededItemHref(item)}
      title={label}
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
      </span>
    </Link>
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

function SummaryList({
  rows,
  participantsByTask,
}: {
  rows: RaidPrepTaskSummary[];
  participantsByTask?: ReadonlyMap<string, readonly RaidPrepParticipant[]>;
}) {
  if (!rows.length) {
    return <div className={styles.summaryEmpty}>还没勾选任务</div>;
  }
  return (
    <div className={styles.summaryTable} role="table">
      <div className={`${styles.summaryRow} ${styles.summaryHead}`} role="row">
        <div role="columnheader">参与人员</div>
        <div className={styles.summaryTask} role="columnheader">
          任务名称
        </div>
        <div role="columnheader">所需钥匙</div>
        <div role="columnheader">所需物品</div>
        <div role="columnheader">类型</div>
      </div>
      {rows.map((row) => (
        <div key={row.taskId} className={styles.summaryRow} role="row">
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
            <Link
              className={styles.summaryTaskName}
              to={tarkovTaskHref(row.taskId)}
              title={row.taskName}
            >
              {row.taskName}
            </Link>
          </div>
          <div className={styles.needList} role="cell">
            {row.keys.length ? (
              row.keys.map((item) => (
                <NeededItemChip key={`key-${item.id}`} item={item} />
              ))
            ) : (
              <span className={styles.summaryNone}>无所需钥匙</span>
            )}
          </div>
          <div className={styles.needList} role="cell">
            {row.items.length ? (
              row.items.map((item) => (
                <NeededItemChip
                  key={`${item.kind}-${item.id}-${item.role}-${item.found_in_raid ? "fir" : "stash"}-${item.optional ? "opt" : "req"}`}
                  item={item}
                />
              ))
            ) : (
              <span className={styles.summaryNone}>无所需物品</span>
            )}
          </div>
          <div className={styles.summaryTypes} role="cell">
            {row.types.length ? (
              row.types.map((type) => (
                <span
                  key={type}
                  className={taskStyles.typeChip}
                  data-tone={tarkovObjectiveTypeTone(type)}
                >
                  {tarkovObjectiveTypeLabel(type)}
                </span>
              ))
            ) : (
              <span className={styles.summaryNone}>—</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export function TarkovRaidPrepSummary({
  tasks,
  mapId,
  participantsByTask,
}: {
  tasks: RaidPrepTaskLike[];
  mapId: string;
  participantsByTask?: ReadonlyMap<string, readonly RaidPrepParticipant[]>;
}) {
  const [open, setOpen] = useState(false);
  const rows = useMemo(() => {
    const built = buildRaidPrepSummary(tasks, mapId);
    return sortRaidPrepSummaryByParticipants(built, participantsByTask);
  }, [tasks, mapId, participantsByTask]);
  const itemCount = rows.reduce((sum, row) => sum + row.items.length, 0);
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
        width={1320}
        classNames={{ body: styles.summaryModalBody }}
      >
        <p className={styles.summaryModalLead}>{meta}</p>
        <SummaryList rows={rows} participantsByTask={participantsByTask} />
      </Modal>
    </>
  );
}
