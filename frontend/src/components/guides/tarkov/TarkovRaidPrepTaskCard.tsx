import { Link } from "react-router-dom";
import type { TarkovRaidPrepTask } from "@/api/guidesApi";
import { tarkovTaskHref } from "@/lib/tarkovHomeNav";
import {
  colorForTaskId,
  neededKeyNamesForMap,
} from "@/lib/tarkovRaidPrep";
import { tarkovTaskProgressLabel } from "@/lib/tarkovTaskProgress";
import { TarkovTraderThumb } from "@/components/guides/tarkov/TarkovTraderThumb";
import styles from "./TarkovRaidPrepPanel.module.css";

type Props = {
  row: TarkovRaidPrepTask;
  mapId: string;
  checked: boolean;
  highlighted: boolean;
  names?: string[];
  disabled?: boolean;
  onToggle: () => void;
};

export function TarkovRaidPrepTaskCard({
  row,
  mapId,
  checked,
  highlighted,
  names,
  disabled,
  onToggle,
}: Props) {
  const keys = neededKeyNamesForMap(row, mapId);
  const progress = tarkovTaskProgressLabel(row.progress_status);
  const meta = [
    names?.length ? names.join("、") : "",
    progress,
    row.min_player_level ? `Lv.${row.min_player_level}` : "",
    row.kappa_required ? "Kappa" : "",
  ].filter(Boolean);

  return (
    <div
      className={`${styles.taskRow} ${highlighted ? styles.taskRowOn : ""} ${
        disabled ? styles.taskRowDisabled : ""
      }`}
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
        aria-label={row.name || row.id}
      />
      {highlighted ? (
        <span
          className={styles.swatch}
          style={{ background: colorForTaskId(row.id) }}
        />
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
          <Link
            className={styles.taskName}
            to={tarkovTaskHref(row.id)}
            title={row.name || row.normalized_name || row.id}
            onClick={(event) => event.stopPropagation()}
          >
            {row.name || row.normalized_name || row.id}
          </Link>
          {row.has_map_markers ? (
            <span className={styles.mark} title="图上有点位">
              点位
            </span>
          ) : null}
          {row.wiki_link ? (
            <a
              className={styles.wiki}
              href={row.wiki_link}
              target="_blank"
              rel="noreferrer"
              onClick={(event) => event.stopPropagation()}
            >
              Wiki
            </a>
          ) : null}
        </div>
        {meta.length ? <div className={styles.meta}>{meta.join(" · ")}</div> : null}
        {keys.length ? (
          <div className={styles.tags}>
            {keys.map((name) => (
              <span key={name} className={styles.keyTag}>
                {name}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
