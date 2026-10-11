import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  TARKOV_COLLECTION_LAYOUT_STORAGE_KEY,
  TARKOV_COLLECTION_LAYOUT_V3_STORAGE_KEY,
  TARKOV_COLLECTION_OWNS_STORAGE_KEY,
} from "./tarkovCollection";
import { TARKOV_KEY_PACKS_STORAGE_KEY } from "./tarkovKeyPacks";
import { TARKOV_PMC_FACTION_STORAGE_KEY } from "./tarkovPmcFaction";
import {
  TARKOV_GUEST_OWNER,
  TARKOV_GUEST_PROGRESS_KEY,
  TARKOV_PERSONAL_STORAGE_KEYS,
  TARKOV_PROGRESS_OWNER_KEY,
  claimTarkovProgressOwner,
  discardTarkovGuestProgress,
  planTarkovProgressOwner,
  readTarkovGuestProgress,
  tarkovProgressOwnerOf,
} from "./tarkovProgressOwner";
import { RAID_PREP_OBJ_DONE_STORAGE } from "./tarkovRaidPrep";
import {
  TARKOV_TASK_DONES_STORAGE_KEY,
  loadTaskDoneIds,
  planAccountTaskHydrate,
  saveTaskProgress,
} from "./tarkovTaskTree";

function memoryStorage(seed: Record<string, string> = {}) {
  const mem = new Map(Object.entries(seed));
  return {
    mem,
    getItem: (key: string) => mem.get(key) ?? null,
    setItem: (key: string, value: string) => {
      mem.set(key, value);
    },
    removeItem: (key: string) => {
      mem.delete(key);
    },
  };
}

describe("planTarkovProgressOwner", () => {
  const userA = tarkovProgressOwnerOf(1);
  const userB = tarkovProgressOwnerOf(2);

  it("keeps the same owner and adopts data written before owners existed", () => {
    expect(planTarkovProgressOwner({ stored: userA, next: userA })).toBe("keep");
    expect(planTarkovProgressOwner({ stored: null, next: userA })).toBe("adopt");
    expect(planTarkovProgressOwner({ stored: "", next: TARKOV_GUEST_OWNER })).toBe(
      "adopt",
    );
  });

  it("clears an account's progress on logout or when someone else signs in", () => {
    expect(planTarkovProgressOwner({ stored: userA, next: TARKOV_GUEST_OWNER })).toBe(
      "clear",
    );
    expect(planTarkovProgressOwner({ stored: userA, next: userB })).toBe("clear");
  });

  it("stashes guest progress instead of merging it into the account", () => {
    expect(planTarkovProgressOwner({ stored: TARKOV_GUEST_OWNER, next: userA })).toBe(
      "stash",
    );
    expect(
      planTarkovProgressOwner({
        stored: TARKOV_GUEST_OWNER,
        next: userA,
        leaving: TARKOV_GUEST_OWNER,
      }),
    ).toBe("stash");
  });

  it("clears when this tab leaves an account even if another tab moved the marker", () => {
    expect(
      planTarkovProgressOwner({
        stored: TARKOV_GUEST_OWNER,
        next: TARKOV_GUEST_OWNER,
        leaving: userA,
      }),
    ).toBe("clear");
    expect(
      planTarkovProgressOwner({ stored: userB, next: userB, leaving: userB }),
    ).toBe("keep");
  });
});

