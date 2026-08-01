import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Avatar,
  Button,
  DatePicker,
  Empty,
  Radio,
  Space,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchSteamDay,
  fetchSteamNow,
  fetchSteamAppStore,
  triggerSteamPoll,
} from "@/api/client";
import type {
  SteamNowItem,
  SteamTimelineRow,
} from "@/api/types";
import { PageHeader } from "@/components/PageHeader";
import { datePickerLocale } from "@/locales/zhCN";
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

function steamStoreUrl(appId: string): string {
  return `https://store.steampowered.com/app/${encodeURIComponent(appId)}`;
}

function steamLibraryCapsuleUrl(appId: string): string {
  return `https://cdn.cloudflare.steamstatic.com/steam/apps/${encodeURIComponent(appId)}/library_600x900.jpg`;
}

function GameIcon({
  appId,
  iconUrl,
  name,
  size = 40,
}: {
  appId?: string | null;
  iconUrl?: string | null;
  name: string;
  size?: number;
}) {
  const candidates = useMemo(() => {
    const list: string[] = [];
    if (iconUrl) list.push(iconUrl);
    if (appId) {
      const library = steamLibraryCapsuleUrl(appId);
      if (!list.includes(library)) list.push(library);
    }
    return list;
  }, [appId, iconUrl]);
  const [idx, setIdx] = useState(0);
  useEffect(() => setIdx(0), [candidates]);
  const src = candidates[idx];

  return (
    <Avatar
      shape="square"
      size={size}
      src={src}
      onError={() => {
        if (idx + 1 < candidates.length) {
          setIdx((v) => v + 1);
          return false;
        }
        return true;
      }}
      style={{ flexShrink: 0, background: "#1b2838" }}
    >
      {name[0]}
    </Avatar>
  );
}

function sessionDurationSeconds(
  item: SteamNowItem,
  fetchedAtMs: number,
  nowMs: number,
): number {
  // 以服务端已算好的 UTC 时长为准，再叠加自拉取后的流逝时间，避免本地误解析时区
  const elapsed = Math.max(0, Math.floor((nowMs - fetchedAtMs) / 1000));
  return Math.max(0, item.duration_seconds + elapsed);
}

type NowPlayingGroup = {
  steam_app_id: string;
  game_name: string;
  icon_url?: string | null;
  players: SteamNowItem[];
};

function groupNowPlaying(items: SteamNowItem[]): NowPlayingGroup[] {
  const map = new Map<string, NowPlayingGroup>();
  for (const item of items) {
    const key = item.steam_app_id || item.game_name;
    let group = map.get(key);
    if (!group) {
      group = {
        steam_app_id: item.steam_app_id,
        game_name: item.game_name,
        icon_url: item.icon_url,
        players: [],
      };
      map.set(key, group);
    }
    group.players.push(item);
    if (!group.icon_url && item.icon_url) {
      group.icon_url = item.icon_url;
    }
  }
  return Array.from(map.values()).sort((a, b) => {
    const byCount = b.players.length - a.players.length;
    if (byCount !== 0) return byCount;
    return a.game_name.localeCompare(b.game_name, "zh");
  });
}

