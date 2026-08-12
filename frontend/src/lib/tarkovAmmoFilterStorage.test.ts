import { describe, expect, it } from "vitest";
import { resolveCategorySelection } from "./tarkovAmmoFilterStorage";

describe("resolveCategorySelection", () => {
  it("defaults to all available when category has no history", () => {
    expect(
      resolveCategorySelection("rifle", ["a", "b"], {}),
    ).toEqual(["a", "b"]);
  });

  it("keeps empty selection when user cleared the tab", () => {
    expect(
      resolveCategorySelection("rifle", ["a", "b"], { rifle: [] }),
    ).toEqual([]);
  });

  it("drops calibers no longer available", () => {
    expect(
      resolveCategorySelection("rifle", ["a", "b"], {
        rifle: ["a", "gone"],
      }),
    ).toEqual(["a"]);
  });
});
