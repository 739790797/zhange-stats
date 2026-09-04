import { describe, expect, it } from "vitest";
import {
  localMapFileMatchesRemote,
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
