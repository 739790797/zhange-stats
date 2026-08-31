import { EnvironmentOutlined } from "@ant-design/icons";
import { memo, useMemo } from "react";
import type { TarkovRaidPrepTask } from "@/api/guidesApi";
import {
  collectRaidPrepTaskObjectives,
  colorForTaskId,
  displayRaidPrepTaskName,
  groupObjectiveDonesForTask,
  type RaidPrepObjectiveDoneLike,
} from "@/lib/tarkovRaidPrep";
import { TarkovTraderThumb } from "@/components/guides/tarkov/TarkovTraderThumb";
import { TarkovRaidPrepObjectiveHint } from "@/components/guides/tarkov/TarkovRaidPrepObjectiveHint";
import styles from "./TarkovRaidPrepPanel.module.css";

type Props = {
  row: TarkovRaidPrepTask;
  checked: boolean;
  highlighted: boolean;
  active?: boolean;
  color?: string;
  floors?: string[];
  names?: string[];
  disabled?: boolean;
  done?: boolean;
  mapSlug?: string;
  skipped?: ReadonlySet<string>;
  objectiveDones?: readonly RaidPrepObjectiveDoneLike[] | null;
  currentUserId?: number | null;
  onToggleObjective?: (taskId: string, objectiveId: string) => void;
  /** 只显示任务名，不渲染楼层 / 进度 / 参与人等次行。 */
  compact?: boolean;
  onToggle: (taskId: string) => void;
  onNeedDetail?: (taskId: string) => void;
  onLocate?: (row: TarkovRaidPrepTask) => void;
  onTitle?: (taskId: string) => void;
};

function TarkovRaidPrepTaskCardInner({
  row,
  checked,
  highlighted,
  active,
  color,
  floors,
  names,
  disabled,
  done,
  mapSlug = "",
  skipped,
  objectiveDones,
  currentUserId,
  onToggleObjective,
  compact,
  onToggle,
  onNeedDetail,
  onLocate,
  onTitle,
}: Props) {
  const isDone = Boolean(done);
  const title = displayRaidPrepTaskName(row);
  const objectives = useMemo(
    () => collectRaidPrepTaskObjectives(row, mapSlug),
    [row, mapSlug],
  );
  const doneByOthers = useMemo(
    () =>
      groupObjectiveDonesForTask(row.id, objectiveDones, {
        excludeUserId: currentUserId,
      }),
    [row.id, objectiveDones, currentUserId],
  );
  const meta = compact
    ? []
    : [
        names?.length ? names.join("、") : "",
        floors?.length ? floors.join(" / ") : "",
      ].filter(Boolean);
  const swatch = color || colorForTaskId(row.id);
  const nameEl = onTitle ? (
    <button
      type="button"
      className={styles.taskName}
      onClick={(event) => {
        event.stopPropagation();
        onTitle(row.id);
      }}
    >
      {title}
    </button>
  ) : (
    <span className={styles.taskName}>{title}</span>
  );

  return (
    <div
      className={`${styles.taskRow} ${highlighted ? styles.taskRowOn : ""} ${
        disabled ? styles.taskRowDisabled : ""
      } ${active ? styles.taskRowActive : ""} ${isDone ? styles.taskRowDone : ""} ${
        compact ? styles.taskRowCompact : ""
      }`}
      data-raid-prep-task={row.id}
    >
      <label
        className={styles.checkWrap}
        onClick={(event) => event.stopPropagation()}
      >
        <input
          className={styles.check}
          type="checkbox"
          checked={checked}
          disabled={disabled}
          aria-label={`选择 ${title}`}
          onChange={() => {
            if (!disabled) onToggle(row.id);
          }}
        />
      </label>
      {highlighted ? (
        <span className={styles.swatch} style={{ background: swatch }} />
      ) : null}
      {row.trader_slug ? (
        <TarkovTraderThumb
          slug={row.trader_slug}
          size={28}
          title={row.trader_name || row.trader_slug}
        />
      ) : null}
      <div className={styles.taskBody}>
        <div className={styles.taskTitle}>
          <TarkovRaidPrepObjectiveHint
            taskId={row.id}
            objectives={objectives}
            skipped={skipped}
            doneByOthers={doneByOthers}
            onNeedDetail={onNeedDetail}
            onToggle={
              onToggleObjective
                ? (objectiveId) => onToggleObjective(row.id, objectiveId)
                : undefined
            }
            trigger={["hover"]}
          >
            {nameEl}
          </TarkovRaidPrepObjectiveHint>
        </div>
        {meta.length ? (
          <div
            className={styles.meta}
            onClick={
              onTitle
                ? (event) => {
                    event.stopPropagation();
                    onTitle(row.id);
                  }
                : undefined
            }
          >
            {meta.join(" · ")}
          </div>
        ) : null}
      </div>
      {onLocate && row.has_map_markers ? (
        <button
          type="button"
          className={styles.locateBtn}
          aria-label="定位到地图点位"
          title="定位到地图点位"
          onClick={(event) => {
            event.stopPropagation();
            onLocate(row);
          }}
        >
          <EnvironmentOutlined />
        </button>
      ) : null}
    </div>
  );
}

export const TarkovRaidPrepTaskCard = memo(TarkovRaidPrepTaskCardInner);
