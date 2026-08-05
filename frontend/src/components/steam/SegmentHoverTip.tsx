import { type Dayjs } from "dayjs";

import { formatClock, formatPlayDuration } from "@/components/steam/format";
import { TimelineSegmentLogo } from "@/components/steam/SteamClientIcon";

export function SegmentHoverTip({
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
