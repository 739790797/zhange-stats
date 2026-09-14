import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, Modal, Select, Table } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import { TarkovGuideItemCell } from "@/components/guides/tarkov/TarkovGuideItemCell";
import { formatMoney } from "@/lib/tarkovItemFormat";
import {
  aggregateHideoutUpgradeRanges,
  defaultHideoutCalcRange,
  formatHideoutUpgradeStation,
  hideoutCatalogMinLevel,
  hideoutItemNeedsFleaBuy,
  hideoutLevelChoices,
  hideoutMaxLevel,
  hideoutUpgradeFleaCost,
  hideoutUpgradeItemKey,
  hideoutUpgradeMaterialItems,
  isHideoutMoneyItem,
  type HideoutStationSpec,
  type HideoutUpgradeItemNeed,
} from "@/lib/tarkovHideoutProgress";
import tableStyles from "./TarkovDarkTable.module.css";
import styles from "./TarkovHideoutCalcModal.module.css";

type CalcRow = {
  key: string;
  stationId: string;
  from: number;
  to: number;
};

let nextRowKey = 1;

function newRow(): CalcRow {
  nextRowKey += 1;
  return { key: `r${nextRowKey}`, stationId: "", from: 0, to: 1 };
}

export function TarkovHideoutCalcModal({
  open,
  stations,
  onCancel,
}: {
  open: boolean;
  stations: HideoutStationSpec[];
  onCancel: () => void;
}) {
  const [rows, setRows] = useState<CalcRow[]>(() => [newRow()]);
  useEffect(() => {
    if (!open) return;
    setRows((prev) => (prev.length ? prev : [newRow()]));
  }, [open]);
  const used = useMemo(
    () => new Set(rows.map((row) => row.stationId).filter(Boolean)),
    [rows],
  );
  const canAdd = stations.some((station) => {
    const ident = (station.id || "").trim();
    return ident && !used.has(ident);
  });
  const ranges = useMemo(
    () =>
      rows
        .filter((row) => row.stationId)
        .map((row) => ({
          stationId: row.stationId,
          from: row.from,
          to: row.to,
        })),
    [rows],
  );
  const items = useMemo(
    () => aggregateHideoutUpgradeRanges(stations, ranges),
    [stations, ranges],
  );
  const materials = useMemo(() => hideoutUpgradeMaterialItems(items), [items]);
  const fleaCost = hideoutUpgradeFleaCost(items);

  const updateRow = (key: string, patch: Partial<CalcRow>) => {
    setRows((prev) =>
      prev.map((row) => (row.key === key ? { ...row, ...patch } : row)),
    );
  };

  const pickStation = (key: string, stationId: string) => {
    const station = stations.find((row) => row.id === stationId);
    updateRow(key, { stationId, ...defaultHideoutCalcRange(station) });
  };

  const setBound = (row: CalcRow, field: "from" | "to", value: number) => {
    const station = stations.find((item) => item.id === row.stationId);
    const low = hideoutCatalogMinLevel(station);
    const high = Math.max(hideoutMaxLevel(station), low);
    let from = field === "from" ? value : row.from;
    let to = field === "to" ? value : row.to;
    from = Math.min(Math.max(from, low), high);
    to = Math.min(Math.max(to, low), high);
    if (field === "from" && to <= from) to = Math.min(from + 1, high);
    if (field === "to" && to <= from) from = Math.max(to - 1, low);
    updateRow(row.key, { from, to });
  };

  const columns: ColumnsType<HideoutUpgradeItemNeed> = [
    {
      title: "材料",
      key: "item",
      render: (_: unknown, row) => (
        <TarkovGuideItemCell item={row} showCount={false} />
      ),
    },
    {
      title: "数量",
      dataIndex: "count",
      width: 72,
      align: "right",
      render: (count: number, row) => (
        <span className={styles.needCount}>
          {isHideoutMoneyItem(row) ? formatMoney(count) : count}
        </span>
      ),
    },
    {
      title: "跳蚤",
      key: "flea",
      width: 112,
      align: "right",
      render: (_: unknown, row) =>
        hideoutItemNeedsFleaBuy(row) ? formatMoney(row.flea_price) : "—",
    },
    {
      title: "小计",
      key: "subtotal",
      width: 120,
      align: "right",
      render: (_: unknown, row) => {
        if (isHideoutMoneyItem(row)) return formatMoney(row.count);
        if (!hideoutItemNeedsFleaBuy(row)) return "—";
        const price = row.flea_price;
        if (price == null || !Number.isFinite(price) || price <= 0) return "—";
        return formatMoney(price * Number(row.count || 1));
      },
    },
    {
      title: "设施",
      key: "stations",
      render: (_: unknown, row) => (
        <span className={styles.needStations}>
          {row.stations.map((station) => (
            <span key={`${station.id}-${station.from}-${station.to}`}>
              {formatHideoutUpgradeStation(station)}
            </span>
          ))}
        </span>
      ),
    },
  ];

  return (
    <Modal
      title="升级材料计算"
      open={open}
      onCancel={onCancel}
      footer={null}
      width="min(760px, calc(100vw - 24px))"
      className={styles.modal}
      classNames={{ body: styles.body, content: styles.content }}
    >
      <div className={styles.rows}>
        {rows.map((row) => {
            const station = stations.find((item) => item.id === row.stationId);
            const choices = hideoutLevelChoices(station);
            return (
              <div key={row.key} className={styles.row}>
                <Select
                  className={styles.station}
                  showSearch
                  allowClear
                  placeholder="选择设施"
                  optionFilterProp="label"
                  value={row.stationId || undefined}
                  listHeight={320}
                  popupMatchSelectWidth
                  onChange={(value) => {
                    if (!value) updateRow(row.key, { stationId: "" });
                    else pickStation(row.key, value);
                  }}
                  getPopupContainer={() => document.body}
                  options={stations
                    .filter((item) => {
                      const ident = (item.id || "").trim();
                      if (!ident) return false;
                      return ident === row.stationId || !used.has(ident);
                    })
                    .map((item) => ({
                      value: item.id,
                      label: item.name || item.slug || item.id,
                    }))}
                  optionRender={(option) => {
                    const picked = stations.find((item) => item.id === option.value);
                    return (
                      <span className={styles.option}>
                        {picked?.image_link ? (
                          <img src={picked.image_link} alt="" />
                        ) : null}
                        {option.label}
                      </span>
                    );
                  }}
                />
                <span className={styles.bound}>
                  从
                  <Select
                    className={styles.level}
                    disabled={!row.stationId}
                    value={row.stationId ? row.from : undefined}
                    placeholder="N"
                    getPopupContainer={() => document.body}
                    onChange={(value) => setBound(row, "from", Number(value))}
                    options={choices.map((level) => ({
                      value: level,
                      label: `Lv.${level}`,
                    }))}
                  />
                  升到
                  <Select
                    className={styles.level}
                    disabled={!row.stationId}
                    value={row.stationId ? row.to : undefined}
                    placeholder="M"
                    getPopupContainer={() => document.body}
                    onChange={(value) => setBound(row, "to", Number(value))}
                    options={choices.map((level) => ({
                      value: level,
                      label: `Lv.${level}`,
                    }))}
                  />
                </span>
                <Button
                  type="text"
                  size="small"
                  icon={<DeleteOutlined />}
                  aria-label="移除"
                  onClick={() =>
                    setRows((prev) => prev.filter((item) => item.key !== row.key))
                  }
                />
              </div>
            );
        })}
        {canAdd ? (
          <div className={styles.addWrap}>
            <Button
              type="dashed"
              block
              className={styles.plusSm}
              icon={<PlusOutlined />}
              aria-label="添加设施"
              onClick={() => setRows((prev) => [...prev, newRow()])}
            />
          </div>
        ) : null}
      </div>

      {ranges.length ? (
        <div className={styles.needs}>
          <h4 className={styles.needTitle}>
            合计材料
            <span className={styles.needMeta}>
              {materials.length
                ? ` · ${materials.length} 种${
                    fleaCost != null
                      ? ` · 跳蚤合计 ${formatMoney(fleaCost)}`
                      : " · 部分无跳蚤价"
                  }`
                : " · 该区间无额外材料"}
            </span>
          </h4>
          {materials.length ? (
            <div className={tableStyles.table}>
              <Table<HideoutUpgradeItemNeed>
                rowKey={(row) => hideoutUpgradeItemKey(row) || row.id}
                columns={columns}
                dataSource={materials}
                pagination={false}
                size="small"
              />
            </div>
          ) : null}
        </div>
      ) : null}
    </Modal>
  );
}
