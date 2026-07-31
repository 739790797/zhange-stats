import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
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
import dayjs, { type Dayjs } from "dayjs";
import { useEffect, useMemo, useState } from "react";
import {
  fetchSteamCalendar,
  fetchSteamDay,
  fetchSteamNow,
  triggerSteamPoll,
} from "@/api/client";
import type {
  SteamCalendarCell,
  SteamCalendarMemberSeries,
  SteamDayData,
  SteamTimelineRow,
} from "@/api/types";
import { PageHeader } from "@/components/PageHeader";
import { useAuthStore } from "@/stores/authStore";

type Granularity = "day" | "week" | "month" | "year";

const DAY_SECONDS = 86400;
const HOUR_MARKS = [0, 3, 6, 9, 12, 15, 18, 21, 24];
const WEEKDAY_LABELS = ["一", "二", "三", "四", "五", "六", "日"];
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

function monthHeatColor(seconds: number, maxSeconds: number): string {
  if (seconds <= 0 || maxSeconds <= 0) return "#f0f2f5";
  const t = Math.min(1, seconds / maxSeconds);
  const alpha = 0.15 + t * 0.85;
  return `rgba(47, 111, 78, ${alpha.toFixed(3)})`;
}

function githubHeatColor(seconds: number, maxSeconds: number): string {
  if (seconds <= 0 || maxSeconds <= 0) return "#ebedf0";
  const t = Math.min(1, seconds / maxSeconds);
  if (t < 0.25) return "#9be9a8";
  if (t < 0.5) return "#40c463";
  if (t < 0.75) return "#30a14e";
  return "#216e39";
}

function hashColor(key: string): string {
  let h = 0;
  for (let i = 0; i < key.length; i++) {
    h = (h * 31 + key.charCodeAt(i)) >>> 0;
  }
  return GAME_PALETTE[h % GAME_PALETTE.length];
}

function segmentColor(status: string, appId?: string | null): string {
  if (status === "offline") return "#d9d9d9";
  if (status === "online") return "#5b8ff9";
  if (status === "playing") return hashColor(appId || "playing");
  return "#bfbfbf";
}

