import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Avatar,
  Button,
  Empty,
  List,
  Radio,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import dayjs from "dayjs";
import { useMemo, useState } from "react";
import {
  fetchSteamCalendar,
  fetchSteamDay,
  fetchSteamNow,
  triggerSteamPoll,
} from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { useAuthStore } from "@/stores/authStore";

type Granularity = "day" | "week" | "month" | "year";

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}秒`;
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}分钟`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return rm ? `${h}小时${rm}分` : `${h}小时`;
}

function heatColor(seconds: number, maxSeconds: number): string {
  if (seconds <= 0 || maxSeconds <= 0) return "#f0f2f5";
  const t = Math.min(1, seconds / maxSeconds);
  // 深绿热力
  const alpha = 0.15 + t * 0.85;
  return `rgba(47, 111, 78, ${alpha.toFixed(3)})`;
}

export default function SteamCalendarPage() {
  const queryClient = useQueryClient();
  const isAdmin = useAuthStore((s) => s.user?.is_admin);
  const [granularity, setGranularity] = useState<Granularity>("month");
  const [anchor, setAnchor] = useState(dayjs());
  const [selectedDate, setSelectedDate] = useState(dayjs().format("YYYY-MM-DD"));

  const dateParam = anchor.format("YYYY-MM-DD");

  const { data: calendar, isLoading: calLoading } = useQuery({
    queryKey: ["steam-calendar", granularity, dateParam],
    queryFn: () =>
      fetchSteamCalendar({ granularity, date: dateParam }),
  });

  const { data: dayData, isLoading: dayLoading } = useQuery({
    queryKey: ["steam-day", selectedDate],
    queryFn: () => fetchSteamDay(selectedDate),
  });

  const { data: nowPlaying } = useQuery({
    queryKey: ["steam-now"],
    queryFn: fetchSteamNow,
    refetchInterval: 60_000,
  });

  const poll = useMutation({
    mutationFn: triggerSteamPoll,
    onSuccess: (res) => {
      if (res.status === "ok") {
        message.success(res.message || "轮询完成");
      } else {
        message.error(res.message || "轮询失败");
      }
      queryClient.invalidateQueries({ queryKey: ["steam-calendar"] });
      queryClient.invalidateQueries({ queryKey: ["steam-day"] });
      queryClient.invalidateQueries({ queryKey: ["steam-now"] });
    },
    onError: () => message.error("轮询请求失败"),
  });

  const maxSeconds = useMemo(() => {
    if (!calendar?.cells?.length) return 0;
    return Math.max(...calendar.cells.map((c) => c.total_seconds), 0);
  }, [calendar]);

  const cellMap = useMemo(() => {
    const m = new Map<string, { total_seconds: number; session_count: number }>();
    for (const c of calendar?.cells ?? []) {
      m.set(c.date, c);
    }
    return m;
  }, [calendar]);

  const shift = (dir: -1 | 1) => {
    if (granularity === "day") setAnchor((d) => d.add(dir, "day"));
    else if (granularity === "week") setAnchor((d) => d.add(dir, "week"));
    else if (granularity === "month") setAnchor((d) => d.add(dir, "month"));
    else setAnchor((d) => d.add(dir, "year"));
  };

  const weekdays = ["一", "二", "三", "四", "五", "六", "日"];

  const gridStart = calendar?.range_start
    ? dayjs(calendar.range_start)
    : anchor.startOf("month");
  const gridEnd = calendar?.range_end
    ? dayjs(calendar.range_end)
    : anchor.endOf("month");

  // 月视图补齐周一开头空白；周/日/年直接按 cells 顺序
  const leadingPad =
    granularity === "month" ? (gridStart.day() + 6) % 7 : 0;

  const days: (string | null)[] = [];
  for (let i = 0; i < leadingPad; i++) days.push(null);
  let cursor = gridStart;
  while (cursor.isBefore(gridEnd) || cursor.isSame(gridEnd, "day")) {
    days.push(cursor.format("YYYY-MM-DD"));
    cursor = cursor.add(1, "day");
  }

  return (
    <div>
      <PageHeader
        title="Steam 日历"
        subtitle="轮询正在游玩 · 日/周/月/年热力统计"
        extra={
          isAdmin ? (
            <Button loading={poll.isPending} onClick={() => poll.mutate()}>
              立即轮询
            </Button>
          ) : null
        }
      />

      {nowPlaying && nowPlaying.length > 0 ? (
        <div style={{ marginBottom: 16 }}>
          <Typography.Text type="secondary">正在游玩</Typography.Text>
          <Space wrap style={{ display: "flex", marginTop: 8 }}>
            {nowPlaying.map((p) => (
              <Tag key={p.id} color="green">
                {p.member_nickname} · {p.game_name}（{formatDuration(p.duration_seconds)}）
              </Tag>
            ))}
          </Space>
        </div>
      ) : null}

      <Space style={{ marginBottom: 16 }} wrap>
        <Radio.Group
          value={granularity}
          onChange={(e) => {
            setGranularity(e.target.value);
          }}
          optionType="button"
          options={[
            { label: "日", value: "day" },
            { label: "周", value: "week" },
            { label: "月", value: "month" },
            { label: "年", value: "year" },
          ]}
        />
        <Button onClick={() => shift(-1)}>上一段</Button>
        <Typography.Text strong>
          {calendar
            ? `${calendar.range_start} ~ ${calendar.range_end}`
            : dateParam}
        </Typography.Text>
        <Button onClick={() => shift(1)}>下一段</Button>
        <Button
          type="link"
          onClick={() => {
            const today = dayjs();
            setAnchor(today);
            setSelectedDate(today.format("YYYY-MM-DD"));
          }}
        >
          今天
        </Button>
        <Typography.Text type="secondary">
          区间合计{" "}
          {formatDuration(calendar?.total_seconds ?? 0)}
        </Typography.Text>
      </Space>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(7, minmax(0, 1fr))",
          gap: 6,
          marginBottom: 8,
          opacity: calLoading ? 0.6 : 1,
        }}
      >
        {weekdays.map((w) => (
          <div
            key={w}
            style={{
              textAlign: "center",
              fontSize: 12,
              color: "#8c8c8c",
              padding: "4px 0",
            }}
          >
            {w}
          </div>
        ))}
        {days.map((d, idx) => {
          if (!d) {
            return <div key={`pad-${idx}`} />;
          }
          const cell = cellMap.get(d);
          const seconds = cell?.total_seconds ?? 0;
          const selected = d === selectedDate;
          return (
            <button
              key={d}
              type="button"
              onClick={() => setSelectedDate(d)}
              style={{
                border: selected ? "2px solid #1a2332" : "1px solid #e8e8e8",
                borderRadius: 6,
                minHeight: granularity === "year" ? 36 : 64,
                padding: 6,
                background: heatColor(seconds, maxSeconds),
                cursor: "pointer",
                textAlign: "left",
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 600 }}>
                {granularity === "year"
                  ? dayjs(d).format("M/D")
                  : dayjs(d).format("D")}
              </div>
              {granularity !== "year" ? (
                <div style={{ fontSize: 11, color: "#595959", marginTop: 4 }}>
                  {seconds > 0 ? formatDuration(seconds) : "—"}
                </div>
              ) : null}
            </button>
          );
        })}
      </div>

      <Typography.Title level={5} style={{ marginTop: 24 }}>
        {selectedDate} 大家玩了什么
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        当日合计 {formatDuration(dayData?.total_seconds ?? 0)}
      </Typography.Paragraph>

      {dayData?.by_member?.length ? (
        <List
          loading={dayLoading}
          dataSource={dayData.by_member}
          style={{ marginBottom: 24 }}
          renderItem={(item) => (
            <List.Item>
              <List.Item.Meta
                avatar={
                  <Avatar src={item.avatar_url || undefined}>
                    {item.member_nickname[0]}
                  </Avatar>
                }
                title={
                  <Space>
                    <span>{item.member_nickname}</span>
                    <Typography.Text type="secondary">
                      {formatDuration(item.total_seconds)}
                    </Typography.Text>
                  </Space>
                }
                description={item.games.join(" · ")}
              />
            </List.Item>
          )}
        />
      ) : (
        <Empty
          description="这一天还没有记录到 Steam 游玩"
          style={{ marginBottom: 24 }}
        />
      )}

      <Table
        rowKey="id"
        loading={dayLoading}
        dataSource={dayData?.sessions ?? []}
        pagination={{ pageSize: 10 }}
        locale={{ emptyText: "暂无会话明细" }}
        columns={[
          { title: "成员", dataIndex: "member_nickname" },
          { title: "游戏", dataIndex: "game_name" },
          {
            title: "开始",
            dataIndex: "started_at",
            render: (v: string) => dayjs(v).format("HH:mm:ss"),
          },
          {
            title: "时长",
            dataIndex: "duration_seconds",
            render: (v: number) => formatDuration(v),
          },
          {
            title: "状态",
            dataIndex: "is_ongoing",
            render: (v: boolean) =>
              v ? <Tag color="processing">进行中</Tag> : <Tag>已结束</Tag>,
          },
        ]}
      />
    </div>
  );
}
