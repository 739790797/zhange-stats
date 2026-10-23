import { describe, expect, it } from "vitest";
import {
  readAllowedInt,
  readCatalogSort,
  readPositiveInt,
  readRigKindFilter,
} from "./tarkovQueryState";

describe("tarkovQueryState", () => {
  it("reads page numbers and ignores junk", () => {
    expect(readPositiveInt("3", 1)).toBe(3);
    expect(readPositiveInt("0", 1)).toBe(1);
    expect(readPositiveInt("-2", 1)).toBe(1);
    expect(readPositiveInt("foo", 1)).toBe(1);
  });

  it("reads page size only when allowed", () => {
    expect(readAllowedInt("50", 20, [20, 50, 100])).toBe(50);
    expect(readAllowedInt("7", 20, [20, 50, 100])).toBe(20);
  });

  it("reads catalog sort only when key and dir are valid", () => {
    expect(readCatalogSort("weight", "desc", ["weight", "price"])).toEqual({
      key: "weight",
      order: "descend",
    });
    expect(readCatalogSort("weight", "ascend", ["weight"])).toEqual({
      key: "weight",
      order: "ascend",
    });
    expect(readCatalogSort("grid", "desc", ["weight"])).toBeNull();
    expect(readCatalogSort("weight", "sideways", ["weight"])).toBeNull();
  });

  it("reads rig kind filter from the URL", () => {
    expect(readRigKindFilter(null)).toBe("all");
    expect(readRigKindFilter("plain")).toBe("plain");
    expect(readRigKindFilter("armored")).toBe("armored");
    expect(readRigKindFilter("guns")).toBe("all");
  });
});
