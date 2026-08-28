import { describe, expect, it } from "vitest";
import {
  EFTARKOV_GUIDE_ORIGIN,
  eftarkovTaskGuideUrl,
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

  it("falls back to first selected task", () => {
    expect(resolveRaidPrepGuideId(["a", "b"], "")).toBe("a");
    expect(resolveRaidPrepGuideId(["a", "b"], "z")).toBe("a");
  });
});
