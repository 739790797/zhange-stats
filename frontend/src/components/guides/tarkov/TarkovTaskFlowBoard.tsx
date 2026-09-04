/** 个人中心任务进度：有序任务横向链、无序任务网格；商人栏仍纵向。 */

import { forwardRef, useEffect, useRef, useState, type HTMLAttributes } from "react";
import { Link } from "react-router-dom";
import { Popover } from "antd";
import type { TarkovTaskListItem } from "@/api/guidesApi";
import { TarkovTraderThumb } from "@/components/guides/tarkov/TarkovTraderThumb";
import { tarkovTaskHref, traderDisplayName } from "@/lib/tarkovHomeNav";
import {
  displayTaskProgressName,
  isWritableTaskStatus,
  resolveTaskStatus,
  TASK_STATUS_KINDS,
  TASK_STATUS_LABELS,
  taskLoyaltyLevel,
  taskPlayerLevelLabel,
  type TaskProgressSummary,
  type TaskStatusKind,
} from "@/lib/tarkovTaskTree";
import {
  flowCardRibbonGradient,
  flowCardRibbonKinds,
  splitFlowForest,
  taskChoiceLabel,
  tarkovFlowTaskAnchor,
  tarkovFlowTraderAnchor,
  type FlowRibbonKind,
  type TaskForestChild,
  type TaskForestNode,
} from "@/lib/tarkovTaskForest";
import styles from "./TarkovTaskFlowBoard.module.css";

export type TarkovTaskFlowLane = {
  traderSlug: string;
  traderName: string;
  forest: TaskForestChild<TarkovTaskListItem>[];
  count: TaskProgressSummary;
  visible: number;
};

function formatMeta(count: TaskProgressSummary, visible: number): string {
  const bits = [`显示 ${visible}`];
  if (count.active) bits.push(`进行中 ${count.active}`);
  if (count.failed) bits.push(`失败 ${count.failed}`);
  if (count.unreachable) bits.push(`无法完成 ${count.unreachable}`);
  if (count.completed) bits.push(`已完成 ${count.completed}`);
  return bits.join(" · ");
}

function statusTone(status: TaskStatusKind): string {
  if (status === "done") return styles.cardDone;
  if (status === "failed") return styles.cardFailed;
  if (status === "unreachable") return styles.cardUnreachable;
  return "";
}

function LoyaltyMark({ level }: { level: number | null | undefined }) {
  const n = taskLoyaltyLevel(level);
  if (n >= 4) {
    return (
      <svg
        className={styles.loyaltyIcon}
        viewBox="0 0 24 24"
        aria-label="商人好感 4"
      >
        <path
          fill="currentColor"
          d="M4 17.2 6.4 8.5l3.7 4.2L12 6l1.9 6.7 3.7-4.2L20 17.2H4Zm0 1.6h16V21H4v-2.2Z"
        />
      </svg>
    );
  }
  const roman = n === 1 ? "I" : n === 2 ? "II" : "III";
  return (
    <span className={styles.loyaltyRoman} aria-label={`商人好感 ${n}`}>
      {roman}
    </span>
  );
}

function StatusSelect({
  task,
  done,
  started,
  onSetStatus,
}: {
  task: TarkovTaskListItem;
  done: ReadonlySet<string>;
  started: ReadonlySet<string>;
  onSetStatus: (taskId: string, status: TaskStatusKind) => void;
}) {
  const label = displayTaskProgressName(task);
  const status = resolveTaskStatus(task.id, done, started, task);
  const derived = !isWritableTaskStatus(status);
  return (
    <select
      className={styles.statusSelect}
      aria-label={`${label} 状态`}
      value={status}
      disabled={derived}
      onClick={(event) => event.stopPropagation()}
      onMouseDown={(event) => event.stopPropagation()}
      onChange={(event) =>
        onSetStatus(task.id, event.target.value as TaskStatusKind)
      }
    >
      {TASK_STATUS_KINDS.map((value) => (
        <option
          key={value}
          value={value}
          disabled={!isWritableTaskStatus(value) && value !== status}
        >
          {TASK_STATUS_LABELS[value]}
        </option>
      ))}
    </select>
  );
}

function RelationHead({
  title,
  hint,
  className,
}: {
  title: string;
  hint: string;
  className: string;
}) {
  return (
    <div className={styles.relationHead}>
      <div className={className}>{title}</div>
      <div className={styles.relationHint}>{hint}</div>
    </div>
  );
}

function lookupTasks(
  ids: readonly string[] | null | undefined,
  itemById: ReadonlyMap<string, TarkovTaskListItem>,
  skip: ReadonlySet<string>,
): TarkovTaskListItem[] {
  const out: TarkovTaskListItem[] = [];
  const seen = new Set<string>();
  for (const raw of ids || []) {
    const ident = String(raw || "").trim();
    if (!ident || skip.has(ident) || seen.has(ident)) continue;
    seen.add(ident);
    const row = itemById.get(ident);
    if (row) out.push(row);
  }
  return out;
}

