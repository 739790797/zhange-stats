import { describe, expect, it } from "vitest";
import {
  resetLogoutOnce,
  shouldLogoutOn401,
  takeLogoutOnce,
} from "./shouldLogoutOn401";

describe("shouldLogoutOn401", () => {
  it("does not logout on 403", () => {
    expect(
      shouldLogoutOn401({
        status: 403,
        url: "/api/settings/auth",
        hasSession: true,
      }),
    ).toBe(false);
  });

  it("does not logout on login 401", () => {
    expect(
      shouldLogoutOn401({
        status: 401,
        url: "/auth/login",
        hasSession: false,
      }),
    ).toBe(false);
  });

  it("does not logout when guest hits a protected API", () => {
    expect(
      shouldLogoutOn401({
        status: 401,
        url: "/profile/me",
        hasSession: false,
      }),
    ).toBe(false);
  });

  it("logs out on /auth/me 401", () => {
    expect(
      shouldLogoutOn401({
        status: 401,
        url: "/auth/me",
        hasSession: false,
      }),
    ).toBe(true);
  });

  it("logs out when a sessioned request gets 401", () => {
    expect(
      shouldLogoutOn401({
        status: 401,
        url: "/guides/tarkov/raid-rooms",
        hasSession: true,
      }),
    ).toBe(true);
  });

  it("only takes logout once until reset", () => {
    resetLogoutOnce();
    expect(takeLogoutOnce()).toBe(true);
    expect(takeLogoutOnce()).toBe(false);
    resetLogoutOnce();
    expect(takeLogoutOnce()).toBe(true);
    resetLogoutOnce();
  });
});
