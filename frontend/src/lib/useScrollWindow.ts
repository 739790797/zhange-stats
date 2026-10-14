import { useCallback, useEffect, useState } from "react";

export type ScrollWindow = { scrollTop: number; viewportHeight: number };

const SCROLLABLE = /(auto|scroll|overlay)/;

/** 从某个元素往上找真正滚动的那层（侧栏任务列表是外面那圈 .taskList）。 */
export function findScrollParent(el: HTMLElement | null): HTMLElement | null {
  let node = el?.parentElement ?? null;
  while (node) {
    if (SCROLLABLE.test(window.getComputedStyle(node).overflowY)) return node;
    node = node.parentElement;
  }
  return null;
}

/**
 * 跟随承载元素的滚动窗口位置（滚动 + 尺寸变化）。
 *
 * 侧栏任务列表动辄上百行、每行都挂提示气泡；拿到滚动位置和可视高度后，
 * 交给 raidPrepVirtualWindow 只渲染看得见的那一段。
 */
export function useScrollWindow<T extends HTMLElement>() {
  const [root, setRoot] = useState<T | null>(null);
  const [container, setContainer] = useState<HTMLElement | null>(null);
  const [win, setWin] = useState<ScrollWindow>({
    scrollTop: 0,
    viewportHeight: 0,
  });
  const setRootRef = useCallback((next: T | null) => setRoot(next), []);

  useEffect(() => {
    if (!root) return undefined;
    const found = findScrollParent(root);
    setContainer(found);
    if (!found) return undefined;
    const sync = () => {
      setWin((prev) => {
        const scrollTop = found.scrollTop;
        const viewportHeight = found.clientHeight;
        return prev.scrollTop === scrollTop &&
          prev.viewportHeight === viewportHeight
          ? prev
          : { scrollTop, viewportHeight };
      });
    };
    sync();
    found.addEventListener("scroll", sync, { passive: true });
    const observer =
      typeof ResizeObserver === "undefined" ? null : new ResizeObserver(sync);
    observer?.observe(found);
    return () => {
      found.removeEventListener("scroll", sync);
      observer?.disconnect();
    };
  }, [root]);

  return [setRootRef, win, container] as const;
}
