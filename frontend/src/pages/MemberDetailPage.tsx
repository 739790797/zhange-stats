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
import { useParams } from "react-router-dom";
import { fetchMemberPlayStats } from "@/api/client";
import { formatDuration } from "@/api/types";
import { PageHeader } from "@/components/PageHeader";
import { formatBeijing } from "@/lib/time";

export default function MemberDetailPage() {
  const { id } = useParams();
  const memberId = Number(id);

  const { data, isLoading } = useQuery({
    queryKey: ["member-play", memberId],
    queryFn: () => fetchMemberPlayStats(memberId),
    enabled: Number.isFinite(memberId),
  });

  const maxSeconds = Math.max(
    1,
    ...(data?.trend.map((t) => t.total_seconds) ?? [1]),
  );

  return (
    <div>
      <PageHeader
        title={data?.member.nickname ?? "成员详情"}
        subtitle="Steam 游玩统计"
        extra={
          data ? (
            <Avatar size={56} src={data.member.avatar_url || undefined}>
              {data.member.nickname[0]}
            </Avatar>
          ) : null
        }
      />

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={8}>
          <Card>
            <Statistic
              title="本周"
              value={formatDuration(data?.week_play_seconds ?? 0)}
              loading={isLoading}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8}>
          <Card>
            <Statistic
              title="本月"
              value={formatDuration(data?.month_play_seconds ?? 0)}
              loading={isLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="会话数（近期）"
              value={data?.session_count ?? 0}
              loading={isLoading}
            />
          </Card>
        </Col>
      </Row>

      {!data?.member.steam_id ? (
        <Typography.Paragraph type="secondary" style={{ marginBottom: 24 }}>
          该成员尚未绑定 Steam ID
        </Typography.Paragraph>
      ) : null}

      <Typography.Title level={5}>近两周游玩时长</Typography.Title>
      {data?.trend?.some((t) => t.total_seconds > 0) ? (
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
              <Typography.Text style={{ width: 100 }}>
                {point.date}
              </Typography.Text>
              <div style={{ flex: 1 }}>
                <Progress
                  percent={Math.round((point.total_seconds / maxSeconds) * 100)}
                  strokeColor="#1a2332"
                  format={() =>
                    `${formatDuration(point.total_seconds)} / ${point.session_count} 次`
                  }
                />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <Empty
          style={{ marginBottom: 32 }}
          description="近两周暂无游玩记录"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      )}

      <Typography.Title level={5}>近期会话</Typography.Title>
      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data?.recent_sessions ?? []}
        pagination={{ pageSize: 10 }}
        locale={{ emptyText: <Empty description="暂无会话" /> }}
        columns={[
          {
            title: "开始",
            dataIndex: "started_at",
            render: (v: string) => formatBeijing(v, "YYYY-MM-DD HH:mm"),
          },
          { title: "游戏", dataIndex: "game_name" },
          {
            title: "时长",
            dataIndex: "duration_seconds",
            render: (v: number) => formatDuration(v),
          },
          {
            title: "状态",
            dataIndex: "is_ongoing",
            render: (v: boolean) =>
              v ? <Tag color="green">进行中</Tag> : <Tag>已结束</Tag>,
          },
        ]}
      />
    </div>
  );
}
