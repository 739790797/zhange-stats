import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import {
  RAID_PREP_ACTIVE_MAP_GROUP_LABELS,
  RAID_PREP_LIST_SCOPE_LABELS,
  RAID_PREP_PROGRESS_STATUSES,
  raidPrepVirtualWindow,
  splitRaidPrepRowsByCurrentMap,
  type RaidPrepTaskProgressStatus,
} from "@/lib/tarkovRaidPrep";
import { useScrollWindow } from "@/lib/useScrollWindow";
import styles from "./TarkovRaidPrepPanel.module.css";

type Row = { id: string; on_this_map?: boolean };

type Props<T extends Row> = {
  groups: Record<RaidPrepTaskProgressStatus, readonly T[]>;
  renderRow: (row: T, index: number) => ReactNode;
  empty?: ReactNode;
};

/** 与 .taskRowCompact 的高度对齐。 */
const ROW_PX = 40;
/** 少于这么多行就直接全渲染，省掉测量与占位。 */
const VIRTUAL_MIN_ROWS = 60;
const OVERSCAN = 8;

/**
 * 一段连续行：按滚动窗口只挂看得见的那几条，上下用等高占位补回总高，
 * 保证块的 offsetTop 与总高不随窗口变化（否则外层滚动条会跳）。
 */
function VirtualRowBlock<T extends Row>({
  rows,
  renderRow,
  top,
  viewportHeight,
  offset,
  measure,
}: {
  rows: readonly T[];
  renderRow: (row: T, index: number) => ReactNode;
  top: number;
  viewportHeight: number;
  offset: number | null;
  measure: (node: HTMLDivElement | null) => void;
}) {
  const virtual = rows.length >= VIRTUAL_MIN_ROWS && offset != null;
  const win = virtual
    ? raidPrepVirtualWindow({
        scrollTop: top - offset,
        viewportHeight,
        count: rows.length,
        rowHeight: ROW_PX,
        overscan: OVERSCAN,
      })
    : null;
  const slice = win ? rows.slice(win.start, win.end) : rows;
  const start = win ? win.start : 0;
  return (
    <div ref={measure} data-raid-prep-row-block="">
      {win?.padTop ? <div style={{ height: win.padTop }} aria-hidden="true" /> : null}
      {slice.map((row, index) => renderRow(row, start + index))}
      {win?.padBottom ? (
        <div style={{ height: win.padBottom }} aria-hidden="true" />
      ) : null}
    </div>
  );
}

export function TarkovRaidPrepTaskGroups<T extends Row>({
  groups,
  renderRow,
  empty,
}: Props<T>) {
  const [rootRef, win, container] = useScrollWindow<HTMLDivElement>();
  const [offsets, setOffsets] = useState<Record<string, number>>({});
  const blockRefs = useRef(new Map<string, HTMLDivElement>());

  const measure = (key: string) => (node: HTMLDivElement | null) => {
    if (node) blockRefs.current.set(key, node);
    else blockRefs.current.delete(key);
  };

  useLayoutEffect(() => {
    const next: Record<string, number> = {};
    for (const [key, node] of blockRefs.current) {
      // 相对滚动容器内容顶端的距离：不随滚动变化，块高又是固定的，量一次就稳。
      next[key] = container
        ? node.getBoundingClientRect().top -
          container.getBoundingClientRect().top +
          container.scrollTop
        : node.offsetTop;
    }
    setOffsets((prev) => {
      const keys = Object.keys(next);
      if (
        keys.length === Object.keys(prev).length &&
        keys.every((key) => prev[key] === next[key])
      ) {
        return prev;
      }
      return next;
    });
  }, [container, groups, win.viewportHeight]);

  const visible = RAID_PREP_PROGRESS_STATUSES.filter(
    (status) => groups[status].length,
  );
  if (!visible.length) return <>{empty}</>;

  const rowBlock = (key: string, rows: readonly T[]) => (
    <VirtualRowBlock
      key={key}
      rows={rows}
      renderRow={renderRow}
      top={win.scrollTop}
      viewportHeight={win.viewportHeight}
      offset={offsets[key] ?? null}
      measure={measure(key)}
    />
  );

  return (
    <div ref={rootRef}>
      {visible.map((status) => (
        <div key={status} className={styles.taskGroup}>
          <p className={styles.taskGroupLabel} data-status={status}>
            {RAID_PREP_LIST_SCOPE_LABELS[status]} {groups[status].length}
          </p>
          {status === "active" ? (
            <ActiveMapGroups
              status={status}
              rows={groups[status]}
              rowBlock={rowBlock}
            />
          ) : (
            rowBlock(status, groups[status])
          )}
        </div>
      ))}
    </div>
  );
}

function ActiveMapGroups<T extends Row>({
  status,
  rows,
  rowBlock,
}: {
  status: RaidPrepTaskProgressStatus;
  rows: readonly T[];
  rowBlock: (key: string, rows: readonly T[]) => ReactNode;
}) {
  const { onMap, offMap } = splitRaidPrepRowsByCurrentMap(rows);
  const blocks: Array<{
    key: keyof typeof RAID_PREP_ACTIVE_MAP_GROUP_LABELS;
    rows: readonly T[];
  }> = [];
  if (onMap.length) blocks.push({ key: "onMap", rows: onMap });
  if (offMap.length) blocks.push({ key: "offMap", rows: offMap });
  return (
    <>
      {blocks.map((block) => (
        <div key={block.key} className={styles.taskSubGroup}>
          <p
            className={styles.taskSubGroupLabel}
            data-map={block.key === "onMap" ? "on" : "off"}
          >
            {RAID_PREP_ACTIVE_MAP_GROUP_LABELS[block.key]} {block.rows.length}
          </p>
          {rowBlock(`${status}:${block.key}`, block.rows)}
        </div>
      ))}
    </>
  );
}
