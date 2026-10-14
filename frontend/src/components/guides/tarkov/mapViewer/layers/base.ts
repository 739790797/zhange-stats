/** 底图：SVG / 瓦片挂载、楼层 class 切换、平移缩放护栏与缩放控件。 */

import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "@/components/guides/tarkov/tarkovFonts.css";
import { getBounds } from "@/lib/tarkovMapCrs";
import { mapBaseOffLevel, svgFloorGroupClasses } from "@/lib/tarkovMapFloors";
import { svgFallbackUrl, type TarkovDevMapLayer } from "@/lib/tarkovMapImages";
import { sanitizeTarkovMapSvg } from "@/lib/tarkovMapSvg";
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
}

async function loadSvgElement(svgPath: string): Promise<SVGSVGElement> {
  const urls = [svgPath, svgFallbackUrl(svgPath)];
  let lastError: unknown;
  for (const url of urls) {
    try {
      const res = await fetch(url);
      if (!res.ok) continue;
      const text = await res.text();
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
