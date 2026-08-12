import { Scatter } from "@ant-design/plots";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Space, Spin, Tag, Tooltip, Typography } from "antd";
import { CheckSquareOutlined, ClearOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { useEffect, useMemo, useState } from "react";
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

function formatSyncedAt(value: string | null | undefined): string {
  if (!value) return "—";
  const d = dayjs(value);
  return d.isValid() ? d.format("YYYY-MM-DD HH:mm:ss") : value;
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

const AMMO_SOURCE_LINKS: Record<string, { label: string; href: string }> = {
  "tarkov.dev": {
    label: "api.tarkov.dev/graphql",
    href: "https://api.tarkov.dev/graphql",
  },
  "json.tarkov.dev": {
    label: "json.tarkov.dev/regular/items",
    href: "https://json.tarkov.dev/regular/items",
  },
  tarkovdata: {
    label: "TarkovTracker/tarkovdata",
    href: "https://github.com/TarkovTracker/tarkovdata",
  },
};

function renderAmmoSource(source: string | null | undefined) {
  const key = (source || "").trim();
  const hit = AMMO_SOURCE_LINKS[key];
  if (!hit) {
    return <Typography.Text type="secondary">{key || "未知"}</Typography.Text>;
  }
  return (
    <Typography.Link href={hit.href} target="_blank" rel="noreferrer">
      {hit.label}
    </Typography.Link>
  );
}

export function TarkovAmmoScatterPanel() {
  const ammoQuery = useQuery({
    queryKey: ["guides-tarkov-ammo"],
    queryFn: fetchTarkovAmmo,
    staleTime: 5 * 60_000,
    retry: 1,
  });

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

  const meta = ammoQuery.data;

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Space direction="vertical" size={0}>
        <Typography.Text type="secondary">
          数据来源：{renderAmmoSource(meta?.source)}
        </Typography.Text>
        <Typography.Text type="secondary">
          更新时间：{formatSyncedAt(meta?.synced_at)}
        </Typography.Text>
      </Space>

      <div>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 8,
            alignItems: "center",
            marginBottom: 10,
          }}
        >
          <Button size="small" onClick={() => persistSelection([...allCalibers])}>
            全选
          </Button>
          <Button size="small" onClick={() => persistSelection([])}>
            清空
          </Button>
        </div>
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
        <Scatter {...config} />
      </Card>

      <Card size="small" styles={{ body: { padding: 12 } }}>
        <TarkovAmmoWikiTable data={data} />
      </Card>
    </Space>
  );
}
