import {
  articleStatusColor,
  articleStatusLabel,
} from "./articleStatus";
import { describe, expect, it } from "vitest";

describe("articleStatus", () => {
  it("maps known statuses", () => {
    expect(articleStatusLabel("draft")).toBe("草稿");
    expect(articleStatusLabel("published")).toBe("已发布");
    expect(articleStatusLabel("other")).toBe("other");
  });

  it("picks tag colors", () => {
    expect(articleStatusColor("published")).toBe("success");
    expect(articleStatusColor("draft")).toBe("default");
  });
});
