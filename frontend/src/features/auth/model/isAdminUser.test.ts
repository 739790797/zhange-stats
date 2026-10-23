import { describe, expect, it } from "vitest";
import { isAdminUser } from "./isAdminUser";

describe("isAdminUser", () => {
  it("returns false for nullish", () => {
    expect(isAdminUser(null)).toBe(false);
    expect(isAdminUser(undefined)).toBe(false);
  });

  it("accepts role admin", () => {
    expect(isAdminUser({ role: "admin" })).toBe(true);
  });

  it("rejects derived is_admin when role is user", () => {
    expect(isAdminUser({ role: "user", is_admin: true })).toBe(false);
  });

  it("falls back to is_admin only when role is missing", () => {
    expect(isAdminUser({ is_admin: true })).toBe(true);
    expect(isAdminUser({ role: "", is_admin: true })).toBe(true);
  });

  it("rejects plain user", () => {
    expect(isAdminUser({ role: "user", is_admin: false })).toBe(false);
  });
});
