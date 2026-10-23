/**
 * 经典滚动条（Windows）出现时会占掉布局宽度。
 * 原生条宽度为 0；这里只在内容溢出时，把拇指画在内容上面。
 */
import { TARKOV_SCROLLBAR_HIDE_CLASS } from "@/features/guides/tarkov/model/tarkovUi";

const THUMB_MIN = 28;
const BAR = 8;
const EDGE = 2;
const OVERFLOW_EPS = 2;
const BASE_Z = 30;
const SCROLLABLE = new Set(["auto", "scroll", "overlay"]);
const STOP_KEY = "__zhangeOverlayScrollStop";
const HIDE_SELECTOR = `.${TARKOV_SCROLLBAR_HIDE_CLASS}`;

export type Box = { top: number; left: number; right: number; bottom: number };

type Axis = "x" | "y";

type ThumbSnapshot = {
  offset: number;
  viewport: number;
  total: number;
  track: number;
};

type Track = {
  el: HTMLElement;
  axisY: boolean;
  axisX: boolean;
  onDark: boolean;
  z: number;
  y: HTMLDivElement | null;
  x: HTMLDivElement | null;
};

type Host = Window & { [STOP_KEY]?: () => void };

export function intersectBox(a: Box, b: Box): Box | null {
  const top = Math.max(a.top, b.top);
  const left = Math.max(a.left, b.left);
  const right = Math.min(a.right, b.right);
  const bottom = Math.min(a.bottom, b.bottom);
  if (right - left < 1 || bottom - top < 1) return null;
  return { top, left, right, bottom };
}

export function thumbSize(viewport: number, total: number, track: number): number {
  if (viewport <= 0 || total <= 0 || track <= 0) return 0;
  const proportional = (viewport / total) * track;
  const min = Math.min(THUMB_MIN, track);
  return Math.min(track, Math.max(min, proportional));
}

export function thumbMetrics(
  scroll: number,
  viewport: number,
  total: number,
  track: number,
): { offset: number; size: number } | null {
  if (viewport <= 0 || track <= 0 || total <= viewport + OVERFLOW_EPS) return null;
  const size = thumbSize(viewport, total, track);
  if (size <= 0) return null;
  const maxOffset = Math.max(0, track - size);
  const maxScroll = total - viewport;
  const current = clamp(scroll, 0, Math.max(0, maxScroll));
  const offset = maxScroll <= 0 || maxOffset <= 0 ? 0 : (current / maxScroll) * maxOffset;
  return { offset, size };
}

