/** 地图运行时句柄与 Leaflet 图层 pane：拆出的图层模块与组件共用。 */

import type L from "leaflet";
import type { TarkovMapCanvasMarkerLayer } from "@/lib/tarkovMapCanvasMarkerLayer";

export type MapRuntime = {
  map: L.Map;
  fitBox?: L.LatLngBounds;
  svgOverlay?: L.SVGOverlay;
  tileLayer?: L.TileLayer;
  floorTiles: Map<string, L.TileLayer>;
  extracts: L.LayerGroup;
  outlines: L.LayerGroup;
  outlineById: Map<string, L.Polygon>;
  hoveredOutlineId: string | null;
  iconCanvas?: TarkovMapCanvasMarkerLayer;
  btrStops: L.LayerGroup;
  labels: L.LayerGroup;
  placeBoxes: L.LayerGroup;
  quests: L.LayerGroup;
  questLabels: L.LayerGroup;
  board: L.LayerGroup;
  live: L.LayerGroup;
  mine: L.LayerGroup;
  remote: L.LayerGroup;
  player: L.LayerGroup;
  pulse: L.LayerGroup;
  localStroke?: L.Polyline;
  mineKeys: Set<string>;
  strokeLayers: Map<string, L.Layer>;
  draftLayers: Map<number, L.Layer>;
  playerLayers: Map<string, L.Marker>;
  /** 每个玩家标记上次用过的图标 HTML：没变就不必 setIcon 重建 DOM。 */
  playerIconHtml: Map<string, string>;
  pulseLayers: Map<string, L.Polyline>;
  boardPane?: HTMLElement;
  svgRoot?: SVGSVGElement;
};

export const BOARD_PANE = "boardPane";
export const PLAYER_PULSE_PANE = "playerPulsePane";
export const SVG_BASE_PANE = "svgBasePane";
