import { ReloadOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Empty,
  Space,
  Spin,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import { useMemo, useState, type CSSProperties } from "react";
import type { Dayjs } from "dayjs";
import { fetchSklandGameEvents } from "@/api/client";
import type { GameScheduleCalendar, GameScheduleEvent } from "@/api/types";
import { apiError } from "@/lib/apiError";
import { nowBeijing, parseBeijing } from "@/lib/time";

type GameTab = "arknights" | "endfield";

/** 条形高度（含图+标题）；无左侧活动列；图按原比例，高度撑满条内 */
const ROW_HEIGHT = 88;
const DAY_WIDTH = 36;
const HEADER_HEIGHT = 36;
const BAR_PAD_Y = 6;
const BAR_IMG_H = ROW_HEIGHT - BAR_PAD_Y * 2 - 4;

const BAR_COLORS = [
  "#3b82f6",
  "#0d9488",
  "#ea580c",
  "#4f46e5",
  "#059669",
  "#b45309",
  "#0284c7",
  "#be123c",
];

function barColor(index: number, status: string): string {
  const base = BAR_COLORS[index % BAR_COLORS.length];
  if (status === "upcoming") return `${base}99`;
  return base;
}

function startOfDay(d: Dayjs): Dayjs {
  return d.startOf("day");
}

function dayIndex(rangeStart: Dayjs, t: Dayjs): number {
  return startOfDay(t).diff(startOfDay(rangeStart), "day");
}

type LaidOutEvent = {
  event: GameScheduleEvent;
  start: Dayjs;
  end: Dayjs;
  left: number;
  width: number;
  color: string;
};

function layoutEvents(
  events: GameScheduleEvent[],
  rangeStart: Dayjs,
  dayCount: number,
): LaidOutEvent[] {
  const out: LaidOutEvent[] = [];
  events.forEach((event, i) => {
    const start = parseBeijing(event.start_time);
    const end = parseBeijing(event.end_time);
    if (!start.isValid() || !end.isValid()) return;
    const s = Math.max(0, dayIndex(rangeStart, start));
    const e = Math.min(dayCount, dayIndex(rangeStart, end) + 1);
    if (e <= s) return;
    out.push({
      event,
      start,
      end,
      left: s * DAY_WIDTH,
      width: Math.max(DAY_WIDTH * 0.5, (e - s) * DAY_WIDTH),
      color: barColor(i, event.status),
    });
  });
  return out;
}

function buildRange(events: GameScheduleEvent[]): {
  rangeStart: Dayjs;
  dayCount: number;
} {
  const today = startOfDay(nowBeijing());
  let min = today.subtract(2, "day");
  let max = today.add(14, "day");
  for (const ev of events) {
    const s = parseBeijing(ev.start_time);
    const e = parseBeijing(ev.end_time);
    if (s.isValid() && s.isBefore(min)) min = startOfDay(s);
    if (e.isValid() && e.isAfter(max)) max = startOfDay(e);
  }
  // 横轴略向右多留几天，避免贴边
  max = max.add(1, "day");
  const dayCount = Math.max(7, max.diff(min, "day") + 1);
  return { rangeStart: min, dayCount };
}

function EventTimeline({ events }: { events: GameScheduleEvent[] }) {
  const { rangeStart, dayCount } = useMemo(
    () => buildRange(events),
    [events],
  );
  const laidOut = useMemo(
    () => layoutEvents(events, rangeStart, dayCount),
    [events, rangeStart, dayCount],
  );
  const today = startOfDay(nowBeijing());
  const todayOffset = dayIndex(rangeStart, today);
  const trackWidth = dayCount * DAY_WIDTH;
  const days = useMemo(
    () => Array.from({ length: dayCount }, (_, i) => rangeStart.add(i, "day")),
    [rangeStart, dayCount],
  );

  if (!laidOut.length) {
    return <Empty description="暂无可展示的活动时间" />;
  }

  return (
    <div
      style={{
        overflowX: "auto",
        overflowY: "hidden",
        border: "1px solid rgba(0,0,0,0.06)",
        borderRadius: 8,
        background: "#fafafa",
      }}
    >
      <div style={{ minWidth: trackWidth }}>
        {/* 顶部时间轴（无左侧活动列） */}
        <div
          style={{
            position: "sticky",
            top: 0,
            zIndex: 2,
            background: "#f5f5f5",
            borderBottom: "1px solid rgba(0,0,0,0.08)",
            height: HEADER_HEIGHT,
            width: trackWidth,
          }}
        >
          <div style={{ position: "relative", width: trackWidth, height: HEADER_HEIGHT }}>
            {days.map((d, i) => {
              const isToday = d.isSame(today, "day");
              const isMonthStart = d.date() === 1 || i === 0;
              return (
                <div
                  key={d.format("YYYY-MM-DD")}
                  style={{
                    position: "absolute",
                    left: i * DAY_WIDTH,
                    width: DAY_WIDTH,
                    height: "100%",
                    borderLeft:
                      i === 0 ? undefined : "1px solid rgba(0,0,0,0.04)",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 11,
                    lineHeight: 1.15,
                    color: isToday ? "#1677ff" : "rgba(0,0,0,0.55)",
                    fontWeight: isToday || isMonthStart ? 600 : 400,
                    background: isToday ? "rgba(22,119,255,0.08)" : undefined,
                  }}
                >
                  {isMonthStart ? (
                    <span style={{ fontSize: 10 }}>{d.format("M月")}</span>
                  ) : null}
                  <span>{d.format("D")}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* 活动行：条内放缩略图 + 名称 */}
        {laidOut.map(({ event, start, end, left, width, color }) => {
          const tip = (
            <div style={{ lineHeight: 1.5 }}>
              <div>{event.title}</div>
              <div>
                {start.format("YYYY-MM-DD HH:mm")} ~{" "}
                {end.format("YYYY-MM-DD HH:mm")}
              </div>
              {event.event_type ? <div>{event.event_type}</div> : null}
            </div>
          );
          // 整条 absolute 铺时长；悬浮触发放在 sticky 标题块上，避免长条滚出视口后
          // Tooltip 仍按整条中心定位、飘到左侧。
          const barShellStyle: CSSProperties = {
            position: "absolute",
            left,
            top: BAR_PAD_Y,
            height: ROW_HEIGHT - BAR_PAD_Y * 2,
            width,
            borderRadius: 6,
            background: color,
            boxShadow: "inset 0 0 0 1px rgba(0,0,0,0.06)",
            // 不用 overflow:hidden：否则 sticky 无法相对外层横向滚动容器生效
            minWidth: 4,
            boxSizing: "border-box",
          };
          const labelStyle: CSSProperties = {
            position: "sticky",
            left: 0,
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            height: "100%",
            maxWidth: "100%",
            paddingInline: 6,
            boxSizing: "border-box",
            cursor: event.link_url ? "pointer" : "default",
            color: "inherit",
            textDecoration: "none",
          };
          const barContent = (
            <>
              {event.banner ? (
                <img
                  src={event.banner}
                  alt=""
                  style={{
                    height: BAR_IMG_H,
                    width: "auto",
                    maxWidth: 220,
                    objectFit: "contain",
                    objectPosition: "left center",
                    borderRadius: 4,
                    flexShrink: 0,
                    display: "block",
                  }}
                  loading="lazy"
                  referrerPolicy="no-referrer"
                />
              ) : null}
              <Typography.Text
                style={{
                  color: "#fff",
                  fontSize: 13,
                  fontWeight: 600,
                  whiteSpace: "nowrap",
                  textOverflow: "ellipsis",
                  overflow: "hidden",
                  margin: 0,
                  textShadow: "0 1px 2px rgba(0,0,0,0.25)",
                }}
              >
                {event.title}
              </Typography.Text>
            </>
          );

          return (
            <div
              key={event.id}
              style={{
                position: "relative",
                width: trackWidth,
                height: ROW_HEIGHT,
                borderBottom: "1px solid rgba(0,0,0,0.04)",
                background: "#fff",
                backgroundImage:
                  "linear-gradient(to right, rgba(0,0,0,0.03) 1px, transparent 1px)",
                backgroundSize: `${DAY_WIDTH}px 100%`,
              }}
            >
              {todayOffset >= 0 && todayOffset < dayCount ? (
                <div
                  style={{
                    position: "absolute",
                    left: todayOffset * DAY_WIDTH + DAY_WIDTH / 2 - 0.5,
                    top: 0,
                    bottom: 0,
                    width: 1,
                    background: "rgba(22,119,255,0.45)",
                    pointerEvents: "none",
                    zIndex: 0,
                  }}
                />
              ) : null}
              <div style={barShellStyle}>
                <Tooltip
                  title={tip}
                  mouseEnterDelay={0.15}
                  placement="topLeft"
                  getPopupContainer={() => document.body}
                >
                  {event.link_url ? (
                    <a
                      href={event.link_url}
                      target="_blank"
                      rel="noreferrer"
                      style={labelStyle}
                    >
                      {barContent}
                    </a>
                  ) : (
                    <div style={labelStyle}>{barContent}</div>
                  )}
                </Tooltip>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function GameEventsTimeline({ game }: { game: GameTab }) {
  const queryClient = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);

  const query = useQuery({
    queryKey: ["skland-game-events", game],
    queryFn: () => fetchSklandGameEvents(game, false),
    staleTime: 60_000,
    retry: false,
  });

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      const data = await fetchSklandGameEvents(game, true);
      queryClient.setQueryData(["skland-game-events", game], data);
      message.success("已刷新活动日历");
    } catch (e: unknown) {
      message.error(apiError(e, "刷新活动日历失败"));
    } finally {
      setRefreshing(false);
    }
  };

  const data = query.data as GameScheduleCalendar | undefined;
  const events = data?.events ?? [];
  const permanentEvents = data?.permanent_events ?? [];

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
        }}
      >
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {data
            ? `进行中 ${data.ongoing_count} · 未开始 ${data.upcoming_count}` +
              (data.permanent_count
                ? ` · 常驻 ${data.permanent_count}`
                : "")
            : "加载中…"}
          {data?.synced_at ? ` · 同步 ${data.synced_at}` : ""}
        </Typography.Text>
        <Button
          size="small"
          icon={<ReloadOutlined />}
          loading={refreshing}
          onClick={() => void onRefresh()}
        >
          刷新
        </Button>
      </div>
      {query.isLoading ? (
        <div style={{ textAlign: "center", padding: 24 }}>
          <Spin />
        </div>
      ) : null}
      {query.isError ? (
        <Alert
          type="warning"
          showIcon
          message={apiError(query.error, "加载活动日历失败")}
          style={{ marginBottom: 8 }}
        />
      ) : null}
      {data?.stale ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 8 }}
          message="展示的是本地缓存，上游刷新失败"
        />
      ) : null}
      {!query.isLoading && !query.isError && events.length === 0 ? (
        <Empty description="暂无进行中或即将开始的限时活动" />
      ) : null}
      {!query.isLoading && !query.isError && events.length > 0 ? (
        <EventTimeline events={events} />
      ) : null}
      {!query.isLoading && !query.isError && permanentEvents.length > 0 ? (
        <div style={{ marginTop: 16 }}>
          <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
            常驻活动
          </Typography.Text>
          <Space direction="vertical" size={8} style={{ width: "100%" }}>
            {permanentEvents.map((event) => {
              const body = (
                <div
                  style={{
                    display: "flex",
                    gap: 10,
                    alignItems: "center",
                    padding: "8px 10px",
                    border: "1px solid rgba(0,0,0,0.06)",
                    borderRadius: 8,
                    background: "#fff",
                  }}
                >
                  {event.banner ? (
                    <img
                      src={event.banner}
                      alt=""
                      style={{
                        height: 40,
                        width: "auto",
                        maxWidth: 120,
                        objectFit: "contain",
                        borderRadius: 4,
                        flexShrink: 0,
                      }}
                      loading="lazy"
                      referrerPolicy="no-referrer"
                    />
                  ) : null}
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <Space size={6} wrap style={{ marginBottom: 2 }}>
                      {event.event_type ? (
                        <Tag style={{ marginInlineEnd: 0 }}>
                          {event.event_type}
                        </Tag>
                      ) : (
                        <Tag style={{ marginInlineEnd: 0 }}>常驻</Tag>
                      )}
                    </Space>
                    <Typography.Text
                      strong
                      ellipsis
                      style={{ display: "block" }}
                    >
                      {event.title}
                    </Typography.Text>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {event.start_time} 起
                    </Typography.Text>
                  </div>
                </div>
              );
              return event.link_url ? (
                <a
                  key={event.id}
                  href={event.link_url}
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: "inherit", display: "block" }}
                >
                  {body}
                </a>
              ) : (
                <div key={event.id}>{body}</div>
              );
            })}
          </Space>
        </div>
      ) : null}
      <Typography.Paragraph
        type="secondary"
        style={{ fontSize: 12, marginTop: 12, marginBottom: 0 }}
      >
        数据来自{" "}
        <a
          href="https://github.com/jacket-sikaha/game-schedule"
          target="_blank"
          rel="noreferrer"
        >
          game-schedule
        </a>
        ，非森空岛官方接口。限时活动用时间轴；常驻活动单独列表。横轴可左右滑动。
      </Typography.Paragraph>
    </div>
  );
}

/** 森空岛各游戏 Tab：单游戏活动时间轴（game-schedule）。 */
export function SklandGameEventsPanel({ game }: { game: GameTab }) {
  return (
    <Card title="活动日历">
      <GameEventsTimeline game={game} />
    </Card>
  );
}