export function scrollForThumbOffset(
  offset: number,
  viewport: number,
  total: number,
  track: number,
): number {
  if (viewport <= 0 || track <= 0 || total <= viewport) return 0;
  const size = thumbSize(viewport, total, track);
  const maxOffset = Math.max(0, track - size);
  const maxScroll = total - viewport;
  if (maxOffset <= 0 || maxScroll <= 0) return 0;
  return (clamp(offset, 0, maxOffset) / maxOffset) * maxScroll;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function startOverlayScrollbars(): void {
  if (typeof document === "undefined") return;
  const host = window as Host;
  host[STOP_KEY]?.();
  host[STOP_KEY] = install();
}

function install(): () => void {
  const tracks = new Map<HTMLElement, Track>();
  const pending = new Set<HTMLElement>();
  const dirty = new Set<HTMLElement>();
  let raf = 0;

  const resizeObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      if (entry.target instanceof HTMLElement) queue(entry.target);
    }
  });

  const mutationObserver = new MutationObserver((records) => {
    for (const record of records) {
      const target = record.target;
      if (isThumb(target)) continue;
      if (record.type === "childList") {
        if (target instanceof HTMLElement) queueAncestors(target);
        for (const node of record.addedNodes) {
          if (isThumb(node) || !(node instanceof HTMLElement)) continue;
          queueTree(node);
        }
        continue;
      }
      if (target instanceof HTMLElement) queueAncestors(target);
    }
  });

  function schedule() {
    if (raf) return;
    raf = requestAnimationFrame(flush);
  }

  function queue(el: HTMLElement) {
    if (isThumb(el)) return;
    pending.add(el);
    schedule();
  }

  function queueAncestors(el: HTMLElement | null) {
    let node = el;
    while (node) {
      queue(node);
      node = node.parentElement;
    }
  }

  function queueTree(el: HTMLElement) {
    queue(el);
    if (el.childElementCount === 0) return;
    for (const node of el.querySelectorAll("*")) {
      if (node instanceof HTMLElement) queue(node);
    }
  }

  function mark(el: HTMLElement) {
    dirty.add(el);
    schedule();
  }

  function flush() {
    raf = 0;
    const syncList = [...pending];
    pending.clear();
    for (const el of syncList) sync(el);
    const layoutList = [...dirty];
    dirty.clear();
    const jobs: Measured[] = [];
    for (const el of layoutList) {
      const track = tracks.get(el);
      if (!track) continue;
      if (!el.isConnected) {
        untrack(el);
        continue;
      }
      jobs.push(measure(track));
    }
    for (const job of jobs) apply(job);
    for (const el of tracks.keys()) {
      if (!el.isConnected) untrack(el);
    }
  }

  function sync(el: HTMLElement) {
    if (!el.isConnected || isThumb(el)) {
      untrack(el);
      return;
    }
    const style = getComputedStyle(el);
    let axisY = SCROLLABLE.has(style.overflowY);
    let axisX = SCROLLABLE.has(style.overflowX);
    // 视口滚动条的 computed overflow 常常仍是 visible，但内容高出窗口时仍会滚动。
    if (
      (el === document.scrollingElement || el === document.documentElement) &&
      style.overflowY !== "hidden" &&
      style.overflowY !== "clip" &&
      el.scrollHeight > el.clientHeight + OVERFLOW_EPS
    ) {
      axisY = true;
    }
    if (
      (el === document.scrollingElement || el === document.documentElement) &&
      style.overflowX !== "hidden" &&
      style.overflowX !== "clip" &&
      el.scrollWidth > el.clientWidth + OVERFLOW_EPS
    ) {
      axisX = true;
    }
    if (!axisY && !axisX) {
      untrack(el);
      return;
    }
    if (el.closest(HIDE_SELECTOR)) {
      untrack(el);
      return;
    }
    let track = tracks.get(el);
    if (!track) {
      track = { el, axisY, axisX, onDark: false, z: BASE_Z, y: null, x: null };
      tracks.set(el, track);
      resizeObserver.observe(el);
    }
    track.axisY = axisY;
    track.axisX = axisX;
    track.onDark = !isLightSurface(el);
    track.z = layerZ(el);
    apply(measure(track));
  }

  function untrack(el: HTMLElement) {
    const track = tracks.get(el);
    if (!track) return;
    resizeObserver.unobserve(el);
    track.y?.remove();
    track.x?.remove();
    tracks.delete(el);
    dirty.delete(el);
  }

  function onScroll(event: Event) {
    const el = scrollerFrom(event.target);
    if (!el || isThumb(el)) return;
    if (!tracks.has(el)) {
      queue(el);
      return;
    }
    mark(el);
    for (const other of tracks.keys()) {
      if (other !== el && el.contains(other)) mark(other);
    }
  }

  const onWheel = (event: WheelEvent) => {
    const el = scrollerFrom(event.target);
    if (el && !isThumb(el) && !tracks.has(el)) queue(el);
  };
  const onLoad = (event: Event) => {
    const target = event.target;
    if (target instanceof HTMLElement) queueAncestors(target);
  };
  const onResize = () => {
    for (const el of tracks.keys()) mark(el);
  };
  document.addEventListener("scroll", onScroll, { capture: true, passive: true });
  document.addEventListener("wheel", onWheel, { capture: true, passive: true });
  document.addEventListener("load", onLoad, true);
  window.addEventListener("resize", onResize);
  window.visualViewport?.addEventListener("resize", onResize);
  window.visualViewport?.addEventListener("scroll", onResize);
  mutationObserver.observe(document.documentElement, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ["class", "hidden", "open"],
  });
  queueTree(document.documentElement);

  return () => {
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    mutationObserver.disconnect();
    resizeObserver.disconnect();
    document.removeEventListener("scroll", onScroll, true);
    document.removeEventListener("wheel", onWheel, true);
    document.removeEventListener("load", onLoad, true);
    window.removeEventListener("resize", onResize);
    window.visualViewport?.removeEventListener("resize", onResize);
    window.visualViewport?.removeEventListener("scroll", onResize);
    for (const el of [...tracks.keys()]) untrack(el);
  };
}

