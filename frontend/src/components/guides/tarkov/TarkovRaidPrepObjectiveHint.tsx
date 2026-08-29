import { Popover } from "antd";
import type { ReactNode } from "react";
import {
  formatRaidPrepKeyNeedLine,
  type RaidPrepObjectiveHint,
} from "@/lib/tarkovRaidPrep";
import styles from "./TarkovRaidPrepPanel.module.css";

type Props = {
  objectives: RaidPrepObjectiveHint[];
  skipped?: ReadonlySet<string>;
  onToggle?: (objectiveId: string) => void;
  children: ReactNode;
  placement?: "top" | "topLeft" | "topRight" | "leftTop" | "bottomLeft";
  trigger?: Array<"hover" | "click">;
};

export function TarkovRaidPrepObjectiveHint({
  objectives,
  skipped,
  onToggle,
  children,
  placement = "topLeft",
  trigger = ["hover", "click"],
}: Props) {
  const doneIds = skipped || new Set<string>();
  const content = (
    <div
      className={styles.taskObjHint}
      onClick={(event) => event.stopPropagation()}
      onMouseDown={(event) => event.stopPropagation()}
    >
      <div className={styles.taskObjHintLead}>
        勾选表示这部分已经做完，本局不再显示点位和对应钥匙
      </div>
      {objectives.length ? (
        objectives.map((obj) => {
          const done = doneIds.has(obj.id);
          const keyLine = formatRaidPrepKeyNeedLine(obj.keyNames);
          return (
            <label key={obj.id} className={styles.taskObjCheck}>
              <input
                type="checkbox"
                checked={done}
                disabled={!onToggle}
                aria-label={`${done ? "取消勾选" : "勾选已完成"} ${obj.text}${keyLine ? ` ${keyLine}` : ""}`}
                onChange={() => onToggle?.(obj.id)}
              />
              <span className={done ? styles.taskObjLineDone : styles.taskObjLine}>
                <span>{obj.text}</span>
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
  return (
    <Popover
      content={content}
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
