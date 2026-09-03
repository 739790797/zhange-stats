import { EnvironmentOutlined } from "@ant-design/icons";
import { memo, useMemo } from "react";
import type { TarkovRaidPrepTask } from "@/api/guidesApi";
import {
  collectRaidPrepFailChips,
  collectRaidPrepOtherMapGroups,
  collectRaidPrepSequenceGroups,
  collectRaidPrepTaskObjectives,
  colorForTaskId,
  displayRaidPrepTaskName,
  raidPrepMapObjectivesComplete,
  raidPrepTaskCanLocate,
  RAID_PREP_LIST_SCOPE_LABELS,
  RAID_PREP_STATUS_SELECT_OPTIONS,
  type RaidPrepTaskProgressStatus,
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
  /** 仅禁止勾进房间，不影响状态下拉。 */
  claimDisabled?: boolean;
  done?: boolean;
  status?: RaidPrepTaskProgressStatus;
  mapSlug?: string;
  skipped?: ReadonlySet<string>;
  onToggleObjective?: (taskId: string, objectiveId: string) => void;
  /** 只显示任务名，不渲染楼层 / 进度 / 参与人等次行。 */
  compact?: boolean;
  onToggle: (taskId: string) => void;
  onNeedDetail?: (taskId: string) => void;
  onLocate?: (row: TarkovRaidPrepTask) => void;
  onTitle?: (taskId: string) => void;
  onSetStatus?: (taskId: string, status: RaidPrepTaskProgressStatus) => void;
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
  claimDisabled,
  done,
  status,
  mapSlug = "",
  skipped,
  onToggleObjective,
  compact,
  onToggle,
  onNeedDetail,
  onLocate,
  onTitle,
  onSetStatus,
}: Props) {
  const isDone = Boolean(done);
  const title = displayRaidPrepTaskName(row);
  const objectives = useMemo(
    () => collectRaidPrepTaskObjectives(row, mapSlug),
    [row, mapSlug],
  );
  const otherMapGroups = useMemo(
    () => collectRaidPrepOtherMapGroups(row, mapSlug),
    [row, mapSlug],
  );
  const sequenceGroups = useMemo(
    () => collectRaidPrepSequenceGroups(row, mapSlug),
    [row, mapSlug],
  );
  const failChips = useMemo(
    () => collectRaidPrepFailChips(row.fail_conditions),
    [row],
  );
  const mapDone =
    isDone || raidPrepMapObjectivesComplete(row, mapSlug, skipped);
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
        mapDone ? styles.taskRowMapDone : ""
      } ${compact ? styles.taskRowCompact : ""}`}
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
          disabled={disabled || claimDisabled || (isDone && !checked)}
          aria-label={`选择 ${title}`}
          onChange={() => {
            if (disabled || claimDisabled || (isDone && !checked)) return;
            onToggle(row.id);
          }}
        />
      </label>
      <span
        className={styles.swatch}
        style={highlighted ? { background: swatch } : undefined}
        data-empty={highlighted ? undefined : ""}
      />
      <span className={styles.taskTraderSlot}>
        {row.trader_slug ? (
          <TarkovTraderThumb
            slug={row.trader_slug}
            size={28}
            title={row.trader_name || row.trader_slug}
          />
        ) : null}
      </span>
      <div className={styles.taskBody}>
        <div className={styles.taskTitle}>
          <TarkovRaidPrepObjectiveHint
            taskId={row.id}
            taskName={title}
            traderSlug={row.trader_slug || ""}
            traderName={row.trader_name || ""}
            taskDone={isDone || status === "done"}
            objectives={objectives}
            otherMapGroups={otherMapGroups}
            sequenceGroups={sequenceGroups}
            failChips={failChips}
            skipped={skipped}
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
      {onSetStatus && status ? (
        <select
          className={styles.taskStatusSelect}
          data-status={status}
          aria-label={`${title} 状态`}
          value={status}
          disabled={disabled}
          onClick={(event) => event.stopPropagation()}
          onChange={(event) => {
            event.stopPropagation();
            onSetStatus(row.id, event.target.value as RaidPrepTaskProgressStatus);
          }}
        >
          {RAID_PREP_STATUS_SELECT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : (
        <span className={styles.taskStatus} data-status={status || undefined}>
          {status ? RAID_PREP_LIST_SCOPE_LABELS[status] : ""}
        </span>
      )}
      <span className={styles.taskLocateSlot}>
        {onLocate &&
        raidPrepTaskCanLocate(row, mapSlug, skipped, {
          taskDone: isDone,
          hasMapMarkers: row.has_map_markers,
        }) ? (
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
      </span>
    </div>
  );
}

export const TarkovRaidPrepTaskCard = memo(TarkovRaidPrepTaskCardInner);
