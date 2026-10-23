import { describe, expect, it } from "vitest";
import {
  ARMOR_EFFECT_LABELS,
  armorEffectLevel,
  armorEffectsForAmmo,
} from "./tarkovAmmoArmorEffect";

describe("tarkovAmmoArmorEffect", () => {
  it("exposes Chinese labels for wiki levels 0–6", () => {
    expect(ARMOR_EFFECT_LABELS[0]).toBe("无效");
    expect(ARMOR_EFFECT_LABELS[5]).toBe("很好");
    expect(ARMOR_EFFECT_LABELS[6]).toBe("无视");
  });

  it("rates high-pen ammo well against low armor", () => {
    // SSA AP ~57 pen：低甲应接近无视
    const levels = armorEffectsForAmmo(57, 58);
    expect(levels[0]).toBeGreaterThanOrEqual(5);
    expect(levels[1]).toBeGreaterThanOrEqual(5);
    expect(levels[5]).toBeGreaterThanOrEqual(4);
  });

  it("rates soft ammo poorly against high armor", () => {
    expect(armorEffectLevel(7, 4, 27)).toBe(0);
    expect(armorEffectLevel(7, 6, 27)).toBe(0);
  });

  it("returns six class ratings", () => {
    expect(armorEffectsForAmmo(31, 37)).toHaveLength(6);
  });
});
