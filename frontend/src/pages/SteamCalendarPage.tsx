import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LoadingOutlined } from "@ant-design/icons";
import {
  Alert,
  Avatar,
  Button,
  DatePicker,
  Empty,
  Radio,
  Space,
  Spin,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import { type Dayjs } from "dayjs";
import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import {
  fetchSteamDay,
  fetchSteamNow,
  fetchSteamAppStore,
  triggerSteamPoll,
} from "@/api/client";
import type {
  SteamDayData,
  SteamNowItem,
  SteamTimelineRow,
} from "@/api/types";
import { PageHeader } from "@/components/PageHeader";
import { datePickerLocale } from "@/locales/zhCN";
import { nowBeijing, parseBeijing } from "@/lib/time";
import {
  loadSteamClientIcon,
  rememberSteamIcons,
  resolveSteamIcon,
} from "@/lib/steamIconCache";
import { useAuthStore } from "@/stores/authStore";

type Granularity = "day" | "week" | "month" | "year";

const DAY_SECONDS = 86400;
const HOUR_MARKS = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24];
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

/** 悬浮时段后缀：不足 1 小时「xx分钟」，否则「xx小时xx分钟」。 */
function formatPlayDuration(seconds: number): string {
  if (seconds < 60) return "不足1分钟";
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}分钟`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return rm ? `${h}小时${rm}分钟` : `${h}小时`;
}

function formatClock(sec: number, spanSeconds: number, rangeStart: Dayjs): string {
  const s = Math.max(0, Math.min(spanSeconds, Math.floor(sec)));
  const t = rangeStart.add(s, "second");
  if (spanSeconds <= DAY_SECONDS) {
    return t.format("HH:mm");
  }
  return t.format("M/D HH:mm");
}

function SegmentHoverTip({
  status,
  gameName,
  appId,
  iconUrl,
  startSec,
  endSec,
  spanSeconds,
  rangeStart,
}: {
  status: string;
  gameName?: string | null;
  appId?: string | null;
  iconUrl?: string | null;
  startSec: number;
  endSec: number;
  spanSeconds: number;
  rangeStart: Dayjs;
}) {
  const timeRange = `${formatClock(startSec, spanSeconds, rangeStart)}~${formatClock(endSec, spanSeconds, rangeStart)}`;
  const timeLine = `${timeRange}（${formatPlayDuration(Math.max(0, endSec - startSec))}）`;
  if (status === "playing") {
    return (
      <div style={{ maxWidth: 280, lineHeight: 1.35 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            minWidth: 0,
          }}
        >
          {appId ? (
            <TimelineSegmentLogo appId={appId} iconUrl={iconUrl} size={28} />
          ) : null}
          <span
            style={{
              fontWeight: 600,
              fontSize: 13,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {gameName || "游戏中"}
          </span>
        </div>
        <div style={{ marginTop: 6, fontSize: 12, opacity: 0.9 }}>
          {timeLine}
        </div>
      </div>
    );
  }
  const label = status === "online" ? "在线" : "离线";
  return (
    <div style={{ lineHeight: 1.35 }}>
      <div style={{ fontWeight: 600, fontSize: 13 }}>{label}</div>
      <div style={{ marginTop: 6, fontSize: 12, opacity: 0.9 }}>
        {timeLine}
      </div>
    </div>
  );
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

function steamStoreUrl(appId: string): string {
  return `https://store.steampowered.com/app/${encodeURIComponent(appId)}`;
}

function IconPlaceholder({ size }: { size: number }) {
  return (
    <span
      aria-hidden
      style={{
        width: size,
        height: size,
        borderRadius: 2,
        flexShrink: 0,
        display: "inline-block",
        background: "#d9d9d9",
        boxShadow: "inset 0 0 0 1px rgba(0,0,0,0.08)",
      }}
    />
  );
}

function IconLoading({ size }: { size: number }) {
  return (
    <span
      aria-busy
      aria-label="加载图标"
      style={{
        width: size,
        height: size,
        borderRadius: 2,
        flexShrink: 0,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0,0,0,0.04)",
        boxShadow: "inset 0 0 0 1px rgba(0,0,0,0.06)",
      }}
    >
      <LoadingOutlined
        spin
        style={{
          fontSize: Math.max(10, Math.round(size * 0.5)),
          color: "rgba(0,0,0,0.35)",
        }}
      />
    </span>
  );
}

