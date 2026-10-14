import { describe, expect, it } from "vitest";
import { formatMoney } from "./tarkovMoney";

describe("formatMoney", () => {
  it("formats rubles by default and rounds", () => {
    expect(formatMoney(1234.6)).toBe("1,235 ₽");
    expect(formatMoney(0)).toBe("0 ₽");
  });

  it("uses the currency symbol", () => {
    expect(formatMoney(1500, "USD")).toBe("1,500 $");
    expect(formatMoney(1500, "eur")).toBe("1,500 €");
    expect(formatMoney(1500, "other")).toBe("1,500 ₽");
  });

  it("renders a dash for missing values", () => {
    expect(formatMoney(null)).toBe("—");
    expect(formatMoney(undefined)).toBe("—");
    expect(formatMoney(Number.NaN)).toBe("—");
    expect(formatMoney(Number.POSITIVE_INFINITY)).toBe("—");
  });
});
