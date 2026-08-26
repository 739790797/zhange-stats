import { describe, expect, it, vi } from "vitest";
import {
  consumePostLoginPath,
  postLoginPath,
  rememberPostLoginPath,
} from "./postLoginPath";

describe("postLoginPath", () => {
  it("falls back to home", () => {
    expect(postLoginPath(null)).toBe("/");
    expect(postLoginPath({ pathname: "/" })).toBe("/");
    expect(postLoginPath({ pathname: "/login" })).toBe("/");
    expect(postLoginPath({ pathname: "/register" })).toBe("/");
  });

  it("keeps in-app deep links", () => {
    expect(postLoginPath({ pathname: "/skland" })).toBe("/skland");
    expect(
      postLoginPath({ pathname: "/guides/tarkov", search: "?q=ammo" }),
    ).toBe("/guides/tarkov?q=ammo");
  });
});

describe("rememberPostLoginPath", () => {
  it("round-trips via sessionStorage", () => {
    const store: Record<string, string> = {};
    vi.stubGlobal("sessionStorage", {
      getItem: (key: string) => store[key] ?? null,
      setItem: (key: string, value: string) => {
        store[key] = value;
      },
      removeItem: (key: string) => {
        delete store[key];
      },
    });
    rememberPostLoginPath("/daily");
    expect(consumePostLoginPath()).toBe("/daily");
    expect(consumePostLoginPath()).toBeNull();
    vi.unstubAllGlobals();
  });
});
