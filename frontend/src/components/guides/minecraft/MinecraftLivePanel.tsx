import { LeftOutlined, RightOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Avatar,
  Button,
  Card,
  DatePicker,
  Radio,
  Space,
  Spin,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { type Dayjs } from "dayjs";
import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import {
  fetchMinecraftPresence,
  fetchMinecraftStatus,
} from "@/api/minecraftApi";
import type { components } from "@/api/generated/schema";
import { apiError } from "@/lib/apiError";
import { nowBeijing, parseBeijing } from "@/lib/time";
import { datePickerLocale } from "@/locales/zhCN";
import {
  DAY_SECONDS,
  HOUR_MARKS,
  WEEKDAY_LABELS,
} from "@/components/steam/constants";
import { formatDuration } from "@/components/steam/format";
import { SegmentHoverTip } from "@/components/steam/SegmentHoverTip";
import {
  DEFAULT_SERVER_ICON,
  displayJoinHost,
  minecraftHeadUrl,
  pingBadge,
} from "./minecraftUi";
import { parseMotdLines, motdColorOnLight } from "./minecraftMotd";
import { PanelFallback } from "@/components/RouteFallback";
import styles from "./MinecraftLivePanel.module.css";

const MinecraftPerfCard = lazy(() =>
  import("./MinecraftPerfCard").then((m) => ({
    default: m.MinecraftPerfCard,
  })),
);

type RosterPlayer = components["schemas"]["MinecraftRosterPlayerOut"];
type PresenceRow = components["schemas"]["MinecraftPresenceRowOut"];

function rosterPlayerKey(row: { name: string; id?: string | null }) {
  const id = (row.id || "").replace(/-/g, "").toLowerCase();
  if (/^[0-9a-f]{32}$/.test(id)) return `id:${id}`;
  const name = (row.name || "").trim().toLowerCase();
  return name ? `name:${name}` : "";
}

function MinecraftMotd({ raw, fallback }: { raw: string; fallback?: string }) {
  const lines = parseMotdLines(raw);
  if (!lines.length) {
    if (!fallback) return null;
    return (
      <div className={styles.motd}>
        <div className={styles.motdLine}>{fallback}</div>
      </div>
    );
  }
  return (
    <div className={styles.motd}>
      {lines.map((spans, lineIdx) => (
        <div key={lineIdx} className={styles.motdLine}>
          {spans.map((span, spanIdx) => (
            <span
              key={spanIdx}
              style={{
                color: motdColorOnLight(span.color),
                fontWeight: span.bold ? 700 : undefined,
                fontStyle: span.italic ? "italic" : undefined,
                textDecoration:
                  [span.underline ? "underline" : "", span.strike ? "line-through" : ""]
                    .filter(Boolean)
                    .join(" ") || undefined,
              }}
            >
              {span.text}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}

function RosterCard({
  roster,
  onlineCount,
  max,
}: {
  roster: RosterPlayer[];
  onlineCount: number;
  max?: number | null;
}) {
  const [granularity, setGranularity] = useState<"day" | "week">("day");
  const [anchor, setAnchor] = useState(() => nowBeijing().startOf("day"));

  const range = useMemo(() => {
    if (granularity === "week") {
      const start = anchor.startOf("isoWeek");
      return {
        start: start.format("YYYY-MM-DD"),
        end: start.endOf("isoWeek").format("YYYY-MM-DD"),
        rangeStart: start,
      };
    }
    const start = anchor.startOf("day");
    return {
      start: start.format("YYYY-MM-DD"),
      end: start.format("YYYY-MM-DD"),
      rangeStart: start,
    };
  }, [granularity, anchor]);

  const presenceQuery = useQuery({
    queryKey: ["minecraft-presence", range.start, range.end],
    queryFn: () => fetchMinecraftPresence(range.start, range.end),
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 1,
  });

  const spanSeconds = presenceQuery.data?.span_seconds || DAY_SECONDS;
  const dayCount = Math.max(1, Math.round(spanSeconds / DAY_SECONDS));
  const isWeek = dayCount > 1;

  const marks = useMemo(() => {
    if (!isWeek) {
      return HOUR_MARKS.map((h) => {
        let label: string;
        if (h < 24) {
          label = range.rangeStart.add(h * 3600, "second").format("HH:mm");
        } else if (range.rangeStart.hour() === 0) {
          label = "24:00";
        } else {
          label = range.rangeStart.add(DAY_SECONDS, "second").format("HH:mm");
        }
        return { at: h * 3600, label };
      });
    }
    return Array.from({ length: dayCount }, (_, i) => {
      const d = range.rangeStart.add(i, "day");
      return {
        at: i * DAY_SECONDS,
        label: `${WEEKDAY_LABELS[d.day() === 0 ? 6 : d.day() - 1]} ${d.format("M/D")}`,
      };
    });
  }, [isWeek, dayCount, range.rangeStart]);

  const rows = useMemo(() => {
    const byKey = new Map<string, PresenceRow>();
    for (const row of presenceQuery.data?.rows ?? []) {
      byKey.set(row.player_key, {
        ...row,
        online: Boolean(row.online),
        segments: [...(row.segments ?? [])],
      });
    }
    for (const live of roster) {
      const key = rosterPlayerKey(live);
      if (!key) continue;
      const hit =
        byKey.get(key) ||
        [...byKey.values()].find(
          (row) => row.name.toLowerCase() === live.name.toLowerCase(),
        );
      if (hit) {
        if (live.online) hit.online = true;
        hit.name = live.name || hit.name;
        if (live.id) hit.id = live.id;
        continue;
      }
      byKey.set(key, {
        player_key: key,
        name: live.name,
        id: live.id || "",
        online: Boolean(live.online),
        online_seconds: 0,
        offline_seconds: 0,
        segments: [],
      });
    }
    return [...byKey.values()].sort((a, b) => {
      if (a.online !== b.online) return a.online ? -1 : 1;
      return a.name.localeCompare(b.name, "en", { sensitivity: "base" });
    });
  }, [presenceQuery.data, roster]);

  const shift = (dir: -1 | 1) => {
    setAnchor((cur) =>
      granularity === "week" ? cur.add(dir, "week") : cur.add(dir, "day"),
    );
  };

  const onAnchorChange = (value: Dayjs | null) => {
    if (!value) return;
    const next = parseBeijing(value.format("YYYY-MM-DD"));
    setAnchor(
      granularity === "week" ? next.startOf("isoWeek") : next.startOf("day"),
    );
  };

  return (
    <Card
      size="small"
      title="玩家"
      extra={`${onlineCount}${max ? ` / ${max}` : ""}`}
    >
      <div className={styles.rosterToolbar}>
        <Space wrap>
          <Tag color="#5b8ff9" style={{ userSelect: "none" }}>
            在线
          </Tag>
        </Space>
        <Space wrap>
          <Radio.Group
            size="small"
            value={granularity}
            onChange={(e) => {
              const next = e.target.value as "day" | "week";
              setGranularity(next);
              setAnchor((cur) =>
                next === "week" ? cur.startOf("isoWeek") : cur.startOf("day"),
              );
            }}
            optionType="button"
            options={[
              { label: "日", value: "day" },
              { label: "周", value: "week" },
            ]}
          />
          <Button type="text" size="small" icon={<LeftOutlined />} onClick={() => shift(-1)} />
          {granularity === "week" ? (
            <DatePicker
              picker="week"
              locale={datePickerLocale}
              size="small"
              value={anchor}
              allowClear={false}
              onChange={onAnchorChange}
              style={{ width: 180 }}
            />
          ) : (
            <DatePicker
              locale={datePickerLocale}
              size="small"
              value={anchor}
              allowClear={false}
              onChange={onAnchorChange}
              style={{ width: 148 }}
            />
          )}
          <Button type="text" size="small" icon={<RightOutlined />} onClick={() => shift(1)} />
        </Space>
      </div>

      {presenceQuery.isError ? (
        <Alert
          type="error"
          showIcon
          message={apiError(presenceQuery.error, "无法读取在线时长")}
          style={{ marginBottom: 12 }}
        />
      ) : null}

      <Spin spinning={presenceQuery.isFetching && !presenceQuery.data}>
        {rows.length ? (
          <div className={styles.rosterScroll}>
            <div
              style={{
                minWidth: isWeek ? Math.max(640, dayCount * 96) : undefined,
              }}
            >
            <div className={styles.rosterMarks}>
              {marks.map((mark) => (
                <div
                  key={mark.at}
                  className={styles.rosterMark}
                  style={{ left: `${(mark.at / spanSeconds) * 100}%` }}
                >
                  {mark.label}
                </div>
              ))}
            </div>
            <div className={styles.rosterShell}>
              {rows.map((row) => (
                <div key={row.player_key} className={styles.rosterRow}>
                  <div className={styles.rosterLabel}>
                    <Avatar
                      size={24}
                      shape="square"
                      src={minecraftHeadUrl(row)}
                      className={`${styles.head}${
                        row.online ? "" : ` ${styles.headOffline}`
                      }`}
                    >
                      {row.name.slice(0, 1)}
                    </Avatar>
                    <span
                      className={`${styles.rosterName}${
                        row.online ? "" : ` ${styles.rosterNameOffline}`
                      }`}
                      title={row.name}
                    >
                      {row.name}
                    </span>
                  </div>
                  <div className={styles.rosterTrack}>
                    {marks
                      .filter((mark) => mark.at > 0 && mark.at < spanSeconds)
                      .map((mark) => (
                        <div
                          key={mark.at}
                          className={styles.rosterTick}
                          style={{ left: `${(mark.at / spanSeconds) * 100}%` }}
                        />
                      ))}
                    {(row.segments ?? []).map((seg, idx) => {
                      if (seg.status !== "online") return null;
                      const left = (seg.start_sec / spanSeconds) * 100;
                      const widthPct =
                        ((seg.end_sec - seg.start_sec) / spanSeconds) * 100;
                      return (
                        <Tooltip
                          key={`${row.player_key}-${idx}`}
                          title={
                            <SegmentHoverTip
                              status="online"
                              startSec={seg.start_sec}
                              endSec={seg.end_sec}
                              spanSeconds={spanSeconds}
                              rangeStart={range.rangeStart}
                            />
                          }
                        >
                          <div
                            className={`${styles.rosterSeg} ${styles.rosterOnline}`}
                            style={{
                              left: `${left}%`,
                              width: `${Math.max(widthPct, 0.08)}%`,
                            }}
                          />
                        </Tooltip>
                      );
                    })}
                  </div>
                  <span
                    className={styles.rosterDuration}
                    title={
                      row.online_seconds
                        ? formatDuration(row.online_seconds)
                        : "轮询开始后才会累计时长"
                    }
                  >
                    {row.segments?.length
                      ? formatDuration(row.online_seconds)
                      : "—"}
                  </span>
                </div>
              ))}
            </div>
            </div>
          </div>
        ) : (
          <Typography.Text type="secondary">当前没有可显示的玩家</Typography.Text>
        )}
      </Spin>
    </Card>
  );
}

export function MinecraftLivePanel() {
  const statusQuery = useQuery({
    queryKey: ["minecraft-status"],
    queryFn: fetchMinecraftStatus,
    refetchInterval: 10_000,
    retry: 1,
  });

  const status = statusQuery.data;
  const applied = status?.applied;
  const [iconFailed, setIconFailed] = useState(false);

  useEffect(() => {
    setIconFailed(false);
  }, [status?.favicon]);

  const badge = pingBadge(
    Boolean(status?.ping_online),
    status?.power_state,
    status?.rcon_connected,
  );
  const iconSrc =
    !iconFailed && status?.favicon ? status.favicon : DEFAULT_SERVER_ICON;
  const motdRaw =
    status?.motd_raw || status?.motd || applied?.properties?.motd || "";
  const motdFallback = status?.ping_online || status?.rcon_connected
    ? "A Minecraft Server"
    : statusQuery.isLoading
      ? ""
      : "无法连接";
  const joinHost = displayJoinHost({
    publicHost: status?.public_host,
    address: status?.address,
  });
  const versionLabel = applied?.mc_version || status?.version_name || "";
  const onlineCount = status?.players_online || 0;
  const roster = useMemo(() => {
    if (status?.roster?.length) return status.roster;
    return (status?.players || []).map((row) => ({ ...row, online: true }));
  }, [status]);

  return (
    <div className={styles.wrap}>
      {statusQuery.isError ? (
        <Alert
          type="error"
          showIcon
          message={apiError(statusQuery.error, "无法读取服况")}
        />
      ) : null}
      {status && status.pelican_configured === false ? (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="服务器尚未接入"
          description="请联系管理员配置 Pelican 面板后即可查看服况。"
        />
      ) : null}

      <Card size="small" title="服况">
        {statusQuery.isLoading && !status ? (
          <div className={`${styles.hero} ${styles.heroLoading}`}>
            <div className={styles.skelIcon} />
            <div className={styles.skelBody}>
              <div className={styles.skelLine} />
              <div className={`${styles.skelLine} ${styles.skelLineShort}`} />
            </div>
          </div>
        ) : (
          <div className={styles.hero}>
            <img
              className={styles.icon}
              src={iconSrc}
              alt=""
              width={64}
              height={64}
              onError={() => setIconFailed(true)}
            />
            <div className={styles.body}>
              <div className={styles.titleBlock}>
                <MinecraftMotd raw={motdRaw} fallback={motdFallback} />
                {joinHost ? (
                  <div className={styles.joinHost}>{joinHost}</div>
                ) : null}
              </div>
              <div className={styles.badge}>
                <span
                  className={`${styles.dot} ${
                    badge.kind === "online"
                      ? styles.dotOnline
                      : badge.kind === "busy"
                        ? styles.dotBusy
                        : ""
                  }`}
                />
                {badge.text}
              </div>
              {status?.message && !status.ping_online ? (
                <span className={styles.version}>{status.message}</span>
              ) : null}
            </div>
            <div className={styles.side}>
              <div className={styles.players}>
                {status ? `${onlineCount} / ${status.players_max || "—"}` : "—"}
              </div>
              <div className={styles.latency}>
                {status?.latency_ms != null ? `${status.latency_ms} ms` : " "}
              </div>
              {versionLabel ? (
                <div className={styles.version}>{versionLabel}</div>
              ) : null}
            </div>
          </div>
        )}
      </Card>

      <RosterCard
        roster={roster}
        onlineCount={onlineCount}
        max={status?.players_max}
      />

      <Suspense fallback={<PanelFallback tip="加载性能图…" />}>
        <MinecraftPerfCard />
      </Suspense>
    </div>
  );
}
