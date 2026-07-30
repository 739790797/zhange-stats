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
  Tooltip,
  Typography,
  message,
} from "antd";
import dayjs from "dayjs";
import { useEffect, useMemo, useState } from "react";
import {
  fetchSteamCalendar,
  fetchSteamDay,
  fetchSteamNow,
  triggerSteamPoll,
} from "@/api/client";
import type { SteamTimelineRow } from "@/api/types";
import { PageHeader } from "@/components/PageHeader";
import { useAuthStore } from "@/stores/authStore";

type Granularity = "day" | "week" | "month" | "year";

const HOUR_MARKS = [0, 3, 6, 9, 12, 15, 18, 21, 24];
const GAME_PALETTE = [
  "#e67e22",
  "#8e44ad",
  "#16a085",
  "#c0392b",
  "#2980b9",
  "#d35400",
  "#27ae60",
  "#9b59b6",
  "#1abc9c",
  "#e74c3c",
  "#3498db",
  "#f39c12",
];

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
  const alpha = 0.15 + t * 0.85;
  return `rgba(47, 111, 78, ${alpha.toFixed(3)})`;
}

function hashColor(key: string): string {
  let h = 0;
  for (let i = 0; i < key.length; i++) {
    h = (h * 31 + key.charCodeAt(i)) >>> 0;
  }
  return GAME_PALETTE[h % GAME_PALETTE.length];
}

function segmentColor(
  status: string,
  appId?: string | null,
): string {
  if (status === "offline") return "#d9d9d9";
  if (status === "online") return "#5b8ff9";
  if (status === "playing") return hashColor(appId || "playing");
  return "#bfbfbf";
}