type TaskCardFaceProps = {
  task: TarkovTaskListItem;
  done: ReadonlySet<string>;
  started: ReadonlySet<string>;
  onSetStatus: (taskId: string, status: TaskStatusKind) => void;
  id?: string;
  highlight?: boolean;
  dim?: boolean;
  ribbonKinds?: readonly FlowRibbonKind[];
  open?: boolean;
  onActivate?: () => void;
} & Omit<HTMLAttributes<HTMLElement>, "id">;

const TaskCardFace = forwardRef<HTMLElement, TaskCardFaceProps>(
  function TaskCardFace(
    {
      task,
      done,
      started,
      onSetStatus,
      id,
      highlight,
      dim,
      ribbonKinds,
      open,
      onActivate,
      className,
      onClick,
      ...rest
    },
    ref,
  ) {
    const label = displayTaskProgressName(task);
    const status = resolveTaskStatus(task.id, done, started, task);
    const hasRibbon = Boolean(ribbonKinds?.length);
    return (
      <article
        {...rest}
        ref={ref}
        id={id}
        className={`${styles.card} ${statusTone(status)}${
          hasRibbon ? ` ${styles.cardHasRibbon}` : ""
        }${dim ? ` ${styles.cardDim}` : ""}${
          highlight ? ` ${styles.flash}` : ""
        }${onActivate ? ` ${styles.cardJump}` : ""}${
          className ? ` ${className}` : ""
        }`}
        aria-haspopup={hasRibbon ? "dialog" : undefined}
        aria-expanded={hasRibbon ? open : undefined}
        onClick={(event) => {
          onClick?.(event);
          onActivate?.();
        }}
      >
        {hasRibbon ? (
          <span
            className={styles.cardRibbon}
            style={{ background: flowCardRibbonGradient(ribbonKinds ?? []) }}
            aria-hidden
          />
        ) : null}
        <Link
          className={styles.cardTitle}
          to={tarkovTaskHref(task.id)}
          onClick={(event) => event.stopPropagation()}
        >
          {label}
        </Link>
        <div className={styles.cardMeta}>
          <div className={styles.cardReq}>
            <span>等级要求：</span>
            <span className={styles.cardReqValue}>
              {taskPlayerLevelLabel(task.min_player_level)}
            </span>
            <span>商人好感：</span>
            <LoyaltyMark level={task.min_trader_level} />
          </div>
          <StatusSelect
            task={task}
            done={done}
            started={started}
            onSetStatus={onSetStatus}
          />
        </div>
      </article>
    );
  },
);

function PeekTask({
  item,
  done,
  started,
  onSetStatus,
  onJump,
}: {
  item: TarkovTaskListItem;
  done: ReadonlySet<string>;
  started: ReadonlySet<string>;
  onSetStatus: (taskId: string, status: TaskStatusKind) => void;
  onJump: () => void;
}) {
  return (
    <TaskCardFace
      task={item}
      done={done}
      started={started}
      onSetStatus={onSetStatus}
      onActivate={onJump}
    />
  );
}

