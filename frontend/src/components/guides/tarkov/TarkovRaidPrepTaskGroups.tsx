import type { ReactNode } from "react";
import {
  RAID_PREP_ACTIVE_MAP_GROUP_LABELS,
  RAID_PREP_LIST_SCOPE_LABELS,
  RAID_PREP_PROGRESS_STATUSES,
  splitRaidPrepRowsByCurrentMap,
  type RaidPrepTaskProgressStatus,
} from "@/lib/tarkovRaidPrep";
import styles from "./TarkovRaidPrepPanel.module.css";

type Row = { id: string; on_this_map?: boolean };

type Props<T extends Row> = {
  groups: Record<RaidPrepTaskProgressStatus, readonly T[]>;
  renderRow: (row: T, index: number) => ReactNode;
  empty?: ReactNode;
};

function ActiveMapGroups<T extends Row>({
  rows,
  renderRow,
}: {
  rows: readonly T[];
  renderRow: (row: T, index: number) => ReactNode;
}) {
  const { onMap, offMap } = splitRaidPrepRowsByCurrentMap(rows);
  const blocks: Array<{
    key: keyof typeof RAID_PREP_ACTIVE_MAP_GROUP_LABELS;
    rows: readonly T[];
  }> = [];
  if (onMap.length) blocks.push({ key: "onMap", rows: onMap });
  if (offMap.length) blocks.push({ key: "offMap", rows: offMap });
  return (
    <>
      {blocks.map((block) => (
        <div key={block.key} className={styles.taskSubGroup}>
          <p
            className={styles.taskSubGroupLabel}
            data-map={block.key === "onMap" ? "on" : "off"}
          >
            {RAID_PREP_ACTIVE_MAP_GROUP_LABELS[block.key]} {block.rows.length}
          </p>
          {block.rows.map((row, index) => renderRow(row, index))}
        </div>
      ))}
    </>
  );
}

export function TarkovRaidPrepTaskGroups<T extends Row>({
  groups,
  renderRow,
  empty,
}: Props<T>) {
  const visible = RAID_PREP_PROGRESS_STATUSES.filter(
    (status) => groups[status].length,
  );
  if (!visible.length) return <>{empty}</>;
  return (
    <>
      {visible.map((status) => (
        <div key={status} className={styles.taskGroup}>
          <p className={styles.taskGroupLabel} data-status={status}>
            {RAID_PREP_LIST_SCOPE_LABELS[status]} {groups[status].length}
          </p>
          {status === "active" ? (
            <ActiveMapGroups rows={groups[status]} renderRow={renderRow} />
          ) : (
            groups[status].map((row, index) => renderRow(row, index))
          )}
        </div>
      ))}
    </>
  );
}
