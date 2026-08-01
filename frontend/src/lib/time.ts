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
  if (typeof input === "string") {
    const s = input.trim();
    if (HAS_OFFSET.test(s)) {
      return dayjs(s).tz(BEIJING_TZ);
    }
    return dayjs.tz(s, BEIJING_TZ);
  }
  return dayjs(input).tz(BEIJING_TZ);
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
