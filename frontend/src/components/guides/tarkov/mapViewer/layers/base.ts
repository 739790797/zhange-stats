/** 底图：SVG / 瓦片挂载、楼层 class 切换、平移缩放护栏与缩放控件。 */

import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { fetchTarkovMapSvg } from "@/api/guidesApi";
import "@/components/guides/tarkov/tarkovFonts.css";
import { getBounds } from "@/lib/tarkovMapCrs";
import { mapBaseOffLevel, svgFloorGroupClasses } from "@/lib/tarkovMapFloors";
import { svgFallbackUrl, type TarkovDevMapLayer } from "@/lib/tarkovMapImages";
import { sanitizeTarkovMapSvg } from "@/lib/tarkovMapSvg";
import { svgBasemapZoomLimit, svgOverlayScale } from "@/lib/tarkovMapSvgOverlay";
import styles from "../../TarkovMapViewer.module.css";
import { type MapRuntime, SVG_BASE_PANE } from "../runtime";

export function setSvgFloor(
  root: SVGSVGElement | undefined,
  baseId: string,
  floorId: string,
  keepBaseOpaque = false,
) {
  const inner = root?.children[0];
  if (!root || !inner) return;
  root.classList.toggle(
    "off-level",
    mapBaseOffLevel(floorId, keepBaseOpaque),
  );
  for (const child of Array.from(inner.children)) {
    if (child.nodeName.toLowerCase() !== "g") continue;
    const group = child as SVGGElement;
    if (!group.id) continue;
    const flags = svgFloorGroupClasses(
      { id: group.id, keepWithGroup: group.dataset.keepWithGroup },
      baseId,
      floorId,
    );
    group.classList.toggle("base-layer", flags["base-layer"]);
    group.classList.toggle("overlay-layer", flags["overlay-layer"]);
    group.classList.toggle("hidden-layer", flags["hidden-layer"]);
  }
}

export function attachInteractiveTiles(
  runtime: MapRuntime,
  layer: TarkovDevMapLayer,
  bounds: L.LatLngBounds,
  maxZoom: number,
) {
  const tileSize = layer.tileSize || 256;
  if (!runtime.tileLayer && layer.tilePath) {
    runtime.tileLayer = L.tileLayer(layer.tilePath, {
      tileSize,
      bounds,
      maxZoom,
      maxNativeZoom: layer.maxZoom ?? 5,
    });
  }
  for (const floorLayer of layer.layers || []) {
    if (!floorLayer.tilePath || runtime.floorTiles.has(floorLayer.name)) continue;
    runtime.floorTiles.set(
      floorLayer.name,
      L.tileLayer(floorLayer.tilePath, {
        tileSize,
        bounds,
        maxZoom,
        maxNativeZoom: layer.maxZoom ?? 5,
      }),
    );
  }
}

const SVG_CAP_ATTR = "data-svg-cap";

type CappedSvgOverlay = L.SVGOverlay & {
  _map?: L.Map;
  _reset: (this: CappedSvgOverlay) => void;
  _animateZoom: (this: CappedSvgOverlay, event: L.ZoomAnimEvent) => void;
};

type ZoomBoundsMap = L.Map & {
  _latLngBoundsToNewLayerBounds: (
    bounds: L.LatLngBounds,
    zoom: number,
    center: L.LatLng,
  ) => L.Bounds;
};

/** 抽象图挂上之后把最大缩放收到安全范围内；切回瓦片时还原。 */
export function applyBasemapZoomCap(
  map: L.Map,
  bounds: L.LatLngBounds,
  tileMaxZoom: number,
  svg: boolean,
) {
  const minZoom = map.getMinZoom();
  let limit = tileMaxZoom;
  if (svg) {
    const nw = map.project(bounds.getNorthWest(), 0);
    const se = map.project(bounds.getSouthEast(), 0);
    limit = svgBasemapZoomLimit(
      Math.abs(se.x - nw.x),
      Math.abs(se.y - nw.y),
      tileMaxZoom,
      minZoom,
    );
  }
  if (Math.abs(map.getMaxZoom() - limit) > 1e-6) map.setMaxZoom(limit);
  if (map.getZoom() > limit + 1e-6) map.setZoom(limit, { animate: false });
}

function capSvgOverlayElement(overlay: CappedSvgOverlay) {
  const map = overlay._map;
  const el = overlay.getElement();
  if (!map || !el) return;
  const box = overlay.getBounds();
  const px = L.bounds(
    map.latLngToLayerPoint(box.getNorthWest()),
    map.latLngToLayerPoint(box.getSouthEast()),
  );
  const size = px.getSize();
  const min = px.min;
  if (!min) return;
  const factor = svgOverlayScale(size.x, size.y);
  el.style.transformOrigin = "0 0";
  if (factor <= 1) {
    el.removeAttribute(SVG_CAP_ATTR);
    return;
  }
  el.setAttribute(SVG_CAP_ATTR, String(factor));
  el.style.width = `${size.x / factor}px`;
  el.style.height = `${size.y / factor}px`;
  el.style.transform = `translate3d(${min.x}px,${min.y}px,0) scale(${factor})`;
}