function NowPlayingPanel({ items }: { items: SteamNowItem[] }) {
  const groups = useMemo(() => groupNowPlaying(items), [items]);
  const fetchedAtRef = useRef(Date.now());
  const [nowMs, setNowMs] = useState(Date.now());
  useEffect(() => {
    fetchedAtRef.current = Date.now();
    setNowMs(Date.now());
  }, [items]);
  useEffect(() => {
    const timer = window.setInterval(() => setNowMs(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div style={{ marginBottom: 16 }}>
      <Typography.Text type="secondary">正在游玩</Typography.Text>
      <div
        style={{
          marginTop: 10,
          display: "flex",
          flexDirection: "row",
          flexWrap: "nowrap",
          alignItems: "stretch",
          gap: 12,
          overflowX: "auto",
          overflowY: "hidden",
          paddingBottom: 6,
          WebkitOverflowScrolling: "touch",
        }}
      >
        {groups.map((group) => (
          <div
            key={group.steam_app_id || group.game_name}
            style={{
              width: 260,
              flex: "0 0 260px",
              boxSizing: "border-box",
              border: "1px solid #f0f0f0",
              borderRadius: 10,
              background: "#fff",
              boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "10px 12px",
                background: "#fafafa",
                borderBottom: "1px solid #f0f0f0",
                cursor: group.steam_app_id ? "pointer" : "default",
              }}
              onClick={() => {
                if (group.steam_app_id) {
                  window.open(
                    steamStoreUrl(group.steam_app_id),
                    "_blank",
                    "noopener,noreferrer",
                  );
                }
              }}
            >
              <GameIcon
                appId={group.steam_app_id}
                iconUrl={group.icon_url}
                name={group.game_name}
                size={40}
              />
              <div style={{ minWidth: 0, flex: 1 }}>
                <div
                  style={{
                    fontWeight: 600,
                    fontSize: 13,
                    lineHeight: 1.35,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                  title={group.game_name}
                >
                  {group.game_name}
                </div>
                <div style={{ fontSize: 12, color: "rgba(0,0,0,0.45)", marginTop: 2 }}>
                  {group.players.length} 人在玩
                </div>
              </div>
            </div>
            <div
              style={{
                padding: "8px 10px 10px",
                display: "flex",
                flexDirection: "column",
                gap: 8,
                flex: 1,
              }}
            >
              {group.players.map((p) => (
                <div
                  key={p.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    minHeight: 36,
                  }}
                >
                  <Avatar size={28} src={p.avatar_url || undefined}>
                    {p.member_nickname[0]}
                  </Avatar>
                  <div style={{ minWidth: 0, flex: 1, lineHeight: 1.3 }}>
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 500,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                      title={p.member_nickname}
                    >
                      {p.member_nickname}
                    </div>
                    <div style={{ fontSize: 12, color: "#52c41a" }}>
                      本次{" "}
                      {formatDuration(
                        sessionDurationSeconds(p, fetchedAtRef.current, nowMs),
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function GameStoreHoverCard({
  appId,
  fallbackName,
}: {
  appId: string;
  fallbackName: string;
}) {
  const { data: card, isLoading, isError } = useQuery({
    queryKey: ["steam-app-store", appId],
    queryFn: () => fetchSteamAppStore(appId),
    staleTime: 30 * 60 * 1000,
    retry: 1,
  });

  const title = card?.name || fallbackName;

  return (
    <div
      style={{
        width: 240,
        boxSizing: "border-box",
        overflow: "hidden",
        background: "#fff",
        color: "rgba(0,0,0,0.88)",
        lineHeight: 1.4,
      }}
    >
      <div
        style={{
          width: "100%",
          height: 112,
          background: "#1b2838",
          overflow: "hidden",
          lineHeight: 0,
        }}
      >
        {card?.header_image ? (
          <img
            src={card.header_image}
            alt={title}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              objectPosition: "center",
              display: "block",
            }}
          />
        ) : (
          <div
            style={{
              height: "100%",
              minHeight: 80,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "rgba(255,255,255,0.65)",
              fontSize: 12,
              lineHeight: 1.4,
            }}
          >
            {isLoading ? "加载中…" : isError ? "暂无宣传图" : "加载中…"}
          </div>
        )}
      </div>
      <div style={{ padding: "10px 12px 12px", boxSizing: "border-box" }}>
        <div
          style={{
            fontWeight: 600,
            fontSize: 13,
            lineHeight: 1.35,
            marginBottom: 6,
            wordBreak: "break-word",
          }}
        >
          {title}
        </div>
        {card?.short_description ? (
          <div
            style={{
              fontSize: 12,
              color: "rgba(0,0,0,0.55)",
              lineHeight: 1.45,
              marginBottom: 10,
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
              wordBreak: "break-word",
            }}
          >
            {card.short_description}
          </div>
        ) : null}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 8,
            minHeight: 22,
          }}
        >
          {isLoading && !card ? (
            <span style={{ fontSize: 12, color: "rgba(0,0,0,0.45)" }}>获取价格…</span>
          ) : card?.is_free ? (
            <span style={{ fontSize: 14, fontWeight: 700, color: "#2ecc71" }}>免费</span>
          ) : card?.final_formatted ? (
            <>
              {(card.discount_percent ?? 0) > 0 ? (
                <span
                  style={{
                    background: "#4c6b22",
                    color: "#beee11",
                    fontWeight: 700,
                    fontSize: 12,
                    padding: "1px 6px",
                    borderRadius: 2,
                  }}
                >
                  -{card.discount_percent}%
                </span>
              ) : null}
              {(card.discount_percent ?? 0) > 0 && card.initial_formatted ? (
                <span
                  style={{
                    fontSize: 12,
                    color: "rgba(0,0,0,0.45)",
                    textDecoration: "line-through",
                  }}
                >
                  {card.initial_formatted}
                </span>
              ) : null}
              <span style={{ fontSize: 14, fontWeight: 700, color: "#acbf2f" }}>
                {card.final_formatted}
              </span>
            </>
          ) : (
            <span style={{ fontSize: 12, color: "rgba(0,0,0,0.45)" }}>暂无价格信息</span>
          )}
        </div>
      </div>
    </div>
  );
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
  const [hoveredAppId, setHoveredAppId] = useState<string | null>(null);
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
        {gamesLegend.map((g) => {
          const active = hoveredAppId === g.steam_app_id;
          const dimmed = Boolean(hoveredAppId) && !active;
          return (
            <Tooltip
              key={g.steam_app_id}
              color="#ffffff"
              mouseEnterDelay={0.25}
              destroyTooltipOnHide
              overlayInnerStyle={{
                padding: 0,
                overflow: "hidden",
                borderRadius: 8,
                minHeight: 0,
                minWidth: 0,
                boxShadow: "0 6px 16px rgba(0,0,0,0.12)",
              }}
              title={
                <GameStoreHoverCard
                  appId={g.steam_app_id}
                  fallbackName={g.game_name}
                />
              }
            >
              <Tag
                color={hashColor(g.steam_app_id)}
                onMouseEnter={() => setHoveredAppId(g.steam_app_id)}
                onMouseLeave={() => setHoveredAppId(null)}
                onClick={() =>
                  window.open(steamStoreUrl(g.steam_app_id), "_blank", "noopener,noreferrer")
                }
                style={{
                  cursor: "pointer",
                  opacity: dimmed ? 0.35 : 1,
                  outline: active ? "2px solid rgba(0,0,0,0.45)" : undefined,
                  outlineOffset: 1,
                  transition: "opacity 0.15s ease, outline-color 0.15s ease",
                  userSelect: "none",
                }}
              >
                {g.game_name}
              </Tag>
            </Tooltip>
          );
        })}
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
                  const isMatch =
                    hoveredAppId != null &&
                    seg.status === "playing" &&
                    seg.steam_app_id === hoveredAppId;
                  const isDimmed = hoveredAppId != null && !isMatch;
                  return (
                    <Tooltip key={`${row.member_id}-${idx}`} title={title}>
                      <div
                        style={{
                          position: "absolute",
                          left: `${left}%`,
                          width: `${Math.max(width, 0.08)}%`,
                          top: isMatch ? 1 : 3,
                          bottom: isMatch ? 1 : 3,
                          background: color,
                          borderRadius: 3,
                          minWidth: 2,
                          opacity: isDimmed ? 0.18 : 1,
                          boxShadow: isMatch
                            ? "0 0 0 1px rgba(0,0,0,0.35), 0 0 6px rgba(0,0,0,0.25)"
                            : undefined,
                          zIndex: isMatch ? 2 : 1,
                          transition:
                            "opacity 0.15s ease, top 0.15s ease, bottom 0.15s ease",
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


export default function SteamCalendarPage() {
  const queryClient = useQueryClient();
  const isAdmin = useAuthStore((s) => s.user?.is_admin);
  const [granularity, setGranularity] = useState<Granularity>("day");
  const [anchor, setAnchor] = useState(dayjs());

  const weekRangeStart = useMemo(() => anchor.startOf("isoWeek"), [anchor]);
  const weekRangeEnd = useMemo(
    () => weekRangeStart.endOf("isoWeek"),
    [weekRangeStart],
  );

  const dayQueryDate = anchor.format("YYYY-MM-DD");
  const isPendingGranularity =
    granularity === "month" || granularity === "year";

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
    enabled: Boolean(timelineRange?.start),
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
      queryClient.invalidateQueries({ queryKey: ["steam-timeline"] });
      queryClient.invalidateQueries({ queryKey: ["steam-now"] });
    },
    onError: () => message.error("轮询请求失败"),
  });

  const shift = (dir: -1 | 1) => {
    if (granularity === "day") setAnchor((d) => d.add(dir, "day"));
    else if (granularity === "week") setAnchor((d) => d.add(dir, "week"));
  };

  const spanSeconds =
    timelineData?.span_seconds ??
    (granularity === "week" ? 7 * DAY_SECONDS : DAY_SECONDS);
  const timelineStart = dayjs(
    timelineData?.range_start ??
      (granularity === "week"
        ? weekRangeStart.format("YYYY-MM-DD")
        : dayQueryDate),
  );

  return (
    <div>
      <PageHeader
        title="今天玩什么"
        subtitle="仅显示你与 Steam 好友 · 日/周时间轴"
        extra={
          isAdmin ? (
            <Button loading={poll.isPending} onClick={() => poll.mutate()}>
              立即轮询
            </Button>
          ) : null
        }
      />

      {timelineData?.visibility?.hint && (
        <Alert
          type={
            timelineData.visibility.friends_list_public === false
              ? "warning"
              : "info"
          }
          showIcon
          style={{ marginBottom: 16 }}
          message={timelineData.visibility.hint}
        />
      )}

      {nowPlaying && nowPlaying.length > 0 ? (
        <NowPlayingPanel items={nowPlaying} />
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
        {!isPendingGranularity && (
          <>
            <Button onClick={() => shift(-1)}>上一段</Button>
            {granularity === "week" ? (
              <DatePicker
                picker="week"
                locale={datePickerLocale}
                value={anchor}
                allowClear={false}
                onChange={(d) => d && setAnchor(d.startOf("isoWeek"))}
                style={{ width: 180 }}
              />
            ) : (
              <DatePicker
                locale={datePickerLocale}
                value={anchor}
                allowClear={false}
                onChange={(d) => d && setAnchor(d)}
                style={{ width: 150 }}
              />
            )}
            <Button onClick={() => shift(1)}>下一段</Button>
          </>
        )}
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
        <Empty description="月统计待开发" style={{ marginTop: 48 }} />
      )}
      {granularity === "year" && (
        <Empty description="年统计待开发" style={{ marginTop: 48 }} />
      )}
    </div>
  );
}
