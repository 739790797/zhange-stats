import { describe, expect, it } from "vitest";
import {
  ARKNIGHTS_ITEM_ICON_BASE,
  awardsForDisplay,
  formatAwardsPlainText,
  isStatusAwardsText,
  parseAwardsText,
  resolveAwardIconUrl,
  todayAwardsHint,
} from "./checkinAwards";

describe("isStatusAwardsText", () => {
  it("treats bare status copy as not an award", () => {
    expect(isStatusAwardsText("今日已签到")).toBe(true);
    expect(isStatusAwardsText("签到成功")).toBe(true);
    expect(isStatusAwardsText("B服不支持查询")).toBe(true);
    expect(isStatusAwardsText("原石×20")).toBe(false);
  });
});

describe("parseAwardsText", () => {
  it("splits mixed separators and counts", () => {
    expect(parseAwardsText("情报拼图×10 · 经验×55 · 积分×40")).toEqual([
      { name: "情报拼图", count: 10 },
      { name: "经验", count: 55 },
      { name: "积分", count: 40 },
    ]);
    expect(parseAwardsText("库洛币+40")).toEqual([
      { name: "库洛币", count: 40 },
    ]);
    expect(parseAwardsText("合成玉x80")).toEqual([
      { name: "合成玉", count: 80 },
    ]);
  });

  it("ignores status-only copy", () => {
    expect(parseAwardsText("今日已签到")).toEqual([]);
  });
});

describe("resolveAwardIconUrl", () => {
  it("prefers upstream icon_url", () => {
    expect(
      resolveAwardIconUrl({
        name: "原石",
        icon_url: "https://example.com/a.png",
      }),
    ).toBe("https://example.com/a.png");
  });

  it("uses arknights item art only for ALL_CAPS types", () => {
    expect(
      resolveAwardIconUrl({ name: "合成玉", resource_type: "DIAMOND_SHD" }),
    ).toBe(`${ARKNIGHTS_ITEM_ICON_BASE}/DIAMOND_SHD.png`);
    expect(
      resolveAwardIconUrl({ name: "积分", resource_type: "score" }),
    ).toBeNull();
    expect(resolveAwardIconUrl({ name: "情报拼图" })).toBeNull();
  });
});

describe("formatAwardsPlainText", () => {
  it("joins name*count with commas", () => {
    expect(
      formatAwardsPlainText([
        { name: "情报拼图", count: 10 },
        { name: "经验", count: 55 },
        { name: "积分", count: 40 },
      ]),
    ).toBe("情报拼图*10, 经验*55, 积分*40");
  });
});

describe("awardsForDisplay", () => {
  it("keeps structured awards and parses text when empty", () => {
    expect(
      awardsForDisplay([{ name: "原石", count: 20 }], "今日已签到"),
    ).toEqual([{ name: "原石", count: 20 }]);
    expect(awardsForDisplay([], "今日已签到")).toEqual([]);
    expect(awardsForDisplay(null, "经验+10")).toEqual([
      { name: "经验", count: 10 },
    ]);
  });
});

describe("todayAwardsHint", () => {
  it("shows today-only hints when not signed", () => {
    expect(todayAwardsHint({ status: "pending" })).toBe("今日未签到");
    expect(todayAwardsHint({ status: "unknown" })).toBe("待确认");
    expect(todayAwardsHint({ status: "error" })).toBe("签到失败");
    expect(todayAwardsHint({ status: "skipped" })).toBe("已跳过");
  });

  it("renders awards when signed with items", () => {
    expect(
      todayAwardsHint({
        status: "already",
        awards: [{ name: "原石", count: 20 }],
      }),
    ).toBeNull();
  });

  it("hints bili arknights cannot query awards", () => {
    expect(
      todayAwardsHint({
        status: "ok",
        gameCode: "arknights",
        channelName: "B服",
      }),
    ).toBe("B服不支持查询");
  });

  it("hides the awards slot when signed with no items", () => {
    expect(todayAwardsHint({ status: "ok" })).toBe("");
  });
});
