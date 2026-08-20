import { Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMemo } from "react";
import {
  averageWipeLength,
  buildWipeRows,
  type TarkovWipeRow,
} from "@/lib/tarkovWipeLength";
import tableStyles from "./TarkovDarkTable.module.css";
import styles from "./TarkovGuideTrade.module.css";

function formatDay(iso: string): string {
  return iso.slice(0, 10);
}

export function TarkovWipeLengthPanel() {
  const rows = useMemo(() => buildWipeRows(), []);
  const average = useMemo(() => averageWipeLength(), []);

  const columns: ColumnsType<TarkovWipeRow> = [
    { title: "补丁", dataIndex: "name", key: "name", width: 140 },
    {
      title: "开始",
      key: "start",
      render: (_: unknown, row) => formatDay(row.start),
    },
    {
      title: "结束",
      key: "end",
      render: (_: unknown, row) =>
        row.ongoing ? "进行中" : formatDay(row.end),
    },
    {
      title: "天数",
      dataIndex: "lengthDays",
      key: "days",
      width: 100,
      render: (value: number) => `${value} 天`,
    },
  ];

  return (
    <div className={styles.stack}>
      <div className={styles.summary}>近 6 次已结束删档平均 {average} 天</div>
      <div className={styles.meta}>
        日期对齐 tarkov.dev 公开记录；当前赛季结束日按今天计算。
      </div>
      <div className={tableStyles.table}>
        <Table
          rowKey={(row) => row.name}
          columns={columns}
          dataSource={rows}
          pagination={false}
          size="small"
        />
      </div>
    </div>
  );
}
