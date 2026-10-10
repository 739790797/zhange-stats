import type { Locale } from "antd/es/locale";
import antdZhCN from "antd/es/locale/zh_CN";
import datePickerZhCN from "antd/es/date-picker/locale/zh_CN";

export const antdLocale: Locale = antdZhCN;

export const datePickerLocale = {
  ...datePickerZhCN,
  lang: {
    ...datePickerZhCN.lang,
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
