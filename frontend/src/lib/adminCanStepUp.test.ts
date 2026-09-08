import { describe, expect, it } from "vitest";
import { adminCanStepUp } from "./adminCanStepUp";

describe("adminCanStepUp", () => {
  it("requires a verified email", () => {
    expect(adminCanStepUp(null)).toBe(false);
    expect(adminCanStepUp({ email: "a@b.c", email_verified: false })).toBe(false);
    expect(adminCanStepUp({ email: "a@b.c", email_verified: true })).toBe(true);
  });
});
