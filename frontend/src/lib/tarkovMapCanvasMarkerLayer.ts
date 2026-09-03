/** Leaflet 图层：把密集图标画进一张跟 pane 走的 Canvas。 */

import L from "leaflet";
import { pos } from "./tarkovMapCrs";
import {
  canvasIconScreenRect,
  canvasIconViewSize,
  hitTestCanvasIcons,
  ICON_CANVAS_PADDING,
  ICON_CANVAS_PANE,
  ICON_CANVAS_Z_INDEX,
  layerPointToCanvasPoint,
  markCanvasMarkerEvent,
  rectsOverlap,
  sortCanvasMarkersByZ,
  uniqueCanvasIconUrls,
  type TarkovCanvasIconHit,
  type TarkovCanvasMarker,
} from "./tarkovMapCanvasMarkers";
import {
  estimatedCanvasTooltipHeight,
  lootDetailCardOverflowFlip,
  pickTooltipVerticalSide,
  siblingMapTooltips,
  spawnTooltipSideAfterLayout,
  CANVAS_TOOLTIP_HIDE_MS,
  TARKOV_MAP_TIP_SPAWN,
  tooltipSideFromClassName,
  type TarkovMapTooltipSide,
} from "./tarkovMapTooltip";
import { lootItemFromChip } from "./tarkovMapLootLoose";

const ICON_CACHE = new Map<string, HTMLImageElement>();
const ICON_LOADING = new Map<string, Promise<HTMLImageElement | null>>();

const BADGE_FILL: Record<string, string> = {
  own: "#2ea44f",
  missing: "#d64545",
  teammate: "#4a8fd4",
};

