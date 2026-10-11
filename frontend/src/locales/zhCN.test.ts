import { describe, expect, it } from "vitest";
import { antdLocale, datePickerLocale } from "./zhCN";

describe("zhCN locale", () => {
  it("loads antd's zh-CN pack as a plain object", () => {
    expect(antdLocale).not.toHaveProperty("default");
    expect(antdLocale.locale).toBe("zh-cn");
    expect(antdLocale.Pagination?.items_per_page).toBe("条/页");
  });

  it("layers the short week/month names on top of the date picker pack", () => {
    expect(datePickerLocale).not.toHaveProperty("default");
    expect(datePickerLocale.lang.locale).toBe("zh_CN");
    expect(datePickerLocale.lang.ok).toBe("确定");
    expect(datePickerLocale.lang.shortWeekDays).toEqual([
      "日",
      "一",
      "二",
      "三",
      "四",
      "五",
      "六",
    ]);
    expect(datePickerLocale.lang.shortMonths?.[11]).toBe("12月");
  });
});
