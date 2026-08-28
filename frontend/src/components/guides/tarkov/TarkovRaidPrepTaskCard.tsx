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
  onToggle,
  onLocate,
  onTitle,
}: Props) {
  const isDone = done ?? row.progress_status === "complete";
  const progress = tarkovTaskProgressLabel(row.progress_status);
  const title = displayRaidPrepTaskName(row);
  const meta = [
    names?.length ? names.join("、") : "",
    floors?.length ? floors.join(" / ") : "",
    progress,
    row.min_player_level ? `Lv.${row.min_player_level}` : "",
    row.kappa_required ? "Kappa" : "",
  ].filter(Boolean);
  const swatch = color || colorForTaskId(row.id);

  return (
    <div
      className={`${styles.taskRow} ${highlighted ? styles.taskRowOn : ""} ${
        disabled ? styles.taskRowDisabled : ""
      } ${active ? styles.taskRowActive : ""} ${isDone ? styles.taskRowDone : ""}`}
      data-raid-prep-task={row.id}
      role={disabled ? undefined : "button"}
      tabIndex={disabled ? undefined : 0}
      onClick={() => {
        if (!disabled) onToggle();
      }}
      onKeyDown={(event) => {
        if (disabled) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onToggle();
        }
      }}
    >
      <input
        className={styles.check}
        type="checkbox"
        checked={checked}
        readOnly
        disabled={disabled}
        tabIndex={-1}
        aria-label={title}
      />
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
        {meta.length ? <div className={styles.meta}>{meta.join(" · ")}</div> : null}
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
