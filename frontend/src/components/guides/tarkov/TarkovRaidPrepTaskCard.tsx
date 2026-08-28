import { EnvironmentOutlined } from "@ant-design/icons";
import type { TarkovRaidPrepTask } from "@/api/guidesApi";
import { colorForTaskId, displayRaidPrepTaskName } from "@/lib/tarkovRaidPrep";
import { tarkovTaskProgressLabel } from "@/lib/tarkovTaskProgress";
import { TarkovTraderThumb } from "@/components/guides/tarkov/TarkovTraderThumb";
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
  /** 只显示任务名，不渲染楼层 / 进度 / 参与人等次行。 */
  compact?: boolean;
  onToggle: () => void;
  onLocate?: () => void;
  onTitle?: () => void;
};

export function TarkovRaidPrepTaskCard({
  row,
  checked,
  highlighted,
  active,
  color,
  floors,
  names,
  disabled,
  done,
  compact,
  onToggle,
  onLocate,
  onTitle,
}: Props) {
  const isDone = done ?? row.progress_status === "complete";
  const progress = tarkovTaskProgressLabel(row.progress_status);
  const title = displayRaidPrepTaskName(row);
  const meta = compact
    ? []
    : [
        names?.length ? names.join("、") : "",
        floors?.length ? floors.join(" / ") : "",
        progress,
        row.kappa_required ? "Kappa" : "",
      ].filter(Boolean);
  const swatch = color || colorForTaskId(row.id);

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
            if (!disabled) onToggle();
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
          {onTitle ? (
            <button
              type="button"
              className={styles.taskName}
              title={title}
              onClick={(event) => {
                event.stopPropagation();
                onTitle();
              }}
            >
              {title}
            </button>
          ) : (
            <span className={styles.taskName} title={title}>
              {title}
            </span>
          )}
        </div>
        {meta.length ? (
          <div
            className={styles.meta}
            onClick={
              onTitle
                ? (event) => {
                    event.stopPropagation();
                    onTitle();
                  }
                : undefined
            }
          >
            {meta.join(" · ")}
          </div>
        ) : null}
      </div>
      {onLocate ? (
        <button
          type="button"
          className={styles.locateBtn}
          aria-label="定位到地图点位"
          title="定位到地图点位"
          onClick={(event) => {
            event.stopPropagation();
            onLocate();
          }}
        >
          <EnvironmentOutlined />
        </button>
      ) : null}
    </div>
  );
}
