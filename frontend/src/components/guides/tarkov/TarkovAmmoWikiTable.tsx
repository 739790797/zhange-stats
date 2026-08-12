import { Table } from "antd";
import type { ColumnsType, TableProps } from "antd/es/table";
import { useMemo, useState } from "react";
import type { TarkovAmmoItem } from "@/api/guidesApi";
import { formatCaliberLabel } from "@/lib/tarkovAmmoCategories";
import {
  ARMOR_EFFECT_COLORS,
  ARMOR_EFFECT_LABELS,
  armorEffectLevel,
  type ArmorEffectLevel,
} from "@/lib/tarkovAmmoArmorEffect";

type Props = {
  data: TarkovAmmoItem[];
};

type SortKey = "damage" | "penetration" | "armor_damage";

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

export function TarkovAmmoWikiTable({ data }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("penetration");
  const [sortOrder, setSortOrder] = useState<"ascend" | "descend">("ascend");

  const rows = useMemo(() => {
    return [...data].sort((a, b) => {
      const byCaliber = formatCaliberLabel(a.caliber).localeCompare(
        formatCaliberLabel(b.caliber),
        "zh",
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
    if (key === "damage" || key === "penetration" || key === "armor_damage") {
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
      width: 120,
      fixed: "left",
      onCell: (row) => ({
        rowSpan: caliberRowSpan.get(row.id) ?? 1,
        style: {
          verticalAlign: "middle",
          textAlign: "center",
          fontWeight: 600,
        },
      }),
      render: (caliber: string) => formatCaliberLabel(caliber),
    },
    {
      title: "名称",
      dataIndex: "name",
      key: "name",
      width: 220,
      fixed: "left",
      ellipsis: true,
      render: (_: unknown, row) => row.name || row.short_name || row.id,
    },
    {
      title: "伤害",
      dataIndex: "damage",
      key: "damage",
      width: 72,
      align: "right",
      sorter: true,
      sortOrder: sortKey === "damage" ? sortOrder : null,
    },
    {
      title: "穿透",
      dataIndex: "penetration",
      key: "penetration",
      width: 72,
      align: "right",
      sorter: true,
      sortOrder: sortKey === "penetration" ? sortOrder : null,
    },
    {
      title: "对甲%",
      dataIndex: "armor_damage",
      key: "armor_damage",
      width: 72,
      align: "right",
      sorter: true,
      sortOrder: sortKey === "armor_damage" ? sortOrder : null,
    },
    {
      title: "对护甲效果（估）",
      children: [1, 2, 3, 4, 5, 6].map((armorClass) => ({
        title: String(armorClass),
        key: `armor_${armorClass}`,
        width: 72,
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
              padding: "4px 2px",
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

  return (
    <Table<TarkovAmmoItem>
      size="small"
      rowKey="id"
      columns={columns}
      dataSource={rows}
      pagination={false}
      scroll={{ x: 900 }}
      locale={{ emptyText: "当前筛选下无弹药" }}
      onChange={onTableChange}
    />
  );
}
