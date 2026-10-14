/** 自定义地名：标签与区域框，含库内编辑（选中 / 拖动）。 */

import { escapeHtml } from "@/lib/escapeHtml";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "@/components/guides/tarkov/tarkovFonts.css";
import { pos } from "@/lib/tarkovMapCrs";
import {
  PLACE_LABEL_FONT_PX,
  placeLabelIconSize,
  placeNameLines,
  type ResolvedMapPlace,
  type TarkovMapPlaceEdit,
} from "@/lib/tarkovMapPlaceLabels";
import styles from "../../TarkovMapViewer.module.css";

export function addLabelMarkers(
  group: L.LayerGroup,
  labels: ResolvedMapPlace[],
  edit?: TarkovMapPlaceEdit,
) {
  group.clearLayers();
  const selecting = edit?.mode === "select";
  for (const label of labels) {
    if (!label.position || label.position.length < 2) continue;
    const rotation = label.rotation || 0;
    const lines = placeNameLines(label.text || "");
    if (!lines.length) continue;
    const box = placeLabelIconSize(lines.join("\n"), PLACE_LABEL_FONT_PX);
    const canEdit = selecting && label.id != null;
    const selected = canEdit && edit?.selectedId === label.id;
    const body = lines
      .map((line) => `<span class="${styles.labelLine}">${escapeHtml(line)}</span>`)
      .join("");
    const rotate = rotation ? `transform:rotate(${rotation}deg)` : "";
    const marker = L.marker(pos({ x: label.position[0], z: label.position[1] }), {
      icon: L.divIcon({
        className: `${styles.labelIcon}${selected ? ` ${styles.labelIconOn}` : ""}`,
        html: `<span class="${styles.labelText}"${rotate ? ` style="${rotate}"` : ""}>${body}</span>`,
        iconSize: [box.w, box.h],
        iconAnchor: [box.w / 2, box.h / 2],
      }),
      interactive: canEdit,
      draggable: canEdit,
      autoPan: false,
    });
    if (canEdit && label.id != null) {
      const id = label.id;
      let dragging = false;
      marker.on("dragstart", () => {
        dragging = true;
      });
      marker.on("click", (event) => {
        L.DomEvent.stopPropagation(event);
        if (dragging) return;
        edit?.onSelect?.(id);
      });
      marker.on("dragend", () => {
        const latlng = marker.getLatLng();
        edit?.onMove?.(id, { x: latlng.lng, z: latlng.lat });
        window.setTimeout(() => {
          dragging = false;
        }, 0);
      });
    }
    marker.addTo(group);
  }
}

export function addPlaceBoxes(
  group: L.LayerGroup,
  places: ResolvedMapPlace[],
  edit?: TarkovMapPlaceEdit,
) {
  group.clearLayers();
  const selecting = edit?.mode === "select";
  for (const place of places) {
    if (place.kind !== "box" || place.x == null || place.z == null) continue;
    if (place.x2 == null || place.z2 == null) continue;
    const selected = selecting && place.id != null && edit?.selectedId === place.id;
    const rect = L.rectangle(
      L.latLngBounds(pos({ x: place.x, z: place.z }), pos({ x: place.x2, z: place.z2 })),
      {
        color: selected ? "#e8b84a" : "#c8932a",
        weight: selected ? 2 : 1,
        fillColor: "#c8932a",
        fillOpacity: selected ? 0.18 : 0.08,
        interactive: selecting && place.id != null,
        className: styles.placeBox,
      },
    );
    if (selecting && place.id != null) {
      const id = place.id;
      rect.on("click", (event) => {
        L.DomEvent.stopPropagation(event);
        edit?.onSelect?.(id);
      });
    }
    rect.addTo(group);
  }
}
