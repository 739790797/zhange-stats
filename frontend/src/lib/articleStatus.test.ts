import {
  articleStatusColor,
  articleStatusLabel,
} from "@/lib/articleStatus";
import { describe, expect, it } from "vitest";

describe("articleStatus", () => {
  it("maps known statuses", () => {
    expect(articleStatusLabel("draft")).toBe("草稿");
    expect(articleStatusLabel("published")).toBe("已发布");
    expect(articleStatusLabel("deleted")).toBe("已删除");
    expect(articleStatusLabel("other")).toBe("other");
  });

  it("picks tag colors", () => {
    expect(articleStatusColor("published")).toBe("success");
    expect(articleStatusColor("deleted")).toBe("error");
    expect(articleStatusColor("draft")).toBe("default");
  });
});
