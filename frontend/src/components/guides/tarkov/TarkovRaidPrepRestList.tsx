import { useEffect, useState, type ReactNode } from "react";
import {
  RAID_PREP_REST_ROW_PX,
  RAID_PREP_REST_VIRTUAL_MIN,
  raidPrepVirtualWindow,
} from "@/lib/tarkovRaidPrep";

type Props<T> = {
  items: readonly T[];
  scrollParent: HTMLElement | null;
  head: HTMLElement | null;
  renderRow: (item: T, index: number) => ReactNode;
  rowHeight?: number;
};

export function TarkovRaidPrepRestList<T>({
  items,
  scrollParent,
  head,
  renderRow,
  rowHeight = RAID_PREP_REST_ROW_PX,
}: Props<T>) {
  const count = items.length;
  const virtual = count >= RAID_PREP_REST_VIRTUAL_MIN;
  const [win, setWin] = useState(() =>
    raidPrepVirtualWindow({
      scrollTop: 0,
      viewportHeight: 480,
      count,
      rowHeight,
    }),
  );

  useEffect(() => {
    if (!virtual || !scrollParent) {
      setWin({ start: 0, end: count, padTop: 0, padBottom: 0 });
      return undefined;
    }
    const update = () => {
      const offset = head?.offsetHeight ?? 0;
      setWin(
        raidPrepVirtualWindow({
          scrollTop: Math.max(0, scrollParent.scrollTop - offset),
          viewportHeight: scrollParent.clientHeight,
          count,
          rowHeight,
        }),
      );
    };
    update();
    scrollParent.addEventListener("scroll", update, { passive: true });
    const observer = new ResizeObserver(update);
    observer.observe(scrollParent);
    if (head) observer.observe(head);
    return () => {
      scrollParent.removeEventListener("scroll", update);
      observer.disconnect();
    };
  }, [count, head, rowHeight, scrollParent, virtual]);

  const slice = virtual ? items.slice(win.start, win.end) : items;
  const start = virtual ? win.start : 0;

  return (
    <>
      {virtual && win.padTop ? (
        <div style={{ height: win.padTop }} aria-hidden />
      ) : null}
      {slice.map((item, index) => renderRow(item, start + index))}
      {virtual && win.padBottom ? (
        <div style={{ height: win.padBottom }} aria-hidden />
      ) : null}
    </>
  );
}
