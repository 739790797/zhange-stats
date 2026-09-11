import { ReloadOutlined } from "@ant-design/icons";
import { Bar, DualAxes } from "@ant-design/plots";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Col, Radio, Row, Space, Statistic, Typography, theme } from "antd";
import { useMemo, useState } from "react";
import { fetchRumSummary } from "@/api/rumApi";
import { PageHeader } from "@/components/PageHeader";
import { apiError } from "@/lib/apiError";
import { formatRumMs } from "@/lib/rumCollect";
import {
  rumBarHeight,
  rumBarPoints,
  rumTrendPoints,
} from "@/lib/rumCharts";

/* DualAxes 用 children 配双轴，不是 React 子节点 */
/* oxlint-disable react/no-children-prop */

const HOUR_OPTIONS = [
  { value: 1, label: "1 小时" },
  { value: 6, label: "6 小时" },
  { value: 24, label: "24 小时" },
  { value: 168, label: "7 天" },
  { value: 336, label: "14 天" },
];

function formatAxisTick(ms: number, hours: number) {
  const d = new Date(ms);
  const fmt = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const parts = Object.fromEntries(
    fmt.formatToParts(d).map((p) => [p.type, p.value]),
  );
  const clock = `${parts.hour}:${parts.minute}`;
  if (hours <= 24) return clock;
  return `${parts.month}-${parts.day} ${clock}`;
}

export default function RumPage() {
  const { token } = theme.useToken();
  const [hours, setHours] = useState(24);
  const query = useQuery({
    queryKey: ["rum-summary", hours],
    queryFn: () => fetchRumSummary(hours),
  });
  const data = query.data;
  const trend = useMemo(() => rumTrendPoints(data?.series), [data?.series]);
  const apiBars = useMemo(() => rumBarPoints(data?.api), [data?.api]);
  const imgBars = useMemo(() => rumBarPoints(data?.img), [data?.img]);
  const hasTrend = trend.some((p) => p.count > 0);
  const xMin = trend[0]?.t;
  const xMax = trend[trend.length - 1]?.t;
  const apiBarRows = Math.round(apiBars.length / 2);
  const imgBarRows = Math.round(imgBars.length / 2);

  return (
    <div>
      <PageHeader
        title="用户等待"
        subtitle="浏览器实测：接口转圈与第三方图加载（含网络/CDN）。访客也会上报。"
        extra={
          <Space wrap>
            <Radio.Group
              size="small"
              optionType="button"
              value={hours}
              onChange={(e) => setHours(Number(e.target.value))}
              options={HOUR_OPTIONS}
            />
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={() => query.refetch()}
              loading={query.isFetching}
            >
              刷新
            </Button>
          </Space>
        }
      />
      {query.error ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message={apiError(query.error, "加载失败")}
        />
      ) : null}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} md={6}>
          <Card size="small">
            <Statistic
              title="接口次数"
              loading={query.isLoading}
              value={data?.api_count ?? 0}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card size="small">
            <Statistic
              title="接口 p95"
              loading={query.isLoading}
              value={data?.api_p95_ms ?? 0}
              formatter={() => formatRumMs(data?.api_p95_ms)}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card size="small">
            <Statistic
              title="第三方图次数"
              loading={query.isLoading}
              value={data?.img_count ?? 0}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card size="small">
            <Statistic
              title="第三方图 p95"
              loading={query.isLoading}
              value={data?.img_p95_ms ?? 0}
              formatter={() => formatRumMs(data?.img_p95_ms)}
            />
          </Card>
        </Col>
      </Row>
      <Card size="small" title="等待趋势" style={{ marginBottom: 16 }}>
        {hasTrend ? (
          <DualAxes
            height={280}
            autoFit
            data={trend}
            xField="t"
            scale={{
              x: {
                type: "linear",
                domainMin: xMin,
                domainMax: xMax,
                tickCount: 6,
                nice: false,
              },
              color: {
                relations: [
                  ["接口", token.colorPrimary],
                  ["第三方图", token.colorWarning],
                ],
              },
            }}
            axis={{
              x: {
                title: false,
                labelFormatter: (value: number) =>
                  formatAxisTick(Number(value), hours),
              },
            }}
            tooltip={{
              title: (d: { t?: number }) =>
                formatAxisTick(Number(d?.t), hours),
            }}
            children={[
              {
                type: "interval",
                yField: "count",
                colorField: "series",
                stack: true,
                scale: {
                  y: { domainMin: 0, independent: true, nice: true },
                },
                axis: { y: { title: "次数", position: "left" } },
                style: { fillOpacity: 0.35 },
                tooltip: {
                  items: [{ field: "count", name: "次数" }],
                },
              },
              {
                type: "line",
                yField: "p95",
                colorField: "series",
                shapeField: "smooth",
                scale: {
                  y: { domainMin: 0, independent: true, nice: true },
                },
                axis: {
                  y: {
                    title: "p95",
                    position: "right",
                    labelFormatter: (v: number) => formatRumMs(v),
                  },
                },
                style: { lineWidth: 2 },
                tooltip: {
                  items: [
                    {
                      field: "p95",
                      name: "p95",
                      valueFormatter: (v: number) => formatRumMs(v),
                    },
                  ],
                },
              },
            ]}
          />
        ) : (
          <Typography.Text type="secondary">
            {query.isLoading ? "加载中…" : "该时间段暂无样本"}
          </Typography.Text>
        )}
      </Card>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card size="small" title="最慢接口（p50 / p95）">
            {apiBars.length ? (
              <Bar
                data={apiBars}
                height={rumBarHeight(apiBarRows)}
                autoFit
                xField="label"
                yField="ms"
                colorField="metric"
                group
                legend={{ color: {} }}
                scale={{
                  color: {
                    relations: [
                      ["p50", token.colorPrimary],
                      ["p95", token.colorWarning],
                    ],
                  },
                }}
                axis={{
                  x: { title: false },
                  y: {
                    title: false,
                    labelFormatter: (v: number) => formatRumMs(v),
                  },
                }}
                tooltip={{
                  items: [
                    {
                      field: "ms",
                      valueFormatter: (v: number) => formatRumMs(v),
                    },
                  ],
                }}
              />
            ) : (
              <Typography.Text type="secondary">
                {query.isLoading ? "加载中…" : "暂无接口样本"}
              </Typography.Text>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card size="small" title="最慢第三方图（p50 / p95）">
            {imgBars.length ? (
              <Bar
                data={imgBars}
                height={rumBarHeight(imgBarRows)}
                autoFit
                xField="label"
                yField="ms"
                colorField="metric"
                group
                legend={{ color: {} }}
                scale={{
                  color: {
                    relations: [
                      ["p50", token.colorPrimary],
                      ["p95", token.colorWarning],
                    ],
                  },
                }}
                axis={{
                  x: { title: false },
                  y: {
                    title: false,
                    labelFormatter: (v: number) => formatRumMs(v),
                  },
                }}
                tooltip={{
                  items: [
                    {
                      field: "ms",
                      valueFormatter: (v: number) => formatRumMs(v),
                    },
                  ],
                }}
              />
            ) : (
              <Typography.Text type="secondary">
                {query.isLoading ? "加载中…" : "暂无第三方图样本"}
              </Typography.Text>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