/** 库列表 client icon：异步补全时转圈，真失败才灰块。 */
function SteamClientIcon({
  appId,
  iconUrl,
  size,
  imgStyle,
}: {
  appId?: string | null;
  iconUrl?: string | null;
  size: number;
  imgStyle?: CSSProperties;
}) {
  const known = useMemo(
    () => resolveSteamIcon(appId, iconUrl),
    [appId, iconUrl],
  );
  const [src, setSrc] = useState<string | null>(known);
  const [phase, setPhase] = useState<"loading" | "ready" | "failed">(() =>
    known ? "ready" : appId ? "loading" : "failed",
  );
  const [imgFailed, setImgFailed] = useState(false);

  useEffect(() => {
    const resolved = resolveSteamIcon(appId, iconUrl);
    if (resolved) {
      setSrc(resolved);
      setPhase("ready");
      setImgFailed(false);
      return;
    }
    if (!appId) {
      setSrc(null);
      setPhase("failed");
      return;
    }
    let cancelled = false;
    setPhase("loading");
    setImgFailed(false);
    void loadSteamClientIcon(appId).then((url) => {
      if (cancelled) return;
      if (url) {
        setSrc(url);
        setPhase("ready");
      } else {
        setSrc(null);
        setPhase("failed");
      }
    });
    return () => {
      cancelled = true;
    };
  }, [appId, iconUrl]);

  if (phase === "loading") return <IconLoading size={size} />;
  if (phase === "failed" || !src || imgFailed) {
    return <IconPlaceholder size={size} />;
  }
  return (
    <img
      key={src}
      src={src}
      alt=""
      draggable={false}
      referrerPolicy="no-referrer"
      onError={() => setImgFailed(true)}
      style={{
        width: size,
        height: size,
        objectFit: "cover",
        objectPosition: "center",
        borderRadius: 2,
        flexShrink: 0,
        display: "block",
        background: "#d9d9d9",
        ...imgStyle,
      }}
    />
  );
}

function TimelineSegmentLogo({
  appId,
  iconUrl,
  size,
}: {
  appId: string;
  iconUrl?: string | null;
  size: number;
}) {
  return (
    <SteamClientIcon
      appId={appId}
      iconUrl={iconUrl}
      size={size}
      imgStyle={{ boxShadow: "0 0 0 1px rgba(0,0,0,0.2)" }}
    />
  );
}

function GameIcon({
  appId,
  iconUrl,
  size = 40,
}: {
  appId?: string | null;
  iconUrl?: string | null;
  name: string;
  size?: number;
}) {
  return <SteamClientIcon appId={appId} iconUrl={iconUrl} size={size} />;
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
        {groups.map((group) => {
          const header = (
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
          );
          return (
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
            {group.steam_app_id ? (
              <Tooltip
                placement="top"
                autoAdjustOverflow={false}
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
                    appId={group.steam_app_id}
                    fallbackName={group.game_name}
                  />
                }
              >
                {header}
              </Tooltip>
            ) : (
              header
            )}
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
          );
        })}
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

/** 把「自然日×2」的接口结果裁成从中午起的 24 小时窗口（查询仍用 date/end）。 */
function clipTimelineToNoonWindow(data: SteamDayData): SteamDayData {
  const shift = 12 * 3600;
  const windowEnd = shift + DAY_SECONDS;
  const baseStart = parseBeijing(data.range_start ?? data.date);
  const clippedRows: SteamTimelineRow[] = (data.timeline ?? []).map((row) => ({
    ...row,
    segments: row.segments
      .map((seg) => {
        const start = Math.max(seg.start_sec, shift);
        const end = Math.min(seg.end_sec, windowEnd);
        if (end <= start) return null;
        return {
          ...seg,
          start_sec: start - shift,
          end_sec: end - shift,
        };
      })
      .filter((s): s is NonNullable<typeof s> => s != null),
  }));
  const legend = new Map<string, { game_name: string; icon_url?: string | null }>();
  for (const row of clippedRows) {
    for (const seg of row.segments) {
      if (seg.status === "playing" && seg.steam_app_id) {
        const prev = legend.get(seg.steam_app_id);
        legend.set(seg.steam_app_id, {
          game_name: seg.game_name || prev?.game_name || `App ${seg.steam_app_id}`,
          icon_url: seg.icon_url || prev?.icon_url,
        });
      }
    }
  }
  return {
    ...data,
    range_start: baseStart.add(12, "hour").toISOString(),
    range_end: baseStart.add(36, "hour").toISOString(),
    span_seconds: DAY_SECONDS,
    timeline: clippedRows,
    games_legend: Array.from(legend, ([steam_app_id, meta]) => ({
      steam_app_id,
      game_name: meta.game_name,
      icon_url: meta.icon_url,
    })),
  };
}

