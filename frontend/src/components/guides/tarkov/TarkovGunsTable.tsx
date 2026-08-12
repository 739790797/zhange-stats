import { Image, Input, Table } from "antd";
import type { ColumnsType, TableProps } from "antd/es/table";
import { useMemo, useState } from "react";
import type { TarkovGunItem } from "@/api/guidesApi";
import {
  formatCaliberLabel,
  formatWeaponClass,
} from "@/lib/tarkovGunCategories";

type Props = {
  data: TarkovGunItem[];
};

const CDN_SUFFIX_RE =
  /-(?:icon|grid-image|base-image|512|8x|image)\.webp(\?.*)?$/i;

/** icon 为灰黑底；base-image 为透明小图 */
function transparentThumbUrl(src: string | null | undefined): string {
  const url = (src || "").trim();
  if (!url) return "";
  return url.replace(CDN_SUFFIX_RE, "-base-image.webp$1");
}

/** CDN 最大透明高清：image512pxLink / image8xLink → -512.webp */
function hdPreviewUrl(src: string | null | undefined): string {
  const url = (src || "").trim();
  if (!url) return "";
  return url.replace(CDN_SUFFIX_RE, "-512.webp$1");
}

type SortKey =
  | "fire_rate"
  | "ergonomics"
  | "recoil_vertical"
  | "recoil_horizontal"
  | "effective_distance";

