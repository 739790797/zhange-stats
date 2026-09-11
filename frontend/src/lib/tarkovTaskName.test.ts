import { describe, expect, it } from "vitest";
import { displayTaskProgressName } from "./tarkovTaskName";

describe("displayTaskProgressName", () => {
  it("appends line hint without duplicating faction", () => {
    expect(
      displayTaskProgressName({
        id: "p1",
        name: "独立的代价",
        line_hint: "经「横插一杠」",
      }),
    ).toBe("独立的代价（经「横插一杠」）");
    expect(
      displayTaskProgressName({
        id: "u",
        name: "湿活",
        faction_name: "USEC",
        line_hint: "USEC",
      }),
    ).toBe("湿活 (USEC)");
    expect(
      displayTaskProgressName({
        id: "nb5",
        name: "New Beginning",
        line_hint: "五转",
      }),
    ).toBe("New Beginning（五转）");
  });
});
