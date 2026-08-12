import { Scatter } from "@ant-design/plots";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Space, Spin, Tag, Tooltip, Typography } from "antd";
import { CheckSquareOutlined, ClearOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchTarkovAmmo, type TarkovAmmoItem } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import {
  AMMO_TYPE_ORDER,
  formatAmmoTypeLabel,
  formatCaliberLabel,
} from "@/lib/tarkovAmmoCategories";
import {
  loadTarkovAmmoFilters,
  resolveCaliberSelection,
  saveTarkovAmmoFilters,
} from "@/lib/tarkovAmmoFilterStorage";
import { TarkovAmmoWikiTable } from "@/components/guides/tarkov/TarkovAmmoWikiTable";
import {
  ARMOR_EFFECT_COLORS,
  ARMOR_EFFECT_LABELS,
  armorEffectsForAmmo,
  type ArmorEffectLevel,
} from "@/lib/tarkovAmmoArmorEffect";

const EMPTY_ITEMS: TarkovAmmoItem[] = [];
const CHART_HEIGHT = 520;

/** 黄金角分散色相，避免相邻口径落到近似色 */
function distinctCaliberColor(index: number): string {
  const hue = Math.round((index * 137.508) % 360);
  const sat = index % 2 === 0 ? 78 : 68;
  const light = index % 3 === 0 ? 34 : index % 3 === 1 ? 40 : 36;
  return `hsl(${hue} ${sat}% ${light}%)`;
}

function compareCaliberLabel(a: string, b: string): number {
  return formatCaliberLabel(a).localeCompare(formatCaliberLabel(b), "zh", {
    numeric: true,
    sensitivity: "base",
  });
}

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
    <div style="font-size:13px;font-weight:600;color:rgba(0,0,0,0.88);margin-bottom:8px;line-height:1.35;word-break:break-word">${safeTitle}</div>
    <div style="display:flex;gap:10px;align-items:flex-start">
      <div style="flex:0 0 72px;font-size:12px;color:rgba(0,0,0,0.75);line-height:1.7">
        <div>穿透　${penetration}</div>
        <div>伤害　${damage}</div>
        <div>对甲　${armorDamage}</div>
      </div>
      <div style="flex:0 0 auto">
        <div style="font-size:11px;color:rgba(0,0,0,0.55);margin-bottom:4px">对护甲效果（估）</div>
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
        const row =
          typeof idx === "number" ? data[idx] : undefined;
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

