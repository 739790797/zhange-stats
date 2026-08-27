import { apiError } from "@/lib/apiError";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Spin } from "antd";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { TarkovMapBoss, TarkovMapExtract } from "@/api/guidesApi";
import { getBounds, getCRS, getScaledBounds, pos } from "@/lib/tarkovMapCrs";
import { tarkovMapLabel } from "@/lib/tarkovMapLabelsZh";
import type { TarkovRaidPrepOverlay } from "@/lib/tarkovRaidPrep";
import { colorForUserId } from "@/lib/tarkovRaidPrep";
import {
  RAID_ROOM_OTHER_FLOOR_OPACITY,
  markMatchesFloor,
  type RaidRoomMarkLike,
} from "@/lib/tarkovRaidRooms";
import {
  findInteractiveMap,
  findRasterMap,
  floorLabel,
  svgFallbackUrl,
  type TarkovDevMapLayer,
} from "@/lib/tarkovMapImages";
import styles from "./TarkovMapViewer.module.css";

type Props = {
  slug: string;
  parentSlug?: string;
  extracts?: TarkovMapExtract[];
  bosses?: TarkovMapBoss[];
  questOverlays?: TarkovRaidPrepOverlay[];
  fill?: boolean;
  className?: string;
  boardMarks?: RaidRoomMarkLike[];
  draftLine?: {
    x: number;
    z: number;
    x2: number;
    z2: number;
    floor: string;
    color: string;
  } | null;
  drawMode?: "pan" | "pin" | "line";
  onMapPoint?: (point: { x: number; z: number; floor: string }) => void;
  onFloorChange?: (floor: string) => void;
};

type MapRuntime = {
  map: L.Map;
  svgOverlay?: L.SVGOverlay;
  tileLayer?: L.TileLayer;
  floorTiles: Map<string, L.TileLayer>;
  extracts: L.LayerGroup;
  bosses: L.LayerGroup;
  labels: L.LayerGroup;
  quests: L.LayerGroup;
  board: L.LayerGroup;
  svgRoot?: SVGSVGElement;
};

const FACTION_COLOR: Record<string, string> = {
  PMC: "#6fbf4a",
  Scav: "#e08a2c",
  通用: "#6cb6ff",
};

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function factionColor(faction: string): string {
  return FACTION_COLOR[faction] || "#e8e3cf";
}

