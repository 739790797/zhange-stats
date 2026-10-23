import { describe, expect, it } from "vitest";
import {
  filterRor2Entries,
  ror2ItemRarityText,
  ror2ItemTableStackTexts,
  ror2Number,
  ror2Rarities,
  ror2StackText,
} from "./ror2Catalog";

describe("ror2 catalog labels", () => {
  it("orders rarities that are actually present", () => {
    expect(ror2Rarities([{ rarity: "Void" }, { rarity: "Common" }, { rarity: "" }, { rarity: "Zz" }])).toEqual([
      "Common",
      "Void",
      "Zz",
    ]);
  });

  it("uses tokenized rarity and stack text, with the Wiki source as the only fallback", () => {
    const raritySource = { text: "Common", original: "Common", token: "items.items.ITEM_A.Rarity" };
    const rarityTranslation = { text: "普通译名", original: "Common", token: "items.items.ITEM_B.Rarity" };
    expect(
      ror2ItemRarityText(
        [
          { rarity: "Common", localizedText: { rarity: raritySource } },
          { rarity: "Common", localizedText: { rarity: rarityTranslation } },
        ],
        "Common",
      ),
    ).toEqual(rarityTranslation);
    expect(ror2ItemRarityText([{ rarity: "Common" }], "Common")).toEqual({
      text: "Common",
      original: "Common",
      token: null,
    });

    const stacks = ror2ItemTableStackTexts([
      { stack: "Linear", localizedText: { stack: { text: "Linear", original: "Linear", token: "items.items.ITEM_A.Stats.1.Stack" } } },
      { stack: "Linear", localizedText: { stack: { text: "线性译名", original: "Linear", token: "items.items.ITEM_B.Stats.1.Stack" } } },
      { stack: "ProcCoeff", localizedText: { stack: { text: "触发系数", original: "ProcCoeff", token: "items.items.ITEM_B.Stats.2.Stack" } } },
    ]);
    expect(stacks).toEqual([{ text: "线性译名", original: "Linear", token: "items.items.ITEM_B.Stats.1.Stack" }]);
    expect(ror2ItemTableStackTexts([{ stack: "Hyperbolic" }])).toEqual([
      { text: "Hyperbolic", original: "Hyperbolic", token: null },
    ]);
  });

  it("keeps stack keys and numeric values as stored", () => {
    expect(ror2StackText("Hyperbolic", "+15%")).toBe("Hyperbolic +15%");
    expect(ror2StackText("", "+1")).toBe("+1");
    expect(ror2Number(110)).toBe("110");
    expect(ror2Number(2.4)).toBe("2.4");
    expect(ror2Number(0)).toBe("0");
    expect(ror2Number(null)).toBe("");
  });

  it("filters by rarity and by name, quote, or description", () => {
    const rows = [
      { name: "Soldier's Syringe", rarity: "Common", quote: "attack", description: "speed", internal_name: "ITEM_SYRINGE" },
      { name: "Brilliant Behemoth", rarity: "Legendary", quote: "explode", description: "radius" },
    ];
    expect(filterRor2Entries(rows, "syringe", "").map((row) => row.name)).toEqual(["Soldier's Syringe"]);
    expect(filterRor2Entries(rows, "ITEM_SYRINGE", "Common")).toHaveLength(1);
    expect(filterRor2Entries(rows, "explode", "Common")).toEqual([]);
    expect(filterRor2Entries(rows, "  ", "Legendary").map((row) => row.name)).toEqual(["Brilliant Behemoth"]);
    const styled = [{ name: "Will", description: "传送（<style=cIsDamage>{0}%</style>）" }];
    expect(filterRor2Entries(styled, "传送", "").map((row) => row.name)).toEqual(["Will"]);
    expect(filterRor2Entries(styled, "cIsDamage", "")).toEqual([]);
  });
});