type Measured = {
  track: Track;
  y: { box: Box; metrics: { offset: number; size: number }; snapshot: ThumbSnapshot } | null;
  x: { box: Box; metrics: { offset: number; size: number }; snapshot: ThumbSnapshot } | null;
  rtl: boolean;
};

function measure(track: Track): Measured {
  const el = track.el;
  const box = clippedClientBox(el);
  const rtl = getComputedStyle(el).direction === "rtl";
  if (!box) return { track, y: null, x: null, rtl };
  const yOn = track.axisY && el.scrollHeight > el.clientHeight + OVERFLOW_EPS;
  const xOn = track.axisX && el.scrollWidth > el.clientWidth + OVERFLOW_EPS;
  const yTravel = box.bottom - box.top - EDGE * 2 - (xOn ? BAR + EDGE : 0);
  const xTravel = box.right - box.left - EDGE * 2 - (yOn ? BAR + EDGE : 0);
  const yMetrics = yOn
    ? thumbMetrics(el.scrollTop, el.clientHeight, el.scrollHeight, yTravel)
    : null;
  const xMetrics = xOn
    ? thumbMetrics(el.scrollLeft, el.clientWidth, el.scrollWidth, xTravel)
    : null;
  return {
    track,
    rtl,
    y: yMetrics
      ? {
          box,
          metrics: yMetrics,
          snapshot: {
            offset: yMetrics.offset,
            viewport: el.clientHeight,
            total: el.scrollHeight,
            track: yTravel,
          },
        }
      : null,
    x: xMetrics
      ? {
          box,
          metrics: xMetrics,
          snapshot: {
            offset: xMetrics.offset,
            viewport: el.clientWidth,
            total: el.scrollWidth,
            track: xTravel,
          },
        }
      : null,
  };
}

function apply(measured: Measured) {
  const { track } = measured;
  paintAxis(track, "y", measured.y, measured.rtl);
  paintAxis(track, "x", measured.x, measured.rtl);
}

function paintAxis(
  track: Track,
  axis: Axis,
  placed: Measured["y"],
  rtl: boolean,
) {
  if (!placed) {
    const thumb = track[axis];
    if (thumb) thumb.hidden = true;
    return;
  }
  const thumb = ensureThumb(track, axis);
  thumb.hidden = false;
  thumb.classList.toggle("app-overlay-scrollbar--on-dark", track.onDark);
  thumb.style.zIndex = String(track.z);
  writeSnapshot(thumb, placed.snapshot);
  if (axis === "y") {
    thumb.style.width = `${BAR}px`;
    thumb.style.height = `${placed.metrics.size}px`;
    thumb.style.top = `${placed.box.top + EDGE + placed.metrics.offset}px`;
    thumb.style.left = rtl
      ? `${placed.box.left + EDGE}px`
      : `${placed.box.right - BAR - EDGE}px`;
    return;
  }
  thumb.style.height = `${BAR}px`;
  thumb.style.width = `${placed.metrics.size}px`;
  thumb.style.left = `${placed.box.left + EDGE + placed.metrics.offset}px`;
  thumb.style.top = `${placed.box.bottom - BAR - EDGE}px`;
}

function ensureThumb(track: Track, axis: Axis): HTMLDivElement {
  const existing = track[axis];
  if (existing) return existing;
  const thumb = document.createElement("div");
  thumb.className =
    axis === "x"
      ? "app-overlay-scrollbar app-overlay-scrollbar--x"
      : "app-overlay-scrollbar";
  thumb.hidden = true;
  thumb.setAttribute("aria-hidden", "true");
  bindThumb(track.el, axis, thumb);
  document.body.appendChild(thumb);
  track[axis] = thumb;
  return thumb;
}

