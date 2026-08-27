import { Alert, Spin, Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchTarkovHideout } from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { tarkovHideoutHref } from "@/lib/tarkovHomeNav";
import { formatMoney } from "@/lib/tarkovItemFormat";
import tableStyles from "./TarkovDarkTable.module.css";
import styles from "./TarkovGuideTrade.module.css";

type CostRow = {
  slug: string;
  name: string;
  levels: number;
  cost: number | null;
};

export function TarkovHideoutCostPanel() {
  const gameMode = useTarkovGameMode();
  const catalogQuery = useQuery({
    queryKey: ["guides-tarkov-hideout", gameMode],
    queryFn: fetchTarkovHideout,
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const rows = useMemo<CostRow[]>(() => {
    const items = catalogQuery.data?.items ?? [];
    return items.map((station) => {
      let cost = 0;
      let priced = false;
      for (const level of station.levels || []) {
        for (const req of level.item_requirements || []) {
          const price = req.flea_price;
          if (price != null && price > 0) {
            cost += price * Number(req.count || 1);
            priced = true;
          }
        }
      }
      return {
        slug: station.slug,
        name: station.name,
        levels: station.level_count,
        cost: priced ? cost : null,
      };
    });
  }, [catalogQuery.data]);

  const total = rows.reduce((sum, row) => sum + (row.cost || 0), 0);

  const columns: ColumnsType<CostRow> = [
    {
      title: "模块",
      key: "name",
      render: (_: unknown, row) => (
        <Link to={tarkovHideoutHref(row.slug)}>{row.name}</Link>
      ),
    },
    { title: "等级数", dataIndex: "levels", key: "levels", width: 90 },
    {
      title: "跳蚤合计",
      key: "cost",
      align: "right",
      render: (_: unknown, row) => formatMoney(row.cost),
    },
  ];

  if (catalogQuery.isLoading) {
    return (
      <div className={styles.status}>
        <Spin />
      </div>
    );
  }

  if (catalogQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message="建造成本加载失败"
        description={apiError(catalogQuery.error, "建造成本加载失败")}
      />
    );
  }

  return (
    <div className={styles.stack}>
      <div className={styles.summary}>全部模块合计 {formatMoney(total)}</div>
      <div className={styles.meta}>
        按跳蚤低价估算升级材料；无报价的物品不计入。
      </div>
      <div className={tableStyles.table}>
        <Table
          rowKey={(row) => row.slug}
          columns={columns}
          dataSource={rows}
          pagination={false}
          size="small"
        />
      </div>
    </div>
  );
}
