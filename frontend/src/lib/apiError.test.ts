import { describe, expect, it } from "vitest";
import { apiError, apiStatus, isApiForbidden } from "./apiError";

describe("apiError helpers", () => {
  it("reads HTTP status without importing axios", () => {
    expect(apiStatus({ response: { status: 403 } })).toBe(403);
    expect(apiStatus(new Error("x"))).toBeUndefined();
    expect(isApiForbidden({ response: { status: 403 } })).toBe(true);
    expect(isApiForbidden({ response: { status: 404 } })).toBe(false);
  });

  it("still formats 403 via apiError", () => {
    expect(apiError({ response: { status: 403, data: {} } }, "失败")).toBe(
      "没有权限或尚未完成验证",
    );
  });
});
