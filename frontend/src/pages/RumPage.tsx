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
  RUM_BIZ_ALL,
  rumBarHeight,
  rumBarPoints,
  rumBizBarPoints,
  rumBizFilterOptions,
  rumRowsForBiz,
  rumTrendDomain,
  rumTrendPoints,
  type RumBarPoint,
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

function RumP50P95Bar({
  data,
  height,
  token,
}: {
  data: RumBarPoint[];
  height: number;
  token: { colorPrimary: string; colorWarning: string };
}) {
  return (
    <Bar
      data={data}
      height={height}
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
  );
}

export default function RumPage() {
  const { token } = theme.useToken();
  const [hours, setHours] = useState(24);
  const [apiBiz, setApiBiz] = useState(RUM_BIZ_ALL);
  const [imgBiz, setImgBiz] = useState(RUM_BIZ_ALL);
  const query = useQuery({
    queryKey: ["rum-summary", hours],
    queryFn: () => fetchRumSummary(hours),
  });
  const data = query.data;
  const trend = useMemo(() => rumTrendPoints(data?.series), [data?.series]);
  const trendDomain = useMemo(() => rumTrendDomain(data?.series), [data?.series]);
  const apiBizOptions = useMemo(
    () => rumBizFilterOptions(data?.api_biz),
    [data?.api_biz],
  );
  const imgBizOptions = useMemo(
    () => rumBizFilterOptions(data?.img_biz),
    [data?.img_biz],
  );
  const activeApiBiz =
    apiBiz !== RUM_BIZ_ALL && apiBizOptions.some((item) => item.value === apiBiz)
      ? apiBiz
      : RUM_BIZ_ALL;
  const activeImgBiz =
    imgBiz !== RUM_BIZ_ALL && imgBizOptions.some((item) => item.value === imgBiz)
      ? imgBiz
      : RUM_BIZ_ALL;
  const apiRows = useMemo(
    () => rumRowsForBiz(data?.api, activeApiBiz),
    [data?.api, activeApiBiz],
  );
  const imgRows = useMemo(
    () => rumRowsForBiz(data?.img, activeImgBiz),
    [data?.img, activeImgBiz],
  );
  const apiBars = useMemo(() => rumBarPoints(apiRows), [apiRows]);
  const imgBars = useMemo(() => rumBarPoints(imgRows), [imgRows]);
  const bizBars = useMemo(() => rumBizBarPoints(data?.api_biz), [data?.api_biz]);
  const hasTrend = trend.length > 0;
  const xMin = trendDomain.min;
  const xMax = trendDomain.max;
  const apiBarRows = Math.round(apiBars.length / 2);
  const imgBarRows = Math.round(imgBars.length / 2);
  const bizBarRows = Math.round(bizBars.length / 2);
  const apiBizRadio = [
    { label: "全部", value: RUM_BIZ_ALL },
    ...apiBizOptions,
  ];
  const imgBizRadio = [
    { label: "全部", value: RUM_BIZ_ALL },
    ...imgBizOptions,
  ];

  return (
    <div>
      <PageHeader
        title="用户等待"
        subtitle="浏览器实测：接口转圈与第三方图加载（含网络/CDN）。接口按侧栏业务分类。访客也会上报。"
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
      <Card
        size="small"
        title="等待趋势"
        extra={
          hasTrend ? (
            <Space size={16}>
              <Typography.Text type="secondary">
                <span
                  style={{
                    display: "inline-block",
                    width: 8,
                    height: 8,
                    marginRight: 6,
                    borderRadius: 2,
                    background: token.colorPrimary,
                  }}
                />
                接口
              </Typography.Text>
              <Typography.Text type="secondary">
                <span
                  style={{
                    display: "inline-block",
                    width: 8,
                    height: 8,
                    marginRight: 6,
                    borderRadius: 2,
                    background: token.colorWarning,
                  }}
                />
                第三方图
              </Typography.Text>
            </Space>
          ) : null
        }
        style={{ marginBottom: 16 }}
      >
        {hasTrend ? (
          <DualAxes
            height={280}
            autoFit
            data={trend}
            xField="t"
            legend={false}
            scale={{
              x: {
                type: "linear",
                domainMin: xMin,
                domainMax: xMax,
                tickCount: 6,
                nice: false,
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
                scale: {
                  y: { domainMin: 0, independent: true, nice: true, key: "count" },
                },
                axis: { y: { title: "次数", position: "left" } },
                style: { fill: token.colorPrimary, fillOpacity: 0.35 },
                tooltip: {
                  items: [
                    { field: "api_count", name: "接口次数" },
                    { field: "img_count", name: "第三方图次数" },
                  ],
                },
              },
              {
                type: "line",
                yField: "api_p95",
                scale: {
                  y: { domainMin: 0, independent: true, nice: true, key: "p95" },
                },
                axis: {
                  y: {
                    title: "p95",
                    position: "right",
                    labelFormatter: (v: number) => formatRumMs(v),
                  },
                },
                style: { stroke: token.colorPrimary, lineWidth: 2 },
                tooltip: {
                  items: [
                    {
                      field: "api_p95",
                      name: "接口 p95",
                      valueFormatter: (v: number) => formatRumMs(v),
                    },
                  ],
                },
              },
              {
                type: "line",
                yField: "img_p95",
                scale: {
                  y: { domainMin: 0, independent: true, nice: true, key: "p95" },
                },
                axis: { y: false },
                style: { stroke: token.colorWarning, lineWidth: 2 },
                tooltip: {
                  items: [
                    {
                      field: "img_p95",
                      name: "第三方图 p95",
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
      {bizBars.length ? (
        <Card size="small" title="接口按业务（p50 / p95）" style={{ marginBottom: 16 }}>
          <RumP50P95Bar
            data={bizBars}
            height={rumBarHeight(bizBarRows)}
            token={token}
          />
        </Card>
      ) : null}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card size="small" title="最慢接口（p50 / p95）">
            {apiBizOptions.length > 1 ? (
              <Radio.Group
                size="small"
                optionType="button"
                value={activeApiBiz}
                onChange={(e) => setApiBiz(String(e.target.value))}
                options={apiBizRadio}
                style={{ marginBottom: 12, flexWrap: "wrap", rowGap: 8 }}
              />
            ) : null}
            {apiBars.length ? (
              <RumP50P95Bar
                data={apiBars}
                height={rumBarHeight(apiBarRows)}
                token={token}
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
            {imgBizOptions.length > 1 ? (
              <Radio.Group
                size="small"
                optionType="button"
                value={activeImgBiz}
                onChange={(e) => setImgBiz(String(e.target.value))}
                options={imgBizRadio}
                style={{ marginBottom: 12, flexWrap: "wrap", rowGap: 8 }}
              />
            ) : null}
            {imgBars.length ? (
              <RumP50P95Bar
                data={imgBars}
                height={rumBarHeight(imgBarRows)}
                token={token}
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
