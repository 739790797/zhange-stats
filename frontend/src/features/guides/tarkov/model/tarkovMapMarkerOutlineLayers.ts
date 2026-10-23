/** Leaflet 轮廓层：默认隐藏，hover 显示。 */

import L from "leaflet";
import { pos } from "./tarkovMapCrs";
import {
  MARKER_OUTLINE_HIDDEN,
  markerOutlineShown,
  usableOutlinePoints,
  type TarkovMapOutlinePoint,
} from "./tarkovMapMarkerOutlines";

export function addMarkerOutline(
  group: L.LayerGroup,
  outline: TarkovMapOutlinePoint[] | null | undefined,
  color?: string,
): L.Polygon | null {
  const pts = usableOutlinePoints(outline);
  if (!pts.length) return null;
  const stroke = color || MARKER_OUTLINE_HIDDEN.color;
  const polygon = L.polygon(
    pts.map((point) => pos({ x: point.x, z: point.z })),
    {
      ...MARKER_OUTLINE_HIDDEN,
      color: stroke,
      fillColor: stroke,
    },
  );
  polygon.addTo(group);
  return polygon;
}

export function bindMarkerOutlineHover(
  marker: L.Marker,
  polygon: L.Polygon | null,
  color?: string,
) {
  if (!polygon) return;
  const shown = markerOutlineShown(color);
  marker.on("mouseover", () => polygon.setStyle(shown));
  marker.on("mouseout", () =>
    polygon.setStyle({
      ...MARKER_OUTLINE_HIDDEN,
      color: color || MARKER_OUTLINE_HIDDEN.color,
      fillColor: color || MARKER_OUTLINE_HIDDEN.fillColor,
    }),
  );
}

export function setMarkerOutlineVisible(
  polygon: L.Polygon | undefined,
  on: boolean,
) {
  if (!polygon) return;
  const color = String(polygon.options.color || "#f4e6b3");
  polygon.setStyle(
    on
      ? markerOutlineShown(color)
      : { ...MARKER_OUTLINE_HIDDEN, color, fillColor: color },
  );
}
