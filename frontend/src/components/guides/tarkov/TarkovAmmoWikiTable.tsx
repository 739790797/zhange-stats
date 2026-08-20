import { Image, Table } from "antd";
import type { ColumnsType, TableProps } from "antd/es/table";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { TarkovAmmoItem } from "@/api/guidesApi";
import { formatCaliberLabel } from "@/lib/tarkovAmmoCategories";
import { ammoDetailHref } from "@/lib/tarkovItemTypes";
import { hdPreviewUrl, transparentThumbUrl } from "@/lib/tarkovItemImages";
import {
  ARMOR_EFFECT_COLORS,
  ARMOR_EFFECT_LABELS,
  armorEffectLevel,
  type ArmorEffectLevel,
} from "@/lib/tarkovAmmoArmorEffect";
import tableStyles from "./TarkovDarkTable.module.css";
import styles from "./TarkovAmmoWikiTable.module.css";

type Props = {
  data: TarkovAmmoItem[];
  defaultAmmoId?: string;
  compact?: boolean;
  highlightedId?: string | null;
  onHoverId?: (id: string | null) => void;
};

type SortKey =
  | "damage"
  | "penetration"
  | "armor_damage"
  | "initial_speed"
  | "accuracy_modifier"
  | "recoil_modifier"
  | "light_bleed_modifier"
  | "heavy_bleed_modifier";

function formatModifierPct(value: number | null | undefined): string {
  const n = Number(value);
  if (!Number.isFinite(n) || n === 0) return "0%";
  const pct = Math.round(n * 1000) / 10;
  const text = Number.isInteger(pct) ? String(pct) : pct.toFixed(1);
  return pct > 0 ? `+${text}%` : `${text}%`;
}

function renderModifierPct(value: number | null | undefined) {
  const n = Number(value);
  const text = formatModifierPct(n);
  if (!Number.isFinite(n) || n === 0) {
    return <span style={{ color: "#8a8a8a" }}>{text}</span>;
  }
  return text;
}

/** polarity: "accuracy" 增绿减红；"recoil" 增红减绿 */
function renderSignedModifier(
  value: number | null | undefined,
  polarity: "accuracy" | "recoil",
) {
  const n = Number(value);
  const text = formatModifierPct(n);
  if (!Number.isFinite(n) || n === 0) {
    return <span style={{ color: "#8a8a8a" }}>{text}</span>;
  }
  const positiveIsGood = polarity === "accuracy";
  const good = positiveIsGood ? n > 0 : n < 0;
  return (
    <span style={{ color: good ? "#8bc34a" : "#e07070", fontWeight: 600 }}>
      {text}
    </span>
  );
}

function formatInitialSpeed(value: number | null | undefined): string {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return "—";
  return String(Math.round(n));
}

function ArmorEffectCell({ level }: { level: ArmorEffectLevel }) {
  return (
    <span title={ARMOR_EFFECT_LABELS[level]}>{ARMOR_EFFECT_LABELS[level]}</span>
  );
}

function buildCaliberRowSpan(rows: TarkovAmmoItem[]): Map<string, number> {
  const map = new Map<string, number>();
  let i = 0;
  while (i < rows.length) {
    let j = i + 1;
    while (j < rows.length && rows[j].caliber === rows[i].caliber) j += 1;
    map.set(rows[i].id, j - i);
    for (let k = i + 1; k < j; k += 1) map.set(rows[k].id, 0);
    i = j;
  }
  return map;
}

