import { useQuery } from "@tanstack/react-query";
import {
  Avatar,
  Card,
  Col,
  Empty,
  Progress,
  Row,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import dayjs from "dayjs";
import { useParams } from "react-router-dom";
import { fetchMemberStats } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";

const resultLabel: Record<string, string> = {
  win: "胜",
  lose: "负",
  draw: "平",
  unknown: "未知",
};

export default function MemberDetailPage() {
  const { id } = useParams();
  const memberId = Number(id);

  const { data, isLoading } = useQuery({
    queryKey: ["member-stats", memberId],
    queryFn: () => fetchMemberStats(memberId),
    enabled: Number.isFinite(memberId),
  });

  const maxTotal = Math.max(1, ...(data?.trend.map((t) => t.total) ?? [1]));

  return (
    <div>
      <PageHeader
        title={data?.member.nickname ?? "个人主页"}
        subtitle="历史战绩与近两周趋势"
        extra={
          data ? (
            <Avatar size={56} src={data.member.avatar_url || undefined}>
              {data.member.nickname[0]}
            </Avatar>
          ) : null
        }
      />

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic title="场次" value={data?.total_matches ?? 0} loading={isLoading} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic title="胜" value={data?.wins ?? 0} loading={isLoading} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic title="负" value={data?.losses ?? 0} loading={isLoading} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card>
            <Statistic
              title="胜率"
              value={data?.win_rate ?? 0}
              suffix="%"
              loading={isLoading}
            />
          </Card>
        </Col>
      </Row>

      <Typography.Title level={5}>近两周场次趋势</Typography.Title>
      {data?.trend?.length ? (
        <div style={{ marginBottom: 32 }}>
          {data.trend.map((point) => (
            <div
              key={point.date}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                marginBottom: 8,
              }}
            >
              <Typography.Text style={{ width: 100 }}>{point.date}</Typography.Text>
              <div style={{ flex: 1 }}>
                <Progress
                  percent={Math.round((point.total / maxTotal) * 100)}
                  strokeColor="#1a2332"
                  format={() => `${point.total} 场 / 胜率 ${point.win_rate}%`}
                />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <Empty
          style={{ marginBottom: 32 }}
          description="近两周暂无战绩"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      )}

      <Typography.Title level={5}>历史战绩</Typography.Title>
      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data?.recent_records ?? []}
        pagination={{ pageSize: 10 }}
        columns={[
          {
            title: "时间",
            dataIndex: "played_at",
            render: (v: string) => dayjs(v).format("YYYY-MM-DD HH:mm"),
          },
          { title: "游戏", dataIndex: "game_name" },
          { title: "模式", dataIndex: "mode", render: (v) => v || "-" },
          {
            title: "结果",
            dataIndex: "result",
            render: (v: string) => <Tag>{resultLabel[v] || v}</Tag>,
          },
        ]}
      />
    </div>
  );
}
