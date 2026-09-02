/** 密集地图图标的投影 / 命中；Leaflet 图层在 tarkovMapCanvasMarkerLayer。 */

export const ICON_CANVAS_PANE = "iconCanvasPane";
export const ICON_CANVAS_PADDING = 0.45;
export const ICON_CANVAS_Z_INDEX = "580";
export const CANVAS_MARKER_EVENT = "_zhangeTarkovCanvasHit";

export type TarkovCanvasMarker = {
  id: string;
  x: number;
  z: number;
  iconUrl: string;
  iconSize: [number, number];
  iconAnchor: [number, number];
  tooltipHtml: string;
  onClick?: () => void;
  zIndex?: number;
};

export type TarkovCanvasIconHit = {
  id: string;
  left: number;
  top: number;
  right: number;
  bottom: number;
  zIndex: number;
  marker: TarkovCanvasMarker;
};

export function canvasIconViewSize(
  mapSize: { x: number; y: number },
  padding: number,
): { width: number; height: number; padX: number; padY: number } {
  const padX = mapSize.x * padding;
  const padY = mapSize.y * padding;
  return {
    width: mapSize.x + padX * 2,
    height: mapSize.y + padY * 2,
    padX,
    padY,
  };
}

export function layerPointToCanvasPoint(
  layerPoint: { x: number; y: number },
  origin: { x: number; y: number },
): { x: number; y: number } {
  return {
    x: layerPoint.x - origin.x,
    y: layerPoint.y - origin.y,
  };
}

export function canvasIconScreenRect(
  layerPoint: { x: number; y: number },
  iconSize: readonly [number, number],
  iconAnchor: readonly [number, number],
): { left: number; top: number; right: number; bottom: number } {
  const left = layerPoint.x - iconAnchor[0];
  const top = layerPoint.y - iconAnchor[1];
  return {
    left,
    top,
    right: left + iconSize[0],
    bottom: top + iconSize[1],
  };
}

export function rectsOverlap(
  a: { left: number; top: number; right: number; bottom: number },
  b: { left: number; top: number; right: number; bottom: number },
): boolean {
  return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
}

export function pointHitsCanvasIcon(
  point: { x: number; y: number },
  rect: { left: number; top: number; right: number; bottom: number },
): boolean {
  return (
    point.x >= rect.left &&
    point.x < rect.right &&
    point.y >= rect.top &&
    point.y < rect.bottom
  );
}

export function hitTestCanvasIcons<T extends TarkovCanvasIconHit>(
  hits: readonly T[],
  point: { x: number; y: number },
): T | null {
  let best: T | null = null;
  for (const hit of hits) {
    if (!pointHitsCanvasIcon(point, hit)) continue;
    if (!best || hit.zIndex >= best.zIndex) best = hit;
  }
  return best;
}

export function uniqueCanvasIconUrls(
  markers: ReadonlyArray<{ iconUrl: string }>,
): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const row of markers) {
    const url = row.iconUrl.trim();
    if (!url || seen.has(url)) continue;
    seen.add(url);
    out.push(url);
  }
  return out;
}

export function sortCanvasMarkersByZ<T extends { zIndex?: number }>(
  markers: readonly T[],
): T[] {
  return markers
    .map((row, index) => ({ row, index }))
    .sort(
      (a, b) =>
        (a.row.zIndex ?? 0) - (b.row.zIndex ?? 0) || a.index - b.index,
    )
    .map((item) => item.row);
}

export function markCanvasMarkerEvent(event: Event): void {
  (event as unknown as Record<string, boolean>)[CANVAS_MARKER_EVENT] = true;
}

export function isCanvasMarkerEvent(event: Event | undefined | null): boolean {
  if (!event) return false;
  return Boolean(
    (event as unknown as Record<string, boolean>)[CANVAS_MARKER_EVENT],
  );
}
