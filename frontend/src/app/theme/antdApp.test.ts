import { describe, expect, it } from "vitest";
import { antdThemeWithMotion } from "./antdApp";

describe("antdThemeWithMotion", () => {
  it("toggles the shared motion token", () => {
    expect(antdThemeWithMotion(false).token?.motion).toBe(false);
    expect(antdThemeWithMotion(true).token?.motion).toBe(true);
  });
});
