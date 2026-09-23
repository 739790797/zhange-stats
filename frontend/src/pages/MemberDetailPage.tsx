import { useQuery } from "@tanstack/react-query";
import {
  Avatar,
  Button,
  Card,
  Col,
  Empty,
  Progress,
  Radio,
  Result,
  Row,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Tooltip,
  Typography,
  theme,
} from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import {
  fetchMemberPlayStats,
  fetchSteamDay,
  fetchSteamNow,
} from "@/api/client";
import type { MemberPlayStats, SteamNowItem } from "@/api/types";
import { PageHeader } from "@/components/PageHeader";
import { DAY_SECONDS, type Granularity } from "@/components/steam/constants";
import { DayTimeline } from "@/components/steam/DayTimeline";
import { formatDuration } from "@/components/steam/format";
import { GameStoreHoverCard } from "@/components/steam/GameStoreHoverCard";
import { sessionDurationSeconds } from "@/components/steam/nowPlayingUtils";
import { GameIcon } from "@/components/steam/SteamClientIcon";
import { TimelineControls } from "@/components/steam/TimelineControls";
import {
  clipTimelineToNoonWindow,
  steamStoreUrl,
} from "@/components/steam/timelineUtils";
import { apiError } from "@/lib/apiError";
import { rememberSteamIcons } from "@/lib/steamIconCache";
import { formatBeijing, nowBeijing, parseBeijing } from "@/lib/time";

const SUBTITLE = "站内轮询记录的游玩片段，不是 Steam 官方累计时长";

type GameSpan = "today" | "week" | "month";

type PlayGame = MemberPlayStats["games_today"][number];

const STORE_TOOLTIP = {
  placement: "top" as const,
  autoAdjustOverflow: false,
  color: "#ffffff",
  mouseEnterDelay: 0.25,
  destroyTooltipOnHide: true,
  overlayInnerStyle: {
    padding: 0,
    overflow: "hidden" as const,
    borderRadius: 8,
    minHeight: 0,
    minWidth: 0,
    boxShadow: "0 6px 16px rgba(0,0,0,0.12)",
  },
};

function steamProfileUrl(steamId: string): string {
  return `https://steamcommunity.com/profiles/${encodeURIComponent(steamId)}`;
}

