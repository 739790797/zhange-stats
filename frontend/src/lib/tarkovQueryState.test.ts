import { describe, expect, it } from "vitest";
import {
  readAllowedInt,
  readPositiveInt,
  readTarkovTaskView,
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

  it("defaults task list to table / search view", () => {
    expect(readTarkovTaskView(null)).toBe("table");
    expect(readTarkovTaskView("")).toBe("table");
    expect(readTarkovTaskView("table")).toBe("table");
    expect(readTarkovTaskView("chain")).toBe("chain");
    expect(readTarkovTaskView("other")).toBe("table");
  });
});
