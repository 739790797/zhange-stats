import { describe, expect, it } from "vitest";
import { featureIconName } from "./platformIcons";

describe("featureIconName", () => {
  it("maps tarkov and minecraft guide games to their logos", () => {
    expect(featureIconName("guides.tarkov")).toBe("tarkov");
    expect(featureIconName("guides.minecraft")).toBe("minecraft");
  });
});
