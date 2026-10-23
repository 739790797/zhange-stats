import { describe, expect, it } from "vitest";
import { isUnsafeHttpMethod, readCookie, readCsrfToken } from "./csrfCookie";

describe("csrfCookie", () => {
  it("reads zhange_csrf from a cookie header", () => {
    expect(readCsrfToken("foo=1; zhange_csrf=abc%2B1; bar=2")).toBe("abc+1");
    expect(readCookie("missing", "a=1")).toBe("");
  });

  it("treats mutating methods as unsafe", () => {
    expect(isUnsafeHttpMethod("get")).toBe(false);
    expect(isUnsafeHttpMethod("POST")).toBe(true);
    expect(isUnsafeHttpMethod("delete")).toBe(true);
  });
});
