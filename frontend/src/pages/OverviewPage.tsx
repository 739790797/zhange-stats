import { useQuery } from "@tanstack/react-query";
import { Card, Col, Empty, Row, Statistic, Table, Tag, Typography } from "antd";
import dayjs from "dayjs";
import { fetchOverview } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";

const resultColor: Record<string, string> = {
  win: "success",
  lose: "error",
  draw: "warning",
  unknown: "default",
};

const resultLabel: Record<string, string> = {
  win: "胜",
  lose: "负",
  draw: "平",
  unknown: "未知",
};

export default function OverviewPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["overview"],
    queryFn: fetchOverview,
  });

  return (
    <div>
      <PageHeader title="总览看板" subtitle="最近战绩 · 本周之星 · 胜率概览" />

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="总场次"
              value={data?.win_rate.total_matches ?? 0}
              loading={isLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="总胜率"
              value={data?.win_rate.win_rate ?? 0}
              suffix="%"
              loading={isLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="本周之星"
              value={data?.week_star?.member_nickname ?? "暂无"}
              loading={isLoading}
            />
            {data?.week_star ? (
              <Typography.Text type="secondary">
                {data.week_star.wins} 胜 / {data.week_star.total} 场 · 胜率{" "}
                {data.week_star.win_rate}%
              </Typography.Text>
            ) : null}
          </Card>
        </Col>
      </Row>

      <Typography.Title level={5}>最近战绩</Typography.Title>
      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data?.recent_records ?? []}
        pagination={false}
        locale={{ emptyText: <Empty description="还没有战绩，去录入一条吧" /> }}
        columns={[
          {
            title: "时间",
            dataIndex: "played_at",
            render: (v: string) => dayjs(v).format("YYYY-MM-DD HH:mm"),
          },
          { title: "成员", dataIndex: "member_nickname" },
          { title: "游戏", dataIndex: "game_name" },
          { title: "模式", dataIndex: "mode", render: (v) => v || "-" },
          {
            title: "结果",
            dataIndex: "result",
            render: (v: string) => (
              <Tag color={resultColor[v] || "default"}>
                {resultLabel[v] || v}
              </Tag>
            ),
          },
        ]}
      />
    </div>
  );
}
