import { Popover } from "antd";
import type { ReactNode } from "react";
import {
  formatRaidPrepKeyNeedLine,
  type RaidPrepCompletedUser,
  type RaidPrepObjectiveHint,
} from "@/lib/tarkovRaidPrep";
import styles from "./TarkovRaidPrepPanel.module.css";

export type TarkovRaidPrepObjectiveProgressProps = {
  objectives: RaidPrepObjectiveHint[];
  skipped?: ReadonlySet<string>;
  /** 他人已完成的步骤（不含当前用户）。 */
  doneByOthers?: ReadonlyMap<string, readonly RaidPrepCompletedUser[]>;
  onToggle?: (objectiveId: string) => void;
};

type HintProps = TarkovRaidPrepObjectiveProgressProps & {
  children: ReactNode;
  placement?: "top" | "topLeft" | "topRight" | "leftTop" | "bottomLeft";
  trigger?: Array<"hover" | "click">;
};

function formatOthersDone(names: readonly string[]): string {
  if (!names.length) return "";
  return `${names.join("、")} 已完成`;
}

export function TarkovRaidPrepObjectiveProgress({
  objectives,
  skipped,
  doneByOthers,
  onToggle,
}: TarkovRaidPrepObjectiveProgressProps) {
  const doneIds = skipped || new Set<string>();
  return (
    <div
      className={styles.taskObjHint}
      onClick={(event) => event.stopPropagation()}
      onMouseDown={(event) => event.stopPropagation()}
    >
      <div className={styles.taskObjHintLead}>
        勾选表示你已做完：只对你划掉并隐藏点位。他人完成的步骤会在后方标注。
      </div>
      {objectives.length ? (
        objectives.map((obj) => {
          const mineDone = doneIds.has(obj.id);
          const others = doneByOthers?.get(obj.id) || [];
          const keyLine = formatRaidPrepKeyNeedLine(obj.keyNames);
          const othersLabel = formatOthersDone(others.map((row) => row.name));
          return (
            <label key={obj.id} className={styles.taskObjCheck}>
              <input
                type="checkbox"
                checked={mineDone}
                disabled={!onToggle}
                aria-label={`${mineDone ? "取消勾选" : "勾选已完成"} ${obj.text}${othersLabel ? `，${othersLabel}` : ""}${keyLine ? ` ${keyLine}` : ""}`}
                onChange={() => onToggle?.(obj.id)}
              />
              <span
                className={mineDone ? styles.taskObjLineDone : styles.taskObjLine}
              >
                <span className={styles.taskObjLineMain}>
                  <span>{obj.text}</span>
                  {othersLabel ? (
                    <span className={styles.taskObjDoneBy}>{othersLabel}</span>
                  ) : null}
                </span>
                {keyLine ? (
                  <span className={styles.taskObjKeys}>{keyLine}</span>
                ) : null}
              </span>
            </label>
          );
        })
      ) : (
        <div className={styles.taskObjLine}>无目标数据</div>
      )}
    </div>
  );
}

export function TarkovRaidPrepObjectiveHint({
  objectives,
  skipped,
  doneByOthers,
  onToggle,
  children,
  placement = "topLeft",
  trigger = ["hover", "click"],
}: HintProps) {
  return (
    <Popover
      content={
        <TarkovRaidPrepObjectiveProgress
          objectives={objectives}
          skipped={skipped}
          doneByOthers={doneByOthers}
          onToggle={onToggle}
        />
      }
      trigger={trigger}
      mouseEnterDelay={0.12}
      mouseLeaveDelay={0.35}
      placement={placement}
      autoAdjustOverflow
      zIndex={1200}
      rootClassName={styles.taskObjTooltip}
    >
      {children}
    </Popover>
  );
}
