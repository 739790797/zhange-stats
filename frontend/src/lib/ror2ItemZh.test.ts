import { describe, expect, it } from "vitest";
import { ror2ItemExpansionZh, ror2ItemRarityZh, ror2ItemStackZh, ror2LoadoutSkillRank, ror2LoadoutSkillZh } from "./ror2ItemZh";

describe("ror2 item chinese overlay", () => {
  it("translates the list labels and leaves unknown tokens alone", () => {
    expect(ror2ItemRarityZh("Common")).toBe("普通");
    expect(ror2ItemRarityZh("Lunar Equipment")).toBe("月球装备");
    expect(ror2ItemRarityZh("Foo")).toBe("Foo");
    expect(ror2ItemStackZh("Linear / None")).toBe("线性 / 无");
    expect(ror2ItemStackZh("")).toBe("");
    expect(ror2ItemExpansionZh("SotV", "Survivors of the Void")).toBe("虚空幸存者");
    expect(ror2ItemExpansionZh("base")).toBe("本体");
    expect(ror2ItemExpansionZh("ZZ", "ZZ")).toBe("ZZ");
    expect(ror2LoadoutSkillZh("Primary")).toBe("主要技能");
    expect(ror2LoadoutSkillZh("Misc")).toBe("其他");
    expect(ror2LoadoutSkillZh("Passive")).toBe("Passive");
    expect(["Special", "Primary", "Misc", "Passive"].sort((a, b) => ror2LoadoutSkillRank(a) - ror2LoadoutSkillRank(b))).toEqual([
      "Primary",
      "Special",
      "Misc",
      "Passive",
    ]);
  });
});
