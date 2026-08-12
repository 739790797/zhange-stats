import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Empty, message } from "antd";
import { useEffect, useMemo, useState } from "react";

import {
  fetchSteamDay,
  fetchSteamNow,
  startSteamOpenIdBind,
  triggerSteamPoll,
} from "@/api/client";
import { DayTimeline } from "@/components/steam/DayTimeline";
import { DAY_SECONDS, type Granularity } from "@/components/steam/constants";
import { NowPlayingPanel } from "@/components/steam/NowPlayingPanel";
import { SteamBindEntry } from "@/components/steam/SteamBindEntry";
import { TimelineControls } from "@/components/steam/TimelineControls";
import { clipTimelineToNoonWindow } from "@/components/steam/timelineUtils";
import { PageHeader } from "@/components/PageHeader";
import { apiError } from "@/lib/apiError";
import { isAdminUser } from "@/lib/isAdminUser";
import { rememberSteamIcons } from "@/lib/steamIconCache";
import { nowBeijing, parseBeijing } from "@/lib/time";
import { useIntegrationsStatus } from "@/hooks/useIntegrationsStatus";
import { useAuthStore } from "@/stores/authStore";

export default function SteamCalendarPage() {
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const isAdmin = isAdminUser(user);
  const steamBound = Boolean(useAuthStore((s) => s.user?.steam_id));
  const integrationsStatus = useIntegrationsStatus(!steamBound);
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

  const timelineEnabled = steamBound && Boolean(timelineRange?.start);

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
    enabled: steamBound,
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

  const startSteamBind = useMutation({
    mutationFn: () => startSteamOpenIdBind(),
    onSuccess: ({ url }) => {
      window.location.href = url;
    },
    onError: (e: unknown) => {
      message.error(apiError(e, "无法跳转 Steam 登录"));
    },
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
        extra={
          isAdmin && steamBound ? (
            <Button loading={poll.isPending} onClick={() => poll.mutate()}>
              立即轮询
            </Button>
          ) : null
        }
      />

      {!steamBound ? (
        <SteamBindEntry
          loading={startSteamBind.isPending}
          steamConfigured={integrationsStatus.data?.steam_configured}
          isAdmin={isAdmin}
          onBind={() => startSteamBind.mutate()}
        />
      ) : (
        <>
          {timelineData?.visibility?.hint && (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
              message={timelineData.visibility.hint}
            />
          )}

          {nowPlaying && nowPlaying.length > 0 ? (
            <NowPlayingPanel items={nowPlaying} />
          ) : null}

          <TimelineControls
            granularity={granularity}
            dayStartHour={dayStartHour}
            anchor={anchor}
            isPendingGranularity={isPendingGranularity}
            onGranularityChange={(value) => {
              setGranularity(value);
              setDayStartHour(0);
            }}
            onShift={shift}
            onAnchorChange={setAnchor}
            onDayStartHourReset={() => setDayStartHour(0)}
          />

          {(granularity === "day" || granularity === "week") && (
            <DayTimeline
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
        </>
      )}
    </div>
  );
}