function TimelineChart({
  rows,
  gamesLegend,
  loading,
  spanSeconds,
  rangeStart,
}: {
  rows: SteamTimelineRow[];
  gamesLegend: {
    steam_app_id: string;
    game_name: string;
    icon_url?: string | null;
  }[];
  loading?: boolean;
  spanSeconds: number;
  rangeStart: Dayjs;
}) {
  const [hoveredAppId, setHoveredAppId] = useState<string | null>(null);
  const [trackWidth, setTrackWidth] = useState(0);
  const trackMeasureRef = useRef<HTMLDivElement>(null);
  const labelWidth = 112;
  const trackHeight = 28;
  const rowGap = 10;
  const logoSize = 18;
  const dayCount = Math.max(1, Math.round(spanSeconds / DAY_SECONDS));
  const isWeek = dayCount > 1;

  useEffect(() => {
    const el = trackMeasureRef.current;
    if (!el) return;
    const update = () => setTrackWidth(el.getBoundingClientRect().width);
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [rows.length, loading, spanSeconds]);

  const marks = useMemo(() => {
    if (!isWeek) {
      return HOUR_MARKS.map((h) => {
        let label: string;
        if (h < 24) {
          label = rangeStart.add(h * 3600, "second").format("HH:mm");
        } else if (rangeStart.hour() === 0 && rangeStart.minute() === 0) {
          // 自然日终点展示 24:00，避免滚成次日 00:00
          label = "24:00";
        } else {
          label = rangeStart.add(DAY_SECONDS, "second").format("HH:mm");
        }
        return { at: h * 3600, label };
      });
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
    <Spin spinning={Boolean(loading)} tip="加载统计中…" size="large">
      <div style={{ minHeight: loading && rows.length === 0 ? 280 : undefined }}>
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
              placement="top"
              autoAdjustOverflow={false}
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
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <TimelineSegmentLogo
                  appId={g.steam_app_id}
                  iconUrl={g.icon_url}
                  size={14}
                />
                {g.game_name}
              </Tag>
            </Tooltip>
          );
        })}
      </Space>

      <div
        ref={trackMeasureRef}
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
                  const widthPct =
                    ((seg.end_sec - seg.start_sec) / spanSeconds) * 100;
                  const segPx =
                    trackWidth > 0
                      ? ((seg.end_sec - seg.start_sec) / spanSeconds) * trackWidth
                      : 0;
                  const color = segmentColor(seg.status, seg.steam_app_id);
                  const isMatch =
                    hoveredAppId != null &&
                    seg.status === "playing" &&
                    seg.steam_app_id === hoveredAppId;
                  const isDimmed = hoveredAppId != null && !isMatch;
                  const showLogo =
                    seg.status === "playing" &&
                    Boolean(seg.steam_app_id) &&
                    (trackWidth <= 0 || segPx >= logoSize + 2);
                  return (
                    <Tooltip
                      key={`${row.member_id}-${idx}`}
                      title={
                        <SegmentHoverTip
                          status={seg.status}
                          gameName={seg.game_name}
                          appId={seg.steam_app_id}
                          iconUrl={seg.icon_url}
                          startSec={seg.start_sec}
                          endSec={seg.end_sec}
                          spanSeconds={spanSeconds}
                          rangeStart={rangeStart}
                        />
                      }
                    >
                      <div
                        style={{
                          position: "absolute",
                          left: `${left}%`,
                          width: `${Math.max(widthPct, 0.08)}%`,
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
                          display: "flex",
                          alignItems: "center",
                          overflow: "hidden",
                          paddingLeft: showLogo ? 2 : 0,
                          boxSizing: "border-box",
                        }}
                      >
                        {showLogo && seg.steam_app_id ? (
                          <TimelineSegmentLogo
                            appId={seg.steam_app_id}
                            iconUrl={seg.icon_url}
                            size={logoSize}
                          />
                        ) : null}
                      </div>
                    </Tooltip>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
      </div>
    </Spin>
  );
}


