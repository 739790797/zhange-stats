import { describe, expect, it } from "vitest";
import { flattenGuideLeaves, GUIDE_LEAF_PATHS } from "./guideNav";

describe("guide navigation", () => {
  it("exposes Risk of Rain 2 as a guest-accessible guide", () => {
    expect(flattenGuideLeaves().find((leaf) => leaf.featureId === "guides.ror2")).toMatchObject({
      path: "/guides/ror2",
      label: "雨中冒险2",
      allowGuest: true,
    });
    expect(GUIDE_LEAF_PATHS).toContain("/guides/ror2");
  });
});