function bindThumb(el: HTMLElement, axis: Axis, thumb: HTMLDivElement) {
  thumb.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    const snapshot = readSnapshot(thumb);
    if (!snapshot) return;
    const origin = axis === "y" ? event.clientY : event.clientX;
    thumb.classList.add("is-active");
    const move = (ev: PointerEvent) => {
      const delta = (axis === "y" ? ev.clientY : ev.clientX) - origin;
      const next = scrollForThumbOffset(
        snapshot.offset + delta,
        snapshot.viewport,
        snapshot.total,
        snapshot.track,
      );
      if (axis === "y") el.scrollTop = next;
      else el.scrollLeft = next;
    };
    const up = () => {
      thumb.classList.remove("is-active");
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  });
  thumb.addEventListener(
    "wheel",
    (event) => {
      if (axis === "y") el.scrollTop += event.deltaY;
      else el.scrollLeft += event.deltaX;
      event.preventDefault();
    },
    { passive: false },
  );
}

function writeSnapshot(thumb: HTMLDivElement, snapshot: ThumbSnapshot) {
  thumb.dataset.offset = String(snapshot.offset);
  thumb.dataset.viewport = String(snapshot.viewport);
  thumb.dataset.total = String(snapshot.total);
  thumb.dataset.track = String(snapshot.track);
}

function readSnapshot(thumb: HTMLDivElement): ThumbSnapshot | null {
  const offset = Number(thumb.dataset.offset);
  const viewport = Number(thumb.dataset.viewport);
  const total = Number(thumb.dataset.total);
  const track = Number(thumb.dataset.track);
  if (![offset, viewport, total, track].every(Number.isFinite)) return null;
  return { offset, viewport, total, track };
}

function clippedClientBox(el: HTMLElement): Box | null {
  let box: Box | null = clientBox(el);
  if (!box) return null;
  box = intersectBox(box, viewportBox());
  let parent = el.parentElement;
  while (box && parent) {
    const style = getComputedStyle(parent);
    if (overflowClips(style.overflowX) || overflowClips(style.overflowY)) {
      const parentBox = clientBox(parent);
      if (parentBox) box = intersectBox(box, parentBox);
    }
    parent = parent.parentElement;
  }
  return box;
}

function clientBox(el: HTMLElement): Box | null {
  const rect = el.getBoundingClientRect();
  const box = {
    top: rect.top + el.clientTop,
    left: rect.left + el.clientLeft,
    right: rect.left + el.clientLeft + el.clientWidth,
    bottom: rect.top + el.clientTop + el.clientHeight,
  };
  if (box.right - box.left < 1 || box.bottom - box.top < 1) return null;
  return box;
}

function viewportBox(): Box {
  const view = window.visualViewport;
  const left = view?.offsetLeft ?? 0;
  const top = view?.offsetTop ?? 0;
  return {
    top,
    left,
    right: left + (view?.width ?? window.innerWidth),
    bottom: top + (view?.height ?? window.innerHeight),
  };
}

function overflowClips(value: string): boolean {
  return value === "auto" || value === "scroll" || value === "hidden" || value === "clip" || value === "overlay";
}

function scrollerFrom(target: EventTarget | null): HTMLElement | null {
  if (target instanceof HTMLElement) return target;
  if (target === document || target === document.documentElement || target === document.body) {
    const scrolling = document.scrollingElement;
    return scrolling instanceof HTMLElement ? scrolling : document.documentElement;
  }
  return null;
}

function isThumb(node: Node | null): boolean {
  return node instanceof HTMLElement && node.classList.contains("app-overlay-scrollbar");
}

function layerZ(el: HTMLElement): number {
  let z = BASE_Z;
  let node: HTMLElement | null = el;
  while (node && node !== document.body) {
    const raw = getComputedStyle(node).zIndex;
    const value = Number(raw);
    if (raw !== "auto" && Number.isFinite(value)) z = Math.max(z, value + 1);
    node = node.parentElement;
  }
  return z;
}

function isLightSurface(el: HTMLElement): boolean {
  let node: HTMLElement | null = el;
  while (node) {
    const color = parseColor(getComputedStyle(node).backgroundColor);
    if (color && color.a >= 0.5) {
      const lum = (0.2126 * color.r + 0.7152 * color.g + 0.0722 * color.b) / 255;
      return lum >= 0.55;
    }
    node = node.parentElement;
  }
  return true;
}

function parseColor(bg: string): { r: number; g: number; b: number; a: number } | null {
  const match = bg.match(
    /rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.]+))?\s*\)/,
  );
  if (!match) return null;
  return {
    r: Number(match[1]),
    g: Number(match[2]),
    b: Number(match[3]),
    a: match[4] === undefined ? 1 : Number(match[4]),
  };
}
