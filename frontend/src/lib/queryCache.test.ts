import { describe, expect, it } from "vitest";
import {
  claimQueryPersistOwner,
  isInitialQueryPending,
  QUERY_PERSIST_OWNER_KEY,
  shouldDehydratePersistedQuery,
  shouldPersistQueryKey,
} from "./queryCache";

function memoryStorage(seed: Record<string, string> = {}) {
  const data = new Map(Object.entries(seed));
  return {
    data,
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => {
      data.set(key, value);
    },
  };
}

describe("claimQueryPersistOwner", () => {
  it("reports a change whenever the persisted cache belongs to someone else", () => {
    const storage = memoryStorage();
    expect(claimQueryPersistOwner(storage, 7)).toBe(true);
    expect(storage.data.get(QUERY_PERSIST_OWNER_KEY)).toBe("7");
    expect(claimQueryPersistOwner(storage, 7)).toBe(false);
    expect(claimQueryPersistOwner(storage, 8)).toBe(true);
    expect(claimQueryPersistOwner(storage, null)).toBe(true);
    expect(claimQueryPersistOwner(storage, undefined)).toBe(false);
  });

  it("treats unreadable storage as a change", () => {
    const broken = {
      getItem: () => {
        throw new Error("denied");
      },
      setItem: () => undefined,
    };
    expect(claimQueryPersistOwner(broken, 7)).toBe(true);
  });
});

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
