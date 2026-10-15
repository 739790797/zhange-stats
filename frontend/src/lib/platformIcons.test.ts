import { describe, expect, it } from "vitest";
import { featureIconName, featureTreeIcon } from "./platformIcons";

describe("featureIconName", () => {
  it("maps tarkov, minecraft, and ror2 guide games to their logos", () => {
    expect(featureIconName("guides.tarkov")).toBe("tarkov");
    expect(featureIconName("guides.minecraft")).toBe("minecraft");
    expect(featureIconName("guides.ror2")).toBe("ror2");
  });
});

describe("featureTreeIcon", () => {
  it("uses the site brand mark for 战鸽数据", () => {
    expect(featureTreeIcon("zhange", "platform")).toBe("brand");
    expect(featureTreeIcon("zhange.texteller_model", "job")).toBeNull();
  });

  it("keeps third-party platform icons", () => {
    expect(featureTreeIcon("steam", "platform")).toBe("steam");
    expect(featureTreeIcon("guides.tarkov", "game")).toBe("tarkov");
    expect(featureTreeIcon("guides.ror2", "game")).toBe("ror2");
  });
});
