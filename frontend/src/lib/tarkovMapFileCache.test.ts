import { describe, expect, it } from "vitest";
import {
  localMapFileMatchesRemote,
  mapFileEvictionEntries,
  mapFileKeysToEvict,
} from "./tarkovMapFileCache";

describe("localMapFileMatchesRemote", () => {
  it("requires both etags and exact match", () => {
    expect(localMapFileMatchesRemote('W/"abc"', 'W/"abc"')).toBe(true);
    expect(localMapFileMatchesRemote('W/"abc"', 'W/"def"')).toBe(false);
    expect(localMapFileMatchesRemote("", 'W/"abc"')).toBe(false);
    expect(localMapFileMatchesRemote('W/"abc"', undefined)).toBe(false);
  });
});

describe("mapFileKeysToEvict", () => {
  it("keeps the newest entries", () => {
    expect(
      mapFileKeysToEvict(
        [
          { key: "old", savedAt: 1 },
          { key: "mid", savedAt: 2 },
          { key: "new", savedAt: 3 },
        ],
        2,
      ),
    ).toEqual(["old"]);
    expect(mapFileKeysToEvict([{ key: "a", savedAt: 1 }], 2)).toEqual([]);
  });
});

describe("mapFileEvictionEntries", () => {
  it("dates body keys from the etag store and evicts orphans first", () => {
    const entries = mapFileEvictionEntries(
      ["orphan", "old", "fresh", 7],
      ["old", "fresh", "gone"],
      [
        { etag: 'W/"1"', savedAt: 10 },
        { etag: 'W/"2"', savedAt: 5 },
        { etag: 'W/"3"', savedAt: 1 },
      ],
      { key: "fresh", savedAt: 99 },
    );
    expect(entries).toEqual([
      { key: "orphan", savedAt: 0 },
      { key: "old", savedAt: 10 },
      { key: "fresh", savedAt: 99 },
    ]);
    expect(mapFileKeysToEvict(entries, 2)).toEqual(["orphan"]);
  });
});
