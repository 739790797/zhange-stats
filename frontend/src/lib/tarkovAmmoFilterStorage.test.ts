import { describe, expect, it } from "vitest";
import { resolveCaliberSelection } from "./tarkovAmmoFilterStorage";

describe("resolveCaliberSelection", () => {
  it("defaults to all available when no history", () => {
    expect(resolveCaliberSelection(["a", "b"], null)).toEqual(["a", "b"]);
  });

  it("keeps empty selection when user cleared", () => {
    expect(resolveCaliberSelection(["a", "b"], [])).toEqual([]);
  });

  it("drops calibers no longer available", () => {
    expect(resolveCaliberSelection(["a", "b"], ["a", "gone"])).toEqual(["a"]);
  });
});
