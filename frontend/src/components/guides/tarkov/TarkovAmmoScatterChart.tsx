import { Scatter } from "@ant-design/plots";
import { useCallback, useMemo, useRef } from "react";
import type { TarkovAmmoItem } from "@/api/guidesApi";
import {
  ARMOR_EFFECT_COLORS,
  ARMOR_EFFECT_LABELS,
  armorEffectsForAmmo,
  type ArmorEffectLevel,
} from "@/lib/tarkovAmmoArmorEffect";
import { distinctCaliberColor } from "@/lib/tarkovAmmoScatter";

const DEFAULT_HEIGHT = 520;

export type AmmoScatterColorField = "caliber" | "name" | "short_name";

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function itemValue(
  items: Array<{ name?: string; value?: unknown }>,
  name: string,
): number {
  const raw = items.find((it) => it.name === name)?.value;
  const n = Number(raw);
  return Number.isFinite(n) ? n : 0;
}

function renderAmmoTooltip(
  title: string,
  items: Array<{ name?: string; value?: unknown }>,
): string {
  const penetration = itemValue(items, "穿透");
  const damage = itemValue(items, "伤害");
  const armorDamage = itemValue(items, "对甲");
  const effects = armorEffectsForAmmo(penetration, armorDamage);

  const cells = effects
    .map((level: ArmorEffectLevel, idx) => {
      const { bg, fg } = ARMOR_EFFECT_COLORS[level];
      const label = ARMOR_EFFECT_LABELS[level];
      return `<div style="width:36px;flex:0 0 36px;box-sizing:border-box;background:${bg};color:${fg};border-radius:3px;padding:4px 0;text-align:center;line-height:1.15">
        <div style="font-size:10px;opacity:0.9">${idx + 1}级</div>
        <div style="font-size:11px;font-weight:600;margin-top:2px">${label}</div>
      </div>`;
    })
    .join("");

  const safeTitle = escapeHtml(title || "—");
  return `<div style="width:320px;box-sizing:border-box;padding:0">
    <div style="font-size:13px;font-weight:600;color:#f2f2f2;margin-bottom:8px;line-height:1.35;word-break:break-word">${safeTitle}</div>
    <div style="display:flex;gap:10px;align-items:flex-start">
      <div style="flex:0 0 72px;font-size:12px;color:#c8c8c8;line-height:1.7">
        <div>穿透　${penetration}</div>
        <div>伤害　${damage}</div>
        <div>对甲　${armorDamage}</div>
      </div>
      <div style="flex:0 0 auto">
        <div style="font-size:11px;color:#8a8a8a;margin-bottom:4px">对护甲效果（估）</div>
        <div style="display:flex;gap:2px;width:226px">${cells}</div>
      </div>
    </div>
  </div>`;
}

type ScatterPlotInstance = {
  container?: HTMLElement;
  options?: { data?: TarkovAmmoItem[] };
  chart?: {
    on: (event: string, handler: (ev: unknown) => void) => void;
    getContext?: () => {
      canvas?: { document?: { documentElement?: unknown } };
    };
  };
  on: (event: string, handler: (ev: unknown) => void) => void;
};

function ammoFromPlotEvent(event: {
  data?: { data?: unknown } | unknown;
}): TarkovAmmoItem | null {
  const raw = (event?.data as { data?: unknown } | undefined)?.data ?? event?.data;
  const candidates = Array.isArray(raw) ? raw : [raw];
  for (const item of candidates) {
    if (!item || typeof item !== "object") continue;
    const row = item as TarkovAmmoItem & { origin?: TarkovAmmoItem };
    const candidate = row.id ? row : row.origin;
    if (candidate && typeof candidate.id === "string" && candidate.id) {
      return candidate;
    }
  }
  return null;
}