export function TarkovAmmoScatterPanel() {
  const navigate = useNavigate();
  const ammoQuery = useQuery({
    queryKey: ["guides-tarkov-ammo"],
    queryFn: fetchTarkovAmmo,
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const goGunsForAmmo = useCallback(
    (ammo: TarkovAmmoItem) => {
      const id = (ammo.id || "").trim();
      if (!id) return;
      navigate(
        `/guides/tarkov/items/guns?ammo=${encodeURIComponent(id)}`,
      );
    },
    [navigate],
  );

  const goGunsRef = useRef(goGunsForAmmo);
  goGunsRef.current = goGunsForAmmo;
  const lastNavRef = useRef<{ id: string; at: number }>({ id: "", at: 0 });

  const onScatterReady = useCallback((plot: ScatterPlotInstance) => {
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
      goGunsRef.current(ammo);
    };
    // 底层 G2：精确命中
    plot.chart?.on("element:click", handle);
    plot.chart?.on("point:click", handle);
    // Plot 包装层只派发原生 click；未命中色点时用邻近拾取兜底
    plot.on("click", handle);
  }, []);

  const items = ammoQuery.data?.items ?? EMPTY_ITEMS;
  const allCalibers = useMemo(
    () =>
      Array.from(new Set(items.map((row) => row.caliber))).sort(
        compareCaliberLabel,
      ),
    [items],
  );

  const [savedSelection, setSavedSelection] = useState<string[] | null>(
    () => loadTarkovAmmoFilters().selectedCalibers,
  );
  const [selectedCalibers, setSelectedCalibers] = useState<string[]>([]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!allCalibers.length) return;
    const next = resolveCaliberSelection(allCalibers, savedSelection);
    setSelectedCalibers(next);
    setReady(true);
  }, [allCalibers, savedSelection]);

  const selectedSet = useMemo(
    () => new Set(selectedCalibers),
    [selectedCalibers],
  );

  const persistSelection = (next: string[]) => {
    setSelectedCalibers(next);
    setSavedSelection(next);
    saveTarkovAmmoFilters({ selectedCalibers: next });
  };

  const typeRows = useMemo(() => {
    const byType = new Map<string, Set<string>>();
    for (const row of items) {
      const t = (row.ammo_type || "").trim() || "";
      if (!byType.has(t)) byType.set(t, new Set());
      byType.get(t)!.add(row.caliber);
    }
    const known = AMMO_TYPE_ORDER.filter((t) => byType.has(t));
    const knownSet = new Set<string>(known);
    const extra = Array.from(byType.keys())
      .filter((t) => !knownSet.has(t))
      .sort((a, b) =>
        formatAmmoTypeLabel(a).localeCompare(formatAmmoTypeLabel(b), "zh"),
      );
    return [...known, ...extra].map((id) => ({
      id: id || "unknown",
      label: formatAmmoTypeLabel(id),
      calibers: Array.from(byType.get(id) || []).sort(compareCaliberLabel),
    }));
  }, [items]);

  const toggleCaliber = (caliber: string) => {
    const next = new Set(selectedSet);
    if (next.has(caliber)) next.delete(caliber);
    else next.add(caliber);
    persistSelection(allCalibers.filter((c) => next.has(c)));
  };

  const toggleCategory = (calibers: string[], selectAll: boolean) => {
    const next = new Set(selectedSet);
    for (const c of calibers) {
      if (selectAll) next.add(c);
      else next.delete(c);
    }
    persistSelection(allCalibers.filter((c) => next.has(c)));
  };

  const caliberColors = useMemo(() => {
    const map = new Map<string, string>();
    allCalibers.forEach((c, i) => {
      map.set(c, distinctCaliberColor(i));
    });
    return map;
  }, [allCalibers]);

  const data = useMemo(() => {
    return items.filter((row) => selectedSet.has(row.caliber));
  }, [items, selectedSet]);

  const axisMax = useMemo(() => {
    const ceil10 = (n: number) => Math.max(10, Math.ceil(n / 10) * 10);
    let maxPen = 0;
    let maxDmg = 0;
    for (const row of items) {
      if (row.penetration > maxPen) maxPen = row.penetration;
      if (row.damage > maxDmg) maxDmg = row.damage;
    }
    return { x: ceil10(maxPen), y: ceil10(maxDmg) };
  }, [items]);

  const config = useMemo(
    () => ({
      data,
      xField: "penetration",
      yField: "damage",
      colorField: "caliber",
      sizeField: 5,
      shapeField: "point",
      autoFit: true,
      height: CHART_HEIGHT,
      axis: {
        x: { title: "穿透 (Penetration)" },
        y: { title: "伤害 (Damage)" },
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
              // 避免 tooltip 盖住色点导致点不到 element:click
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
        stroke: "rgba(255,255,255,0.65)",
        cursor: "pointer",
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
          domain: allCalibers,
          range: allCalibers.map(
            (c) => caliberColors.get(c) || distinctCaliberColor(0),
          ),
        },
      },
    }),
    [allCalibers, axisMax.x, axisMax.y, caliberColors, data],
  );

  if (ammoQuery.isLoading || !ready) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        <Spin tip="加载弹药数据…" />
      </div>
    );
  }

  if (ammoQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="弹药数据加载失败"
        description={apiError(ammoQuery.error, "弹药数据加载失败")}
      />
    );
  }

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <div>
        <div
          style={{
            border: "1px solid #f0f0f0",
            borderRadius: 8,
            overflow: "hidden",
          }}
        >
          {typeRows.length ? (
            typeRows.map((row, idx) => {
              const selectedInRow = row.calibers.filter((c) =>
                selectedSet.has(c),
              ).length;
              const allOn = selectedInRow === row.calibers.length;
              return (
                <div
                  key={row.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: "10px 12px",
                    borderTop: idx === 0 ? undefined : "1px solid #f0f0f0",
                    background: "#fff",
                  }}
                >
                  <div
                    style={{
                      flex: "0 0 72px",
                      fontSize: 13,
                      fontWeight: 600,
                      lineHeight: 1.3,
                      textAlign: "left",
                    }}
                  >
                    {row.label}
                  </div>
                  <div
                    style={{
                      flex: 1,
                      minWidth: 0,
                      display: "flex",
                      flexWrap: "wrap",
                      gap: "6px 8px",
                      alignItems: "center",
                    }}
                  >
                    {row.calibers.map((caliber) => {
                      const checked = selectedSet.has(caliber);
                      const color =
                        caliberColors.get(caliber) || distinctCaliberColor(0);
                      const label = formatCaliberLabel(caliber);
                      return (
                        <Tag.CheckableTag
                          key={caliber}
                          checked={checked}
                          onChange={() => toggleCaliber(caliber)}
                          style={{
                            marginInlineEnd: 0,
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "flex-start",
                            width: 148,
                            maxWidth: "100%",
                            minHeight: 28,
                            paddingInline: 8,
                            boxSizing: "border-box",
                            textAlign: "left",
                            ...(checked
                              ? {
                                  color: "rgba(0, 0, 0, 0.88)",
                                  background: "#f5f5f5",
                                  border: "1px solid #d9d9d9",
                                }
                              : {
                                  color: "rgba(0, 0, 0, 0.45)",
                                  background: "transparent",
                                  border: "1px solid transparent",
                                }),
                          }}
                        >
                          <span
                            style={{
                              display: "inline-block",
                              width: 8,
                              height: 8,
                              borderRadius: "50%",
                              background: color,
                              marginRight: 6,
                              opacity: checked ? 1 : 0.35,
                              flex: "none",
                            }}
                          />
                          <span
                            title={label}
                            style={{
                              flex: 1,
                              minWidth: 0,
                              fontSize: 12,
                              lineHeight: 1.2,
                              textAlign: "left",
                              whiteSpace: "nowrap",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                            }}
                          >
                            {label}
                          </span>
                        </Tag.CheckableTag>
                      );
                    })}
                  </div>
                  <Space
                    size={0}
                    style={{ flex: "none", whiteSpace: "nowrap" }}
                  >
                    <Tooltip title="全选本行">
                      <Button
                        type="text"
                        size="small"
                        icon={<CheckSquareOutlined />}
                        onClick={() => toggleCategory(row.calibers, true)}
                        disabled={allOn}
                        aria-label="全选本行"
                      />
                    </Tooltip>
                    <Tooltip title="清空本行">
                      <Button
                        type="text"
                        size="small"
                        icon={<ClearOutlined />}
                        onClick={() => toggleCategory(row.calibers, false)}
                        disabled={selectedInRow === 0}
                        aria-label="清空本行"
                      />
                    </Tooltip>
                  </Space>
                </div>
              );
            })
          ) : (
            <div style={{ padding: 12 }}>
              <Typography.Text type="secondary">暂无口径数据</Typography.Text>
            </div>
          )}
        </div>
      </div>

      <Card size="small" styles={{ body: { padding: 12 } }}>
        <Typography.Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
          点击色点跳转枪械页，筛选可使用该弹药的枪械
        </Typography.Text>
        <Scatter {...config} onReady={onScatterReady} />
      </Card>

      <Card size="small" styles={{ body: { padding: 12 } }}>
        <TarkovAmmoWikiTable data={data} />
      </Card>
    </Space>
  );
}
