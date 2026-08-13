import { describe, expect, it } from "vitest";
import {
  catalogColumnsForSlug,
  cheapestPrice,
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

  it("flattens zoom levels and names default ammo", () => {
    expect(formatPropValue("zoomLevels", [[1, 4], [6]])).toBe("1, 4, 6");
    expect(formatPropValue("defaultAmmo", { name: "5.56x45 M855" })).toBe(
      "5.56x45 M855",
    );
  });
});

describe("formatPropertyList links", () => {
  it("links default ammo, preset, maps, and handbook categories", () => {
    const rows = formatPropertyList({
      defaultAmmo: { id: "a1", name: "M855", types: ["ammo"] },
      defaultPreset: { id: "p1", name: "AK default", types: ["preset"] },
      usedOnMaps: [{ name: "海关", normalizedName: "customs" }],
      categories: [
        { id: "54009119af1c881c07000029", name: "Item" },
        { id: "5b47574386f77428ca22b342", name: "钥匙" },
      ],
    });
    expect(rows.find((r) => r.key === "defaultAmmo")?.links).toEqual([
      { label: "M855", href: "/guides/tarkov/items/ammo/a1" },
    ]);
    expect(rows.find((r) => r.key === "defaultPreset")?.links).toEqual([
      { label: "AK default", href: "/guides/tarkov/items/guns/p1" },
    ]);
    expect(rows.find((r) => r.key === "usedOnMaps")?.links).toEqual([
      { label: "海关", href: "/guides/tarkov/maps?map=customs" },
    ]);
    expect(rows.find((r) => r.key === "categories")?.links).toEqual([
      { label: "钥匙", href: "/guides/tarkov/items/keys" },
    ]);
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