export function TarkovAmmoWikiTable({
  data,
  defaultAmmoId,
  compact = false,
  highlightedId,
  onHoverId,
}: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("penetration");
  const [sortOrder, setSortOrder] = useState<"ascend" | "descend">("ascend");
  const defaultId = (defaultAmmoId || "").trim();
  const hoverId = (highlightedId || "").trim();
  const w = compact
    ? {
        caliber: 72,
        name: 220,
        num: 44,
        speed: 48,
        mod: 50,
        bleed: 56,
        armor: 36,
        icon: 32,
      }
    : {
        caliber: 88,
        name: 268,
        num: 72,
        speed: 88,
        mod: 88,
        bleed: 100,
        armor: 56,
        icon: 48,
      };

  const rows = useMemo(() => {
    return [...data].sort((a, b) => {
      const byCaliber = formatCaliberLabel(a.caliber).localeCompare(
        formatCaliberLabel(b.caliber),
        "zh",
        { numeric: true, sensitivity: "base" },
      );
      if (byCaliber !== 0) return byCaliber;
      const delta = a[sortKey] - b[sortKey];
      return sortOrder === "ascend" ? delta : -delta;
    });
  }, [data, sortKey, sortOrder]);

  const caliberRowSpan = useMemo(() => buildCaliberRowSpan(rows), [rows]);

  const onTableChange: TableProps<TarkovAmmoItem>["onChange"] = (
    _pagination,
    _filters,
    sorter,
  ) => {
    const s = Array.isArray(sorter) ? sorter[0] : sorter;
    const key = s?.columnKey;
    if (
      key === "damage" ||
      key === "penetration" ||
      key === "armor_damage" ||
      key === "initial_speed" ||
      key === "accuracy_modifier" ||
      key === "recoil_modifier" ||
      key === "light_bleed_modifier" ||
      key === "heavy_bleed_modifier"
    ) {
      if (s?.order) {
        setSortKey(key);
        setSortOrder(s.order);
      } else {
        setSortKey("penetration");
        setSortOrder("ascend");
      }
    }
  };

  const columns: ColumnsType<TarkovAmmoItem> = [
    {
      title: "口径",
      dataIndex: "caliber",
      key: "caliber",
      width: w.caliber,
      ...(compact ? {} : { fixed: "left" as const }),
      onCell: (row) => ({
        rowSpan: caliberRowSpan.get(row.id) ?? 1,
        style: {
          verticalAlign: "middle",
          textAlign: "left",
          fontWeight: 600,
        },
      }),
      render: (caliber: string) => {
        const label = formatCaliberLabel(caliber);
        const raw = (caliber || "").trim();
        if (!raw) return label;
        return (
          <Link
            to={`/guides/tarkov/items/guns?caliber=${encodeURIComponent(raw)}`}
            title={`查看可用 ${label} 的枪械`}
            onClick={(e) => e.stopPropagation()}
          >
            {label}
          </Link>
        );
      },
    },
    {
      title: "名称",
      dataIndex: "name",
      key: "name",
      width: w.name,
      ...(compact ? {} : { fixed: "left" as const }),
      ellipsis: true,
      render: (_: unknown, row) => {
        const label = row.name || row.short_name || row.id;
        const thumb = transparentThumbUrl(row.icon_link);
        const hd = hdPreviewUrl(row.icon_link) || thumb;
        return (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: compact ? 8 : 10,
              minWidth: 0,
              maxWidth: "100%",
              padding: "4px 0",
            }}
          >
            {thumb ? (
              <Image
                src={thumb}
                alt=""
                width={w.icon}
                height={w.icon}
                preview={{ src: hd, mask: false }}
                onClick={(e) => e.stopPropagation()}
                style={{
                  objectFit: "contain",
                  flex: `0 0 ${w.icon}px`,
                  cursor: "zoom-in",
                }}
              />
            ) : (
              <span
                style={{
                  width: w.icon,
                  height: w.icon,
                  flex: `0 0 ${w.icon}px`,
                  display: "inline-block",
                }}
              />
            )}
            <Link
              to={ammoDetailHref(row.id)}
              title="查看弹药详情"
              onClick={(e) => e.stopPropagation()}
              style={{
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                minWidth: 0,
              }}
            >
              {label}
            </Link>
            {defaultId && row.id === defaultId ? (
              <span className={styles.defaultBadge}>默认</span>
            ) : null}
          </span>
        );
      },
    },
    {
      title: "伤害",
      dataIndex: "damage",
      key: "damage",
      width: w.num,
      align: "left",
      sorter: true,
      sortOrder: sortKey === "damage" ? sortOrder : null,
    },
    {
      title: "穿透",
      dataIndex: "penetration",
      key: "penetration",
      width: w.num,
      align: "left",
      sorter: true,
      sortOrder: sortKey === "penetration" ? sortOrder : null,
    },
    {
      title: "对甲%",
      dataIndex: "armor_damage",
      key: "armor_damage",
      width: w.num,
      align: "left",
      sorter: true,
      sortOrder: sortKey === "armor_damage" ? sortOrder : null,
    },
    {
      title: compact ? "初速" : "子弹初速",
      dataIndex: "initial_speed",
      key: "initial_speed",
      width: w.speed,
      align: "left",
      sorter: true,
      sortOrder: sortKey === "initial_speed" ? sortOrder : null,
      render: (v: number) => formatInitialSpeed(v),
    },
    {
      title: compact ? "精度" : "精度修正",
      dataIndex: "accuracy_modifier",
      key: "accuracy_modifier",
      width: w.mod,
      align: "left",
      sorter: true,
      sortOrder: sortKey === "accuracy_modifier" ? sortOrder : null,
      render: (v: number) => renderSignedModifier(v, "accuracy"),
    },
    {
      title: compact ? "后座" : "后座修正",
      dataIndex: "recoil_modifier",
      key: "recoil_modifier",
      width: w.mod,
      align: "left",
      sorter: true,
      sortOrder: sortKey === "recoil_modifier" ? sortOrder : null,
      render: (v: number) => renderSignedModifier(v, "recoil"),
    },
    {
      title: compact ? "小出血" : "小出血概率",
      dataIndex: "light_bleed_modifier",
      key: "light_bleed_modifier",
      width: w.bleed,
      align: "left",
      sorter: true,
      sortOrder: sortKey === "light_bleed_modifier" ? sortOrder : null,
      render: (v: number) => renderModifierPct(v),
    },
    {
      title: compact ? "大出血" : "大出血概率",
      dataIndex: "heavy_bleed_modifier",
      key: "heavy_bleed_modifier",
      width: w.bleed,
      align: "left",
      sorter: true,
      sortOrder: sortKey === "heavy_bleed_modifier" ? sortOrder : null,
      render: (v: number) => renderModifierPct(v),
    },
    {
      title: compact ? "对甲效果" : "对护甲效果（估）",
      children: [1, 2, 3, 4, 5, 6].map((armorClass) => ({
        title: String(armorClass),
        key: `armor_${armorClass}`,
        width: w.armor,
        align: "center" as const,
        onCell: (row: TarkovAmmoItem) => {
          const level = armorEffectLevel(
            row.penetration,
            armorClass,
            row.armor_damage,
          );
          const { bg, fg } = ARMOR_EFFECT_COLORS[level];
          return {
            style: {
              background: bg,
              color: fg,
              fontWeight: 600,
              fontSize: 12,
              padding: compact ? "2px 0" : "4px 2px",
            },
          };
        },
        render: (_: unknown, row: TarkovAmmoItem) => (
          <ArmorEffectCell
            level={armorEffectLevel(
              row.penetration,
              armorClass,
              row.armor_damage,
            )}
          />
        ),
      })),
    },
  ];

  const visibleColumns = compact
    ? columns.filter((col) => col.key !== "caliber")
    : columns;

  return (
    <Table<TarkovAmmoItem>
      className={`${tableStyles.table} ${compact ? styles.compact : ""}`}
      size="small"
      rowKey="id"
      columns={visibleColumns}
      dataSource={rows}
      pagination={false}
      tableLayout={compact ? "fixed" : undefined}
      scroll={compact ? undefined : { x: 1500 }}
      locale={{ emptyText: "当前筛选下无弹药" }}
      onChange={onTableChange}
      onRow={
        onHoverId
          ? (row) => ({
              onMouseEnter: () => onHoverId(row.id),
              onMouseLeave: () => onHoverId(null),
            })
          : undefined
      }
      rowClassName={(row) =>
        hoverId && row.id === hoverId ? styles.hoverRow : ""
      }
    />
  );
}