describe("claimTarkovProgressOwner", () => {
  it("lists every personal storage key the Tarkov modules write", () => {
    expect([...TARKOV_PERSONAL_STORAGE_KEYS].sort()).toEqual(
      [
        TARKOV_TASK_DONES_STORAGE_KEY,
        TARKOV_KEY_PACKS_STORAGE_KEY,
        TARKOV_COLLECTION_OWNS_STORAGE_KEY,
        TARKOV_COLLECTION_LAYOUT_STORAGE_KEY,
        TARKOV_COLLECTION_LAYOUT_V3_STORAGE_KEY,
        TARKOV_PMC_FACTION_STORAGE_KEY,
        RAID_PREP_OBJ_DONE_STORAGE,
      ].sort(),
    );
  });

  it("adopts unmarked progress for whoever is signed in", () => {
    const storage = memoryStorage({ [TARKOV_KEY_PACKS_STORAGE_KEY]: "keys" });
    expect(claimTarkovProgressOwner(storage, 7)).toBe("adopt");
    expect(storage.mem.get(TARKOV_PROGRESS_OWNER_KEY)).toBe("user:7");
    expect(storage.mem.get(TARKOV_KEY_PACKS_STORAGE_KEY)).toBe("keys");
    expect(claimTarkovProgressOwner(storage, 7)).toBe("keep");
  });

  it("drops the previous account's progress but keeps an undecided guest stash", () => {
    const storage = memoryStorage({
      [TARKOV_PROGRESS_OWNER_KEY]: "user:7",
      [TARKOV_TASK_DONES_STORAGE_KEY]: "tasks",
      [TARKOV_PMC_FACTION_STORAGE_KEY]: "usec",
      [TARKOV_GUEST_PROGRESS_KEY]: JSON.stringify({
        [TARKOV_KEY_PACKS_STORAGE_KEY]: "guest-keys",
      }),
    });
    expect(claimTarkovProgressOwner(storage, null, 7)).toBe("clear");
    expect(storage.mem.has(TARKOV_TASK_DONES_STORAGE_KEY)).toBe(false);
    expect(storage.mem.has(TARKOV_PMC_FACTION_STORAGE_KEY)).toBe(false);
    expect(storage.mem.get(TARKOV_PROGRESS_OWNER_KEY)).toBe(TARKOV_GUEST_OWNER);
    expect(readTarkovGuestProgress(storage)).toEqual({
      [TARKOV_KEY_PACKS_STORAGE_KEY]: "guest-keys",
    });
  });

  it("moves guest progress aside on sign-in, newer keys winning", () => {
    const storage = memoryStorage({
      [TARKOV_PROGRESS_OWNER_KEY]: TARKOV_GUEST_OWNER,
      [TARKOV_TASK_DONES_STORAGE_KEY]: "new-tasks",
      [TARKOV_GUEST_PROGRESS_KEY]: JSON.stringify({
        [TARKOV_TASK_DONES_STORAGE_KEY]: "old-tasks",
        [TARKOV_KEY_PACKS_STORAGE_KEY]: "old-keys",
        "zhange.unrelated": "ignored",
      }),
    });
    expect(claimTarkovProgressOwner(storage, 3, null)).toBe("stash");
    expect(storage.mem.has(TARKOV_TASK_DONES_STORAGE_KEY)).toBe(false);
    expect(storage.mem.get(TARKOV_PROGRESS_OWNER_KEY)).toBe("user:3");
    expect(readTarkovGuestProgress(storage)).toEqual({
      [TARKOV_TASK_DONES_STORAGE_KEY]: "new-tasks",
      [TARKOV_KEY_PACKS_STORAGE_KEY]: "old-keys",
    });
    discardTarkovGuestProgress(storage);
    expect(readTarkovGuestProgress(storage)).toBeNull();
  });

  it("still empties the account side when the stash cannot be written", () => {
    const storage = memoryStorage({
      [TARKOV_PROGRESS_OWNER_KEY]: TARKOV_GUEST_OWNER,
      [TARKOV_TASK_DONES_STORAGE_KEY]: "guest-tasks",
    });
    const setItem = storage.setItem;
    storage.setItem = (key: string, value: string) => {
      if (key === TARKOV_GUEST_PROGRESS_KEY) throw new Error("quota");
      setItem(key, value);
    };
    expect(claimTarkovProgressOwner(storage, 3)).toBe("stash");
    expect(storage.mem.has(TARKOV_TASK_DONES_STORAGE_KEY)).toBe(false);
    expect(storage.mem.get(TARKOV_PROGRESS_OWNER_KEY)).toBe("user:3");
  });
});

describe("account switch and task hydrate", () => {
  const storage = memoryStorage();

  beforeEach(() => {
    storage.mem.clear();
    vi.stubGlobal("localStorage", storage);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("lets the next account's server ledger replace local without uploading", () => {
    claimTarkovProgressOwner(storage, 1);
    saveTaskProgress("pvp", ["a-done"], ["a-started"]);
    claimTarkovProgressOwner(storage, 2, 1);
    expect(loadTaskDoneIds("pvp")).toEqual([]);
    expect(
      planAccountTaskHydrate({
        serverDone: ["b-done"],
        serverStarted: [],
        localDone: loadTaskDoneIds("pvp"),
        localStarted: [],
      }),
    ).toMatchObject({ done: ["b-done"], started: [], upload: false });
  });
});