function drawMarkerBadge(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  badge: string,
) {
  const r = 5;
  const cx = x + w - 4;
  const cy = y + h - 4;
  ctx.save();
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.fillStyle = BADGE_FILL[badge] || BADGE_FILL.missing;
  ctx.fill();
  ctx.strokeStyle = "rgba(0,0,0,0.5)";
  ctx.lineWidth = 0.8;
  ctx.stroke();
  ctx.strokeStyle = "#fff";
  ctx.fillStyle = "#fff";
  ctx.lineWidth = 1.35;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  if (badge === "own") {
    ctx.beginPath();
    ctx.moveTo(cx - 2.4, cy);
    ctx.lineTo(cx - 0.5, cy + 2.1);
    ctx.lineTo(cx + 2.6, cy - 2.2);
    ctx.stroke();
  } else if (badge === "missing") {
    ctx.beginPath();
    ctx.moveTo(cx - 2.2, cy - 2.2);
    ctx.lineTo(cx + 2.2, cy + 2.2);
    ctx.moveTo(cx + 2.2, cy - 2.2);
    ctx.lineTo(cx - 2.2, cy + 2.2);
    ctx.stroke();
  } else {
    ctx.beginPath();
    ctx.arc(cx, cy - 1.7, 1.35, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(cx - 2.5, cy + 3.6);
    ctx.quadraticCurveTo(cx - 2.5, cy + 0.6, cx, cy + 0.6);
    ctx.quadraticCurveTo(cx + 2.5, cy + 0.6, cx + 2.5, cy + 3.6);
    ctx.closePath();
    ctx.fill();
  }
  ctx.restore();
}

export type TarkovCanvasLayerOptions = L.LayerOptions & {
  tooltipClassName?: string;
  onHoverId?: (id: string | null) => void;
  onLootItemClick?: (itemId: string, types: readonly string[]) => void;
};

function loadCanvasIcon(url: string): Promise<HTMLImageElement | null> {
  const cached = ICON_CACHE.get(url);
  if (cached) return Promise.resolve(cached);
  const pending = ICON_LOADING.get(url);
  if (pending) return pending;
  const task = new Promise<HTMLImageElement | null>((resolve) => {
    const img = new Image();
    img.onload = () => {
      ICON_CACHE.set(url, img);
      ICON_LOADING.delete(url);
      resolve(img);
    };
    img.onerror = () => {
      ICON_LOADING.delete(url);
      resolve(null);
    };
    img.src = url;
  });
  ICON_LOADING.set(url, task);
  return task;
}

function isLeafletViewReady(map: L.Map): boolean {
  return Boolean((map as unknown as { _loaded?: boolean })._loaded);
}

function eventFromDomTarget(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false;
  return Boolean(
    target.closest(
      ".leaflet-marker-pane, .leaflet-control, .leaflet-popup-pane, .leaflet-tooltip-pane",
    ),
  );
}

function applyCanvasTooltipSide(
  tooltip: L.Tooltip,
  side: TarkovMapTooltipSide,
  pad: number,
) {
  tooltip.options.direction = side;
  tooltip.options.offset = L.point(
    0,
    side === "top" ? -Math.abs(pad) : Math.abs(pad),
  );
}

export class TarkovMapCanvasMarkerLayer extends L.Layer {
  declare options: TarkovCanvasLayerOptions;
  private canvas: HTMLCanvasElement | null = null;
  private ctx: CanvasRenderingContext2D | null = null;
  private markers: TarkovCanvasMarker[] = [];
  private hits: TarkovCanvasIconHit[] = [];
  private origin = { x: 0, y: 0 };
  private viewRect = { left: 0, top: 0, right: 0, bottom: 0 };
  private tooltip: L.Tooltip | null = null;
  private hoverId: string | null = null;
  private hoverPad = 12;
  private hideTimer = 0;
  private hoveredLootChip: HTMLElement | null = null;
  private interactive = true;
  private panning = false;
  private redrawTimer = 0;

  constructor(options?: TarkovCanvasLayerOptions) {
    super();
    L.Util.setOptions(this, {
      pane: ICON_CANVAS_PANE,
      tooltipClassName: "",
      ...options,
    });
  }

  beforeAdd(map: L.Map): this {
    if (!map.getPane(ICON_CANVAS_PANE)) {
      const pane = map.createPane(ICON_CANVAS_PANE);
      pane.style.zIndex = ICON_CANVAS_Z_INDEX;
      pane.style.pointerEvents = "none";
    }
    return this;
  }

  onAdd(map: L.Map): this {
    const pane = this.getPane(ICON_CANVAS_PANE);
    if (!pane) return this;
    const canvas = L.DomUtil.create(
      "canvas",
      "tarkov-icon-canvas",
      pane,
    ) as HTMLCanvasElement;
    canvas.style.position = "absolute";
    canvas.style.pointerEvents = "none";
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    const extra = (this.options.tooltipClassName || "").trim();
    this.tooltip = L.tooltip({
      direction: "top",
      opacity: 0.96,
      interactive: true,
      className: extra
        ? `${extra} ${TARKOV_MAP_TIP_SPAWN}`
        : TARKOV_MAP_TIP_SPAWN,
      offset: [0, -12],
    });
    this.resetView();
    map.getContainer().addEventListener("mousemove", this.onDomMove);
    map.getContainer().addEventListener("mouseleave", this.onDomLeave);
    map.getContainer().addEventListener("click", this.onDomClick, true);
    return this;
  }

  onRemove(map: L.Map): this {
    window.clearTimeout(this.redrawTimer);
    this.cancelHide();
    map.getContainer().removeEventListener("mousemove", this.onDomMove);
    map.getContainer().removeEventListener("mouseleave", this.onDomLeave);
    map.getContainer().removeEventListener("click", this.onDomClick, true);
    this.clearHover();
    this.tooltip = null;
    this.canvas?.remove();
    this.canvas = null;
    this.ctx = null;
    this.hits = [];
    return this;
  }

  getEvents(): { [name: string]: (event: L.LeafletEvent) => void } {
    return {
      moveend: this.resetView,
      zoomend: this.resetView,
      resize: this.resetView,
      viewreset: this.resetView,
      dragstart: this.onDragStart,
      dragend: this.onDragEnd,
      tooltipopen: this.onMapTooltipOpen,
    };
  }

  setMarkers(markers: readonly TarkovCanvasMarker[]): this {
    this.markers = sortCanvasMarkersByZ(markers);
    void this.preloadIcons();
    this.resetView();
    return this;
  }

  setInteractive(on: boolean): this {
    this.interactive = on;
    if (!on) this.clearHover();
    return this;
  }

  private preloadIcons = async () => {
    const urls = uniqueCanvasIconUrls(this.markers);
    if (!urls.length) return;
    const pending = urls.filter((url) => !ICON_CACHE.has(url));
    if (!pending.length) return;
    await Promise.all(pending.map((url) => loadCanvasIcon(url)));
    this.scheduleRedraw();
  };

  private scheduleRedraw = () => {
    window.clearTimeout(this.redrawTimer);
    this.redrawTimer = window.setTimeout(() => this.paint(), 0);
  };

  private resetView = () => {
    const map = this._map;
    const canvas = this.canvas;
    if (!map || !canvas || !isLeafletViewReady(map)) return;
    const size = map.getSize();
    const view = canvasIconViewSize(size, ICON_CANVAS_PADDING);
    const min = map
      .containerPointToLayerPoint(L.point(-view.padX, -view.padY))
      .round();
    this.origin = { x: min.x, y: min.y };
    this.viewRect = {
      left: min.x,
      top: min.y,
      right: min.x + view.width,
      bottom: min.y + view.height,
    };
    const cssW = Math.max(1, Math.round(view.width));
    const cssH = Math.max(1, Math.round(view.height));
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.style.width = `${cssW}px`;
    canvas.style.height = `${cssH}px`;
    canvas.width = Math.max(1, Math.round(cssW * dpr));
    canvas.height = Math.max(1, Math.round(cssH * dpr));
    this.ctx?.setTransform(dpr, 0, 0, dpr, 0, 0);
    L.DomUtil.setPosition(canvas, min);
    this.paint();
  };

  private paint = () => {
    const map = this._map;
    const ctx = this.ctx;
    const canvas = this.canvas;
    if (!map || !ctx || !canvas || !isLeafletViewReady(map)) return;
    const cssW = canvas.clientWidth || 1;
    const cssH = canvas.clientHeight || 1;
    ctx.clearRect(0, 0, cssW, cssH);
    this.hits = [];
    let hover: TarkovCanvasMarker | null = null;
    for (const marker of this.markers) {
      const layerPt = map.latLngToLayerPoint(
        L.latLng(pos({ x: marker.x, z: marker.z })),
      );
      const rect = canvasIconScreenRect(
        layerPt,
        marker.iconSize,
        marker.iconAnchor,
      );
      if (!rectsOverlap(rect, this.viewRect)) continue;
      this.hits.push({
        id: marker.id,
        left: rect.left,
        top: rect.top,
        right: rect.right,
        bottom: rect.bottom,
        zIndex: marker.zIndex ?? 0,
        marker,
      });
      if (marker.id === this.hoverId) {
        hover = marker;
        continue;
      }
      this.drawIcon(ctx, marker, rect);
    }
    if (hover) {
      const layerPt = map.latLngToLayerPoint(
        L.latLng(pos({ x: hover.x, z: hover.z })),
      );
      const rect = canvasIconScreenRect(
        layerPt,
        hover.iconSize,
        hover.iconAnchor,
      );
      this.drawIcon(ctx, hover, rect, true);
    }
  };

  private drawIcon(
    ctx: CanvasRenderingContext2D,
    marker: TarkovCanvasMarker,
    rect: { left: number; top: number; right: number; bottom: number },
    highlight = false,
  ) {
    const img = ICON_CACHE.get(marker.iconUrl);
    if (!img) return;
    const at = layerPointToCanvasPoint(
      { x: rect.left, y: rect.top },
      this.origin,
    );
    const w = marker.iconSize[0];
    const h = marker.iconSize[1];
    if (highlight) {
      ctx.save();
      ctx.strokeStyle = "#e8c36a";
      ctx.lineWidth = 1.5;
      ctx.strokeRect(at.x - 1.5, at.y - 1.5, w + 3, h + 3);
      ctx.restore();
    }
    ctx.drawImage(img, at.x, at.y, w, h);
    if (marker.badge) drawMarkerBadge(ctx, at.x, at.y, w, h, marker.badge);
  }

  private hitFromMouse(event: MouseEvent): TarkovCanvasIconHit | null {
    const map = this._map;
    if (!map || !isLeafletViewReady(map)) return null;
    return hitTestCanvasIcons(this.hits, map.mouseEventToLayerPoint(event));
  }

  private onDragStart = () => {
    this.panning = true;
    this.clearHover();
  };

  private onDragEnd = () => {
    this.panning = false;
  };

  private isOverOwnTooltip(target: EventTarget | null): boolean {
    const el = this.tooltip?.getElement();
    return Boolean(el && target instanceof Node && el.contains(target));
  }

  private cancelHide() {
    if (!this.hideTimer) return;
    window.clearTimeout(this.hideTimer);
    this.hideTimer = 0;
  }

  private scheduleHide() {
    if (!this.hoverId && !this.tooltip?.isOpen()) return;
    this.cancelHide();
    this.hideTimer = window.setTimeout(() => {
      this.hideTimer = 0;
      this.clearHover();
    }, CANVAS_TOOLTIP_HIDE_MS);
  }

  private onDomMove = (event: MouseEvent) => {
    if (!this.interactive || !this._map || this.panning) return;
    if (this.isOverOwnTooltip(event.target)) {
      this.cancelHide();
      return;
    }
    if (eventFromDomTarget(event.target)) {
      this.cancelHide();
      this.clearHover();
      return;
    }
    const hit = this.hitFromMouse(event);
    if (hit) {
      this.cancelHide();
      this.setHover(hit);
      return;
    }
    this.scheduleHide();
  };

  private onDomLeave = () => {
    this.cancelHide();
    this.clearHover();
  };

  private onDomClick = (event: MouseEvent) => {
    if (!this.interactive || !this._map || this.panning) return;
    if (this.handleLootItemClick(event)) return;
    if (eventFromDomTarget(event.target)) return;
    const hit = this.hitFromMouse(event);
    if (!hit) return;
    markCanvasMarkerEvent(event);
    event.preventDefault();
    event.stopPropagation();
    hit.marker.onClick?.();
  };

  private handleLootItemClick(event: MouseEvent): boolean {
    if (!(event.target instanceof Element)) return false;
    const chip = event.target.closest("[data-tarkov-loot-item]");
    if (!(chip instanceof HTMLElement)) return false;
    const item = lootItemFromChip(chip);
    if (!item || !this.options.onLootItemClick) return false;
    markCanvasMarkerEvent(event);
    event.preventDefault();
    event.stopPropagation();
    this.options.onLootItemClick(item.id, item.types);
    return true;
  }

  private onMapTooltipOpen = () => {
    if (!this.tooltip?.isOpen() || !this.hoverId) return;
    const hoverId = this.hoverId;
    const pad = this.hoverPad;
    window.requestAnimationFrame(() => this.avoidQuestOverlap(hoverId, pad));
  };

  private setHover(hit: TarkovCanvasIconHit | null) {
    const map = this._map;
    const nextId = hit?.id ?? null;
    const idChanged = nextId !== this.hoverId;
    if (idChanged) {
      this.hoverId = nextId;
      this.paint();
      this.options.onHoverId?.(nextId);
    }
    if (!map) return;
    L.DomUtil[hit ? "addClass" : "removeClass"](
      map.getContainer(),
      "tarkov-canvas-hit",
    );
    if (!hit || !this.tooltip) {
      this.hideTooltip();
      return;
    }
    const latlng = L.latLng(pos({ x: hit.marker.x, z: hit.marker.z }));
    const pad = Math.max(8, hit.marker.iconAnchor[1] || 12);
    this.hoverPad = pad;
    if (idChanged || !this.tooltip.isOpen()) {
      const point = map.latLngToContainerPoint(latlng);
      const side = pickTooltipVerticalSide({
        pointY: point.y,
        mapHeight: map.getSize().y,
        tooltipHeight: estimatedCanvasTooltipHeight(hit.marker.tooltipHtml),
      });
      applyCanvasTooltipSide(this.tooltip, side, pad);
    }
    this.tooltip.setContent(hit.marker.tooltipHtml);
    this.tooltip.setLatLng(latlng);
    if (!this.tooltip.isOpen()) map.openTooltip(this.tooltip);
    else if (idChanged) this.tooltip.update();
    this.bindTooltipStay();
    if (idChanged) {
      const hoverId = hit.id;
      window.requestAnimationFrame(() => this.avoidQuestOverlap(hoverId, pad));
    }
  }

  private bindTooltipStay() {
    const el = this.tooltip?.getElement();
    if (!el || el.dataset.zhangeStay === "1") return;
    el.dataset.zhangeStay = "1";
    el.addEventListener("mouseenter", this.onTooltipEnter);
    el.addEventListener("mouseleave", this.onTooltipLeave);
    el.addEventListener("mouseover", this.onTooltipItemOver);
  }

  private onTooltipEnter = () => {
    this.cancelHide();
  };

  private onTooltipLeave = () => {
    this.hoveredLootChip = null;
    this.scheduleHide();
  };

  private onTooltipItemOver = (event: MouseEvent) => {
    if (!(event.target instanceof Element)) return;
    const chip = event.target.closest("[data-tarkov-loot-chip]");
    if (!(chip instanceof HTMLElement) || this.hoveredLootChip === chip) return;
    const card = chip.querySelector("[role='tooltip']");
    const wrap = this._map?.getContainer();
    if (!(card instanceof HTMLElement) || !wrap) return;
    this.hoveredLootChip = chip;
    chip.removeAttribute("data-flip-x");
    chip.removeAttribute("data-flip-y");
    window.requestAnimationFrame(() => {
      if (this.hoveredLootChip !== chip || !chip.isConnected) return;
      const next = lootDetailCardOverflowFlip(
        card.getBoundingClientRect(),
        wrap.getBoundingClientRect(),
      );
      if (next.flipX) chip.setAttribute("data-flip-x", "1");
      if (next.flipY) chip.setAttribute("data-flip-y", "1");
    });
  };

  private avoidQuestOverlap(hoverId: string, pad: number) {
    const map = this._map;
    const tooltip = this.tooltip;
    if (!map || !tooltip || this.hoverId !== hoverId || !tooltip.isOpen()) {
      return;
    }
    const el = tooltip.getElement();
    const latlng = tooltip.getLatLng();
    if (!el || !latlng) return;
    const box = el.getBoundingClientRect();
    const point = map.latLngToContainerPoint(latlng);
    const next = spawnTooltipSideAfterLayout({
      current: tooltipSideFromClassName(el.className) || "top",
      self: {
        left: box.left,
        top: box.top,
        right: box.right,
        bottom: box.bottom,
      },
      others: siblingMapTooltips(map.getPane("tooltipPane"), el),
      pointY: point.y,
      mapHeight: map.getSize().y,
      tooltipHeight: el.offsetHeight || 56,
    });
    const current = tooltipSideFromClassName(el.className) || "top";
    if (next === current) return;
    applyCanvasTooltipSide(tooltip, next, pad);
    tooltip.update();
  }

  private clearHover() {
    const map = this._map;
    if (this.hoverId) {
      this.hoverId = null;
      this.paint();
      this.options.onHoverId?.(null);
    }
    if (map) L.DomUtil.removeClass(map.getContainer(), "tarkov-canvas-hit");
    this.hideTooltip();
  }

  private hideTooltip() {
    this.cancelHide();
    const map = this._map;
    const tooltip = this.tooltip;
    if (!map || !tooltip || !tooltip.isOpen()) return;
    map.closeTooltip(tooltip);
  }
}
