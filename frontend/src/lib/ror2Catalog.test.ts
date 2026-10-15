import { describe, expect, it } from "vitest";
import { filterRor2Entries, ror2Number, ror2Rarities, ror2StackText } from "./ror2Catalog";

describe("ror2 catalog labels", () => {
  it("orders rarities that are actually present", () => {
    expect(ror2Rarities([{ rarity: "Void" }, { rarity: "Common" }, { rarity: "" }, { rarity: "Zz" }])).toEqual([
      "Common",
      "Void",
      "Zz",
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
