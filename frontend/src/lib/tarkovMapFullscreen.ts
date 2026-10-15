import { createContext, useContext } from "react";

export type TarkovMapFullscreenRoot = {
  root: HTMLElement | null;
  fullscreen: boolean;
  toggle: () => void;
};

export const TarkovMapFullscreenRootContext =
  createContext<TarkovMapFullscreenRoot>({
    root: null,
    fullscreen: false,
    toggle: () => {},
  });

/** 房间地图把左右栏和地图放在同一层，全屏这个节点才能带着两侧的展开/收起一起走。 */
export const RAID_WORKSPACE_SELECTOR = "[data-raid-workspace]";

export function mapFullscreenTarget(wrap: HTMLElement): HTMLElement {
  const workspace = wrap.closest(RAID_WORKSPACE_SELECTOR);
  return workspace instanceof HTMLElement ? workspace : wrap;
}

/** 全屏元素是地图本身，或包着地图的房间工作区。 */
export function fullscreenElementIncludesMap(
  fullscreenEl: Element | null,
  wrap: Element | null,
): boolean {
  if (!fullscreenEl || !wrap) return false;
  return fullscreenEl === wrap || fullscreenEl.contains(wrap);
}

export function mapWrapInFullscreen(wrap: HTMLElement | null): boolean {
  return fullscreenElementIncludesMap(mapFullscreenElement(), wrap);
}

/** 全屏时把弹层挂到地图根节点，否则走页面 body。 */
export function resolveMapOverlayContainer(
  root: HTMLElement | null | undefined,
  fullscreen: boolean,
): HTMLElement | undefined {
  if (fullscreen && root) return root;
  return undefined;
}

export function useTarkovMapOverlayContainer(): HTMLElement | undefined {
  const { root, fullscreen } = useContext(TarkovMapFullscreenRootContext);
  return resolveMapOverlayContainer(root, fullscreen);
}

export function mapFullscreenElement(): Element | null {
  if (typeof document === "undefined") return null;
  const doc = document as Document & { webkitFullscreenElement?: Element | null };
  return document.fullscreenElement ?? doc.webkitFullscreenElement ?? null;
}

export function mapFullscreenEnabled(): boolean {
  if (typeof document === "undefined") return false;
  const doc = document as Document & { webkitFullscreenEnabled?: boolean };
  return Boolean(document.fullscreenEnabled || doc.webkitFullscreenEnabled);
}

export function requestMapFullscreen(el: HTMLElement): Promise<void> {
  const node = el as HTMLElement & {
    webkitRequestFullscreen?: () => void | Promise<void>;
  };
  if (el.requestFullscreen) return el.requestFullscreen();
  node.webkitRequestFullscreen?.();
  return Promise.resolve();
}

export function exitMapFullscreen(): Promise<void> {
  if (typeof document === "undefined") return Promise.resolve();
  const doc = document as Document & {
    webkitExitFullscreen?: () => void | Promise<void>;
  };
  if (document.exitFullscreen) return document.exitFullscreen();
  doc.webkitExitFullscreen?.();
  return Promise.resolve();
}
