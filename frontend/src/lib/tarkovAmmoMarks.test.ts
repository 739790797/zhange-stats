import { describe, expect, it } from "vitest";
import {
  ammoTraitMarks,
  formatChancePct,
  isSubsonicAmmo,
  tracerMarkLabel,
} from "./tarkovAmmoMarks";

describe("isSubsonicAmmo", () => {
  it("marks rounds slower than the speed of sound", () => {
    expect(isSubsonicAmmo(340)).toBe(true);
    expect(isSubsonicAmmo(290)).toBe(true);
    expect(isSubsonicAmmo(343)).toBe(false);
    expect(isSubsonicAmmo(0)).toBe(false);
  });
});

describe("tracerMarkLabel", () => {
  it("uses the Chinese color plus 曳光弹", () => {
    expect(tracerMarkLabel("red")).toBe("红色曳光弹");
    expect(tracerMarkLabel("tracerGreen")).toBe("绿色曳光弹");
    expect(tracerMarkLabel("")).toBe("曳光弹");
  });
});

describe("ammoTraitMarks", () => {
  it("orders S before T like Wiki / eftforge", () => {
    expect(
      ammoTraitMarks({
        initial_speed: 290,
        tracer: true,
        tracer_color: "red",
      }).map((m) => m.key),
    ).toEqual(["S", "T"]);
  });

  it("omits marks when neither applies", () => {
    expect(ammoTraitMarks({ initial_speed: 900, tracer: false })).toEqual([]);
  });
});

describe("formatChancePct", () => {
  it("renders dump 0–1 chances as percents", () => {
    expect(formatChancePct(1)).toBe("100%");
    expect(formatChancePct(0.5)).toBe("50%");
    expect(formatChancePct(0.01)).toBe("1%");
    expect(formatChancePct(0)).toBe("0%");
  });
});
