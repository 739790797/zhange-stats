import { describe, expect, it } from "vitest";
import { ror2ItemExpansionZh, ror2LoadoutSkillRank, ror2LoadoutSkillZh } from "./ror2ItemZh";

describe("ror2 item chinese overlay", () => {
  it("keeps DLC names and loadout categories on the existing local naming rules", () => {
    expect(ror2ItemExpansionZh("SotV", "Survivors of the Void")).toBe("虚空幸存者");
    expect(ror2ItemExpansionZh("SotS", "Seekers of the Storm")).toBe("风暴探寻者");
    expect(ror2ItemExpansionZh("AC", "Alloyed Collective")).toBe("合金意念");
    expect(ror2ItemExpansionZh("HC", "Hallowed Concepts")).toBe("神圣观念");
    expect(ror2ItemExpansionZh("base")).toBe("雨中冒险2");
    expect(ror2ItemExpansionZh("")).toBe("雨中冒险2");
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