/** Leaflet 会把 SVG 元素设成整张图的像素尺寸；超过上限就缩小再 scale，避免铺出几十万像素的层。 */
function installSvgOverlayCap(overlay: L.SVGOverlay) {
  const layer = overlay as CappedSvgOverlay;
  const originalReset = layer._reset;
  layer._reset = function cappedReset() {
    originalReset.call(this);
    capSvgOverlayElement(this);
  };
  const originalAnim = layer._animateZoom;
  layer._animateZoom = function cappedAnim(event) {
    originalAnim.call(this, event);
    const el = this.getElement();
    const factor = Number(el?.getAttribute(SVG_CAP_ATTR) || "1");
    const map = this._map as ZoomBoundsMap | undefined;
    if (!el || !map || !(factor > 1)) return;
    const zoomScale = map.getZoomScale(event.zoom);
    const offset = map._latLngBoundsToNewLayerBounds(
      this.getBounds(),
      event.zoom,
      event.center,
    ).min;
    if (!offset) return;
    el.style.transformOrigin = "0 0";
    el.style.transform = `translate3d(${offset.x}px,${offset.y}px,0) scale(${zoomScale * factor})`;
  };
}

export async function attachInteractiveSvg(
  runtime: MapRuntime,
  layer: TarkovDevMapLayer,
  bounds: L.LatLngBounds,
) {
  if (runtime.svgOverlay || !layer.svgPath) return;
  const svg = await loadSvgElement(layer.svgPath);
  runtime.svgRoot = svg;
  setSvgFloor(svg, layer.svgLayer || "", "");
  const svgBounds = getBounds(layer.svgBounds) || bounds;
  runtime.svgOverlay = L.svgOverlay(svg, svgBounds, {
    pane: SVG_BASE_PANE,
    interactive: false,
  });
  installSvgOverlayCap(runtime.svgOverlay);
}

async function loadSvgElement(svgPath: string): Promise<SVGSVGElement> {
  const urls = [svgPath, svgFallbackUrl(svgPath)];
  let lastError: unknown;
  for (const url of urls) {
    try {
      let text: string;
      if (url.startsWith("/api/guides/tarkov/map-svg/")) {
        const name = url.slice(url.lastIndexOf("/") + 1);
        text = await fetchTarkovMapSvg(decodeURIComponent(name));
      } else {
        const res = await fetch(url);
        if (!res.ok) continue;
        text = await res.text();
      }
      const holder = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      holder.setAttribute("xmlns", "http://www.w3.org/2000/svg");
      holder.innerHTML = sanitizeTarkovMapSvg(text);
      const inner = holder.children[0];
      if (inner?.getAttribute("viewBox")) {
        holder.setAttribute("viewBox", inner.getAttribute("viewBox") || "");
      }
      return holder;
    } catch (exc) {
      lastError = exc;
    }
  }
  throw lastError instanceof Error ? lastError : new Error("无法加载 SVG 地图");
}

export function setSvgBakedTextHidden(
  root: SVGSVGElement | undefined,
  hidden: boolean,
) {
  if (!root) return;
  if (hidden) root.setAttribute("data-hide-baked-text", "1");
  else root.removeAttribute("data-hide-baked-text");
}

export function attachPanPerfGuards(map: L.Map, wrapEl: HTMLElement) {
  const closeMapTooltip = () => {
    /* 拖动中关掉气泡即可；Leaflet 在尚未 bind tooltip / 初次 fitBounds 时
       closeTooltip() 会读到 undefined.close，把整张底图初始化打崩。 */
    try {
      const tooltip = (
        map as unknown as { _tooltip?: { _close?: () => void } | null }
      )._tooltip;
      if (tooltip && typeof tooltip._close === "function") {
        tooltip._close();
      }
    } catch {
      /* ignore */
    }
  };
  const setPanning = (on: boolean) => {
    wrapEl.classList.toggle(styles.isPanning, on);
    if (on) closeMapTooltip();
  };
  const setZooming = (on: boolean) => {
    wrapEl.classList.toggle(styles.isZooming, on);
    if (on) closeMapTooltip();
  };
  const onDragStart = () => setPanning(true);
  const onDragEnd = () => setPanning(false);
  const onZoomStart = () => {
    setPanning(true);
    setZooming(true);
  };
  const onZoomEnd = () => {
    setPanning(false);
    setZooming(false);
  };
  map.on("dragstart", onDragStart);
  map.on("zoomstart", onZoomStart);
  map.on("dragend", onDragEnd);
  map.on("zoomend", onZoomEnd);
  return () => {
    map.off("dragstart", onDragStart);
    map.off("zoomstart", onZoomStart);
    map.off("dragend", onDragEnd);
    map.off("zoomend", onZoomEnd);
    wrapEl.classList.remove(styles.isPanning);
    wrapEl.classList.remove(styles.isZooming);
  };
}

export function attachZoomControl(map: L.Map) {
  L.control
    .zoom({
      position: "bottomleft",
      zoomInTitle: "放大",
      zoomOutTitle: "缩小",
    })
    .addTo(map);
}