function FlowCard({
  node,
  done,
  started,
  itemById,
  highlight,
  onSetStatus,
  onJumpTask,
}: {
  node: TaskForestNode<TarkovTaskListItem>;
  done: ReadonlySet<string>;
  started: ReadonlySet<string>;
  itemById: ReadonlyMap<string, TarkovTaskListItem>;
  highlight: boolean;
  onSetStatus: (taskId: string, status: TaskStatusKind) => void;
  onJumpTask: (taskId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const task = node.task;
  const skip = new Set([task.id]);
  const prereqs = lookupTasks(node.extraPrereqIds, itemById, skip);
  const prereqIds = new Set(prereqs.map((row) => row.id));
  const conflicts = lookupTasks(
    task.mutex_ids,
    itemById,
    new Set([...skip, ...prereqIds]),
  );
  const conflictIds = new Set(conflicts.map((row) => row.id));
  const blocked = lookupTasks(
    task.blocked_by,
    itemById,
    new Set([...skip, ...prereqIds, ...conflictIds]),
  );
  const ribbonKinds = flowCardRibbonKinds({
    prereq: prereqs.length > 0,
    blocked: blocked.length > 0,
    conflict: conflicts.length > 0,
  });
  const hasRibbon = ribbonKinds.length > 0;

  const card = (
    <TaskCardFace
      task={task}
      done={done}
      started={started}
      onSetStatus={onSetStatus}
      id={tarkovFlowTaskAnchor(task.id)}
      highlight={highlight}
      dim={!node.matched}
      ribbonKinds={ribbonKinds}
      open={open}
    />
  );

  if (!hasRibbon) return card;

  return (
    <Popover
      trigger={["hover", "click"]}
      mouseEnterDelay={0.12}
      mouseLeaveDelay={0.22}
      placement="leftTop"
      autoAdjustOverflow
      zIndex={1100}
      getPopupContainer={() => document.body}
      open={open}
      onOpenChange={setOpen}
      destroyTooltipOnHide
      rootClassName={styles.prereqPopover}
      content={
        <div className={styles.prereqList}>
          {prereqs.length ? (
            <div className={styles.relationCol}>
              <RelationHead
                className={styles.prereqHead}
                title="前置"
                hint="你需要先完成下列任务"
              />
              {prereqs.map((item) => (
                <PeekTask
                  key={item.id}
                  item={item}
                  done={done}
                  started={started}
                  onSetStatus={onSetStatus}
                  onJump={() => {
                    setOpen(false);
                    onJumpTask(item.id);
                  }}
                />
              ))}
            </div>
          ) : null}
          {blocked.length ? (
            <div className={styles.relationCol}>
              <RelationHead
                className={styles.blockedHead}
                title="阻断"
                hint="完成以下任务，将会使本任务失败/无法接取"
              />
              {blocked.map((item) => (
                <PeekTask
                  key={item.id}
                  item={item}
                  done={done}
                  started={started}
                  onSetStatus={onSetStatus}
                  onJump={() => {
                    setOpen(false);
                    onJumpTask(item.id);
                  }}
                />
              ))}
            </div>
          ) : null}
          {conflicts.length ? (
            <div className={styles.relationCol}>
              <RelationHead
                className={styles.conflictHead}
                title="冲突"
                hint="完成本任务，将会使下列任务失败/无法接取"
              />
              {conflicts.map((item) => (
                <PeekTask
                  key={item.id}
                  item={item}
                  done={done}
                  started={started}
                  onSetStatus={onSetStatus}
                  onJump={() => {
                    setOpen(false);
                    onJumpTask(item.id);
                  }}
                />
              ))}
            </div>
          ) : null}
        </div>
      }
    >
      {card}
    </Popover>
  );
}

function FlowBranch({
  forest,
  done,
  started,
  itemById,
  highlightTask,
  rooted,
  onSetStatus,
  onJumpTask,
}: {
  forest: TaskForestChild<TarkovTaskListItem>[];
  done: ReadonlySet<string>;
  started: ReadonlySet<string>;
  itemById: ReadonlyMap<string, TarkovTaskListItem>;
  highlightTask: string;
  rooted?: boolean;
  onSetStatus: (taskId: string, status: TaskStatusKind) => void;
  onJumpTask: (taskId: string) => void;
}) {
  if (!forest.length) return null;
  return (
    <div
      className={`${styles.branch}${
        rooted || forest.length === 1 ? ` ${styles.branchOne}` : ""
      }${rooted ? ` ${styles.branchRoot}` : ""}`}
    >
      {forest.map((child) =>
        child.kind === "choice" ? (
          <div
            key={`choice:${child.options.map((row) => row.task.id).join(",")}`}
            className={styles.choice}
          >
            <div className={styles.choiceLabel}>
              {taskChoiceLabel(child.options.length)}
            </div>
            <div className={styles.choiceRow}>
              {child.options.map((node) => (
                <FlowColumn
                  key={node.task.id}
                  node={node}
                  done={done}
                  started={started}
                  itemById={itemById}
                  highlightTask={highlightTask}
                  onSetStatus={onSetStatus}
                  onJumpTask={onJumpTask}
                />
              ))}
            </div>
          </div>
        ) : (
          <FlowColumn
            key={child.node.task.id}
            node={child.node}
            done={done}
            started={started}
            itemById={itemById}
            highlightTask={highlightTask}
            onSetStatus={onSetStatus}
            onJumpTask={onJumpTask}
          />
        ),
      )}
    </div>
  );
}

function FlowColumn({
  node,
  done,
  started,
  itemById,
  highlightTask,
  onSetStatus,
  onJumpTask,
}: {
  node: TaskForestNode<TarkovTaskListItem>;
  done: ReadonlySet<string>;
  started: ReadonlySet<string>;
  itemById: ReadonlyMap<string, TarkovTaskListItem>;
  highlightTask: string;
  onSetStatus: (taskId: string, status: TaskStatusKind) => void;
  onJumpTask: (taskId: string) => void;
}) {
  const hasKids = node.children.length > 0;
  return (
    <div className={styles.col}>
      <FlowCard
        node={node}
        done={done}
        started={started}
        itemById={itemById}
        highlight={highlightTask === node.task.id}
        onSetStatus={onSetStatus}
        onJumpTask={onJumpTask}
      />
      {hasKids ? (
        <>
          <div className={styles.across} aria-hidden>
            <span className={styles.acrossStem} />
            <span className={styles.acrossHead} />
          </div>
          <FlowBranch
            forest={node.children}
            done={done}
            started={started}
            itemById={itemById}
            highlightTask={highlightTask}
            onSetStatus={onSetStatus}
            onJumpTask={onJumpTask}
          />
        </>
      ) : null}
    </div>
  );
}

function FlowLaneBody({
  forest,
  done,
  started,
  itemById,
  highlightTask,
  onSetStatus,
  onJumpTask,
}: {
  forest: TaskForestChild<TarkovTaskListItem>[];
  done: ReadonlySet<string>;
  started: ReadonlySet<string>;
  itemById: ReadonlyMap<string, TarkovTaskListItem>;
  highlightTask: string;
  onSetStatus: (taskId: string, status: TaskStatusKind) => void;
  onJumpTask: (taskId: string) => void;
}) {
  const split = splitFlowForest(forest);
  return (
    <>
      {split.chains.length ? (
        <div className={styles.canvas}>
          <p className={styles.legend}>有序任务</p>
          <FlowBranch
            rooted
            forest={split.chains}
            done={done}
            started={started}
            itemById={itemById}
            highlightTask={highlightTask}
            onSetStatus={onSetStatus}
            onJumpTask={onJumpTask}
          />
        </div>
      ) : null}
      {split.isolates.length ? (
        <div className={styles.isolates}>
          <p className={styles.isolatesHead}>
            无序任务 · {split.isolates.length}
          </p>
          <div className={styles.isolateGrid}>
            {split.isolates.map((child) =>
              child.kind === "task" ? (
                <FlowColumn
                  key={child.node.task.id}
                  node={child.node}
                  done={done}
                  started={started}
                  itemById={itemById}
                  highlightTask={highlightTask}
                  onSetStatus={onSetStatus}
                  onJumpTask={onJumpTask}
                />
              ) : null,
            )}
          </div>
        </div>
      ) : null}
    </>
  );
}

export function TarkovTaskFlowBoard({
  lanes,
  done,
  started,
  itemById,
  highlightTrader,
  highlightTask,
  onSetStatus,
  onJumpTask,
  onVisibleTrader,
}: {
  lanes: TarkovTaskFlowLane[];
  done: ReadonlySet<string>;
  started: ReadonlySet<string>;
  itemById: ReadonlyMap<string, TarkovTaskListItem>;
  highlightTrader: string;
  highlightTask: string;
  onSetStatus: (taskId: string, status: TaskStatusKind) => void;
  onJumpTask: (taskId: string) => void;
  onVisibleTrader: (slug: string) => void;
}) {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root || !lanes.length) return;
    const nodes = [
      ...root.querySelectorAll<HTMLElement>("[data-flow-trader]"),
    ];
    if (!nodes.length) return;
    const io = new IntersectionObserver(
      (entries) => {
        const hit = entries
          .filter((row) => row.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        const slug = hit?.target.getAttribute("data-flow-trader");
        if (slug) onVisibleTrader(slug);
      },
      { root: null, threshold: [0.15, 0.35, 0.6], rootMargin: "-20% 0px -55% 0px" },
    );
    for (const node of nodes) io.observe(node);
    return () => io.disconnect();
  }, [lanes, onVisibleTrader]);

  if (!lanes.length) {
    return <div className={styles.empty}>当前筛选下无任务</div>;
  }

  return (
    <div ref={rootRef} className={styles.stack}>
      {lanes.map((lane) => {
        const title =
          traderDisplayName(lane.traderSlug, lane.traderName) || "未知商人";
        const lit = highlightTrader === lane.traderSlug;
        return (
          <section
            key={lane.traderSlug || "none"}
            id={tarkovFlowTraderAnchor(lane.traderSlug)}
            data-flow-trader={lane.traderSlug}
            className={`${styles.lane}${lit ? ` ${styles.laneFlash}` : ""}`}
          >
            <h3 className={styles.head}>
              <span className={styles.headTitle}>
                {lane.traderSlug ? (
                  <TarkovTraderThumb
                    slug={lane.traderSlug}
                    size={28}
                    title={title}
                  />
                ) : null}
                <span>{title}</span>
              </span>
              <span className={styles.headMeta}>
                {formatMeta(lane.count, lane.visible)}
              </span>
            </h3>
            <FlowLaneBody
              forest={lane.forest}
              done={done}
              started={started}
              itemById={itemById}
              highlightTask={highlightTask}
              onSetStatus={onSetStatus}
              onJumpTask={onJumpTask}
            />
          </section>
        );
      })}
    </div>
  );
}
