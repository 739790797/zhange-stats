import { useQuery } from "@tanstack/react-query";
import { Card, Col, Empty, Row, Statistic, Table, Tag, Typography } from "antd";
import dayjs from "dayjs";
import { Link } from "react-router-dom";
import { fetchSteamOverview } from "@/api/client";
import { formatDuration } from "@/api/types";
import { PageHeader } from "@/components/PageHeader";

export default function OverviewPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["steam-overview"],
    queryFn: fetchSteamOverview,
    refetchInterval: 60_000,
  });

  return (
    <div>
      <PageHeader title="总览" subtitle="圈子 Steam 游玩概况" />

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="成员数"
              value={data?.member_count ?? 0}
              loading={isLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="已绑 Steam"
              value={data?.steam_bound_count ?? 0}
              loading={isLoading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="本周游玩"
              value={formatDuration(data?.week_play_seconds ?? 0)}
              loading={isLoading}
            />
          </Card>
        </Col>
      </Row>

      <Typography.Title level={5}>正在游玩</Typography.Title>
      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data?.now_playing ?? []}
        pagination={false}
        style={{ marginBottom: 24 }}
        locale={{ emptyText: <Empty description="当前无人在线游玩" /> }}
        columns={[
          {
            title: "成员",
            dataIndex: "member_nickname",
            render: (name: string, row) => (
              <Link to={`/members/${row.member_id}`}>{name}</Link>
            ),
          },
          { title: "游戏", dataIndex: "game_name" },
          {
            title: "已玩",
            dataIndex: "duration_seconds",
            render: (v: number) => formatDuration(v),
          },
        ]}
      />

      <Typography.Title level={5}>近期会话</Typography.Title>
      <Table
        rowKey="id"
        loading={isLoading}
        dataSource={data?.recent_sessions ?? []}
        pagination={false}
        locale={{ emptyText: <Empty description="暂无游玩记录" /> }}
        columns={[
          {
            title: "开始",
            dataIndex: "started_at",
            render: (v: string) => dayjs(v).format("MM-DD HH:mm"),
          },
          {
            title: "成员",
            dataIndex: "member_nickname",
            render: (name: string, row) => (
              <Link to={`/members/${row.member_id}`}>{name}</Link>
            ),
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
