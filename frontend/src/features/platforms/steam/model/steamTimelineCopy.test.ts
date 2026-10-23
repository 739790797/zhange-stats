import { describe, expect, it } from "vitest";
import {
  steamPrivacySkipHint,
  steamTimelineEmptyText,
} from "./steamTimelineCopy";

describe("steamTimelineEmptyText", () => {
  it("distinguishes no members vs no sessions", () => {
    expect(steamTimelineEmptyText({ rowCount: 0, visibleMemberCount: 0 })).toBe(
      "暂无绑定 Steam 的圈子成员",
    );
    expect(steamTimelineEmptyText({ rowCount: 0, visibleMemberCount: 3 })).toBe(
      "该时段暂无游玩记录",
    );
    expect(steamTimelineEmptyText({ rowCount: 2, visibleMemberCount: 3 })).toBe(
      "",
    );
  });
});

describe("steamPrivacySkipHint", () => {
  it("prefers API hint", () => {
    expect(
      steamPrivacySkipHint({ hint: "资料未公开", steam_bound: true }, 0),
    ).toBe("资料未公开");
  });

  it("explains skip only when bound and empty", () => {
    expect(steamPrivacySkipHint({ steam_bound: true }, 0)).toMatch(/游戏详情/);
    expect(steamPrivacySkipHint({ steam_bound: true }, 2)).toBeNull();
    expect(steamPrivacySkipHint({ steam_bound: false }, 0)).toBeNull();
  });
});