function buildCaliberRowSpan(rows: TarkovGunItem[]): Map<string, number> {
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

export function TarkovGunsTable({ data }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("ergonomics");
  const [sortOrder, setSortOrder] = useState<"ascend" | "descend">("descend");
  const [caliberFilter, setCaliberFilter] = useState<string[] | null>(null);
  const [classFilter, setClassFilter] = useState<string[] | null>(null);
  const [nameKeyword, setNameKeyword] = useState("");

  const caliberFilters = useMemo(() => {
    const set = new Set(data.map((r) => r.caliber).filter(Boolean));
    return Array.from(set)
      .sort((a, b) =>
        formatCaliberLabel(a).localeCompare(formatCaliberLabel(b), "zh"),
      )
      .map((c) => ({ text: formatCaliberLabel(c), value: c }));
  }, [data]);

  const classFilters = useMemo(() => {
    const set = new Set(data.map((r) => r.weapon_class || ""));
    return Array.from(set)
      .sort((a, b) =>
        formatWeaponClass(a).localeCompare(formatWeaponClass(b), "zh"),
      )
      .map((c) => ({ text: formatWeaponClass(c), value: c }));
  }, [data]);

  const rows = useMemo(() => {
    let list = data;
    if (caliberFilter && caliberFilter.length > 0) {
      const allow = new Set(caliberFilter);
      list = list.filter((r) => allow.has(r.caliber));
    }
    if (classFilter && classFilter.length > 0) {
      const allow = new Set(classFilter);
      list = list.filter((r) => allow.has(r.weapon_class || ""));
    }
    const q = nameKeyword.trim().toLowerCase();
    if (q) {
      list = list.filter((r) => {
        const name = (r.name || "").toLowerCase();
        const shortName = (r.short_name || "").toLowerCase();
        return name.includes(q) || shortName.includes(q);
      });
    }
    return [...list].sort((a, b) => {
      const byCaliber = formatCaliberLabel(a.caliber).localeCompare(
        formatCaliberLabel(b.caliber),
        "zh",
      );
      if (byCaliber !== 0) return byCaliber;
      const delta = Number(a[sortKey]) - Number(b[sortKey]);
      return sortOrder === "ascend" ? delta : -delta;
    });
  }, [caliberFilter, classFilter, data, nameKeyword, sortKey, sortOrder]);

  const caliberRowSpan = useMemo(() => buildCaliberRowSpan(rows), [rows]);

  const onTableChange: TableProps<TarkovGunItem>["onChange"] = (
    _pagination,
    filters,
    sorter,
  ) => {
    const calibers = filters?.caliber;
    const classes = filters?.weapon_class;
    setCaliberFilter(
      Array.isArray(calibers) && calibers.length
        ? calibers.map(String)
        : null,
    );
    setClassFilter(
      Array.isArray(classes) && classes.length ? classes.map(String) : null,
    );

    const s = Array.isArray(sorter) ? sorter[0] : sorter;
    const key = s?.columnKey;
    const order = s?.order;
    // Ant Design「取消排序」时 order 为空；也可能不带 columnKey，需一律回默认
    if (
      order &&
      (key === "fire_rate" ||
        key === "ergonomics" ||
        key === "recoil_vertical" ||
        key === "recoil_horizontal" ||
        key === "effective_distance")
    ) {
      setSortKey(key);
      setSortOrder(order);
    } else if (!order) {
      setSortKey("ergonomics");
      setSortOrder("descend");
    }
  };

  const columns: ColumnsType<TarkovGunItem> = [
    {
      title: "口径",
      dataIndex: "caliber",
      key: "caliber",
      width: 120,
      fixed: "left",
      filters: caliberFilters,
      filteredValue: caliberFilter,
      filterSearch: true,
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
      title: "图片",
      dataIndex: "icon_link",
      key: "icon",
      width: 56,
      align: "center",
      render: (src: string) => {
        const thumb = transparentThumbUrl(src);
        const hd = hdPreviewUrl(src) || thumb;
        return thumb ? (
          <Image
            src={thumb}
            alt=""
            width={36}
            height={36}
            preview={{ src: hd, mask: false }}
            style={{
              objectFit: "contain",
              display: "block",
              margin: "0 auto",
              cursor: "zoom-in",
            }}
          />
        ) : (
          <span style={{ color: "rgba(0, 0, 0, 0.25)" }}>—</span>
        );
      },
    },
    {
      title: (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
          }}
        >
          <span style={{ flex: "none" }}>名称</span>
          <Input
            allowClear
            size="small"
            placeholder="关键词搜索"
            value={nameKeyword}
            onChange={(e) => setNameKeyword(e.target.value)}
            onClick={(e) => e.stopPropagation()}
            style={{ width: 140 }}
          />
        </div>
      ),
      dataIndex: "name",
      key: "name",
      width: 260,
      ellipsis: true,
      render: (_: unknown, row) => row.name || row.short_name || row.id,
    },
    {
      title: "类型",
      dataIndex: "weapon_class",
      key: "weapon_class",
      width: 140,
      filters: classFilters,
      filteredValue: classFilter,
      filterSearch: true,
      render: (v: string) => formatWeaponClass(v),
    },
    {
      title: "射速",
      dataIndex: "fire_rate",
      key: "fire_rate",
      width: 72,
      align: "right",
      sorter: true,
      sortOrder: sortKey === "fire_rate" ? sortOrder : null,
    },
    {
      title: "人机",
      dataIndex: "ergonomics",
      key: "ergonomics",
      width: 72,
      align: "right",
      sorter: true,
      sortOrder: sortKey === "ergonomics" ? sortOrder : null,
      render: (v: number) => (Number.isFinite(v) ? Math.round(v * 10) / 10 : v),
    },
    {
      title: "垂后坐",
      dataIndex: "recoil_vertical",
      key: "recoil_vertical",
      width: 80,
      align: "right",
      sorter: true,
      sortOrder: sortKey === "recoil_vertical" ? sortOrder : null,
    },
    {
      title: "横后坐",
      dataIndex: "recoil_horizontal",
      key: "recoil_horizontal",
      width: 80,
      align: "right",
      sorter: true,
      sortOrder: sortKey === "recoil_horizontal" ? sortOrder : null,
    },
    {
      title: "有效距离",
      dataIndex: "effective_distance",
      key: "effective_distance",
      width: 88,
      align: "right",
      sorter: true,
      sortOrder: sortKey === "effective_distance" ? sortOrder : null,
    },
  ];

  return (
    <Table<TarkovGunItem>
      size="small"
      rowKey="id"
      columns={columns}
      dataSource={rows}
      pagination={false}
      scroll={{ x: 1100 }}
      onChange={onTableChange}
      locale={{ emptyText: "当前筛选下无枪械" }}
    />
  );
}
