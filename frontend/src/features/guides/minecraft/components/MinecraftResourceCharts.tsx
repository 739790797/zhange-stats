import { Area } from "@ant-design/plots";
import { Card, Col, Row, Typography } from "antd";
import { useMemo } from "react";
import { formatBytes } from "./minecraftUi";
import type { ConsoleHistoryPoint } from "./useMinecraftConsole";

type Props = {
  history: ConsoleHistoryPoint[];
  cpu: number;
  cpuLimit: number;
  memory: number;
  memoryLimit: number;
  rxTotal: number;
  txTotal: number;
};

type Point = {
  i: number;
  clock: string;
  v: number;
};

function clockOf(t: number) {
  return new Date(t).toLocaleTimeString("zh-CN", { hour12: false });
}

function niceMax(value: number, floor = 1) {
  if (!Number.isFinite(value) || value <= 0) return floor;
  const padded = Math.max(value * 1.12, floor);
  const mag = 10 ** Math.floor(Math.log10(padded));
  return Math.ceil(padded / mag) * mag;
}

function cpuDomain(dataMax: number, limit: number) {
  if (limit > 0) return Math.max(limit, dataMax);
  if (dataMax <= 100) return 100;
  return niceMax(dataMax);
}

function memDomainGb(dataMax: number, limitGb: number) {
  if (limitGb > 0) return Math.max(limitGb, dataMax);
  return niceMax(Math.max(dataMax, 1), 1);
}

function fmtCpu(v: number) {
  return `${Number(v).toFixed(1)}%`;
}

function fmtGb(v: number) {
  return `${Number(v).toFixed(2)} GB`;
}

function fmtRate(v: number) {
  const n = Number(v);
  if (!Number.isFinite(n) || n <= 0) return "0";
  return `${formatBytes(n)}/s`;
}

function tooltipClock(d: Point | Point[] | undefined) {
  const row = Array.isArray(d) ? d[0] : d;
  return row?.clock || "";
}

function Spark({
  data,
  color,
  name,
  yMax,
  formatValue,
  yNice,
  height = 168,
}: {
  data: Point[];
  color: string;
  name: string;
  yMax: number;
  formatValue: (v: number) => string;
  yNice?: (v: number) => string;
  height?: number;
}) {
  return (
    <Area
      data={data}
      xField="i"
      yField="v"
      height={height}
      autoFit
      legend={false}
      stack={false}
      shapeField="smooth"
      scale={{
        y: { domainMin: 0, domainMax: Math.max(yMax, 0.001), nice: false },
      }}
      axis={{
        x: false,
        y: {
          labelFormatter: (v: number) => (yNice ? yNice(v) : formatValue(v)),
          title: false,
        },
      }}
      tooltip={{
        title: tooltipClock,
        items: [
          {
            field: "v",
            name,
            valueFormatter: (v: number) => formatValue(Number(v)),
          },
        ],
      }}
      style={{
        fill: color,
        fillOpacity: 0.18,
        stroke: color,
        lineWidth: 2,
      }}
    />
  );
}

function NetSpark({
  label,
  color,
  data,
  current,
}: {
  label: string;
  color: string;
  data: Point[];
  current: number;
}) {
  const yMax = useMemo(
    () => niceMax(Math.max(0, ...data.map((p) => p.v)), 1024),
    [data],
  );
  return (
    <div style={{ marginBottom: 4 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          marginBottom: 2,
        }}
      >
        <Typography.Text style={{ fontSize: 12 }}>{label}</Typography.Text>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {fmtRate(current)}
        </Typography.Text>
      </div>
      {data.length ? (
        <Spark
          data={data}
          color={color}
          name={label}
          yMax={yMax}
          formatValue={fmtRate}
          height={68}
        />
      ) : null}
    </div>
  );
}

export function MinecraftResourceCharts({
  history,
  cpu,
  cpuLimit,
  memory,
  memoryLimit,
  rxTotal,
  txTotal,
}: Props) {
  const cpuData = useMemo<Point[]>(
    () =>
      history.map((p, i) => ({
        i,
        clock: clockOf(p.t),
        v: p.cpu,
      })),
    [history],
  );
  const memData = useMemo<Point[]>(
    () =>
      history.map((p, i) => ({
        i,
        clock: clockOf(p.t),
        v: p.memory / 1024 ** 3,
      })),
    [history],
  );
  const rxData = useMemo<Point[]>(
    () =>
      history.map((p, i) => ({
        i,
        clock: clockOf(p.t),
        v: p.rx,
      })),
    [history],
  );
  const txData = useMemo<Point[]>(
    () =>
      history.map((p, i) => ({
        i,
        clock: clockOf(p.t),
        v: p.tx,
      })),
    [history],
  );

  const cpuMax = cpuDomain(
    Math.max(cpu, ...cpuData.map((p) => p.v), 0),
    cpuLimit,
  );
  const memGb = memory / 1024 ** 3;
  const memLimitGb = memoryLimit > 0 ? memoryLimit / 1024 ** 3 : 0;
  const memMax = memDomainGb(
    Math.max(memGb, ...memData.map((p) => p.v), 0),
    memLimitGb,
  );
  const lastRx = rxData[rxData.length - 1]?.v ?? 0;
  const lastTx = txData[txData.length - 1]?.v ?? 0;

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} md={8}>
        <Card
          size="small"
          title="CPU"
          extra={
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {fmtCpu(cpu)}
              {cpuLimit > 0 ? ` / ${cpuLimit}%` : ""}
            </Typography.Text>
          }
        >
          {cpuData.length ? (
            <Spark
              data={cpuData}
              color="#1677ff"
              name="CPU"
              yMax={cpuMax}
              formatValue={fmtCpu}
              yNice={(v) => `${Math.round(v)}%`}
            />
          ) : (
            <Typography.Text type="secondary">等待统计…</Typography.Text>
          )}
        </Card>
      </Col>
      <Col xs={24} md={8}>
        <Card
          size="small"
          title="内存"
          extra={
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {fmtGb(memGb)} / {memLimitGb > 0 ? fmtGb(memLimitGb) : "∞"}
            </Typography.Text>
          }
        >
          {memData.length ? (
            <Spark
              data={memData}
              color="#1677ff"
              name="内存"
              yMax={memMax}
              formatValue={fmtGb}
              yNice={(v) => Number(v).toFixed(1)}
            />
          ) : (
            <Typography.Text type="secondary">等待统计…</Typography.Text>
          )}
        </Card>
      </Col>
      <Col xs={24} md={8}>
        <Card
          size="small"
          title="网络"
          extra={
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              ↓ {formatBytes(rxTotal)}　↑ {formatBytes(txTotal)}
            </Typography.Text>
          }
        >
          {history.length ? (
            <>
              <NetSpark
                label="入站"
                color="#1677ff"
                data={rxData}
                current={lastRx}
              />
              <NetSpark
                label="出站"
                color="#52c41a"
                data={txData}
                current={lastTx}
              />
            </>
          ) : (
            <Typography.Text type="secondary">等待统计…</Typography.Text>
          )}
        </Card>
      </Col>
    </Row>
  );
}
