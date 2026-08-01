import type { Locale } from "antd/es/locale";
import antdZhCN from "antd/locale/zh_CN";
import datePickerZhCN from "antd/es/date-picker/locale/zh_CN";

/** Vite/CJS 互操作下偶发包一层 default，统一解包 */
function unwrapLocale<T>(mod: T | { default: T }): T {
  if (mod && typeof mod === "object" && "default" in (mod as object)) {
    const inner = (mod as { default: T }).default;
    if (inner && typeof inner === "object") return inner;
  }
  return mod as T;
}

export const antdLocale: Locale = {
  ...unwrapLocale(antdZhCN),
};

export const datePickerLocale = {
  ...unwrapLocale(datePickerZhCN),
  lang: {
    ...unwrapLocale(datePickerZhCN).lang,
    shortWeekDays: ["日", "一", "二", "三", "四", "五", "六"],
    shortMonths: [
      "1月",
      "2月",
      "3月",
      "4月",
      "5月",
      "6月",
      "7月",
      "8月",
      "9月",
      "10月",
      "11月",
      "12月",
    ],
  },
};
