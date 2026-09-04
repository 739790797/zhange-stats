import { describe, expect, it } from "vitest";
import {
  CATALOG_HTTP_CACHE_MAX,
  catalogBodyKeysToEvict,
  catalogCacheKeyIsMapFile,
  isTarkovCatalogGet,
  isTarkovMapFileUrl,
  tarkovCatalogCacheKey,
} from "./tarkovCatalogHttp";

describe("isTarkovCatalogGet", () => {
  it("accepts map and raid-prep catalog GETs", () => {
    expect(isTarkovCatalogGet("get", "/guides/tarkov/maps/factory")).toBe(true);
    expect(isTarkovCatalogGet("get", "/guides/tarkov/maps/factory/loot")).toBe(
      true,
    );
    expect(isTarkovCatalogGet("GET", "/guides/tarkov/raid-prep")).toBe(true);
    expect(isTarkovCatalogGet("get", "/guides/tarkov/ammo")).toBe(true);
  });

  it("skips rooms, search, and user progress", () => {
    expect(isTarkovCatalogGet("get", "/guides/tarkov/raid-rooms")).toBe(false);
    expect(isTarkovCatalogGet("get", "/guides/tarkov/raid-rooms/mine")).toBe(
      false,
    );
    expect(isTarkovCatalogGet("get", "/guides/tarkov/search")).toBe(false);
    expect(isTarkovCatalogGet("get", "/guides/tarkov/raid-prep/state")).toBe(
      false,
    );
    expect(isTarkovCatalogGet("get", "/guides/tarkov/key-owns")).toBe(false);
    expect(isTarkovCatalogGet("post", "/guides/tarkov/maps")).toBe(false);
  });
});

describe("tarkovCatalogCacheKey", () => {
  it("includes url and params", () => {
    expect(tarkovCatalogCacheKey("/guides/tarkov/maps", { game_mode: "pvp" })).toBe(
      '/guides/tarkov/maps::{"game_mode":"pvp"}',
    );
  });
});

describe("isTarkovMapFileUrl", () => {
  it("matches map catalog, detail, and loot layers", () => {
    expect(isTarkovMapFileUrl("/guides/tarkov/maps")).toBe(true);
    expect(isTarkovMapFileUrl("/guides/tarkov/maps/factory")).toBe(true);
    expect(isTarkovMapFileUrl("/guides/tarkov/maps/factory/")).toBe(true);
    expect(isTarkovMapFileUrl("/guides/tarkov/maps/factory/loot")).toBe(true);
  });

  it("skips places and other catalogs", () => {
    expect(isTarkovMapFileUrl("/guides/tarkov/maps/factory/places")).toBe(false);
    expect(isTarkovMapFileUrl("/guides/tarkov/ammo")).toBe(false);
  });
});

describe("catalogBodyKeysToEvict", () => {
  it("evicts oldest keys past the cap", () => {
    expect(catalogBodyKeysToEvict(["a", "b", "c"], 2)).toEqual(["a"]);
    expect(catalogBodyKeysToEvict(["a"], CATALOG_HTTP_CACHE_MAX)).toEqual([]);
  });

  it("treats map loot URLs as map files", () => {
    expect(
      catalogCacheKeyIsMapFile(
        '/guides/tarkov/maps/factory/loot::{"loot_loose":true}',
      ),
    ).toBe(true);
    expect(
      catalogCacheKeyIsMapFile('/guides/tarkov/ammo::{"game_mode":"pvp"}'),
    ).toBe(false);
  });
});
