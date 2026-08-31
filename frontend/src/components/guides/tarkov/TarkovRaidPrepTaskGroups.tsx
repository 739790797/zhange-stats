import type { ReactNode } from "react";
import {
  RAID_PREP_LIST_SCOPE_LABELS,
  RAID_PREP_PROGRESS_STATUSES,
  type RaidPrepTaskProgressStatus,
} from "@/lib/tarkovRaidPrep";
import styles from "./TarkovRaidPrepPanel.module.css";

type Props<T extends { id: string }> = {
  groups: Record<RaidPrepTaskProgressStatus, readonly T[]>;
  renderRow: (row: T, index: number) => ReactNode;
  empty?: ReactNode;
};

export function TarkovRaidPrepTaskGroups<T extends { id: string }>({
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
          {groups[status].map((row, index) => renderRow(row, index))}
        </div>
      ))}
    </>
  );
}