function setSvgFloor(
  root: SVGSVGElement | undefined,
  baseId: string,
  floorId: string,
) {
  const inner = root?.children[0];
  if (!inner) return;
  for (const child of Array.from(inner.children)) {
    if (child.nodeName.toLowerCase() !== "g") continue;
    const group = child as SVGGElement;
    if (!group.id) continue;
    const isBase =
      group.id === baseId || group.dataset.keepWithGroup === baseId;
    const visible = floorId ? group.id === floorId : isBase;
    group.classList.toggle("hidden-layer", !visible);
  }
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
      holder.innerHTML = text;
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

function addExtractMarkers(
  group: L.LayerGroup,
  extracts: TarkovMapExtract[],
) {
  group.clearLayers();
  for (const row of extracts) {
    if (row.x == null || row.z == null) continue;
    const color = factionColor(row.faction || "");
    const marker = L.marker(pos({ x: row.x, z: row.z }), {
      icon: L.divIcon({
        className: styles.extractIcon,
        html: `<span class="${styles.extractRow}"><span class="${styles.dot}" style="background:${color}"></span><span class="${styles.extractName}" style="color:${color}">${escapeHtml(row.name)}</span></span>`,
        iconSize: [8, 8],
        iconAnchor: [4, 4],
      }),
      title: `${row.name}（${row.faction || "撤离"}）`,
    });
    marker.bindPopup(
      `<strong>${escapeHtml(row.name)}</strong><div>${escapeHtml(row.faction || "撤离")}</div>`,
    );
    marker.addTo(group);
  }
}

function addBossMarkers(group: L.LayerGroup, bosses: TarkovMapBoss[]) {
  group.clearLayers();
  for (const boss of bosses) {
    for (const loc of boss.locations || []) {
      for (const point of loc.positions || []) {
        const title = loc.name
          ? `${boss.name} · ${tarkovMapLabel(loc.name)}`
          : boss.name;
        const marker = L.marker(pos({ x: point.x, z: point.z }), {
          icon: L.divIcon({
            className: styles.bossIcon,
            html: `<span class="${styles.bossRow}"><span class="${styles.diamond}"></span><span class="${styles.bossName}" style="color:#d44a4a">${escapeHtml(title)}</span></span>`,
            iconSize: [8, 8],
            iconAnchor: [4, 4],
          }),
          title,
        });
        marker.bindPopup(`<strong>${escapeHtml(title)}</strong>`);
        marker.addTo(group);
      }
    }
  }
}

function setSvgBakedTextHidden(
  root: SVGSVGElement | undefined,
  hidden: boolean,
) {
  if (!root) return;
  if (hidden) root.setAttribute("data-hide-baked-text", "1");
  else root.removeAttribute("data-hide-baked-text");
}

function addLabelMarkers(group: L.LayerGroup, layer: TarkovDevMapLayer) {
  group.clearLayers();
  for (const label of layer.labels || []) {
    if (!label.position || label.position.length < 2) continue;
    const size = Math.max(11, Math.round((label.size || 80) / 7));
    const rotation = label.rotation || 0;
    const text = tarkovMapLabel(label.text);
    const marker = L.marker(pos({ x: label.position[0], z: label.position[1] }), {
      icon: L.divIcon({
        className: styles.labelIcon,
        html: `<span class="${styles.labelText}" style="font-size:${size}px;transform:rotate(${rotation}deg)">${escapeHtml(text)}</span>`,
        iconSize: [160, 20],
        iconAnchor: [80, 10],
      }),
      interactive: false,
    });
    marker.addTo(group);
  }
}

function overlayPopupHtml(row: TarkovRaidPrepOverlay): string {
  const kind = row.kind === "spawn" ? "可能刷新点" : "目标区域";
  const sub = row.subtitle
    ? `<div>${escapeHtml(row.subtitle)}</div>`
    : "";
  return `<strong>${escapeHtml(row.title)}</strong>${sub}<div>${kind}</div>`;
}

function addQuestOverlays(
  group: L.LayerGroup,
  overlays: TarkovRaidPrepOverlay[],
) {
  group.clearLayers();
  for (const row of overlays) {
    if (row.outline.length >= 3) {
      const polygon = L.polygon(
        row.outline.map((point) => pos({ x: point.x, z: point.z })),
        {
          color: row.color,
          weight: 2,
          fillColor: row.color,
          fillOpacity: 0.18,
        },
      );
      polygon.bindPopup(overlayPopupHtml(row));
      polygon.addTo(group);
    }
    for (const point of row.points) {
      const marker = L.circleMarker(pos({ x: point.x, z: point.z }), {
        radius: row.kind === "spawn" ? 5 : 7,
        color: "#111",
        weight: 1,
        fillColor: row.color,
        fillOpacity: 0.92,
      });
      marker.bindPopup(overlayPopupHtml(row));
      marker.addTo(group);
    }
  }
}

function addBoardMarks(
  group: L.LayerGroup,
  marks: RaidRoomMarkLike[],
  currentFloor: string,
  draftLine?: Props["draftLine"],
) {
  group.clearLayers();
  const draw = (
    mark: {
      kind: string;
      floor?: string | null;
      x: number;
      z: number;
      x2?: number | null;
      z2?: number | null;
      color: string;
      title?: string;
    },
  ) => {
    const current = markMatchesFloor(mark, currentFloor);
    const opacity = current ? 1 : RAID_ROOM_OTHER_FLOOR_OPACITY;
    if (mark.kind === "line" && mark.x2 != null && mark.z2 != null) {
      L.polyline([pos({ x: mark.x, z: mark.z }), pos({ x: mark.x2, z: mark.z2 })], {
        color: mark.color,
        weight: current ? 3 : 2,
        opacity,
        interactive: false,
      }).addTo(group);
      return;
    }
    L.circleMarker(pos({ x: mark.x, z: mark.z }), {
      radius: current ? 7 : 5,
      color: "#111",
      weight: 1,
      fillColor: mark.color,
      fillOpacity: opacity,
      opacity,
      interactive: false,
    })
      .bindTooltip(mark.title || "", { direction: "top" })
      .addTo(group);
  };
  for (const mark of marks) {
    draw({
      ...mark,
      color: colorForUserId(mark.author_user_id),
      title: mark.author_display_name || "",
    });
  }
  if (draftLine) {
    draw({
      kind: "line",
      floor: draftLine.floor,
      x: draftLine.x,
      z: draftLine.z,
      x2: draftLine.x2,
      z2: draftLine.z2,
      color: draftLine.color,
    });
  }
}

export function TarkovMapViewer({
  slug,
  parentSlug,
  extracts = [],
  bosses = [],
  questOverlays = [],
  fill = false,
  className = "",
  boardMarks = [],
  draftLine = null,
  drawMode = "pan",
  onMapPoint,
  onFloorChange,
}: Props) {
  const interactive = useMemo(
    () => findInteractiveMap(slug, parentSlug),
    [slug, parentSlug],
  );
  const raster = useMemo(
    () => findRasterMap(slug, parentSlug),
    [slug, parentSlug],
  );
  const wrapRef = useRef<HTMLDivElement>(null);
  const mapDivRef = useRef<HTMLDivElement>(null);
  const runtimeRef = useRef<MapRuntime | null>(null);
  const drawModeRef = useRef(drawMode);
  const onMapPointRef = useRef(onMapPoint);
  const floorRef = useRef("");
  const [style, setStyle] = useState<"svg" | "tile">("svg");
  const [floor, setFloor] = useState("");
  const [showExtracts, setShowExtracts] = useState(true);
  const [showBosses, setShowBosses] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [showQuests, setShowQuests] = useState(true);
  const [coords, setCoords] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(0);
  drawModeRef.current = drawMode;
  onMapPointRef.current = onMapPoint;
  floorRef.current = floor;

  useEffect(() => {
    onFloorChange?.(floor);
  }, [floor, onFloorChange]);

  const canSvg = Boolean(interactive?.svgPath);
  const canTile = Boolean(interactive?.tilePath);
  const floors = useMemo(
    () =>
      interactive?.layers?.filter((layer) => layer.svgLayer || layer.tilePath) ??
      [],
    [interactive],
  );

  useEffect(() => {
    setStyle(canSvg ? "svg" : "tile");
    setFloor("");
  }, [interactive?.key, canSvg]);

  useEffect(() => {
    const el = mapDivRef.current;
    if (!el) return;
    let cancelled = false;
    const runtime: MapRuntime = {
      map: null as unknown as L.Map,
      floorTiles: new Map(),
      extracts: L.layerGroup(),
      bosses: L.layerGroup(),
      labels: L.layerGroup(),
      quests: L.layerGroup(),
      board: L.layerGroup(),
    };
    runtimeRef.current = runtime;

    const setupInteractive = async (layer: TarkovDevMapLayer) => {
      const bounds = getBounds(layer.bounds);
      if (!bounds) throw new Error("地图缺少 bounds");
      const maxZoom = Math.max(7, layer.maxZoom ?? 5);
      const map = L.map(el, {
        crs: getCRS(layer),
        zoomSnap: 0.1,
        attributionControl: false,
        minZoom: layer.minZoom ?? 1,
        maxZoom,
      });
      runtime.map = map;
      const scaled = getScaledBounds(layer.bounds || [], 1.5);
      if (scaled) map.setMaxBounds(scaled);
      map.on("mousemove", (event: L.LeafletMouseEvent) => {
        setCoords(
          `x ${event.latlng.lng.toFixed(1)}  z ${event.latlng.lat.toFixed(1)}`,
        );
      });
      const onDrawClick = (event: MouseEvent) => {
        const mode = drawModeRef.current;
        if (mode !== "pin" && mode !== "line") return;
        const target = event.target as HTMLElement | null;
        if (target?.closest(".leaflet-control")) return;
        const latlng = map.mouseEventToLatLng(event);
        onMapPointRef.current?.({
          x: latlng.lng,
          z: latlng.lat,
          floor: floorRef.current,
        });
        event.preventDefault();
        event.stopPropagation();
      };
      map.getContainer().addEventListener("click", onDrawClick, true);

      const tileSize = layer.tileSize || 256;
      if (layer.tilePath) {
        runtime.tileLayer = L.tileLayer(layer.tilePath, {
          tileSize,
          bounds,
          maxZoom,
          maxNativeZoom: layer.maxZoom ?? 5,
        });
      }
      for (const floorLayer of layer.layers || []) {
        if (!floorLayer.tilePath) continue;
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
      if (layer.svgPath) {
        try {
          const svg = await loadSvgElement(layer.svgPath);
          if (cancelled) return;
          runtime.svgRoot = svg;
          setSvgFloor(svg, layer.svgLayer || "", "");
          const svgBounds = getBounds(layer.svgBounds) || bounds;
          runtime.svgOverlay = L.svgOverlay(svg, svgBounds);
        } catch {
          /* 抽象图失败时仍可用瓦片 */
        }
      }
      if (!runtime.tileLayer && !runtime.svgOverlay) {
        throw new Error("没有可用底图");
      }
      runtime.extracts.addTo(map);
      runtime.bosses.addTo(map);
      runtime.labels.addTo(map);
      runtime.quests.addTo(map);
      runtime.board.addTo(map);
      map.fitBounds(bounds, { animate: false });
    };

    const setupRaster = async (url: string) => {
      const img = await new Promise<HTMLImageElement>((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = () => reject(new Error("平面图加载失败"));
        image.src = url;
      });
      if (cancelled) return;
      const map = L.map(el, {
        crs: L.CRS.Simple,
        attributionControl: false,
        minZoom: -2,
        maxZoom: 3,
      });
      runtime.map = map;
      const bounds = L.latLngBounds([0, 0], [img.height, img.width]);
      L.imageOverlay(url, bounds).addTo(map);
      map.fitBounds(bounds, { animate: false });
    };

    setLoading(true);
    setError("");
    const boot = interactive
      ? setupInteractive(interactive)
      : raster
        ? setupRaster(raster.url)
        : Promise.reject(new Error("没有可用底图"));
    boot
      .then(() => {
        if (cancelled) return;
        setLoading(false);
        setReady((value) => value + 1);
      })
      .catch((exc: unknown) => {
        if (cancelled) return;
        setLoading(false);
        setError(apiError(exc, "地图加载失败"));
      });

    return () => {
      cancelled = true;
      runtimeRef.current = null;
      runtime.map?.remove();
    };
  }, [interactive, raster]);

  useEffect(() => {
    const runtime = runtimeRef.current;
    const map = runtime?.map;
    if (!runtime || !map || !interactive) return;
    const wantSvg = style === "svg" && runtime.svgOverlay;
    if (wantSvg) {
      runtime.tileLayer?.remove();
      for (const tile of runtime.floorTiles.values()) tile.remove();
      runtime.svgOverlay?.addTo(map);
      const floorLayer = floors.find((item) => item.name === floor);
      setSvgFloor(
        runtime.svgRoot,
        interactive.svgLayer || "",
        floorLayer?.svgLayer || "",
      );
      return;
    }
    runtime.svgOverlay?.remove();
    runtime.tileLayer?.addTo(map);
    for (const [name, tile] of runtime.floorTiles) {
      if (name === floor) tile.addTo(map);
      else tile.remove();
    }
  }, [style, floor, interactive, floors, ready]);

  useEffect(() => {
    const runtime = runtimeRef.current;
    if (!runtime?.map || !interactive) return;
    if (showExtracts) addExtractMarkers(runtime.extracts, extracts);
    else runtime.extracts.clearLayers();
    if (showBosses) addBossMarkers(runtime.bosses, bosses);
    else runtime.bosses.clearLayers();
    if (showLabels) addLabelMarkers(runtime.labels, interactive);
    else runtime.labels.clearLayers();
    setSvgBakedTextHidden(
      runtime.svgRoot,
      showLabels && Boolean(interactive.labels?.length),
    );
    if (showQuests) addQuestOverlays(runtime.quests, questOverlays);
    else runtime.quests.clearLayers();
    addBoardMarks(runtime.board, boardMarks, floor, draftLine);
  }, [
    extracts,
    bosses,
    questOverlays,
    boardMarks,
    draftLine,
    floor,
    showExtracts,
    showBosses,
    showLabels,
    showQuests,
    interactive,
    ready,
  ]);

  useEffect(() => {
    if (!ready) return undefined;
    const handle = window.setTimeout(() => {
      runtimeRef.current?.map.invalidateSize();
    }, 60);
    return () => window.clearTimeout(handle);
  }, [ready, fill, questOverlays.length]);

  useEffect(() => {
    const map = runtimeRef.current?.map;
    if (!map) return;
    const drawing = drawMode === "pin" || drawMode === "line";
    if (drawing) {
      map.dragging.disable();
      map.doubleClickZoom.disable();
    } else {
      map.dragging.enable();
      map.doubleClickZoom.enable();
    }
  }, [drawMode, ready]);

  const toggleFullscreen = useCallback(() => {
    const node = wrapRef.current;
    if (!node) return;
    if (document.fullscreenElement === node) {
      void document.exitFullscreen();
      return;
    }
    void node.requestFullscreen();
  }, []);

  useEffect(() => {
    const node = wrapRef.current;
    if (!node) return undefined;
    const onChange = () => {
      runtimeRef.current?.map.invalidateSize();
    };
    node.addEventListener("fullscreenchange", onChange);
    return () => node.removeEventListener("fullscreenchange", onChange);
  }, [ready]);

  if (!interactive && !raster) {
    return (
      <div className={styles.status}>这张图还没有可嵌入的底图。</div>
    );
  }

  return (
    <div
      className={`${styles.wrap} ${fill ? styles.wrapFill : ""} ${drawMode !== "pan" ? styles.wrapDraw : ""} ${className}`.trim()}
      ref={wrapRef}
    >
      <div className={styles.map} ref={mapDivRef} />
      {loading ? (
        <div className={`${styles.status} ${styles.overlay}`}>
          <Spin />
        </div>
      ) : null}
      {error ? (
        <div className={`${styles.status} ${styles.overlay}`}>{error}</div>
      ) : null}
      <div className={styles.toolbar}>
        {canSvg ? (
          <button
            type="button"
            className={`${styles.chip} ${style === "svg" ? styles.chipOn : ""}`}
            onClick={() => setStyle("svg")}
          >
            抽象
          </button>
        ) : null}
        {canTile ? (
          <button
            type="button"
            className={`${styles.chip} ${style === "tile" ? styles.chipOn : ""}`}
            onClick={() => setStyle("tile")}
          >
            卫星
          </button>
        ) : null}
        {floors.length ? (
          <button
            type="button"
            className={`${styles.chip} ${!floor ? styles.chipOn : ""}`}
            onClick={() => setFloor("")}
          >
            地面
          </button>
        ) : null}
        {floors.map((item) => (
          <button
            key={item.name}
            type="button"
            className={`${styles.chip} ${floor === item.name ? styles.chipOn : ""}`}
            onClick={() => setFloor(item.name)}
          >
            {floorLabel(item.name)}
          </button>
        ))}
        {interactive ? (
          <>
            <button
              type="button"
              className={`${styles.chip} ${showExtracts ? styles.chipOn : ""}`}
              onClick={() => setShowExtracts((value) => !value)}
            >
              撤离点
            </button>
            <button
              type="button"
              className={`${styles.chip} ${showBosses ? styles.chipOn : ""}`}
              onClick={() => setShowBosses((value) => !value)}
            >
              BOSS
            </button>
            {interactive.labels?.length ? (
              <button
                type="button"
                className={`${styles.chip} ${showLabels ? styles.chipOn : ""}`}
                onClick={() => setShowLabels((value) => !value)}
              >
                地名
              </button>
            ) : null}
            {questOverlays.length ? (
              <button
                type="button"
                className={`${styles.chip} ${showQuests ? styles.chipOn : ""}`}
                onClick={() => setShowQuests((value) => !value)}
              >
                任务
              </button>
            ) : null}
          </>
        ) : null}
        <button type="button" className={styles.chip} onClick={toggleFullscreen}>
          全屏
        </button>
        <a
          className={`${styles.link} ${styles.credit}`}
          href="https://github.com/the-hideout/tarkov-dev-svg-maps"
          target="_blank"
          rel="noreferrer"
        >
          底图 CC BY-NC-SA · tarkov.dev
        </a>
      </div>
      {coords ? <div className={styles.coords}>{coords}</div> : null}
      {!interactive && raster ? (
        <div className={styles.note}>平面图，坐标标记仅互动图层可用。</div>
      ) : null}
    </div>
  );
}