function formatClock(sec: number, spanSeconds: number, rangeStart: Dayjs): string {
  const s = Math.max(0, Math.min(spanSeconds, Math.floor(sec)));
  if (spanSeconds <= DAY_SECONDS) {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
  }
  const dayOffset = Math.floor(s / DAY_SECONDS);
  const within = s % DAY_SECONDS;
  const h = Math.floor(within / 3600);
  const m = Math.floor((within % 3600) / 60);
  const d = rangeStart.add(dayOffset, "day");
  return `${d.format("M/D")} ${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function TimelineChart({
  rows,
  gamesLegend,
  loading,
  spanSeconds,
  rangeStart,
}: {
  rows: SteamTimelineRow[];
  gamesLegend: { steam_app_id: string; game_name: string }[];
  loading?: boolean;
  spanSeconds: number;
  rangeStart: Dayjs;
}) {
  const labelWidth = 112;
  const trackHeight = 28;
  const rowGap = 10;
  const dayCount = Math.max(1, Math.round(spanSeconds / DAY_SECONDS));
  const isWeek = dayCount > 1;

  const marks = useMemo(() => {
    if (!isWeek) {
      return HOUR_MARKS.map((h) => ({
        at: h * 3600,
        label: `${String(h).padStart(2, "0")}:00`,
      }));
    }
    return Array.from({ length: dayCount }, (_, i) => {
      const d = rangeStart.add(i, "day");
      return {
        at: i * DAY_SECONDS,
        label: `${WEEKDAY_LABELS[d.day() === 0 ? 6 : d.day() - 1]} ${d.format("M/D")}`,
      };
    });
  }, [isWeek, dayCount, rangeStart]);

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

      <div
        style={{
          display: "flex",
          marginBottom: 8,
          marginLeft: labelWidth,
          position: "relative",
          height: 20,
        }}
      >
        {marks.map((m) => (
          <div
            key={m.at}
            style={{
              position: "absolute",
              left: `${(m.at / spanSeconds) * 100}%`,
              transform: "translateX(-50%)",
              fontSize: 11,
              color: "#8c8c8c",
              whiteSpace: "nowrap",
            }}
          >
            {m.label}
          </div>
        ))}
      </div>

      <div
        style={{
          border: "1px solid #f0f0f0",
          borderRadius: 8,
          padding: "8px 0",
          background: "#fafafa",
          overflowX: isWeek ? "auto" : undefined,
        }}
      >
        <div style={{ minWidth: isWeek ? Math.max(720, dayCount * 120) : undefined }}>
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
                {marks
                  .filter((m) => m.at > 0 && m.at < spanSeconds)
                  .map((m) => (
                    <div
                      key={m.at}
                      style={{
                        position: "absolute",
                        left: `${(m.at / spanSeconds) * 100}%`,
                        top: 0,
                        bottom: 0,
                        width: 1,
                        background: isWeek
                          ? "rgba(0,0,0,0.08)"
                          : "rgba(0,0,0,0.04)",
                      }}
                    />
                  ))}
                {row.segments.map((seg, idx) => {
                  const left = (seg.start_sec / spanSeconds) * 100;
                  const width =
                    ((seg.end_sec - seg.start_sec) / spanSeconds) * 100;
                  const color = segmentColor(seg.status, seg.steam_app_id);
                  const label =
                    seg.status === "playing"
                      ? seg.game_name || "游戏中"
                      : seg.status === "online"
                        ? "在线"
                        : "离线";
                  const title = `${label} · ${formatClock(seg.start_sec, spanSeconds, rangeStart)}–${formatClock(seg.end_sec, spanSeconds, rangeStart)}`;
                  return (
                    <Tooltip key={`${row.member_id}-${idx}`} title={title}>
                      <div
                        style={{
                          position: "absolute",
                          left: `${left}%`,
                          width: `${Math.max(width, 0.08)}%`,
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
    </div>
  );
}

function GithubHeatmap({
  cells,
  year,
  selectedDate,
  onSelect,
  maxSeconds,
  loading,
}: {
  cells: SteamCalendarCell[];
  year: number;
  selectedDate?: string | null;
  onSelect?: (date: string) => void;
  maxSeconds: number;
  loading?: boolean;
}) {
  const cellMap = useMemo(() => {
    const m = new Map<string, number>();
    for (const c of cells) m.set(c.date, c.total_seconds);
    return m;
  }, [cells]);

  const { weeks, monthLabels } = useMemo(() => {
    const jan1 = dayjs(`${year}-01-01`);
    const dec31 = dayjs(`${year}-12-31`);
    const gridStart = jan1.subtract((jan1.day() + 6) % 7, "day");
    const gridEnd = dec31.add((7 - ((dec31.day() + 6) % 7) - 1) % 7, "day");

    const weekCols: (string | null)[][] = [];
    let cursor = gridStart;
    let col: (string | null)[] = [];
    while (cursor.isBefore(gridEnd) || cursor.isSame(gridEnd, "day")) {
      const inYear = cursor.year() === year;
      col.push(inYear ? cursor.format("YYYY-MM-DD") : null);
      if (col.length === 7) {
        weekCols.push(col);
        col = [];
      }
      cursor = cursor.add(1, "day");
    }
    if (col.length) {
      while (col.length < 7) col.push(null);
      weekCols.push(col);
    }

    const labels: { text: string; col: number }[] = [];
    let lastMonth = -1;
    weekCols.forEach((week, colIdx) => {
      const firstInYear = week.find((d) => d != null);
      if (!firstInYear) return;
      const month = dayjs(firstInYear).month();
      if (month !== lastMonth) {
        labels.push({ text: `${month + 1}月`, col: colIdx });
        lastMonth = month;
      }
    });

    return { weeks: weekCols, monthLabels: labels };
  }, [year]);

  const cellSize = 12;
  const gap = 3;
  const labelW = 28;
  const topH = 18;

  return (
    <div style={{ opacity: loading ? 0.6 : 1, overflowX: "auto" }}>
      <div
        style={{
          display: "inline-block",
          minWidth: labelW + weeks.length * (cellSize + gap),
        }}
      >
        <div
          style={{
            position: "relative",
            height: topH,
            marginLeft: labelW,
            marginBottom: 4,
          }}
        >
          {monthLabels.map((m) => (
            <div
              key={`${m.text}-${m.col}`}
              style={{
                position: "absolute",
                left: m.col * (cellSize + gap),
                fontSize: 11,
                color: "#8c8c8c",
                whiteSpace: "nowrap",
              }}
            >
              {m.text}
            </div>
          ))}
        </div>

        <div style={{ display: "flex" }}>
          <div
            style={{
              width: labelW,
              display: "flex",
              flexDirection: "column",
              gap,
            }}
          >
            {WEEKDAY_LABELS.map((w, i) => (
              <div
                key={w}
                style={{
                  height: cellSize,
                  fontSize: 10,
                  color: "#8c8c8c",
                  lineHeight: `${cellSize}px`,
                  visibility: i % 2 === 1 ? "visible" : "hidden",
                }}
              >
                {w}
              </div>
            ))}
          </div>

          <div style={{ display: "flex", gap }}>
            {weeks.map((week, wi) => (
              <div key={wi} style={{ display: "flex", flexDirection: "column", gap }}>
                {week.map((d, di) => {
                  if (!d) {
                    return (
                      <div
                        key={`${wi}-${di}`}
                        style={{ width: cellSize, height: cellSize }}
                      />
                    );
                  }
                  const seconds = cellMap.get(d) ?? 0;
                  const selected = d === selectedDate;
                  return (
                    <Tooltip
                      key={d}
                      title={`${d} · ${seconds > 0 ? formatDuration(seconds) : "无记录"}`}
                    >
                      <button
                        type="button"
                        onClick={() => onSelect?.(d)}
                        style={{
                          width: cellSize,
                          height: cellSize,
                          padding: 0,
                          border: selected
                            ? "1px solid #1a2332"
                            : "1px solid rgba(27,31,35,0.06)",
                          borderRadius: 2,
                          background: githubHeatColor(seconds, maxSeconds),
                          cursor: onSelect ? "pointer" : "default",
                          display: "block",
                        }}
                      />
                    </Tooltip>
                  );
                })}
              </div>
            ))}
          </div>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            marginTop: 10,
            marginLeft: labelW,
            fontSize: 11,
            color: "#8c8c8c",
          }}
        >
          <span>少</span>
          {[0, 0.2, 0.45, 0.7, 1].map((t, i) => (
            <div
              key={i}
              style={{
                width: cellSize,
                height: cellSize,
                borderRadius: 2,
                background: githubHeatColor(t * Math.max(maxSeconds, 1), maxSeconds || 1),
                border: "1px solid rgba(27,31,35,0.06)",
              }}
            />
          ))}
          <span>多</span>
        </div>
      </div>
    </div>
  );
}

function DayDetailPanel({
  dayData,
  dayLoading,
  titleDate,
}: {
  dayData?: SteamDayData;
  dayLoading: boolean;
  titleDate: string;
}) {
  return (
    <>
      <Typography.Title level={5} style={{ marginTop: 24 }}>
        {titleDate} 大家玩了什么
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
  );
}

export default function SteamCalendarPage() {
  const queryClient = useQueryClient();
  const isAdmin = useAuthStore((s) => s.user?.is_admin);
  const [granularity, setGranularity] = useState<Granularity>("day");
  const [anchor, setAnchor] = useState(dayjs());
  const [selectedDate, setSelectedDate] = useState(dayjs().format("YYYY-MM-DD"));

  const dateParam = anchor.format("YYYY-MM-DD");

  const weekRangeStart = useMemo(() => {
    const d = anchor;
    return d.subtract((d.day() + 6) % 7, "day");
  }, [anchor]);
  const weekRangeEnd = useMemo(
    () => weekRangeStart.add(6, "day"),
    [weekRangeStart],
  );

  useEffect(() => {
    if (granularity === "day") {
      setSelectedDate(anchor.format("YYYY-MM-DD"));
    }
  }, [granularity, anchor]);

  const needCalendar = granularity === "month" || granularity === "year";

  const { data: calendar, isLoading: calLoading } = useQuery({
    queryKey: ["steam-calendar", granularity, dateParam],
    queryFn: () => fetchSteamCalendar({ granularity, date: dateParam }),
    enabled: needCalendar,
  });

  const dayQueryDate =
    granularity === "day" ? anchor.format("YYYY-MM-DD") : selectedDate;

  const timelineRange =
    granularity === "week"
      ? {
          start: weekRangeStart.format("YYYY-MM-DD"),
          end: weekRangeEnd.format("YYYY-MM-DD"),
        }
      : granularity === "day"
        ? { start: dayQueryDate, end: undefined as string | undefined }
        : null;

  const { data: timelineData, isLoading: timelineLoading } = useQuery({
    queryKey: ["steam-timeline", timelineRange?.start, timelineRange?.end],
    queryFn: () => fetchSteamDay(timelineRange!.start, timelineRange!.end),
    enabled: granularity === "day" || granularity === "week",
  });

  const { data: dayData, isLoading: dayLoading } = useQuery({
    queryKey: ["steam-day", dayQueryDate],
    queryFn: () => fetchSteamDay(dayQueryDate),
    enabled: granularity === "month" || granularity === "year",
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
      queryClient.invalidateQueries({ queryKey: ["steam-timeline"] });
      queryClient.invalidateQueries({ queryKey: ["steam-now"] });
    },
    onError: () => message.error("轮询请求失败"),
  });

  const maxSeconds = useMemo(() => {
    if (!calendar?.cells?.length) return 0;
    return Math.max(...calendar.cells.map((c) => c.total_seconds), 0);
  }, [calendar]);

  const memberMaxSeconds = useMemo(() => {
    const series = calendar?.members ?? [];
    let max = 0;
    for (const m of series) {
      for (const c of m.cells) max = Math.max(max, c.total_seconds);
    }
    return max;
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

  const gridStart = calendar?.range_start
    ? dayjs(calendar.range_start)
    : anchor.startOf("month");
  const gridEnd = calendar?.range_end
    ? dayjs(calendar.range_end)
    : anchor.endOf("month");

  const leadingPad =
    granularity === "month" ? (gridStart.day() + 6) % 7 : 0;

  const days: (string | null)[] = [];
  if (granularity === "month") {
    for (let i = 0; i < leadingPad; i++) days.push(null);
    let cursor = gridStart;
    while (cursor.isBefore(gridEnd) || cursor.isSame(gridEnd, "day")) {
      days.push(cursor.format("YYYY-MM-DD"));
      cursor = cursor.add(1, "day");
    }
  }

  const spanSeconds =
    timelineData?.span_seconds ??
    (granularity === "week" ? 7 * DAY_SECONDS : DAY_SECONDS);
  const timelineStart = dayjs(
    timelineData?.range_start ??
      (granularity === "week"
        ? weekRangeStart.format("YYYY-MM-DD")
        : dayQueryDate),
  );

  const rangeLabel = (() => {
    if (granularity === "day") return dayQueryDate;
    if (granularity === "week") {
      return `${weekRangeStart.format("YYYY-MM-DD")} ~ ${weekRangeEnd.format("YYYY-MM-DD")}`;
    }
    if (calendar) return `${calendar.range_start} ~ ${calendar.range_end}`;
    return dateParam;
  })();

  const totalLabel =
    granularity === "day" || granularity === "week"
      ? formatDuration(timelineData?.total_seconds ?? 0)
      : formatDuration(calendar?.total_seconds ?? 0);

  return (
    <div>
      <PageHeader
        title="今天玩什么"
        subtitle="仅显示你与 Steam 好友 · 日/周时间轴 · 月热力 · 年活跃图"
        extra={
          isAdmin ? (
            <Button loading={poll.isPending} onClick={() => poll.mutate()}>
              立即轮询
            </Button>
          ) : null
        }
      />

      {(calendar?.visibility?.hint || timelineData?.visibility?.hint) && (
        <Alert
          type={
            (calendar?.visibility ?? timelineData?.visibility)
              ?.friends_list_public === false
              ? "warning"
              : "info"
          }
          showIcon
          style={{ marginBottom: 16 }}
          message={
            calendar?.visibility?.hint || timelineData?.visibility?.hint
          }
        />
      )}

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
          onChange={(e) => setGranularity(e.target.value)}
          optionType="button"
          options={[
            { label: "日", value: "day" },
            { label: "周", value: "week" },
            { label: "月", value: "month" },
            { label: "年", value: "year" },
          ]}
        />
        <Button onClick={() => shift(-1)}>上一段</Button>
        <Typography.Text strong>{rangeLabel}</Typography.Text>
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
            ? `当日游玩 ${totalLabel}`
            : granularity === "week"
              ? `本周游玩 ${totalLabel}`
              : `区间合计 ${totalLabel}`}
        </Typography.Text>
      </Space>

      {(granularity === "day" || granularity === "week") && (
        <TimelineChart
          rows={timelineData?.timeline ?? []}
          gamesLegend={timelineData?.games_legend ?? []}
          loading={timelineLoading}
          spanSeconds={spanSeconds}
          rangeStart={timelineStart}
        />
      )}

      {granularity === "month" && (
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
            {WEEKDAY_LABELS.map((w) => (
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
              if (!d) return <div key={`pad-${idx}`} />;
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
                    minHeight: 64,
                    padding: 6,
                    background: monthHeatColor(seconds, maxSeconds),
                    cursor: "pointer",
                    textAlign: "left",
                  }}
                >
                  <div style={{ fontSize: 12, fontWeight: 600 }}>
                    {dayjs(d).format("D")}
                  </div>
                  <div style={{ fontSize: 11, color: "#595959", marginTop: 4 }}>
                    {seconds > 0 ? formatDuration(seconds) : "—"}
                  </div>
                </button>
              );
            })}
          </div>
          <DayDetailPanel
            dayData={dayData}
            dayLoading={dayLoading}
            titleDate={selectedDate}
          />
        </>
      )}

      {granularity === "year" && (
        <>
          <Typography.Title level={5} style={{ marginTop: 0 }}>
            {anchor.year()} 年活跃总览
          </Typography.Title>
          <Typography.Paragraph type="secondary">
            颜色表示当天你与好友的合计游玩时长，点击格子查看明细
          </Typography.Paragraph>
          <GithubHeatmap
            cells={calendar?.cells ?? []}
            year={anchor.year()}
            selectedDate={selectedDate}
            onSelect={setSelectedDate}
            maxSeconds={maxSeconds}
            loading={calLoading}
          />

          <Typography.Title level={5} style={{ marginTop: 28 }}>
            成员活跃图
          </Typography.Title>
          <Typography.Paragraph type="secondary">
            每人一张 GitHub 风格日历，展示其在圈子内可见的游玩活跃
          </Typography.Paragraph>

          {(calendar?.members?.length ?? 0) === 0 && !calLoading ? (
            <Empty description="暂无可见成员" />
          ) : (
            <Space direction="vertical" size={24} style={{ width: "100%" }}>
              {(calendar?.members ?? []).map((m: SteamCalendarMemberSeries) => (
                <div key={m.member_id}>
                  <Space style={{ marginBottom: 8 }}>
                    <Avatar size={28} src={m.avatar_url || undefined}>
                      {m.member_nickname[0]}
                    </Avatar>
                    <Typography.Text strong>{m.member_nickname}</Typography.Text>
                    <Typography.Text type="secondary">
                      全年 {formatDuration(m.total_seconds)}
                    </Typography.Text>
                  </Space>
                  <GithubHeatmap
                    cells={m.cells}
                    year={anchor.year()}
                    selectedDate={selectedDate}
                    onSelect={setSelectedDate}
                    maxSeconds={memberMaxSeconds || maxSeconds}
                    loading={calLoading}
                  />
                </div>
              ))}
            </Space>
          )}

          <DayDetailPanel
            dayData={dayData}
            dayLoading={dayLoading}
            titleDate={selectedDate}
          />
        </>
      )}
    </div>
  );
}
