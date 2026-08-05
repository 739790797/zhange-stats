import { type Dayjs } from "dayjs";

import { DAY_SECONDS } from "@/components/steam/constants";

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}秒`;
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}分钟`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return rm ? `${h}小时${rm}分` : `${h}小时`;
}

/** 悬浮时段后缀：不足 1 小时「xx分钟」，否则「xx小时xx分钟」。 */
export function formatPlayDuration(seconds: number): string {
  if (seconds < 60) return "不足1分钟";
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}分钟`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return rm ? `${h}小时${rm}分钟` : `${h}小时`;
}

export function formatClock(sec: number, spanSeconds: number, rangeStart: Dayjs): string {
  const s = Math.max(0, Math.min(spanSeconds, Math.floor(sec)));
  const t = rangeStart.add(s, "second");
  if (spanSeconds <= DAY_SECONDS) {
    return t.format("HH:mm");
  }
  return t.format("M/D HH:mm");
}
