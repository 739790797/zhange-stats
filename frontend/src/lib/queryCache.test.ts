import { describe, expect, it } from "vitest";
import {
  isInitialQueryPending,
  shouldDehydratePersistedQuery,
  shouldPersistQueryKey,
} from "./queryCache";

describe("shouldPersistQueryKey", () => {
  it("keeps platform status and features", () => {
    expect(shouldPersistQueryKey(["skland-status"])).toBe(true);
    expect(shouldPersistQueryKey(["mihoyo-status"])).toBe(true);
    expect(shouldPersistQueryKey(["platform-features-effective"])).toBe(true);
  });

  it("skips credentials, catalogs, and box payloads", () => {
    expect(shouldPersistQueryKey(["auth-me"])).toBe(false);
    expect(shouldPersistQueryKey(["profile-me"])).toBe(false);
    expect(shouldPersistQueryKey(["endfield-box", "uid"])).toBe(false);
    expect(shouldPersistQueryKey(["guides-tarkov-map", "factory"])).toBe(false);
  });
});

describe("shouldDehydratePersistedQuery", () => {
  it("only dehydrates successful persisted keys", () => {
    expect(
      shouldDehydratePersistedQuery({
        queryKey: ["skland-status"],
        state: { status: "success" },
      }),
    ).toBe(true);
    expect(
      shouldDehydratePersistedQuery({
        queryKey: ["skland-status"],
        state: { status: "error" },
      }),
    ).toBe(false);
    expect(
      shouldDehydratePersistedQuery({
        queryKey: ["auth-me"],
        state: { status: "success" },
      }),
    ).toBe(false);
  });
});

describe("isInitialQueryPending", () => {
  it("blocks UI only when there is no data yet", () => {
    expect(isInitialQueryPending({ data: undefined, isPending: true })).toBe(
      true,
    );
    expect(
      isInitialQueryPending({ data: { bound: true }, isPending: false }),
    ).toBe(false);
    expect(
      isInitialQueryPending({ data: { bound: true }, isPending: true }),
    ).toBe(false);
  });
});
