import { DualAxes } from "@ant-design/plots";
import { Card, Radio, Tag, Typography } from "antd";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import dayjs from "dayjs";
import { fetchMinecraftPerf } from "@/api/minecraftApi";
import { apiError } from "@/lib/apiError";
import { MinecraftEntitiesCard } from "./MinecraftEntitiesCard";
import styles from "./MinecraftLivePanel.module.css";

/* DualAxes 用 children 配双轴，不是 React 子节点 */
/* oxlint-disable react/no-children-prop */

const PERF_RANGES = [
  { label: "30分钟", value: "30m" },
  { label: "1小时", value: "1h" },
  { label: "12小时", value: "12h" },
  { label: "24小时", value: "24h" },
  { label: "30天", value: "30d" },
  { label: "全部", value: "all" },
] as const;

type PerfRange = (typeof PERF_RANGES)[number]["value"];

function formatTps(n?: number | null) {
  if (n == null || !Number.isFinite(n)) return "—";
  return n.toFixed(1);
}

function formatMspt(n?: number | null) {
  if (n == null || !Number.isFinite(n)) return "—";
  return `${n.toFixed(1)} ms`;
}

function formatAxisTick(ms: number, spanMs: number) {
  const d = dayjs(ms);
  if (spanMs <= 15 * 60_000) return d.format("HH:mm:ss");
  if (spanMs <= 24 * 3600_000) return d.format("HH:mm");
  if (spanMs <= 3 * 24 * 3600_000) return d.format("MM-DD HH:mm");
  return d.format("MM-DD");
}

function formatTooltipTime(ms: number, spanMs: number) {
  const d = dayjs(ms);
  if (spanMs <= 24 * 3600_000) return d.format("HH:mm:ss");
  return d.format("YYYY-MM-DD HH:mm");
}

export function MinecraftPerfCard() {
  const [range, setRange] = useState<PerfRange>("30m");
  const query = useQuery({
    queryKey: ["minecraft-perf", range],
    queryFn: () => fetchMinecraftPerf(range),
    refetchInterval: 10_000,
    retry: 1,
    placeholderData: keepPreviousData,
  });
  const perf = query.data;
  const rangeStart = perf?.range_start ? dayjs(perf.range_start).valueOf() : 0;
  const rangeEnd = perf?.range_end ? dayjs(perf.range_end).valueOf() : 0;
  const spanMs = Math.max(0, rangeEnd - rangeStart);
  const chartData = useMemo(() => {
    return (perf?.samples || [])
      .map((row) => {
        const t = row.at ? dayjs(row.at).valueOf() : NaN;
        if (!Number.isFinite(t)) return null;
        return {
          t,
          tps: row.tps == null ? Number.NaN : row.tps,
          mspt: row.mspt == null ? Number.NaN : row.mspt,
        };
      })
      .filter((row): row is NonNullable<typeof row> => row != null);
  }, [perf]);
  const hasPoint = chartData.some(
    (row) =>
      (row.tps != null && Number.isFinite(row.tps)) ||
      (row.mspt != null && Number.isFinite(row.mspt)),
  );
  const msptMax = Math.max(
    50,
    ...chartData.map((row) => Number(row.mspt) || 0),
  );
  const xDomainMin = spanMs > 0 ? rangeStart : undefined;
  const xDomainMax = spanMs > 0 ? rangeEnd : undefined;

  return (
    <>
    <Card
      size="small"
      title="性能"
      extra={
        perf?.enabled ? (
          <Tag color={perf.connected ? "green" : "default"}>
            {perf.connected ? "RCON 已连接" : "RCON 未连接"}
          </Tag>
        ) : null
      }
    >
      <div className={styles.perfToolbar}>
        <Radio.Group
          size="small"
          optionType="button"
          value={range}
          onChange={(e) => setRange(e.target.value as PerfRange)}
          options={[...PERF_RANGES]}
        />
      </div>
      {query.isError ? (
        <Typography.Text type="secondary">
          {apiError(query.error, "无法读取性能")}
        </Typography.Text>
      ) : !perf?.enabled && !hasPoint ? (
        <Typography.Text type="secondary">
          {perf?.message || "暂无性能数据"}
        </Typography.Text>
      ) : (
        <>
          {perf?.message && !perf.ok ? (
            <Typography.Text type="secondary">{perf.message}</Typography.Text>
          ) : null}
          {hasPoint ? (
            <DualAxes
              height={240}
              autoFit
              data={chartData}
              xField="t"
              legend
              scale={{
                x: {
                  type: "linear",
                  domainMin: xDomainMin,
                  domainMax: xDomainMax,
                  tickCount: 6,
                  nice: false,
                },
              }}
              axis={{
                x: {
                  title: false,
                  labelFormatter: (value: number) =>
                    formatAxisTick(Number(value), spanMs),
                },
              }}
              tooltip={{
                title: (d: { t?: number }) =>
                  formatTooltipTime(Number(d?.t), spanMs),
              }}
              children={[
                {
                  type: "line",
                  yField: "tps",
                  shapeField: "smooth",
                  style: { stroke: "#5b8ff9", lineWidth: 2 },
                  scale: {
                    y: {
                      domainMin: 0,
                      domainMax: 20,
                      independent: true,
                      nice: false,
                    },
                  },
                  axis: { y: { title: "TPS", position: "left" } },
                  tooltip: {
                    items: [
                      {
                        field: "tps",
                        name: "TPS",
                        valueFormatter: (v: number) => formatTps(v),
                      },
                    ],
                  },
                },
                {
                  type: "line",
                  yField: "mspt",
                  shapeField: "smooth",
                  style: { stroke: "#faad14", lineWidth: 2 },
                  scale: {
                    y: {
                      domainMin: 0,
                      domainMax: msptMax,
                      independent: true,
                      nice: false,
                    },
                  },
                  axis: { y: { title: "MSPT", position: "right" } },
                  tooltip: {
                    items: [
                      {
                        field: "mspt",
                        name: "MSPT",
                        valueFormatter: (v: number) => formatMspt(v),
                      },
                    ],
                  },
                },
              ]}
            />
          ) : (
            <Typography.Text type="secondary">
              {range === "30m"
                ? "正在采集，片刻后显示折线"
                : "该时间段暂无样本"}
            </Typography.Text>
          )}
        </>
      )}
    </Card>
    <MinecraftEntitiesCard entities={perf?.entities} />
    </>
  );
}
