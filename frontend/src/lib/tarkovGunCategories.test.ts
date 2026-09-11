import { describe, expect, it } from "vitest";
import { weaponClassesForHandbookChildId } from "./tarkovGunCategories";

describe("weaponClassesForHandbookChildId", () => {
  it("maps handbook gun children to dump weapon_class values", () => {
    expect(weaponClassesForHandbookChildId("5b5f78fc86f77409407a7f90")).toEqual([
      "assault-rifle",
    ]);
    expect(weaponClassesForHandbookChildId("5b5f792486f77447ed5636b3")).toEqual([
      "handgun",
      "revolver",
    ]);
    expect(weaponClassesForHandbookChildId("")).toBeUndefined();
    expect(weaponClassesForHandbookChildId("5b5f7a0886f77409407a7f96")).toBeUndefined();
  });
});
