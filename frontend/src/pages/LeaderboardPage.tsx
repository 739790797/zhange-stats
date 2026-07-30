import { useQuery } from "@tanstack/react-query";
import { Progress, Select, Space, Table } from "antd";
import { useState } from "react";
import { Link } from "react-router-dom";
import { fetchGames, fetchLeaderboard } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";

export default function LeaderboardPage() {
  const [gameId, setGameId] = useState<number | undefined>();
  const [range, setRange] = useState<string>("all");

  const { data: games } = useQuery({
    queryKey: ["games"],
    queryFn: fetchGames,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["leaderboard", gameId, range],
    queryFn: () =>
      fetchLeaderboard({
        game_id: gameId,
        range,
      }),
  });

  return (
    <div>
      <PageHeader title="排行榜" subtitle="按游戏与时间范围对比" />
      <Space style={{ marginBottom: 16 }} wrap>
        <Select
          allowClear
          placeholder="全部游戏"
          style={{ width: 200 }}
          value={gameId}
          onChange={(v) => setGameId(v)}
          options={(games ?? []).map((g) => ({ value: g.id, label: g.name }))}
        />
        <Select
          style={{ width: 140 }}
          value={range}
          onChange={setRange}
          options={[
            { value: "week", label: "近一周" },
            { value: "month", label: "近一月" },
            { value: "all", label: "全部" },
          ]}
        />
      </Space>
      <Table
        rowKey="member_id"
        loading={isLoading}
        dataSource={data?.items ?? []}
        columns={[
          { title: "排名", dataIndex: "rank", width: 80 },
          {
            title: "成员",
            dataIndex: "member_nickname",
            render: (name: string, row) => (
              <Link to={`/members/${row.member_id}`}>{name}</Link>
            ),
          },
          { title: "胜", dataIndex: "wins", width: 70 },
          { title: "负", dataIndex: "losses", width: 70 },
          { title: "平", dataIndex: "draws", width: 70 },
          { title: "场次", dataIndex: "total", width: 80 },
          {
            title: "胜率",
            dataIndex: "win_rate",
            render: (v: number) => (
              <div style={{ minWidth: 140 }}>
                <Progress
                  percent={v}
                  size="small"
                  strokeColor="#2f6f4e"
                  format={(p) => `${p}%`}
                />
              </div>
            ),
          },
        ]}
      />
    </div>
  );
}
