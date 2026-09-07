import { describe, expect, it } from "vitest";
import {
  allItemPages,
  handbookCategoryFromIds,
  handbookHrefFromCategoryId,
  itemHrefFromTypes,
  itemPageBySlug,
  itemTypeHrefFromTypes,
  itemTypeLabelFromTypes,
  TARKOV_ITEM_LEAVES,
} from "./tarkovItemTypes";

describe("itemPageBySlug", () => {
  it("resolves handbook roots and top-nav leaves", () => {
    expect(itemPageBySlug("gear")?.panel).toBe("catalog");
    expect(itemPageBySlug("ammo")?.panel).toBe("ammo");
    expect(itemPageBySlug("guns")?.panel).toBe("guns");
    expect(itemPageBySlug("headsets")?.label).toBe("耳机");
    expect(itemPageBySlug("pistol-grips")?.types).toContain("pistolGrip");
    expect(itemPageBySlug("suppressors")?.types).toContain("suppressor");
    expect(itemPageBySlug("headsets")?.types).toContain("headphones");
    expect(itemPageBySlug("ammo-packs")?.types).toContain("ammoBox");
    expect(itemPageBySlug("melee")?.types).toContain("melee");
    expect(itemPageBySlug("ammo-packs")?.categoryIds).toContain(
      "5b47574386f77428ca22b33c",
    );
    expect(itemPageBySlug("melee")?.categoryIds).toContain(
      "5b5f7a0886f77409407a7f96",
    );
    expect(itemPageBySlug("battle-pass")?.types).toContain("poster");
    expect(itemPageBySlug("helmets")?.types).toEqual(["helmet"]);
    const mods = itemPageBySlug("weapon-mods");
    expect(mods?.children.map((c) => c.label)).toEqual([
      "装备配件",
      "功能模块",
      "基础部件",
    ]);
    expect(mods?.children[0]?.children?.map((c) => c.label)).toContain(
      "手枪式握把",
    );
    expect(mods?.categoryIds).toContain("5b5f731a86f774093e6cb4f9");
    expect(itemPageBySlug("pistol-grips")?.categoryIds).toContain(
      "5b5f761f86f774094242f1a1",
    );
  });

  it("maps gun aliases", () => {
    expect(itemPageBySlug("weapons")?.slug).toBe("guns");
  });
});

describe("itemHrefFromTypes", () => {
  it("picks ammo/guns/keys then falls back to barter", () => {
    expect(itemHrefFromTypes("a1", ["ammo"])).toBe(
      "/guides/tarkov/items/ammo/a1",
    );
    expect(itemHrefFromTypes("p1", ["ammoBox"])).toBe(
      "/guides/tarkov/items/ammo-packs/p1",
    );
    expect(itemHrefFromTypes("m1", ["melee"])).toBe(
      "/guides/tarkov/items/melee/m1",
    );
    expect(itemHrefFromTypes("g1", ["gun"])).toBe(
      "/guides/tarkov/items/guns/g1",
    );
    expect(itemHrefFromTypes("k1", ["keys"])).toBe(
      "/guides/tarkov/items/keys/k1",
    );
    expect(itemHrefFromTypes("s1", ["suppressor"])).toBe(
      "/guides/tarkov/items/suppressors/s1",
    );
    expect(itemHrefFromTypes("h1", ["headphones"])).toBe(
      "/guides/tarkov/items/headsets/h1",
    );
  });

  it("reads a category label and listing href from item types", () => {
    expect(itemTypeLabelFromTypes(["suppressor"])).toBe("消音器");
    expect(itemTypeHrefFromTypes(["suppressor"])).toBe(
      "/guides/tarkov/items/suppressors",
    );
  });
});

describe("handbookCategoryFromIds", () => {
  it("prefers the handbook child over the parent root", () => {
    expect(
      handbookCategoryFromIds([
        "5b47574386f77428ca22b33e",
        "5b47574386f77428ca22b2ef",
      ]),
    ).toEqual({
      id: "5b47574386f77428ca22b2ef",
      label: "电子产品",
      order: 13_004,
    });
  });

  it("prefers weapon-mod leaves over the three parent groups", () => {
    expect(
      handbookCategoryFromIds([
        "5b5f71a686f77447ed5636ab",
        "5b5f71b386f774093f2ecf11",
        "5b5f724186f77447ed5636ad",
        "5b5f731a86f774093e6cb4f9",
      ]),
    ).toMatchObject({
      id: "5b5f731a86f774093e6cb4f9",
      label: "消音器",
    });
  });

  it("falls back to the root and ignores unknown ids", () => {
    expect(handbookCategoryFromIds(["5b47574386f77428ca22b342"])).toEqual({
      id: "5b47574386f77428ca22b342",
      label: "钥匙",
      order: 6_000,
    });
    expect(handbookCategoryFromIds(["missing", ""])).toBeNull();
    expect(handbookCategoryFromIds([])).toBeNull();
  });
});

describe("handbookHrefFromCategoryId", () => {
  it("skips generic Item nodes and maps handbook roots", () => {
    expect(handbookHrefFromCategoryId("54009119af1c881c07000029")).toBeNull();
    expect(handbookHrefFromCategoryId("5b47574386f77428ca22b342")).toBe(
      "/guides/tarkov/items/keys",
    );
    expect(handbookHrefFromCategoryId("5b47574386f77428ca22b33c")).toBe(
      "/guides/tarkov/items/ammo-packs",
    );
    expect(handbookHrefFromCategoryId("5b5f7a0886f77409407a7f96")).toBe(
      "/guides/tarkov/items/melee",
    );
  });

  it("maps weapon-mod leaves to dedicated pages or the mods catalog", () => {
    expect(handbookHrefFromCategoryId("5b5f731a86f774093e6cb4f9")).toBe(
      "/guides/tarkov/items/suppressors",
    );
    expect(handbookHrefFromCategoryId("5b5f754a86f774094242f19b")).toBe(
      "/guides/tarkov/items/weapon-mods?child=5b5f754a86f774094242f19b",
    );
  });
});

describe("TARKOV_ITEM_LEAVES", () => {
  it("covers gear leaves and weapon-mod subtypes", () => {
    const slugs = TARKOV_ITEM_LEAVES.map((p) => p.slug);
    expect(slugs).toEqual(
      expect.arrayContaining([
        "headsets",
        "helmets",
        "glasses",
        "armors",
        "rigs",
        "backpacks",
        "containers",
        "grenades",
        "ammo-packs",
        "melee",
        "pistol-grips",
        "suppressors",
      ]),
    );
  });

  it("always has a category or type filter", () => {
    for (const page of allItemPages()) {
      if (page.panel !== "catalog") continue;
      const cats = page.categoryIds.filter(Boolean);
      const types = page.types?.filter(Boolean) ?? [];
      expect(page.categoryIds.every(Boolean)).toBe(true);
      expect(cats.length + types.length).toBeGreaterThan(0);
    }
  });
});
