import { useEffect, useState } from "react";
import { goonSightingHint, sameGoonMap } from "@/lib/tarkovGoonTracker";
import { useTarkovGoonTracker } from "@/lib/useTarkovGoonTracker";
import styles from "./TarkovGoonTrackerBanner.module.css";

function useMinuteTick(active: boolean) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return undefined;
    const id = window.setInterval(() => setNow(Date.now()), 15_000);
    return () => window.clearInterval(id);
  }, [active]);
  return now;
}

function useGoonSighting(mapId: string) {
  const { status } = useTarkovGoonTracker();
  const active = sameGoonMap(mapId, status?.map_slug);
  const now = useMinuteTick(active);
  if (!active) return { active: false, short: "", full: "" };
  return {
    active: true,
    short: "三狗出没",
    full: goonSightingHint(status?.seen_at, now),
  };
}

/** 挂在对应地图名旁：三狗出没（12分钟前上报）。 */
export function TarkovGoonSightingHint({
  mapId,
  variant = "row",
}: {
  mapId: string;
  variant?: "row" | "inline" | "tile";
}) {
  const { short, full } = useGoonSighting(mapId);
  const text = variant === "tile" ? short : full;
  if (!text) return null;
  const className =
    variant === "inline"
      ? styles.hintInline
      : variant === "tile"
        ? styles.hintTile
        : styles.hint;
  return (
    <span className={className} title={full || undefined}>
      {text}
    </span>
  );
}

/** 选好地图后的房间内提示：匹配则出现，外站换图后立刻消失。 */
export function TarkovGoonRoomNotice({ mapId }: { mapId: string }) {
  const { full } = useGoonSighting(mapId);
  if (!mapId || !full) return null;
  return (
    <div className={styles.roomNoticeSlot} role="status">
      <div className={styles.roomNotice}>{full}</div>
    </div>
  );
}
