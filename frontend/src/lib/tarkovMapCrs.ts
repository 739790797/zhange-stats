import L from "leaflet";
import type { TarkovDevMapLayer } from "@/lib/tarkovMapImages";

export function pos(position: { x: number; z: number }): L.LatLngExpression {
  return [position.z, position.x];
}

export function getBounds(bounds?: number[][]): L.LatLngBounds | undefined {
  if (!bounds || bounds.length < 2) return undefined;
  const a = bounds[0];
  const b = bounds[1];
  if (!a || !b || a.length < 2 || b.length < 2) return undefined;
  return L.latLngBounds([a[1], a[0]], [b[1], b[0]]);
}

export function getScaledBounds(
  bounds: number[][],
  scaleFactor: number,
): L.LatLngBounds | undefined {
  const box = getBounds(bounds);
  if (!box) return undefined;
  const center = box.getCenter();
  const sw = box.getSouthWest();
  const ne = box.getNorthEast();
  const latSpan = (ne.lat - sw.lat) * scaleFactor;
  const lngSpan = (ne.lng - sw.lng) * scaleFactor;
  return L.latLngBounds(
    [center.lat - latSpan / 2, center.lng - lngSpan / 2],
    [center.lat + latSpan / 2, center.lng + lngSpan / 2],
  );
}

function applyRotation(latLng: L.LatLng, rotation: number): L.LatLng {
  if (!rotation) return latLng;
  const angle = (rotation * Math.PI) / 180;
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  const { lng: x, lat: y } = latLng;
  return L.latLng(x * sin + y * cos, x * cos - y * sin);
}

export function getCRS(mapData: TarkovDevMapLayer): L.CRS {
  let scaleX = 1;
  let scaleY = -1;
  let marginX = 0;
  let marginY = 0;
  const transform = mapData.transform;
  if (transform && transform.length >= 4) {
    scaleX = transform[0];
    scaleY = transform[2] * -1;
    marginX = transform[1];
    marginY = transform[3];
  }
  const rotation = mapData.coordinateRotation || 0;
  return L.extend({}, L.CRS.Simple, {
    transformation: new L.Transformation(scaleX, marginX, scaleY, marginY),
    projection: L.extend({}, L.Projection.LonLat, {
      project: (latLng: L.LatLng) =>
        L.Projection.LonLat.project(applyRotation(latLng, rotation)),
      unproject: (point: L.Point) =>
        applyRotation(
          L.Projection.LonLat.unproject(point),
          rotation * -1,
        ),
    }),
  });
}
