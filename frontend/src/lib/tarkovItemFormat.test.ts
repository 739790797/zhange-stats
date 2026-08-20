import { describe, expect, it } from "vitest";
import {
  catalogColumnsForSlug,
  cheapestPrice,
  DEFAULT_AMMO_HINT,
  extractContentLines,
  extractGridPockets,
  extractPlateSlots,
  formatPropValue,
  formatPropertyList,
  innerSlots,
  itemHasFlea,
  parseVendorOffers,
} from "./tarkovItemFormat";

describe("catalogColumnsForSlug", () => {
  it("uses backpacks / armor presets and falls back", () => {
    expect(catalogColumnsForSlug("backpacks")).toContain("slots");
    expect(catalogColumnsForSlug("armors")).toContain("class");
    expect(catalogColumnsForSlug("unknown-cat")).toEqual([
      "name",
      "grid",
      "weight",
      "price",
    ]);
  });
});

describe("innerSlots", () => {
  it("prefers capacity then sums grids", () => {
    expect(innerSlots({ capacity: 20 })).toBe(20);
    expect(
      innerSlots({
        grids: [
          { width: 2, height: 2 },
          { width: 1, height: 3 },
        ],
      }),
    ).toBe(7);
  });
});

describe("cheapestPrice", () => {
  it("prefers flea then avg then base", () => {
    expect(
      cheapestPrice({
        last_low_price: 10,
        avg24h_price: 20,
        base_price: 30,
      }),
    ).toBe(10);
    expect(
      cheapestPrice({ last_low_price: null, avg24h_price: 0, base_price: 30 }),
    ).toBe(30);
  });
});

describe("formatPropertyList", () => {
  it("skips slots and formats grids / penalties", () => {
    const rows = formatPropertyList({
      slots: [{ id: "x" }],
      propertiesType: "ItemPropertiesBackpack",
      grids: [{ width: 4, height: 5 }],
      turnPenalty: 0.05,
      weight: 1.2,
    });
    expect(rows.map((r) => r.key)).toEqual(["weight", "turnPenalty", "grids"]);
    expect(rows.find((r) => r.key === "grids")?.value).toBe("4×5");
    expect(rows.find((r) => r.key === "turnPenalty")?.value).toBe("5%");
  });
});

describe("formatPropValue", () => {
  it("joins armor zones", () => {
    expect(formatPropValue("zones", ["Chest", "Stomach"])).toBe(
      "Chest · Stomach",
    );
  });

  it("flattens zoom levels", () => {
    expect(formatPropValue("zoomLevels", [[1, 4], [6]])).toBe("1, 4, 6");
  });
});