export default function SteamCalendarPage() {
  const queryClient = useQueryClient();
  const isAdmin = useAuthStore((s) => s.user?.is_admin);
  const [granularity, setGranularity] = useState<Granularity>("day");
  const [anchor, setAnchor] = useState(() => nowBeijing().startOf("day"));
  /** 日视图：0=自然日 00:00–24:00；12=跨夜窗 12:00–次日 12:00 */
  const [dayStartHour, setDayStartHour] = useState<0 | 12>(0);

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
  const isPendingGranularity =
    granularity === "month" || granularity === "year";

  const timelineRange =
    granularity === "week"
      ? {
          start: weekRangeStart.format("YYYY-MM-DD"),
          end: weekRangeEnd.format("YYYY-MM-DD"),
        }
      : granularity === "day"
        ? { start: dayQueryDate, end: dayQueryEnd }
        : null;

  const timelineEnabled = Boolean(timelineRange?.start);

  const {
    data: timelineRaw,
    isLoading: timelineLoading,
    isFetching: timelineFetching,
  } = useQuery({
    queryKey: [
      "steam-timeline",
      timelineRange?.start,
      timelineRange?.end,
      granularity === "day" ? dayStartHour : 0,
    ],
    queryFn: () =>
      fetchSteamDay(timelineRange!.start, timelineRange!.end),
    enabled: timelineEnabled,
    staleTime: 60_000,
  });

  const timelineBase = useMemo(() => {
    if (!timelineRaw) return timelineRaw;
    if (granularity === "day" && dayStartHour === 12) {
      return clipTimelineToNoonWindow(timelineRaw);
    }
    return timelineRaw;
  }, [timelineRaw, granularity, dayStartHour]);

  const timelineData = timelineBase;

  useEffect(() => {
    if (!timelineBase) return;
    const entries: { appId?: string | null; iconUrl?: string | null }[] = [];
    for (const g of timelineBase.games_legend ?? []) {
      entries.push({ appId: g.steam_app_id, iconUrl: g.icon_url });
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

  const { data: nowPlaying } = useQuery({
    queryKey: ["steam-now"],
    queryFn: () => fetchSteamNow(),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (!nowPlaying?.length) return;
    rememberSteamIcons(
      nowPlaying.map((p) => ({
        appId: p.steam_app_id,
        iconUrl: p.icon_url,
      })),
    );
  }, [nowPlaying]);

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
    if (granularity === "week") {
      setAnchor((d) => d.add(dir, "week"));
      return;
    }
    if (granularity !== "day") return;
    // ±12 小时：在 00:00 窗与 12:00 窗之间切换，必要时挪日历日
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
    timelineData?.span_seconds ??
    (granularity === "week" ? 7 * DAY_SECONDS : DAY_SECONDS);
  const timelineStart = useMemo(() => {
    if (timelineData?.range_start) {
      return parseBeijing(timelineData.range_start);
    }
    if (granularity === "week") {
      return weekRangeStart;
    }
    return dayStartHour === 12 ? anchor.hour(12).minute(0).second(0) : anchor;
  }, [
    timelineData?.range_start,
    granularity,
    weekRangeStart,
    anchor,
    dayStartHour,
  ]);

  return (
    <div>
      <PageHeader
        title="Steam"
        subtitle={
          isAdmin
            ? "管理员可见全部成员 · 日/周时间轴"
            : "仅显示你与 Steam 好友 · 日/周时间轴"
        }
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
          onChange={(e) => {
            setGranularity(e.target.value);
            setDayStartHour(0);
          }}
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
            <Button onClick={() => shift(-1)}>
              {granularity === "day" ? "向前12小时" : "上一段"}
            </Button>
            {granularity === "week" ? (
              <DatePicker
                picker="week"
                locale={datePickerLocale}
                value={anchor}
                allowClear={false}
                onChange={(d) =>
                  d &&
                  setAnchor(
                    parseBeijing(d.format("YYYY-MM-DD")).startOf("isoWeek"),
                  )
                }
                style={{ width: 180 }}
              />
            ) : (
              <DatePicker
                className="day-window-picker"
                locale={datePickerLocale}
                value={anchor}
                allowClear={false}
                format={(value) => {
                  const start = value.startOf("day");
                  if (dayStartHour === 12) {
                    const a = start.hour(12);
                    const b = start.add(1, "day").hour(12);
                    return `${a.format("YYYY-MM-DD HH:mm")} ~ ${b.format("YYYY-MM-DD HH:mm")}`;
                  }
                  return `${start.format("YYYY-MM-DD")} 00:00 ~ ${start.format("YYYY-MM-DD")} 24:00`;
                }}
                onChange={(d) => {
                  if (!d) return;
                  setDayStartHour(0);
                  setAnchor(parseBeijing(d.format("YYYY-MM-DD")).startOf("day"));
                }}
                style={{ width: 320 }}
              />
            )}
            <Button onClick={() => shift(1)}>
              {granularity === "day" ? "向后12小时" : "下一段"}
            </Button>
          </>
        )}
      </Space>

      {(granularity === "day" || granularity === "week") && (
        <TimelineChart
          rows={timelineData?.timeline ?? []}
          gamesLegend={timelineData?.games_legend ?? []}
          loading={timelineLoading || timelineFetching}
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