function MemberNowPlaying({ item }: { item: SteamNowItem }) {
  const fetchedAtRef = useRef(Date.now());
  const [nowMs, setNowMs] = useState(Date.now());
  useEffect(() => {
    fetchedAtRef.current = Date.now();
    setNowMs(Date.now());
  }, [item]);
  useEffect(() => {
    const timer = window.setInterval(() => setNowMs(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);
  const seconds = sessionDurationSeconds(item, fetchedAtRef.current, nowMs);
  const openStore = () => {
    if (!item.steam_app_id) return;
    window.open(steamStoreUrl(item.steam_app_id), "_blank", "noopener,noreferrer");
  };
  const body = (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        cursor: item.steam_app_id ? "pointer" : "default",
      }}
      onClick={openStore}
    >
      <GameIcon
        appId={item.steam_app_id}
        iconUrl={item.icon_url}
        name={item.game_name}
        size={40}
      />
      <div style={{ minWidth: 0 }}>
        <div style={{ fontWeight: 600 }}>{item.game_name}</div>
        <Typography.Text type="secondary">
          本次 {formatDuration(seconds)}
        </Typography.Text>
      </div>
    </div>
  );
  return (
    <Card size="small" style={{ marginBottom: 16 }} title="正在游玩">
      {item.steam_app_id ? (
        <Tooltip
          {...STORE_TOOLTIP}
          title={
            <GameStoreHoverCard
              appId={item.steam_app_id}
              fallbackName={item.game_name}
            />
          }
        >
          {body}
        </Tooltip>
      ) : (
        body
      )}
    </Card>
  );
}

function GameBreakdown({ games }: { games: PlayGame[] }) {
  const total = games.reduce((sum, game) => sum + game.total_seconds, 0);
  if (total <= 0) {
    return <Empty description="该时段暂无游玩" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }
  return (
    <div>
      {games.map((game) => {
        const percent = Math.round((game.total_seconds / total) * 100);
        const openStore = () => {
          window.open(
            steamStoreUrl(game.steam_app_id),
            "_blank",
            "noopener,noreferrer",
          );
        };
        return (
          <div
            key={game.steam_app_id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              marginBottom: 12,
            }}
          >
            <GameIcon
              appId={game.steam_app_id}
              iconUrl={game.icon_url}
              name={game.game_name}
              size={32}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <Tooltip
                {...STORE_TOOLTIP}
                title={
                  <GameStoreHoverCard
                    appId={game.steam_app_id}
                    fallbackName={game.game_name}
                  />
                }
              >
                <Typography.Link ellipsis onClick={openStore}>
                  {game.game_name}
                </Typography.Link>
              </Tooltip>
              <Progress
                percent={percent}
                size="small"
                format={() => formatDuration(game.total_seconds)}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function MemberDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { token } = theme.useToken();
  const memberId = Number(id);
  const enabled = Number.isFinite(memberId);

  const [gameSpan, setGameSpan] = useState<GameSpan>("week");
  const [granularity, setGranularity] = useState<Granularity>("day");
  const [anchor, setAnchor] = useState(() => nowBeijing().startOf("day"));
  const [dayStartHour, setDayStartHour] = useState<0 | 12>(0);

  const statsQuery = useQuery({
    queryKey: ["member-play", memberId],
    queryFn: () => fetchMemberPlayStats(memberId),
    enabled,
  });
  const data = statsQuery.data;
  const steamBound = Boolean(data?.member.steam_id);

  const nowQuery = useQuery({
    queryKey: ["steam-now"],
    queryFn: () => fetchSteamNow(),
    enabled: steamBound,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
  const nowPlaying = useMemo(
    () => (nowQuery.data ?? []).filter((item) => item.member_id === memberId),
    [nowQuery.data, memberId],
  );

  const weekRangeStart = useMemo(() => anchor.startOf("isoWeek"), [anchor]);
  const weekRangeEnd = useMemo(
    () => weekRangeStart.endOf("isoWeek"),
    [weekRangeStart],
  );
  const dayQueryDate = anchor.format("YYYY-MM-DD");
  const dayQueryEnd =
    granularity === "day" && dayStartHour === 12
      ? anchor.add(1, "day").format("YYYY-MM-DD")
      : undefined;
  const timelineRange =
    granularity === "week"
      ? {
          start: weekRangeStart.format("YYYY-MM-DD"),
          end: weekRangeEnd.format("YYYY-MM-DD"),
        }
      : granularity === "day"
        ? { start: dayQueryDate, end: dayQueryEnd }
        : null;

  const {
    data: timelineRaw,
    isLoading: timelineLoading,
    isFetching: timelineFetching,
    isError: timelineError,
    error: timelineErrorValue,
  } = useQuery({
    queryKey: [
      "steam-timeline",
      "member",
      memberId,
      timelineRange?.start,
      timelineRange?.end,
      granularity === "day" ? dayStartHour : 0,
    ],
    queryFn: () =>
      fetchSteamDay(timelineRange!.start, timelineRange!.end, memberId),
    enabled: steamBound && Boolean(timelineRange?.start),
    staleTime: 60_000,
  });

  const timelineBase = useMemo(() => {
    if (!timelineRaw) return timelineRaw;
    if (granularity === "day" && dayStartHour === 12) {
      return clipTimelineToNoonWindow(timelineRaw);
    }
    return timelineRaw;
  }, [timelineRaw, granularity, dayStartHour]);

  useEffect(() => {
    if (!data) return;
    rememberSteamIcons([
      ...data.games_today,
      ...data.games_week,
      ...data.games_month,
      ...data.recent_sessions,
      ...nowPlaying,
    ].map((row) => ({
      appId: row.steam_app_id,
      iconUrl: row.icon_url,
    })));
  }, [data, nowPlaying]);

  useEffect(() => {
    if (!timelineBase) return;
    const entries: { appId?: string | null; iconUrl?: string | null }[] = [];
    for (const game of timelineBase.games_legend ?? []) {
      entries.push({ appId: game.steam_app_id, iconUrl: game.icon_url });
    }
    for (const row of timelineBase.timeline ?? []) {
      for (const seg of row.segments) {
        if (seg.steam_app_id) {
          entries.push({ appId: seg.steam_app_id, iconUrl: seg.icon_url });
        }
      }
    }
    rememberSteamIcons(entries);
  }, [timelineBase]);

  const shift = (dir: -1 | 1) => {
    if (granularity === "week") {
      setAnchor((d) => d.add(dir, "week"));
      return;
    }
    if (granularity !== "day") return;
    if (dir === 1) {
      if (dayStartHour === 0) setDayStartHour(12);
      else {
        setDayStartHour(0);
        setAnchor((d) => d.add(1, "day"));
      }
    } else if (dayStartHour === 12) {
      setDayStartHour(0);
    } else {
      setDayStartHour(12);
      setAnchor((d) => d.subtract(1, "day"));
    }
  };

  const spanSeconds =
    timelineBase?.span_seconds ??
    (granularity === "week" ? 7 * DAY_SECONDS : DAY_SECONDS);
  const timelineStart = useMemo(() => {
    if (timelineBase?.range_start) {
      return parseBeijing(timelineBase.range_start);
    }
    if (granularity === "week") return weekRangeStart;
    return dayStartHour === 12 ? anchor.hour(12).minute(0).second(0) : anchor;
  }, [
    timelineBase?.range_start,
    granularity,
    weekRangeStart,
    anchor,
    dayStartHour,
  ]);

  const games =
    gameSpan === "today"
      ? (data?.games_today ?? [])
      : gameSpan === "month"
        ? (data?.games_month ?? [])
        : (data?.games_week ?? []);
  const maxTrend = Math.max(
    1,
    ...(data?.trend.map((point) => point.total_seconds) ?? [1]),
  );
  const selectedTrendDate =
    granularity === "day" && dayStartHour === 0
      ? anchor.format("YYYY-MM-DD")
      : null;

  const backButton = (
    <Button onClick={() => navigate("/steam")}>返回 Steam</Button>
  );

  if (!enabled) {
    return (
      <Result
        status="error"
        title="成员不存在"
        extra={
          <Button type="primary" onClick={() => navigate("/steam")}>
            返回 Steam
          </Button>
        }
      />
    );
  }

  if (statsQuery.isError) {
    return (
      <Result
        status="error"
        title="无法查看该成员"
        subTitle={apiError(statsQuery.error, "成员不存在")}
        extra={
          <Button type="primary" onClick={() => navigate("/steam")}>
            返回 Steam
          </Button>
        }
      />
    );
  }

  return (
    <div>
      <PageHeader
        title={data?.member.nickname ?? "成员详情"}
        subtitle={SUBTITLE}
        extra={
          <Space>
            {backButton}
            {data ? (
              <Avatar size={56} src={data.member.avatar_url || undefined}>
                {data.member.nickname[0]}
              </Avatar>
            ) : null}
          </Space>
        }
      />

      {statsQuery.isPending || !data ? (
        <Spin />
      ) : !steamBound ? (
        <Typography.Paragraph type="secondary">
          该成员尚未绑定 Steam
        </Typography.Paragraph>
      ) : (
        <>
          {data.member.steam_id ? (
            <Space wrap style={{ marginBottom: 16 }}>
              <Typography.Text copyable={{ text: data.member.steam_id }}>
                SteamID：{data.member.steam_id}
              </Typography.Text>
              <Typography.Link
                href={steamProfileUrl(data.member.steam_id)}
                target="_blank"
                rel="noreferrer"
              >
                Steam 社区主页
              </Typography.Link>
            </Space>
          ) : null}

          {nowPlaying.map((item) => (
            <MemberNowPlaying key={item.id} item={item} />
          ))}

          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            <Col xs={12} sm={8}>
              <Card>
                <Statistic
                  title="今日"
                  value={formatDuration(data.today_play_seconds)}
                />
              </Card>
            </Col>
            <Col xs={12} sm={8}>
              <Card>
                <Statistic
                  title="本周"
                  value={formatDuration(data.week_play_seconds)}
                />
              </Card>
            </Col>
            <Col xs={24} sm={8}>
              <Card>
                <Statistic
                  title="本月"
                  value={formatDuration(data.month_play_seconds)}
                />
              </Card>
            </Col>
          </Row>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 12,
              marginBottom: 12,
              flexWrap: "wrap",
            }}
          >
            <Typography.Title level={5} style={{ margin: 0 }}>
              游戏构成
            </Typography.Title>
            <Radio.Group
              size="small"
              optionType="button"
              value={gameSpan}
              onChange={(event) => setGameSpan(event.target.value)}
              options={[
                { label: "今日", value: "today" },
                { label: "本周", value: "week" },
                { label: "本月", value: "month" },
              ]}
            />
          </div>
          <div style={{ marginBottom: 32 }}>
            <GameBreakdown games={games} />
          </div>

          <Typography.Title level={5}>近两周</Typography.Title>
          {data.trend.some((point) => point.total_seconds > 0) ? (
            <div style={{ marginBottom: 32 }}>
              {data.trend.map((point) => {
                const selected = selectedTrendDate === point.date;
                const percent = Math.round(
                  (point.total_seconds / maxTrend) * 100,
                );
                const openDay = () => {
                  setGranularity("day");
                  setDayStartHour(0);
                  setAnchor(parseBeijing(point.date).startOf("day"));
                };
                return (
                  <div
                    key={point.date}
                    role="button"
                    tabIndex={0}
                    onClick={openDay}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        openDay();
                      }
                    }}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 12,
                      marginBottom: 8,
                      cursor: "pointer",
                      padding: "4px 8px",
                      borderRadius: token.borderRadius,
                      background: selected ? token.colorPrimaryBg : undefined,
                    }}
                  >
                    <Typography.Text style={{ width: 48 }}>
                      {point.date.slice(5)}
                    </Typography.Text>
                    <div
                      style={{
                        flex: 1,
                        height: 8,
                        borderRadius: 4,
                        background: token.colorFillSecondary,
                      }}
                    >
                      <div
                        style={{
                          width: `${percent}%`,
                          height: "100%",
                          borderRadius: 4,
                          background: token.colorPrimary,
                        }}
                      />
                    </div>
                    <Typography.Text style={{ width: 88, textAlign: "right" }}>
                      {formatDuration(point.total_seconds)}
                    </Typography.Text>
                  </div>
                );
              })}
            </div>
          ) : (
            <Empty
              style={{ marginBottom: 32 }}
              description="近两周暂无游玩记录"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )}

          <Typography.Title level={5}>时间轴</Typography.Title>
          <TimelineControls
            granularity={granularity}
            dayStartHour={dayStartHour}
            anchor={anchor}
            isPendingGranularity={false}
            onGranularityChange={(value) => {
              setGranularity(value);
              setDayStartHour(0);
            }}
            onShift={shift}
            onAnchorChange={setAnchor}
            onDayStartHourReset={() => setDayStartHour(0)}
          />
          {timelineError ? (
            <Typography.Paragraph type="danger">
              {apiError(timelineErrorValue, "时间轴加载失败")}
            </Typography.Paragraph>
          ) : (
            <DayTimeline
              rows={timelineBase?.timeline ?? []}
              gamesLegend={timelineBase?.games_legend ?? []}
              loading={timelineLoading || timelineFetching}
              spanSeconds={spanSeconds}
              rangeStart={timelineStart}
              emptyText="该时段暂无记录"
              showMemberLabel={false}
            />
          )}

          <Typography.Title level={5} style={{ marginTop: 32 }}>
            近期会话
          </Typography.Title>
          <Table
            rowKey="id"
            dataSource={data.recent_sessions}
            pagination={{ pageSize: 10 }}
            locale={{ emptyText: <Empty description="暂无会话" /> }}
            columns={[
              {
                title: "开始",
                dataIndex: "started_at",
                render: (value: string) =>
                  formatBeijing(value, "YYYY-MM-DD HH:mm"),
              },
              {
                title: "游戏",
                dataIndex: "game_name",
                render: (_name: string, row) => (
                  <Tooltip
                    {...STORE_TOOLTIP}
                    title={
                      <GameStoreHoverCard
                        appId={row.steam_app_id}
                        fallbackName={row.game_name}
                      />
                    }
                  >
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 8,
                        cursor: "pointer",
                      }}
                      onClick={() =>
                        window.open(
                          steamStoreUrl(row.steam_app_id),
                          "_blank",
                          "noopener,noreferrer",
                        )
                      }
                    >
                      <GameIcon
                        appId={row.steam_app_id}
                        iconUrl={row.icon_url}
                        name={row.game_name}
                        size={24}
                      />
                      {row.game_name}
                    </span>
                  </Tooltip>
                ),
              },
              {
                title: "时长",
                dataIndex: "duration_seconds",
                render: (value: number) => formatDuration(value),
              },
              {
                title: "状态",
                dataIndex: "is_ongoing",
                render: (value: boolean) =>
                  value ? <Tag color="green">进行中</Tag> : <Tag>已结束</Tag>,
              },
            ]}
          />
        </>
      )}
    </div>
  );
}