describe("formatPropertyList links", () => {
  it("marks default ammo inside allowed ammo instead of a separate row", () => {
    const rows = formatPropertyList({
      defaultAmmo: {
        id: "a1",
        name: "M855",
        types: ["ammo"],
        iconLink: "https://example/a.webp",
      },
      allowedAmmo: [
        { id: "a2", name: "M995", types: ["ammo"] },
        {
          id: "a1",
          name: "M855",
          types: ["ammo"],
          iconLink: "https://example/a.webp",
        },
      ],
      defaultPreset: { id: "p1", name: "AK default", types: ["preset"] },
      usedOnMaps: [{ name: "海关", normalizedName: "customs" }],
      categories: [
        { id: "54009119af1c881c07000029", name: "Item" },
        { id: "5b47574386f77428ca22b342", name: "钥匙" },
      ],
    });
    expect(rows.find((r) => r.key === "defaultAmmo")).toBeUndefined();
    const ammo = rows.find((r) => r.key === "allowedAmmo");
    expect(ammo?.note).toBe(DEFAULT_AMMO_HINT);
    expect(ammo?.links).toEqual([
      {
        label: "M855",
        href: "/guides/tarkov/items/ammo/a1",
        id: "a1",
        types: ["ammo"],
        icon: "https://example/a.webp",
        badge: "默认",
      },
      {
        label: "M995",
        href: "/guides/tarkov/items/ammo/a2",
        id: "a2",
        types: ["ammo"],
      },
    ]);
    expect(rows.find((r) => r.key === "defaultPreset")?.links).toEqual([
      {
        label: "AK default",
        href: "/guides/tarkov/items/guns/p1",
        id: "p1",
        types: ["preset"],
      },
    ]);
    expect(rows.find((r) => r.key === "usedOnMaps")?.links).toEqual([
      { label: "海关", href: "/guides/tarkov/maps/customs" },
    ]);
    expect(rows.find((r) => r.key === "categories")?.links).toEqual([
      { label: "钥匙", href: "/guides/tarkov/items/keys" },
    ]);
  });

  it("does not annotate allowed ammo when there is no default round", () => {
    const rows = formatPropertyList({
      allowedAmmo: [{ id: "a2", name: "M995", types: ["ammo"] }],
    });
    expect(rows.find((r) => r.key === "allowedAmmo")?.note).toBeUndefined();
    expect(rows.find((r) => r.key === "allowedAmmo")?.links?.[0]?.badge).toBeUndefined();
  });

  it("links presets and hides unresolved content ids", () => {
    const rows = formatPropertyList({
      presets: [{ id: "p1", name: "AK default", types: ["preset"] }],
      conflictingItems: [{ id: "m1", name: "瞄具", types: ["sights"] }],
    });
    expect(rows.find((r) => r.key === "presets")?.links).toEqual([
      {
        label: "AK default",
        href: "/guides/tarkov/items/guns/p1",
        id: "p1",
        types: ["preset"],
      },
    ]);
    expect(rows.find((r) => r.key === "conflictingItems")?.links?.[0]?.label).toBe(
      "瞄具",
    );
    expect(
      extractContentLines({
        content: [
          "录音正文",
          "5fbe3ffdf8b6a877a729ea82",
          "abc_Note_Page1_Text1",
        ],
      }),
    ).toEqual(["录音正文"]);
  });

  it("does not dump bare tarkov ids", () => {
    const rows = formatPropertyList({
      defaultAmmo: "5fbe3ffdf8b6a877a729ea82",
      allowedAmmo: ["5fbe3ffdf8b6a877a729ea82"],
      defaultPreset: "5fd251a31189a17bcc172662",
      categories: ["54009119af1c881c07000029", "5447b5f14bdc2d61278b4567"],
    });
    expect(rows.find((r) => r.key === "defaultAmmo")).toBeUndefined();
    expect(rows.find((r) => r.key === "allowedAmmo")).toBeUndefined();
    expect(rows.find((r) => r.key === "defaultPreset")).toBeUndefined();
    expect(rows.find((r) => r.key === "categories")).toBeUndefined();
  });

  it("hides preset default flag", () => {
    const rows = formatPropertyList({
      default: true,
      ergonomics: 71.9,
    });
    expect(rows.find((r) => r.key === "default")).toBeUndefined();
    expect(rows.find((r) => r.key === "ergonomics")?.value).toBe("71.9");
  });
});

describe("parseVendorOffers", () => {
  it("reads GraphQL-style sellFor rows", () => {
    const offers = parseVendorOffers([
      {
        price: 40000,
        currency: "RUB",
        priceRUB: 40000,
        vendor: { name: "Flea Market", normalizedName: "flea-market" },
      },
    ]);
    expect(offers[0]?.vendor).toBe("flea-market");
    expect(offers[0]?.priceRub).toBe(40000);
  });

  it("falls back to loyaltyLevel requirements", () => {
    const offers = parseVendorOffers([
      {
        price: 12,
        currency: "USD",
        priceRUB: 1200,
        vendor: { name: "Peacekeeper", normalizedName: "peacekeeper" },
        requirements: [{ type: "loyaltyLevel", value: 3 }],
      },
    ]);
    expect(offers[0]?.minLevel).toBe(3);
  });
});

describe("extractGridPockets", () => {
  it("reads width/height and optional col/row", () => {
    expect(
      extractGridPockets({
        grids: [
          { width: 4, height: 5, col: 0, row: 0 },
          { width: 1, height: 2 },
        ],
      }),
    ).toEqual([
      { width: 4, height: 5, col: 0, row: 0 },
      { width: 1, height: 2, col: 1, row: 0 },
    ]);
  });
});

describe("extractPlateSlots", () => {
  it("keeps slots that list allowed plates", () => {
    const groups = extractPlateSlots({
      armorSlots: [
        { name: "Front", durability: 40, class: 4, zones: ["Chest"] },
        {
          name: "Plate",
          allowedPlates: [
            { id: "p1", name: "SAPI", iconLink: "x.webp", types: ["armorPlate"] },
          ],
        },
      ],
    });
    expect(groups).toEqual([
      {
        key: "1-Plate",
        name: "Plate",
        plates: [
          { id: "p1", name: "SAPI", icon: "x.webp", types: ["armorPlate"] },
        ],
      },
    ]);
  });
});

describe("itemHasFlea", () => {
  it("hides flea for noFlea types", () => {
    expect(itemHasFlea({ types: ["keys", "noFlea"] })).toBe(false);
    expect(itemHasFlea({ types: ["ammo"] })).toBe(true);
  });
});
