import { describe, expect, it } from "vitest";
import {
  EFTARKOV_GUIDE_ORIGIN,
  eftarkovTaskGuideUrl,
  mergeRaidPrepGuideTasks,
  resolveRaidPrepGuideId,
} from "./eftarkovGuide";

describe("eftarkovGuide", () => {
  it("builds guide url from upstream task id", () => {
    expect(eftarkovTaskGuideUrl("639135d89444fb141f4e6eea")).toBe(
      `${EFTARKOV_GUIDE_ORIGIN}/news/id/639135d89444fb141f4e6eea.html`,
    );
  });

  it("rejects non-upstream ids", () => {
    expect(eftarkovTaskGuideUrl("75")).toBeNull();
    expect(eftarkovTaskGuideUrl("")).toBeNull();
  });

  it("keeps guide param when still selected", () => {
    expect(resolveRaidPrepGuideId(["a", "b", "c"], "b")).toBe("b");
  });

  it("falls back to first selected task when opening overview", () => {
    expect(resolveRaidPrepGuideId(["a", "b"], "")).toBe("a");
  });

  it("keeps the clicked task even if it is not selected", () => {
    expect(resolveRaidPrepGuideId(["big-customer"], "shooter-born")).toBe(
      "shooter-born",
    );
    expect(resolveRaidPrepGuideId([], "shooter-born")).toBe("shooter-born");
  });

  it("prepends the clicked catalog task when it is not selected", () => {
    const selected = [{ id: "big-customer", name: "大客户" }];
    const catalog = [
      { id: "big-customer", name: "大客户" },
      { id: "shooter-born", name: "天神射手" },
    ];
    expect(
      mergeRaidPrepGuideTasks(selected, catalog, "shooter-born").map(
        (row) => row.id,
      ),
    ).toEqual(["shooter-born", "big-customer"]);
    expect(
      mergeRaidPrepGuideTasks(selected, catalog, "big-customer").map(
        (row) => row.id,
      ),
    ).toEqual(["big-customer"]);
  });
});
