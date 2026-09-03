/** 对齐 tarkov.dev map/index.jsx：撤离 / 危险区 / 转图 hover 才画 outline。 */

export type TarkovMapOutlinePoint = {
  x?: number | null;
  z?: number | null;
};

export type TarkovMapOutlineXz = { x: number; z: number };

export function usableOutlinePoints(
  outline?: TarkovMapOutlinePoint[] | null,
): TarkovMapOutlineXz[] {
  if (!outline || outline.length < 3) return [];
  const pts: TarkovMapOutlineXz[] = [];
  for (const point of outline) {
    if (point.x == null || point.z == null) continue;
    if (!Number.isFinite(point.x) || !Number.isFinite(point.z)) continue;
    pts.push({ x: point.x, z: point.z });
  }
  return pts.length >= 3 ? pts : [];
}

export function hazardOutlineColor(kind: string): string {
  if (kind === "mortar") return "#c8932a";
  if (kind === "sniper") return "#d4b84a";
  return "#d44a4a";
}

export const MARKER_OUTLINE_HIDDEN = {
  color: "#f4e6b3",
  weight: 2,
  opacity: 0,
  fillColor: "#f4e6b3",
  fillOpacity: 0,
  interactive: false,
} as const;

export function markerOutlineShown(color = "#f4e6b3") {
  return {
    ...MARKER_OUTLINE_HIDDEN,
    color,
    fillColor: color,
    opacity: 1,
    fillOpacity: 0.12,
  };
}
