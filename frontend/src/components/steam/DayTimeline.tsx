import { Avatar, Empty, Space, Spin, Tag, Tooltip, Typography } from "antd";
import { type Dayjs } from "dayjs";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import type { SteamTimelineRow } from "@/api/types";
import {
  DAY_SECONDS,
  HOUR_MARKS,
  WEEKDAY_LABELS,
} from "@/components/steam/constants";
import { GameStoreHoverCard } from "@/components/steam/GameStoreHoverCard";
import { SegmentHoverTip } from "@/components/steam/SegmentHoverTip";
import { TimelineSegmentLogo } from "@/components/steam/SteamClientIcon";
import {
  hashColor,
  segmentColor,
  steamStoreUrl,
} from "@/components/steam/timelineUtils";

export function DayTimeline({
  rows,
  gamesLegend,
  loading,
  spanSeconds,
  rangeStart,
  emptyText = "暂无绑定 Steam 的圈子成员",
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
  emptyText?: string;
}) {
  const [hoveredAppId, setHoveredAppId] = useState<string | null>(null);
  const [showOffline, setShowOffline] = useState(true);
  const [showOnline, setShowOnline] = useState(true);
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
    return <Empty description={emptyText} />;
  }

  return (
    <Spin spinning={Boolean(loading)} tip="加载统计中…" size="large">
      <div style={{ minHeight: loading && rows.length === 0 ? 280 : undefined }}>
      <Space wrap style={{ marginBottom: 12 }}>
        <Tag
          color="#d9d9d9"
          role="button"
          tabIndex={0}
          onClick={() => setShowOffline((v) => !v)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              setShowOffline((v) => !v);
            }
          }}
          title={showOffline ? "点击隐藏离线段" : "点击显示离线段"}
          style={{
            color: "#595959",
            cursor: "pointer",
            opacity: showOffline ? 1 : 0.35,
            textDecoration: showOffline ? undefined : "line-through",
            userSelect: "none",
            transition: "opacity 0.15s ease",
          }}
        >
          离线
        </Tag>
        <Tag
          color="#5b8ff9"
          role="button"
          tabIndex={0}
          onClick={() => setShowOnline((v) => !v)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              setShowOnline((v) => !v);
            }
          }}
          title={showOnline ? "点击隐藏在线段" : "点击显示在线段"}
          style={{
            cursor: "pointer",
            opacity: showOnline ? 1 : 0.35,
            textDecoration: showOnline ? undefined : "line-through",
            userSelect: "none",
            transition: "opacity 0.15s ease",
          }}
        >
          在线
        </Tag>
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
                <Link
                  to={`/members/${row.member_id}`}
                  style={{ minWidth: 0 }}
                >
                  <Typography.Text
                    ellipsis
                    style={{ maxWidth: 72, fontSize: 13 }}
                    title={row.member_nickname}
                  >
                    {row.member_nickname}
                  </Typography.Text>
                </Link>
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
                  if (seg.status === "offline" && !showOffline) return null;
                  if (seg.status === "online" && !showOnline) return null;
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