/** 色点很小，tooltip 靠邻近拾取能出，点击却经常 miss；按坐标找最近 element。 */
function ammoNearestFromClick(
  plot: ScatterPlotInstance,
  event: {
    data?: unknown;
    clientX?: number;
    clientY?: number;
    nativeEvent?: { clientX?: number; clientY?: number };
  },
): TarkovAmmoItem | null {
  const direct = ammoFromPlotEvent(event);
  if (direct) return direct;

  const clientX = event.clientX ?? event.nativeEvent?.clientX;
  const clientY = event.clientY ?? event.nativeEvent?.clientY;
  if (!Number.isFinite(clientX) || !Number.isFinite(clientY)) return null;

  const canvas = plot.container?.querySelector?.("canvas");
  if (!canvas) return null;
  const rect = canvas.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return null;
  // G2 getBounds 是画布缓冲像素；client 坐标是 CSS 像素，需按 DPR 换算
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const x = (Number(clientX) - rect.left) * scaleX;
  const y = (Number(clientY) - rect.top) * scaleY;
  const data = plot.options?.data;
  if (!Array.isArray(data) || !data.length) return null;

  type G2Node = {
    className?: string;
    childNodes?: G2Node[];
    __data__?: { index?: number };
    getBounds?: () => { min: [number, number]; max: [number, number] };
  };

  let bestDist = Number.POSITIVE_INFINITY;
  let bestAmmo: TarkovAmmoItem | null = null;
  const hitPx = 20 * Math.max(scaleX, scaleY);

  const walk = (node: G2Node | null | undefined) => {
    if (!node) return;
    if (node.className === "element" && node.getBounds) {
      const b = node.getBounds();
      const cx = (b.min[0] + b.max[0]) / 2;
      const cy = (b.min[1] + b.max[1]) / 2;
      const dist = Math.hypot(cx - x, cy - y);
      if (dist <= hitPx && dist < bestDist) {
        const idx = node.__data__?.index;
        const row = typeof idx === "number" ? data[idx] : undefined;
        if (row?.id) {
          bestDist = dist;
          bestAmmo = row;
        }
      }
    }
    for (const child of node.childNodes || []) walk(child);
  };

  try {
    const root = plot.chart?.getContext?.()?.canvas?.document
      ?.documentElement as G2Node | undefined;
    walk(root);
  } catch {
    return null;
  }

  return bestAmmo;
}

function colorKeyOf(
  row: TarkovAmmoItem,
  field: AmmoScatterColorField,
): string {
  if (field === "caliber") return row.caliber;
  if (field === "short_name") return row.short_name || row.name || row.id;
  return row.name || row.short_name || row.id;
}

type Props = {
  data: TarkovAmmoItem[];
  colorField?: AmmoScatterColorField;
  /** 色域顺序；缺省则从当前 data 推。口径页传入全量口径以免筛选时变色。 */
  colorDomain?: string[];
  axisMax: { x: number; y: number };
  height?: number;
  onAmmoClick?: (ammo: TarkovAmmoItem) => void;
  /** 列表悬停时放大对应色点；图上悬停请走 onHoverAmmo，避免重绘打断 tooltip */
  highlightedId?: string | null;
  onHoverAmmo?: (ammo: TarkovAmmoItem | null) => void;
};

const POINT_SIZE = 5;
const POINT_SIZE_HOVER = 12;

