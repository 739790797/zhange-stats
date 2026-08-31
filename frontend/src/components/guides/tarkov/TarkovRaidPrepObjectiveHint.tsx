import { Popover } from "antd";
import { useEffect, useState, type ReactNode } from "react";
import {
  formatRaidPrepKeyNeedLine,
  type RaidPrepObjectiveHint,
} from "@/lib/tarkovRaidPrep";
import styles from "./TarkovRaidPrepPanel.module.css";

export type TarkovRaidPrepObjectiveProgressProps = {
  objectives: RaidPrepObjectiveHint[];
  skipped?: ReadonlySet<string>;
  onToggle?: (objectiveId: string) => void;
};

type HintProps = TarkovRaidPrepObjectiveProgressProps & {
  children: ReactNode;
  taskId?: string;
  onNeedDetail?: (taskId: string) => void;
  placement?: "top" | "topLeft" | "topRight" | "leftTop" | "bottomLeft";
  trigger?: Array<"hover" | "click">;
};

/** 列表在指针下滚动时 mouseleave 常不触发；这段时间内不再新开气泡。 */
const HINT_SCROLL_ARM_MS = 160;

const hintClosers = new Set<() => void>();
let hintScrollAt = 0;
let hintScrollListen = 0;

function recentHintScroll(): boolean {
  return performance.now() - hintScrollAt < HINT_SCROLL_ARM_MS;
}

function onHintScrollDismiss() {
  hintScrollAt = performance.now();
  for (const close of [...hintClosers]) close();
}

function retainHintScrollListen() {
  if (hintScrollListen === 0) {
    document.addEventListener("scroll", onHintScrollDismiss, true);
    document.addEventListener("wheel", onHintScrollDismiss, {
      capture: true,
      passive: true,
    });
    document.addEventListener("touchmove", onHintScrollDismiss, {
      capture: true,
      passive: true,
    });
  }
  hintScrollListen += 1;
}

function releaseHintScrollListen() {
  hintScrollListen -= 1;
  if (hintScrollListen > 0) return;
  hintScrollListen = 0;
  document.removeEventListener("scroll", onHintScrollDismiss, true);
  document.removeEventListener("wheel", onHintScrollDismiss, true);
  document.removeEventListener("touchmove", onHintScrollDismiss, true);
}

export function TarkovRaidPrepObjectiveProgress({
  objectives,
  skipped,
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
        勾选表示你已做完：只对你划掉，地图点位不会因此隐藏。
      </div>
      {objectives.length ? (
        objectives.map((obj) => {
          const mineDone = doneIds.has(obj.id);
          const keyLine = formatRaidPrepKeyNeedLine(obj.keyNames);
          return (
            <label key={obj.id} className={styles.taskObjCheck}>
              <input
                type="checkbox"
                checked={mineDone}
                disabled={!onToggle}
                aria-label={`${mineDone ? "取消勾选" : "勾选已完成"} ${obj.text}${keyLine ? ` ${keyLine}` : ""}`}
                onChange={() => onToggle?.(obj.id)}
              />
              <span
                className={mineDone ? styles.taskObjLineDone : styles.taskObjLine}
              >
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
}

export function TarkovRaidPrepObjectiveHint({
  objectives,
  skipped,
  onToggle,
  taskId,
  onNeedDetail,
  children,
  placement = "topLeft",
  trigger = ["hover", "click"],
}: HintProps) {
  const [armed, setArmed] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    retainHintScrollListen();
    return () => releaseHintScrollListen();
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const close = () => setOpen(false);
    for (const other of [...hintClosers]) other();
    hintClosers.add(close);
    return () => {
      hintClosers.delete(close);
    };
  }, [open]);

  const setHintOpen = (next: boolean) => {
    if (next && recentHintScroll()) {
      setOpen(false);
      return;
    }
    setOpen(next);
    if (next) {
      setArmed(true);
      if (taskId && !objectives.length) onNeedDetail?.(taskId);
    }
  };

  if (!armed) {
    return (
      <span
        className={styles.taskObjHintHost}
        onMouseEnter={() => setHintOpen(true)}
        onFocus={() => setHintOpen(true)}
      >
        {children}
      </span>
    );
  }

  return (
    <Popover
      open={open}
      onOpenChange={setHintOpen}
      destroyTooltipOnHide
      content={
        <TarkovRaidPrepObjectiveProgress
          objectives={objectives}
          skipped={skipped}
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
