import { Scatter } from "@ant-design/plots";
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Segmented,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import dayjs from "dayjs";
import { useEffect, useMemo, useState } from "react";
import { fetchTarkovAmmo, type TarkovAmmoItem } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import {
  AMMO_CATEGORIES,
  DEFAULT_AMMO_CATEGORY,
  type AmmoCategoryId,
  calibersInCategory,
  formatCaliberLabel,
} from "@/lib/tarkovAmmoCategories";
import {
  loadTarkovAmmoFilters,
  resolveCategorySelection,
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
      Array.from(new Set(items.map((row) => row.caliber))).sort((a, b) =>
        formatCaliberLabel(a).localeCompare(formatCaliberLabel(b), "zh"),
      ),
    [items],
  );

  const [category, setCategory] = useState<AmmoCategoryId>(
    () => loadTarkovAmmoFilters().category || DEFAULT_AMMO_CATEGORY,
  );
  const [selectedByCategory, setSelectedByCategory] = useState<
    Partial<Record<AmmoCategoryId, string[]>>
  >(() => loadTarkovAmmoFilters().selectedByCategory);
  const [calibers, setCalibers] = useState<string[] | null>(null);
  const [categoryReady, setCategoryReady] = useState(false);

  const categoryCalibers = useMemo(
    () => calibersInCategory(allCalibers, category),
    [allCalibers, category],
  );

  useEffect(() => {
    if (!allCalibers.length) return;
    const next = resolveCategorySelection(
      category,
      calibersInCategory(allCalibers, category),
      selectedByCategory,
    );
    setCalibers(next);
    setCategoryReady(true);
  }, [allCalibers, category, selectedByCategory]);

  const selectedCalibers = calibers ?? categoryCalibers;
  const selectedSet = useMemo(
    () => new Set(selectedCalibers),
    [selectedCalibers],
  );

  const persistSelection = (next: string[]) => {
    setCalibers(next);
    setSelectedByCategory((prev) => {
      const updated = { ...prev, [category]: next };
      saveTarkovAmmoFilters({ category, selectedByCategory: updated });
      return updated;
    });
  };

  const toggleCaliber = (caliber: string) => {
    const next = new Set(selectedSet);
    if (next.has(caliber)) next.delete(caliber);
    else next.add(caliber);
    persistSelection(categoryCalibers.filter((c) => next.has(c)));
  };

  const selectAllInCategory = () => persistSelection([...categoryCalibers]);
  const clearInCategory = () => persistSelection([]);

  const onCategoryChange = (value: AmmoCategoryId) => {
    setSelectedByCategory((prev) => {
      const updated =
        calibers !== null ? { ...prev, [category]: calibers } : prev;
      saveTarkovAmmoFilters({ category: value, selectedByCategory: updated });
      return updated;
    });
    setCategory(value);
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

  if (ammoQuery.isLoading || !categoryReady) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        <Spin tip="同步 / 加载弹药数据…" />
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
          <Segmented
            value={category}
            options={AMMO_CATEGORIES.map((c) => ({
              label: c.label,
              value: c.id,
            }))}
            onChange={(value) => onCategoryChange(value as AmmoCategoryId)}
          />
          <Button size="small" onClick={selectAllInCategory}>
            全选
          </Button>
          <Button size="small" onClick={clearInCategory}>
            清空
          </Button>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {categoryCalibers.length ? (
            categoryCalibers.map((caliber) => {
              const checked = selectedSet.has(caliber);
              const color =
                caliberColors.get(caliber) || distinctCaliberColor(0);
              return (
                <Tag.CheckableTag
                  key={caliber}
                  checked={checked}
                  onChange={() => toggleCaliber(caliber)}
                  style={{
                    marginInlineEnd: 0,
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
                      verticalAlign: "middle",
                    }}
                  />
                  {formatCaliberLabel(caliber)}
                </Tag.CheckableTag>
              );
            })
          ) : (
            <Typography.Text type="secondary">该类暂无口径数据</Typography.Text>
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