function formatClock(sec: number): string {
  const s = Math.max(0, Math.min(86400, Math.floor(sec)));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function DayTimelineChart({
  rows,
  gamesLegend,
  loading,
}: {
  rows: SteamTimelineRow[];
  gamesLegend: { steam_app_id: string; game_name: string }[];
  loading?: boolean;
}) {
  const labelWidth = 112;
  const trackHeight = 28;
  const rowGap = 10;

  if (!loading && rows.length === 0) {
    return <Empty description="暂无绑定 Steam 的成员" />;
  }

  return (
    <div style={{ opacity: loading ? 0.6 : 1 }}>
      <Space wrap style={{ marginBottom: 12 }}>
        <Tag color="#d9d9d9" style={{ color: "#595959" }}>
          离线
        </Tag>
        <Tag color="#5b8ff9">在线</Tag>
        {gamesLegend.map((g) => (
          <Tag key={g.steam_app_id} color={hashColor(g.steam_app_id)}>
            {g.game_name}
          </Tag>
        ))}
      </Space>

      {/* 时间刻度 */}
      <div
        style={{
          display: "flex",
          marginBottom: 8,
          marginLeft: labelWidth,
          position: "relative",
          height: 20,
        }}
      >
        {HOUR_MARKS.map((h) => (
          <div
            key={h}
            style={{
              position: "absolute",
              left: `${(h / 24) * 100}%`,
              transform: h === 24 ? "translateX(-100%)" : "translateX(-50%)",
              fontSize: 11,
              color: "#8c8c8c",
              whiteSpace: "nowrap",
            }}
          >
            {String(h).padStart(2, "0")}:00
          </div>
        ))}
      </div>

      <div
        style={{
          border: "1px solid #f0f0f0",
          borderRadius: 8,
          padding: "8px 0",
          background: "#fafafa",
        }}
      >
        {rows.map((row) => (
          <div
            key={row.member_id}
            style={{
              display: "flex",
              alignItems: "center",
              marginBottom: rowGap,
              padding: "0 8px",
            }}
          >
            <div
              style={{
                width: labelWidth,
                flexShrink: 0,
                display: "flex",
                alignItems: "center",
                gap: 8,
                paddingRight: 8,
              }}
            >
              <Avatar size={24} src={row.avatar_url || undefined}>
                {row.member_nickname[0]}
              </Avatar>
              <Typography.Text
                ellipsis
                style={{ maxWidth: 72, fontSize: 13 }}
                title={row.member_nickname}
              >
                {row.member_nickname}
              </Typography.Text>
            </div>
            <div
              style={{
                flex: 1,
                position: "relative",
                height: trackHeight,
                background: "#fff",
                border: "1px solid #e8e8e8",
                borderRadius: 4,
                overflow: "hidden",
              }}
            >
              {/* 小时竖线 */}
              {HOUR_MARKS.filter((h) => h > 0 && h < 24).map((h) => (
                <div
                  key={h}
                  style={{
                    position: "absolute",
                    left: `${(h / 24) * 100}%`,
                    top: 0,
                    bottom: 0,
                    width: 1,
                    background: "rgba(0,0,0,0.04)",
                  }}
                />
              ))}
              {row.segments.map((seg, idx) => {
                const left = (seg.start_sec / 86400) * 100;
                const width = ((seg.end_sec - seg.start_sec) / 86400) * 100;
                const color = segmentColor(seg.status, seg.steam_app_id);
                const label =
                  seg.status === "playing"
                    ? seg.game_name || "游戏中"
                    : seg.status === "online"
                      ? "在线"
                      : "离线";
                const title = `${label} · ${formatClock(seg.start_sec)}–${formatClock(seg.end_sec)}`;
                return (
                  <Tooltip key={`${row.member_id}-${idx}`} title={title}>
                    <div
                      style={{
                        position: "absolute",
                        left: `${left}%`,
                        width: `${Math.max(width, 0.15)}%`,
                        top: 3,
                        bottom: 3,
                        background: color,
                        borderRadius: 3,
                        minWidth: 2,
                      }}
                    />
                  </Tooltip>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function SteamCalendarPage() {
  const queryClient = useQueryClient();
  const isAdmin = useAuthStore((s) => s.user?.is_admin);
  const [granularity, setGranularity] = useState<Granularity>("day");
  const [anchor, setAnchor] = useState(dayjs());
  const [selectedDate, setSelectedDate] = useState(dayjs().format("YYYY-MM-DD"));

  const dateParam = anchor.format("YYYY-MM-DD");

  useEffect(() => {
    if (granularity === "day") {
      setSelectedDate(anchor.format("YYYY-MM-DD"));
    }
  }, [granularity, anchor]);

  const { data: calendar, isLoading: calLoading } = useQuery({
    queryKey: ["steam-calendar", granularity, dateParam],
    queryFn: () => fetchSteamCalendar({ granularity, date: dateParam }),
  });

  const dayQueryDate =
    granularity === "day" ? anchor.format("YYYY-MM-DD") : selectedDate;

  const { data: dayData, isLoading: dayLoading } = useQuery({
    queryKey: ["steam-day", dayQueryDate],
    queryFn: () => fetchSteamDay(dayQueryDate),
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
        subtitle="日时间轴 · 周/月/年热力 · 轮询在线与游玩状态"
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
                {p.member_nickname} · {p.game_name}（
                {formatDuration(p.duration_seconds)}）
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
          {granularity === "day"
            ? dayQueryDate
            : calendar
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
          {granularity === "day"
            ? `当日游玩 ${formatDuration(dayData?.total_seconds ?? 0)}`
            : `区间合计 ${formatDuration(calendar?.total_seconds ?? 0)}`}
        </Typography.Text>
      </Space>

      {granularity === "day" ? (
        <DayTimelineChart
          rows={dayData?.timeline ?? []}
          gamesLegend={dayData?.games_legend ?? []}
          loading={dayLoading}
        />
      ) : (
        <>
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
                    border: selected
                      ? "2px solid #1a2332"
                      : "1px solid #e8e8e8",
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
                    <div
                      style={{ fontSize: 11, color: "#595959", marginTop: 4 }}
                    >
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
        </>
      )}
    </div>
  );
}