export function TarkovAmmoScatterChart({
  data,
  colorField = "caliber",
  colorDomain,
  axisMax,
  height = DEFAULT_HEIGHT,
  onAmmoClick,
  highlightedId,
  onHoverAmmo,
}: Props) {
  const clickRef = useRef(onAmmoClick);
  clickRef.current = onAmmoClick;
  const hoverRef = useRef(onHoverAmmo);
  hoverRef.current = onHoverAmmo;
  const lastNavRef = useRef<{ id: string; at: number }>({ id: "", at: 0 });
  const lastHoverIdRef = useRef<string | null>(null);

  const plotData = useMemo(() => {
    const activeId = (highlightedId || "").trim();
    if (!activeId) return data;
    const sized = data.map((row) => ({
      ...row,
      point_size: row.id === activeId ? POINT_SIZE_HOVER : POINT_SIZE,
    }));
    const hi = sized.filter((row) => row.id === activeId);
    const rest = sized.filter((row) => row.id !== activeId);
    return [...rest, ...hi];
  }, [data, highlightedId]);

  const domain = useMemo(() => {
    if (colorDomain?.length) return colorDomain;
    return Array.from(
      new Set(plotData.map((row) => colorKeyOf(row, colorField))),
    ).sort((a, b) => a.localeCompare(b, "zh", { numeric: true }));
  }, [colorDomain, colorField, plotData]);

  const colors = useMemo(
    () => domain.map((_, i) => distinctCaliberColor(i)),
    [domain],
  );

  const onReady = useCallback((plot: ScatterPlotInstance) => {
    const handle = (ev: unknown) => {
      const ammo = ammoNearestFromClick(
        plot,
        ev as {
          data?: unknown;
          clientX?: number;
          clientY?: number;
          nativeEvent?: { clientX?: number; clientY?: number };
        },
      );
      if (!ammo) return;
      const now = Date.now();
      if (
        lastNavRef.current.id === ammo.id &&
        now - lastNavRef.current.at < 400
      ) {
        return;
      }
      lastNavRef.current = { id: ammo.id, at: now };
      clickRef.current?.(ammo);
    };
    plot.chart?.on("element:click", handle);
    plot.chart?.on("point:click", handle);
    plot.on("click", handle);

    const hover = (ev: unknown) => {
      if (!hoverRef.current) return;
      const ammo = ammoNearestFromClick(
        plot,
        ev as {
          data?: unknown;
          clientX?: number;
          clientY?: number;
          nativeEvent?: { clientX?: number; clientY?: number };
        },
      );
      const nextId = ammo?.id ?? null;
      if (lastHoverIdRef.current === nextId) return;
      lastHoverIdRef.current = nextId;
      hoverRef.current(ammo);
    };
    const clearHover = () => {
      if (!hoverRef.current || lastHoverIdRef.current == null) return;
      lastHoverIdRef.current = null;
      hoverRef.current(null);
    };
    plot.container?.addEventListener("mousemove", hover as EventListener);
    plot.container?.addEventListener("mouseleave", clearHover);
    try {
      plot.on("pointermove", hover);
      plot.on("pointerleave", clearHover);
    } catch {
      /* DOM 监听已覆盖 */
    }
  }, []);

  const clickable = Boolean(onAmmoClick);
  const enlarge = Boolean((highlightedId || "").trim());

  const config = useMemo(
    () => ({
      data: plotData,
      xField: "penetration",
      yField: "damage",
      colorField,
      sizeField: enlarge ? "point_size" : POINT_SIZE,
      shapeField: "point",
      autoFit: true,
      height,
      theme: "classicDark",
      viewStyle: {
        viewFill: "#141414",
        plotFill: "#141414",
      },
      axis: {
        x: {
          title: "穿透 (Penetration)",
          titleFill: "#8a8a8a",
          labelFill: "#8a8a8a",
          lineStroke: "#2a2a2a",
          tickStroke: "#2a2a2a",
          gridStroke: "#1f1f1f",
          gridStrokeOpacity: 1,
        },
        y: {
          title: "伤害 (Damage)",
          titleFill: "#8a8a8a",
          labelFill: "#8a8a8a",
          lineStroke: "#2a2a2a",
          tickStroke: "#2a2a2a",
          gridStroke: "#1f1f1f",
          gridStrokeOpacity: 1,
        },
      },
      legend: false,
      tooltip: {
        title: (d: TarkovAmmoItem) => d.name || d.short_name || d.id,
        items: [
          { field: "penetration", name: "穿透" },
          { field: "damage", name: "伤害" },
          { field: "armor_damage", name: "对甲" },
        ],
      },
      interaction: {
        tooltip: {
          position: "top",
          mount: "body",
          css: {
            ".g2-tooltip": {
              width: "auto",
              "max-width": "none",
              "min-width": "0",
              padding: "10px 12px",
              "box-sizing": "border-box",
              overflow: "visible",
              background: "#161616",
              color: "#f2f2f2",
              border: "1px solid #2a2a2a",
              "box-shadow": "none",
              "pointer-events": "none",
            },
            ".g2-tooltip-title": {
              display: "none",
            },
            ".g2-tooltip-list": {
              display: "none",
            },
          },
          render: (
            _event: unknown,
            {
              title,
              items,
            }: {
              title?: string;
              items?: Array<{ name?: string; value?: unknown }>;
            },
          ) => renderAmmoTooltip(title || "", items || []),
        },
      },
      style: {
        fillOpacity: 1,
        lineWidth: 1,
        stroke: "rgba(13,13,13,0.55)",
        cursor: clickable ? "pointer" : "default",
      },
      scale: {
        x: {
          domainMin: 0,
          domainMax: axisMax.x,
          nice: false,
          tickMethod: () =>
            Array.from({ length: axisMax.x / 10 + 1 }, (_, i) => i * 10),
        },
        y: {
          domainMin: 0,
          domainMax: axisMax.y,
          nice: false,
          tickMethod: () =>
            Array.from({ length: axisMax.y / 10 + 1 }, (_, i) => i * 10),
        },
        color: {
          domain,
          range: colors,
        },
        ...(enlarge
          ? {
              size: {
                domainMin: POINT_SIZE,
                domainMax: POINT_SIZE_HOVER,
                range: [POINT_SIZE, POINT_SIZE_HOVER],
              },
            }
          : {}),
      },
    }),
    [
      axisMax.x,
      axisMax.y,
      clickable,
      colorField,
      colors,
      domain,
      enlarge,
      height,
      plotData,
    ],
  );

  return <Scatter {...config} onReady={onReady} />;
}
