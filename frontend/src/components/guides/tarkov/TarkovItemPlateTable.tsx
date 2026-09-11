import { Image, Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMemo, type Key } from "react";
import { Link } from "react-router-dom";
import {
  formatMoney,
  formatPercent,
  formatWeight,
} from "@/lib/tarkovItemFormat";
import { hdPreviewUrl, transparentThumbUrl } from "@/lib/tarkovItemImages";
import { itemHrefFromTypes } from "@/lib/tarkovItemTypes";
import {
  plateBadgeLabel,
  plateColumnFilters,
  plateColumnMatch,
  type PlateFilterKey,
  type PlatePresetMark,
  type PlateTableRow,
} from "@/lib/tarkovItemPlates";
import tableStyles from "./TarkovDarkTable.module.css";
import catalog from "./TarkovItemCatalogPanel.module.css";
import styles from "./TarkovItemPlateTable.module.css";

function dash(value: string | number | null | undefined): string {
  if (value == null || value === "") return "—";
  return String(value);
}

function compareNullableNumber(left: number | null, right: number | null): number {
  if (left == null && right == null) return 0;
  if (left == null) return 1;
  if (right == null) return -1;
  return left - right;
}

function filterProps(rows: PlateTableRow[], key: PlateFilterKey) {
  return {
    filters: plateColumnFilters(rows, key),
    onFilter: (value: boolean | Key, row: PlateTableRow) =>
      plateColumnMatch(row, key, value),
    filterSearch: key === "slot" || key === "material",
  };
}

type Props = {
  rows: PlateTableRow[];
  marks: PlatePresetMark[];
};

export function TarkovItemPlateTable({ rows, marks }: Props) {
  const columns = useMemo<ColumnsType<PlateTableRow>>(() => {
    if (!rows.length) return [];
    return [
      {
        title: "名称",
        dataIndex: "name",
        key: "name",
        ellipsis: true,
        render: (_: unknown, row) => {
          const thumb = transparentThumbUrl(row.icon);
          const hd = hdPreviewUrl(row.icon) || thumb;
          return (
            <span className={catalog.nameCell}>
              {thumb ? (
                <Image
                  src={thumb}
                  alt=""
                  width={36}
                  height={36}
                  preview={{ src: hd, mask: false }}
                  style={{ objectFit: "contain", flex: "0 0 36px" }}
                />
              ) : (
                <span style={{ width: 36, height: 36, flex: "0 0 36px" }} />
              )}
              <span className={styles.nameBody}>
                <Link
                  className={catalog.nameLink}
                  to={itemHrefFromTypes(row.id, row.types)}
                >
                  {row.name}
                </Link>
                {row.badges.length ? (
                  <span className={styles.badges}>
                    {row.badges.map((kind) => (
                      <span key={kind} className={styles.badge}>
                        {plateBadgeLabel(kind)}
                      </span>
                    ))}
                  </span>
                ) : null}
              </span>
            </span>
          );
        },
      },
      {
        title: "槽位",
        dataIndex: "slot",
        key: "slot",
        width: 140,
        ...filterProps(rows, "slot"),
      },
      {
        title: "等级",
        dataIndex: "class",
        key: "class",
        width: 108,
        align: "center",
        sorter: (a, b) => compareNullableNumber(a.class, b.class),
        ...filterProps(rows, "class"),
        render: (value: number | null) => dash(value),
      },
      {
        title: "材质",
        dataIndex: "material",
        key: "material",
        width: 100,
        ...filterProps(rows, "material"),
        render: (value: string) => dash(value),
      },
      {
        title: "护甲类型",
        dataIndex: "armorType",
        key: "armorType",
        width: 96,
        ...filterProps(rows, "armorType"),
        render: (value: string) => dash(value),
      },
      {
        title: "人机惩罚",
        dataIndex: "ergoPenalty",
        key: "ergoPenalty",
        width: 108,
        align: "right",
        sorter: (a, b) => compareNullableNumber(a.ergoPenalty, b.ergoPenalty),
        render: (value: number | null) => formatPercent(value),
      },
      {
        title: "移速惩罚",
        dataIndex: "speedPenalty",
        key: "speedPenalty",
        width: 108,
        align: "right",
        sorter: (a, b) => compareNullableNumber(a.speedPenalty, b.speedPenalty),
        render: (value: number | null) => formatPercent(value),
      },
      {
        title: "转向惩罚",
        dataIndex: "turnPenalty",
        key: "turnPenalty",
        width: 108,
        align: "right",
        sorter: (a, b) => compareNullableNumber(a.turnPenalty, b.turnPenalty),
        render: (value: number | null) => formatPercent(value),
      },
      {
        title: "耐久",
        dataIndex: "durability",
        key: "durability",
        width: 72,
        align: "right",
        sorter: (a, b) => compareNullableNumber(a.durability, b.durability),
        render: (value: number | null) => dash(value),
      },
      {
        title: "重量",
        dataIndex: "weight",
        key: "weight",
        width: 88,
        align: "right",
        sorter: (a, b) => compareNullableNumber(a.weight, b.weight),
        render: (value: number | null) => formatWeight(value),
      },
      {
        title: "价格",
        dataIndex: "price",
        key: "price",
        width: 110,
        align: "right",
        sorter: (a, b) => compareNullableNumber(a.price, b.price),
        render: (value: number | null) => formatMoney(value),
      },
    ];
  }, [rows]);

  if (!rows.length) return null;
  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <h3 className={styles.title}>兼容护甲板</h3>
        {marks.length ? (
          <p className={styles.legend}>
            {marks.map((mark) => (
              <span key={mark.kind} className={styles.badge}>
                {mark.name}
              </span>
            ))}
            <span className={styles.legendHint}>
              默认是出厂插板；Stripped 是未插板配置，不单独占一页。
            </span>
          </p>
        ) : null}
      </div>
      <Table<PlateTableRow>
        className={tableStyles.table}
        size="small"
        rowKey="key"
        columns={columns}
        dataSource={rows}
        pagination={false}
        scroll={{ x: 1280 }}
      />
    </div>
  );
}
