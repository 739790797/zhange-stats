import { Popover } from "antd";
import {
  Fragment,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { useTarkovMapOverlayContainer } from "@/lib/tarkovMapFullscreen";
import {
  formatRaidPrepAltMapsLead,
  formatRaidPrepKeyNeedLine,
  formatRaidPrepSequenceMapTitle,
  placeRaidPrepListHint,
  raidPrepObjectiveCheckedForViewer,
  tarkovFailConditionTypeLabel,
  type RaidPrepFailChip,
  type RaidPrepHintItem,
  type RaidPrepObjectiveHint,
  type RaidPrepOtherMapGroup,
  type RaidPrepSequenceGroup,
} from "@/lib/tarkovRaidPrep";
import { inventoryThumbUrl } from "@/lib/tarkovItemImages";
import { TarkovTraderThumb } from "@/components/guides/tarkov/TarkovTraderThumb";
import styles from "./TarkovRaidPrepPanel.module.css";

export type TarkovRaidPrepObjectiveProgressProps = {
  objectives: RaidPrepObjectiveHint[];
  skipped?: ReadonlySet<string>;
  onToggle?: (objectiveId: string) => void;
  otherMapGroups?: readonly RaidPrepOtherMapGroup[];
  sequenceGroups?: readonly RaidPrepSequenceGroup[];
  failChips?: readonly RaidPrepFailChip[];
  taskName?: string;
  traderSlug?: string;
  traderName?: string;
  /** 个人进度已完成：当前用户视角步骤全勾，不写共享勾选。 */
  taskDone?: boolean;
};

type HintProps = TarkovRaidPrepObjectiveProgressProps & {
  children: ReactNode;
  taskId?: string;
  onNeedDetail?: (taskId: string) => void;
  placement?: "top" | "topLeft" | "topRight" | "left" | "leftTop" | "bottomLeft";
  trigger?: Array<"hover" | "click">;
};

/** 列表在指针下滚动时 mouseleave 常不触发；这段时间内不再新开气泡。 */
const HINT_SCROLL_ARM_MS = 160;
const HINT_LEAVE_MS = 180;
const HINT_ANIM_MS = 160;
const RAID_PREP_DOCK_ID = "tarkov-raid-dock";

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

function measureHintTrigger(host: HTMLElement): DOMRect {
  const rect = host.getBoundingClientRect();
  if (rect.width >= 2 && rect.height >= 2) return rect;
  const child = host.firstElementChild;
  if (child instanceof HTMLElement) {
    const next = child.getBoundingClientRect();
    if (next.width >= 2 || next.height >= 2) return next;
  }
  return host.parentElement?.getBoundingClientRect() ?? rect;
}

function measureHintEdgeRight(host: HTMLElement): number {
  const dock = document.getElementById(RAID_PREP_DOCK_ID);
  if (dock) return dock.getBoundingClientRect().left;
  return measureHintTrigger(host).left;
}

function markFailText(text: string): ReactNode {
  const parts = text.split("失败");
  if (parts.length === 1) return text;
  return parts.map((part, index) => (
    <Fragment key={index}>
      {part}
      {index < parts.length - 1 ? (
        <span className={styles.taskObjFailMark}>失败</span>
      ) : null}
    </Fragment>
  ));
}

function FailChipText({ chip }: { chip: RaidPrepFailChip }) {
  if (chip.tasks?.length) {
    return (
      <span className={styles.taskObjFailText}>
        完成该任务会使
        {chip.tasks.map((task, index) => (
          <span key={task.id || `${task.name}:${index}`}>
            {index > 0 ? "、" : null}
            <span className={styles.taskObjFailName}>
              {task.traderSlug ? (
                <span className={styles.taskObjFailThumb}>
                  <TarkovTraderThumb
                    slug={task.traderSlug}
                    size={14}
                    title={task.traderName || task.traderSlug}
                  />
                </span>
              ) : null}
              {task.name}
            </span>
          </span>
        ))}
        <span className={styles.taskObjFailMark}>失败</span>
      </span>
    );
  }
  return <span className={styles.taskObjFailText}>{markFailText(chip.text)}</span>;
}

function ObjectiveHintItem({ item }: { item: RaidPrepHintItem }) {
  const preferred = inventoryThumbUrl(item.icon_link, item.id);
  const [src, setSrc] = useState(preferred);
  useEffect(() => {
    setSrc(preferred);
  }, [preferred]);
  const count = item.count > 1 ? ` ×${item.count}` : "";
  return (
    <span className={styles.taskObjItem}>
      {src ? (
        <img
          className={styles.taskObjItemIcon}
          src={src}
          alt=""
          onError={() => setSrc("")}
        />
      ) : null}
      <span>
        {item.name}
        {count}
      </span>
    </span>
  );
}

function objectiveSpokenText(obj: RaidPrepObjectiveHint, keyLine: string): string {
  const names = (obj.items || []).map((item) => item.name).filter(Boolean);
  const itemBit = names.length ? ` ${names.join("、")}` : "";
  return `${obj.text}${itemBit}${keyLine ? ` ${keyLine}` : ""}`;
}

function ObjectiveStepBody({
  obj,
  sharedAlts,
  altLead,
}: {
  obj: RaidPrepObjectiveHint;
  sharedAlts: boolean;
  altLead: ReactNode;
}) {
  const keyLine = formatRaidPrepKeyNeedLine(obj.keyNames);
  return (
    <>
      <span className={styles.taskObjStep}>
        <span className={styles.taskObjStepText}>{obj.text}</span>
        {(obj.items || []).map((item) => (
          <ObjectiveHintItem key={`${item.id}:${item.name}`} item={item} />
        ))}
      </span>
      {keyLine ? <span className={styles.taskObjKeys}>{keyLine}</span> : null}
      {!sharedAlts ? altLead : null}
    </>
  );
}

export function TarkovRaidPrepObjectiveProgress({
  objectives,
  skipped,
  onToggle,
  sequenceGroups,
  failChips,
  taskName,
  traderSlug,
  traderName,
  taskDone,
}: TarkovRaidPrepObjectiveProgressProps) {
  const doneIds = skipped || new Set<string>();
  const seqGroups =
    sequenceGroups?.length
      ? sequenceGroups
      : objectives.length
        ? [
            {
              mapSlug: "",
              mapLabel: "",
              onThisMap: true,
              objectives: [...objectives],
              altMaps: [],
            },
          ]
        : [];
  const hasOtherMaps = seqGroups.some((group) => !group.onThisMap);
  const title = (taskName || "").trim();
  const slug = (traderSlug || "").trim();
  const renderAltLead = (
    maps: RaidPrepSequenceGroup["altMaps"] | undefined,
  ) => {
    const text = formatRaidPrepAltMapsLead(maps, "step");
    if (!text) return null;
    return <div className={styles.taskObjOtherMapsLead}>{text}</div>;
  };
  const renderObjective = (
    obj: RaidPrepObjectiveHint,
    sharedAlts: boolean,
    onThisMap: boolean,
  ) => {
    const mineDone = raidPrepObjectiveCheckedForViewer(
      obj.id,
      doneIds,
      taskDone,
    );
    const keyLine = formatRaidPrepKeyNeedLine(obj.keyNames);
    const lineClass = mineDone
      ? styles.taskObjLineDone
      : onThisMap
        ? styles.taskObjLine
        : styles.taskObjOtherMapLine;
    return (
      <label key={obj.id} className={styles.taskObjCheck}>
        <input
          type="checkbox"
          checked={mineDone}
          disabled={!onToggle || Boolean(taskDone)}
          aria-label={`${mineDone ? "取消勾选" : "勾选已完成"} ${objectiveSpokenText(obj, keyLine)}`}
          onChange={() => {
            if (!taskDone) onToggle?.(obj.id);
          }}
        />
        <span className={lineClass}>
          <ObjectiveStepBody
            obj={obj}
            sharedAlts={sharedAlts}
            altLead={renderAltLead(obj.altMaps)}
          />
        </span>
      </label>
    );
  };
  return (
    <div
      className={styles.taskObjHint}
      onClick={(event) => event.stopPropagation()}
      onMouseDown={(event) => event.stopPropagation()}
    >
      {title || slug ? (
        <div className={styles.taskObjHead}>
          {slug ? (
            <TarkovTraderThumb
              slug={slug}
              size={22}
              title={traderName || slug}
            />
          ) : null}
          {title ? <div className={styles.taskObjTitle}>{title}</div> : null}
        </div>
      ) : null}
      {seqGroups.length ? (
        <div className={hasOtherMaps ? styles.taskObjSeq : undefined}>
          {seqGroups.map((group, index) => {
            const mapTitle = formatRaidPrepSequenceMapTitle(group);
            const showHeader = hasOtherMaps || Boolean(group.altMaps.length);
            const sharedAlts = Boolean(group.altMaps.length);
            return (
              <div
                key={`${group.mapSlug}:${group.onThisMap}:${index}`}
                className={
                  group.onThisMap
                    ? `${styles.taskObjSeqGroup}${
                        hasOtherMaps ? ` ${styles.taskObjSeqGroupHere}` : ""
                      }`
                    : `${styles.taskObjSeqGroup} ${styles.taskObjOtherMap}`
                }
              >
                {showHeader ? (
                  <div
                    className={
                      group.onThisMap
                        ? `${styles.taskObjOtherMapLabel} ${styles.taskObjSeqMapHere}`
                        : styles.taskObjOtherMapLabel
                    }
                  >
                    {mapTitle}
                  </div>
                ) : null}
                {group.objectives.map((obj) =>
                  renderObjective(obj, sharedAlts, group.onThisMap),
                )}
              </div>
            );
          })}
        </div>
      ) : failChips?.length ? null : (
        <div className={styles.taskObjLine}>无目标数据</div>
      )}
      {failChips?.length ? (
        <div className={styles.taskObjFails}>
          {failChips.map((chip) => (
            <div key={`${chip.type}:${chip.text}`} className={styles.taskObjFail}>
              <span className={styles.taskObjFailChip}>
                {tarkovFailConditionTypeLabel(chip.type)}
              </span>
              <FailChipText chip={chip} />
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function TarkovRaidPrepObjectiveHint({
  objectives,
  skipped,
  onToggle,
  otherMapGroups,
  sequenceGroups,
  failChips,
  taskName,
  traderSlug,
  traderName,
  taskDone,
  taskId,
  onNeedDetail,
  children,
  placement = "left",
  trigger = ["hover", "click"],
}: HintProps) {
  const hostRef = useRef<HTMLSpanElement | null>(null);
  const boxRef = useRef<HTMLDivElement | null>(null);
  const leaveTimerRef = useRef(0);
  const [armed, setArmed] = useState(false);
  const [open, setOpen] = useState(false);
  const [renderFloat, setRenderFloat] = useState(false);
  const [shown, setShown] = useState(false);
  const [boxStyle, setBoxStyle] = useState<CSSProperties | null>(null);
  const preferLeft = placement === "left" || placement === "leftTop";
  const overlayRoot = useTarkovMapOverlayContainer();
  const portalRoot = overlayRoot || (typeof document !== "undefined" ? document.body : null);

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

  useEffect(
    () => () => {
      window.clearTimeout(leaveTimerRef.current);
    },
    [],
  );

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

  const cancelLeave = () => {
    window.clearTimeout(leaveTimerRef.current);
    leaveTimerRef.current = 0;
  };

  const armLeave = () => {
    window.clearTimeout(leaveTimerRef.current);
    leaveTimerRef.current = window.setTimeout(() => {
      leaveTimerRef.current = 0;
      setHintOpen(false);
    }, HINT_LEAVE_MS);
  };

  useEffect(() => {
    if (open) {
      setRenderFloat(true);
      return undefined;
    }
    setShown(false);
    if (!renderFloat) return undefined;
    const timer = window.setTimeout(() => {
      setRenderFloat(false);
      setBoxStyle(null);
    }, HINT_ANIM_MS);
    return () => window.clearTimeout(timer);
  }, [open, renderFloat]);

  useEffect(() => {
    if (!preferLeft || !renderFloat) return undefined;
    const host = hostRef.current;
    const box = boxRef.current;
    if (!host || !box) return undefined;
    const update = () => {
      const triggerRect = measureHintTrigger(host);
      const placed = placeRaidPrepListHint({
        viewW: window.innerWidth,
        viewH: window.innerHeight,
        boxW: box.offsetWidth,
        boxH: box.offsetHeight,
        edgeRight: measureHintEdgeRight(host),
        triggerTop: triggerRect.top,
      });
      setBoxStyle((prev) => {
        if (
          prev &&
          prev.left === placed.left &&
          prev.top === placed.top &&
          prev.maxWidth === placed.maxWidth &&
          prev.maxHeight === placed.maxHeight
        ) {
          return prev;
        }
        return {
          left: placed.left,
          top: placed.top,
          maxWidth: placed.maxWidth,
          maxHeight: placed.maxHeight,
        };
      });
    };
    update();
    const raf = window.requestAnimationFrame(update);
    window.addEventListener("resize", update);
    const ro =
      typeof ResizeObserver !== "undefined" ? new ResizeObserver(update) : null;
    ro?.observe(box);
    return () => {
      window.cancelAnimationFrame(raf);
      window.removeEventListener("resize", update);
      ro?.disconnect();
    };
  }, [renderFloat, preferLeft, objectives, otherMapGroups, sequenceGroups, failChips, taskName, traderSlug]);

  useEffect(() => {
    if (!open || !boxStyle) return undefined;
    const raf = window.requestAnimationFrame(() => setShown(true));
    return () => window.cancelAnimationFrame(raf);
  }, [open, boxStyle]);

  if (preferLeft) {
    return (
      <span
        ref={hostRef}
        className={styles.taskObjHintHost}
        onMouseEnter={() => {
          cancelLeave();
          setHintOpen(true);
        }}
        onMouseLeave={armLeave}
        onFocus={() => {
          cancelLeave();
          setHintOpen(true);
        }}
      >
        {children}
        {renderFloat && portalRoot
          ? createPortal(
              <div
                ref={boxRef}
                className={`${styles.taskObjFloat}${shown ? ` ${styles.taskObjFloatOn}` : ""}`}
                style={boxStyle || { left: -9999, top: 0, visibility: "hidden" }}
                onMouseEnter={cancelLeave}
                onMouseLeave={armLeave}
              >
                <TarkovRaidPrepObjectiveProgress
                  objectives={objectives}
                  skipped={skipped}
                  onToggle={onToggle}
                  otherMapGroups={otherMapGroups}
                  sequenceGroups={sequenceGroups}
                  failChips={failChips}
                  taskName={taskName}
                  traderSlug={traderSlug}
                  traderName={traderName}
                  taskDone={taskDone}
                />
              </div>,
              portalRoot,
            )
          : null}
      </span>
    );
  }

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
          otherMapGroups={otherMapGroups}
          sequenceGroups={sequenceGroups}
          failChips={failChips}
          taskName={taskName}
          traderSlug={traderSlug}
          traderName={traderName}
          taskDone={taskDone}
        />
      }
      trigger={trigger}
      mouseEnterDelay={0.12}
      mouseLeaveDelay={0.35}
      placement={placement}
      autoAdjustOverflow
      zIndex={2200}
      getPopupContainer={() => overlayRoot || document.body}
      rootClassName={styles.taskObjTooltip}
    >
      {children}
    </Popover>
  );
}
