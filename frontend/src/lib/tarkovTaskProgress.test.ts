import { describe, expect, it } from "vitest";
import {
  TARKOV_TASK_PROGRESS_FILTERS,
  tarkovTaskProgressLabel,
} from "./tarkovTaskProgress";

describe("tarkovTaskProgressLabel", () => {
  it("maps tracker-derived statuses", () => {
    expect(tarkovTaskProgressLabel("available")).toBe("进行中");
    expect(tarkovTaskProgressLabel("complete")).toBe("已完成");
    expect(tarkovTaskProgressLabel("locked")).toBe("缺少前置");
    expect(tarkovTaskProgressLabel("failed")).toBe("已失败");
    expect(tarkovTaskProgressLabel(null)).toBe("");
  });

  it("lists header filters in default sort order", () => {
    expect(TARKOV_TASK_PROGRESS_FILTERS.map((item) => item.id)).toEqual([
      "available",
      "locked",
      "complete",
      "failed",
    ]);
  });
});
