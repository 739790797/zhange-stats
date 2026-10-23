/** 业务时间一律按北京时间（Asia/Shanghai）解析与展示。 */
import dayjs, { type Dayjs, type ConfigType } from "dayjs";
import timezone from "dayjs/plugin/timezone";
import utc from "dayjs/plugin/utc";

dayjs.extend(utc);
dayjs.extend(timezone);

export const BEIJING_TZ = "Asia/Shanghai";

dayjs.tz.setDefault(BEIJING_TZ);

const HAS_OFFSET = /([zZ]|[+-]\d{2}:?\d{2})$/;

/** 当前北京时间。 */
export function nowBeijing(): Dayjs {
  return dayjs().tz(BEIJING_TZ);
}

/**
 * 解析 API / 库内时间。
 * - 带 Z 或偏移：先按该时区理解，再转到北京
 * - 无偏移的 naive：视为北京墙钟（与后端存储约定一致）
 */
export function parseBeijing(input: ConfigType): Dayjs {
  if (input == null || input === "") {
    return dayjs(NaN);
  }
  try {
    if (typeof input === "string") {
      const s = input.trim();
      if (!s) return dayjs(NaN);
      if (HAS_OFFSET.test(s)) {
        const d = dayjs(s).tz(BEIJING_TZ);
        return d.isValid() ? d : dayjs(NaN);
      }
      const d = dayjs.tz(s, BEIJING_TZ);
      return d.isValid() ? d : dayjs(NaN);
    }
    const d = dayjs(input).tz(BEIJING_TZ);
    return d.isValid() ? d : dayjs(NaN);
  } catch {
    return dayjs(NaN);
  }
}

export function nowBeijingStamp(): string {
  return nowBeijing().format("YYYY-MM-DD HH:mm:ss");
}

/** 比较北京墙钟；无效时间排在有效时间之前。 */
export function compareBeijingClock(left: ConfigType, right: ConfigType): number {
  const a = parseBeijing(left);
  const b = parseBeijing(right);
  if (!a.isValid() && !b.isValid()) return 0;
  if (!a.isValid()) return -1;
  if (!b.isValid()) return 1;
  const av = a.valueOf();
  const bv = b.valueOf();
  if (av === bv) return 0;
  return av < bv ? -1 : 1;
}

export function laterBeijingClock(left: string, right: string): string {
  const a = (left || "").trim();
  const b = (right || "").trim();
  if (!a) return b;
  if (!b) return a;
  return compareBeijingClock(a, b) >= 0 ? a : b;
}

export function formatBeijing(
  input: ConfigType,
  pattern = "YYYY-MM-DD HH:mm:ss",
): string {
  const d = parseBeijing(input);
  return d.isValid() ? d.format(pattern) : "—";
}

/** Unix 秒时间戳 → 北京日期/时间。 */
export function formatUnixBeijing(
  unixSeconds: number,
  pattern = "YYYY-MM-DD",
): string {
  return dayjs.unix(unixSeconds).tz(BEIJING_TZ).format(pattern);
}
