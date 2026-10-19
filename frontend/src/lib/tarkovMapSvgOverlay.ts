/**
 * 抽象底图是一整张 SVG，Leaflet 会按当前缩放把它的 CSS 宽高设成整张图的像素尺寸。
 * 房间页把最大缩放放到 7 级之后，这张图会到几万像素，浏览器按这个尺寸铺层，标签页直接 Out of Memory。
 * 长边收到这个上限里：再放大就用 CSS scale，布局尺寸不再跟着涨。
 */
export const SVG_OVERLAY_MAX_PX = 4096;

/** 缩放 0 级时底图的像素宽高 → 长边刚好碰到上限的缩放级。 */
export function svgOverlayMaxZoom(
  widthAtZoom0: number,
  heightAtZoom0: number,
  capPx = SVG_OVERLAY_MAX_PX,
): number {
  const long = Math.max(widthAtZoom0, heightAtZoom0);
  if (!Number.isFinite(long) || long <= 0 || !Number.isFinite(capPx) || capPx <= 0) {
    return Number.POSITIVE_INFINITY;
  }
  return Math.log2(capPx / long);
}

/**
 * 瓦片可以放到原来的最大级；抽象图不能超过「长边 = cap」的那一级，
 * 也不能低于地图自己的最小级。
 */
export function svgBasemapZoomLimit(
  widthAtZoom0: number,
  heightAtZoom0: number,
  tileMaxZoom: number,
  minZoom: number,
  capPx = SVG_OVERLAY_MAX_PX,
): number {
  const capped = svgOverlayMaxZoom(widthAtZoom0, heightAtZoom0, capPx);
  const limit = Math.min(tileMaxZoom, capped);
  if (!Number.isFinite(limit)) return tileMaxZoom;
  return Math.max(minZoom, limit);
}

/** >1 表示当前像素尺寸已经超过上限，元素要缩小这么多倍再 scale 回去。 */
export function svgOverlayScale(
  width: number,
  height: number,
  capPx = SVG_OVERLAY_MAX_PX,
): number {
  const long = Math.max(width, height);
  if (!Number.isFinite(long) || long <= capPx || !Number.isFinite(capPx) || capPx <= 0) {
    return 1;
  }
  return long / capPx;
}
