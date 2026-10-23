import { describe, expect, it } from "vitest";
import {
  formatTraderStanding,
  indexTraderLoyaltyBySlug,
  nextTraderLoyaltySpec,
  remainingTraderLoyaltySpecs,
  parseTarkovGameEdition,
  parseTarkovPlayerLevel,
  parseTarkovTraderLoyalty,
  tarkovGameEditionLabel,
  tarkovStashFloor,
  traderLevelsForHideout,
  traderLoyaltyReqParts,
  traderLoyaltyReqTitle,
  traderLoyaltySpec,
} from "./tarkovProfile";

describe("tarkovProfile", () => {
  it("maps 白边 / 蓝边 and stash floors", () => {
    expect(parseTarkovGameEdition("")).toBe("standard");
    expect(parseTarkovGameEdition("EOD")).toBe("eod");
    expect(parseTarkovGameEdition("blue")).toBe("eod");
    expect(tarkovGameEditionLabel("standard")).toBe("白边");
    expect(tarkovGameEditionLabel("eod")).toBe("蓝边");
    expect(tarkovStashFloor("standard")).toBe(1);
    expect(tarkovStashFloor("eod")).toBe(4);
  });

  it("clamps player and trader levels", () => {
    expect(parseTarkovPlayerLevel(0)).toBe(1);
    expect(parseTarkovPlayerLevel(42)).toBe(42);
    expect(parseTarkovPlayerLevel(99)).toBe(79);
    expect(parseTarkovTraderLoyalty(0)).toBe(1);
    expect(parseTarkovTraderLoyalty(4)).toBe(4);
    expect(parseTarkovTraderLoyalty(9)).toBe(4);
  });

  it("omits empty trader maps for hideout lights", () => {
    expect(traderLevelsForHideout(undefined)).toBeUndefined();
    expect(traderLevelsForHideout({})).toBeUndefined();
    expect(traderLevelsForHideout({ prapor: 3 })).toEqual({ prapor: 3 });
  });

  it("formats next loyalty unlock from dump levels", () => {
    const levels = [
      { level: 1, required_player_level: 1, required_reputation: 0 },
      { level: 2, required_player_level: 15, required_reputation: 0.2 },
      { level: 3, required_player_level: 26, required_reputation: 0.3 },
    ];
    expect(formatTraderStanding(0.2)).toBe("0.20");
    expect(formatTraderStanding(0)).toBe("0");
    const bySlug = indexTraderLoyaltyBySlug([{ slug: "prapor", levels }]);
    expect(nextTraderLoyaltySpec(bySlug.get("prapor"), 0)?.level).toBe(2);
    expect(nextTraderLoyaltySpec(levels, 2)?.level).toBe(3);
    expect(nextTraderLoyaltySpec(levels, 3)).toBeUndefined();
    expect(remainingTraderLoyaltySpecs(levels, 0).map((row) => row.level)).toEqual([
      2, 3,
    ]);
    expect(remainingTraderLoyaltySpecs(levels, 2).map((row) => row.level)).toEqual([
      3,
    ]);
    expect(traderLoyaltyReqParts(levels[1], 10)).toEqual([
      { key: "level", text: "等级 15", met: false },
      { key: "standing", text: "好感度 0.20", met: null },
    ]);
    expect(traderLoyaltyReqParts(levels[1], 20)[0].met).toBe(true);
    expect(traderLoyaltyReqParts(levels[0], 10)).toEqual([]);
    expect(traderLoyaltyReqParts(levels[0], 10, { includeBaseline: true })).toEqual([
      { key: "level", text: "等级 1", met: true },
      { key: "standing", text: "好感度 0", met: null },
    ]);
    expect(traderLoyaltyReqTitle(traderLoyaltySpec(levels, 1))).toBe(
      "LL1：无额外等级/好感度要求",
    );
    expect(traderLoyaltyReqTitle(levels[1])).toBe("LL2：等级 15 · 好感度 0.20");
  });
});
