import { describe, expect, it } from "vitest";
import {
  catalogColumnsForSlug,
  catalogColumnLabel,
  catalogRowIsArmored,
  catalogSortableColumnIds,
  cheapestPrice,
  compareCatalogRows,
  DEFAULT_AMMO_HINT,
  extractContentLines,
  extractGridPockets,
  extractPlateSlots,
  formatPropValue,
  formatPropertyList,
  innerSlots,
  itemHasFlea,
  matchRigKindFilter,
  namedTraderOffers,
  parseItemBuyOffers,
  parseVendorOffers,
  splitVendorOffers,
} from "./tarkovItemFormat";

describe("catalogColumnsForSlug", () => {
  it("uses backpacks / armor presets and falls back", () => {
    expect(catalogColumnsForSlug("backpacks")).toContain("slots");
    expect(catalogColumnsForSlug("armors")).toEqual([
      "name",
      "class",
      "weight",
      "ergoPenalty",
      "speedPenalty",
      "turnPenalty",
      "price",
    ]);
    expect(catalogColumnsForSlug("rigs")).toEqual([
      "name",
      "slots",
      "weight",
      "ergoPenalty",
      "speedPenalty",
      "turnPenalty",
      "price",
    ]);
    expect(catalogColumnsForSlug("ammo-packs")).toContain("slots");
    expect(catalogColumnsForSlug("melee")).toEqual([
      "name",
      "slashDamage",
      "stabDamage",
      "weight",
      "price",
    ]);
    expect(catalogColumnsForSlug("unknown-cat")).toEqual([
      "name",
      "grid",
      "weight",
      "price",
    ]);
  });
});

describe("catalogColumnLabel / compareCatalogRows", () => {
  it("relabels rig capacity and penalty columns", () => {
    expect(catalogColumnLabel("rigs", "slots")).toBe("容量");
    expect(catalogColumnLabel("rigs", "turnPenalty")).toBe("转向惩罚");
    expect(catalogColumnLabel("armors", "turnPenalty")).toBe("转向惩罚");
    expect(catalogColumnLabel("armors", "class")).toBe("等级");
    expect(catalogColumnLabel("backpacks", "slots")).toBe("内部格");
    expect(catalogColumnLabel("helmets", "turnPenalty")).toBe("转向");
    expect(catalogColumnLabel("rigs", "ergoPenalty")).toBe("人机惩罚");
    expect(catalogColumnLabel("rigs", "speedPenalty")).toBe("移速惩罚");
  });

  it("does not sort the name column on client-sorted catalogs", () => {
    expect(catalogSortableColumnIds("rigs", catalogColumnsForSlug("rigs"))).toEqual([
      "slots",
      "weight",
      "ergoPenalty",
      "speedPenalty",
      "turnPenalty",
      "price",
    ]);
    expect(catalogSortableColumnIds("armors", catalogColumnsForSlug("armors"))).toEqual([
      "class",
      "weight",
      "ergoPenalty",
      "speedPenalty",
      "turnPenalty",
      "price",
    ]);
    expect(catalogSortableColumnIds("backpacks", catalogColumnsForSlug("backpacks"))).toEqual(
      [],
    );
  });

  it("filters plain vs armored rigs", () => {
    const pouch = { id: "p", name: "56式", properties: { capacity: 8 } };
    const sewn = { id: "s", name: "6B3", properties: { class: 4 } };
    const plates = { id: "c", name: "TacTec", properties: { armored: true } };
    expect(catalogRowIsArmored(pouch)).toBe(false);
    expect(catalogRowIsArmored(sewn)).toBe(true);
    expect(catalogRowIsArmored(plates)).toBe(true);
    expect(matchRigKindFilter(pouch, "all")).toBe(true);
    expect(matchRigKindFilter(pouch, "plain")).toBe(true);
    expect(matchRigKindFilter(pouch, "armored")).toBe(false);
    expect(matchRigKindFilter(plates, "plain")).toBe(false);
    expect(matchRigKindFilter(plates, "armored")).toBe(true);
  });

  it("sorts numeric columns with empty values last", () => {
    const light = {
      id: "a",
      name: "轻",
      weight: 1,
      last_low_price: 10,
      properties: { capacity: 12, ergoPenalty: -0.1 },
    };
    const heavy = {
      id: "b",
      name: "重",
      weight: 4,
      last_low_price: 50,
      properties: { capacity: 20, ergoPenalty: -0.2 },
    };
    const missing = { id: "c", name: "无", properties: {} };
    expect(compareCatalogRows(light, heavy, "weight", "ascend")).toBeLessThan(0);
    expect(compareCatalogRows(light, heavy, "slots", "descend")).toBeGreaterThan(0);
    expect(compareCatalogRows(missing, light, "weight", "ascend")).toBeGreaterThan(0);
    expect(compareCatalogRows(missing, light, "weight", "descend")).toBeGreaterThan(0);
    const class4 = { id: "d", name: "甲", properties: { class: 4 } };
    const class6 = { id: "e", name: "重甲", properties: { class: 6 } };
    expect(compareCatalogRows(class4, class6, "class", "ascend")).toBeLessThan(0);
    expect(compareCatalogRows(class4, class6, "class", "descend")).toBeGreaterThan(0);
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
      armored: true,
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
      "胸部 · 腹部",
    );
    expect(
      formatPropValue("zones", [
        "Collider Type RibcageUp",
        "Armor Zone Plate_Granit_SAPI_chest",
      ]),
    ).toBe("上胸 · 前胸插板");
    expect(formatPropValue("material", "Aramid")).toBe("芳纶");
    expect(formatPropValue("armorType", "Light")).toBe("轻型");
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

  it("hides unlabeled dump keys", () => {
    const rows = formatPropertyList({
      weight: 1.2,
      someInternalFlag: true,
      mysteryObject: { id: "x" },
    });
    expect(rows.map((r) => r.key)).toEqual(["weight"]);
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

  it("reads json dump buyFromTrader rows", () => {
    const offers = parseVendorOffers([
      {
        trader: { id: "abc", normalizedName: "prapor", name: "Prapor" },
        price: 49222,
        priceRUB: 49222,
        currency: "RUB",
        minTraderLevel: 2,
      },
    ]);
    expect(offers[0]).toMatchObject({
      vendor: "prapor",
      vendorName: "Prapor",
      priceRub: 49222,
      minLevel: 2,
    });
  });

  it("maps dump sellToTrader trader ids to slugs", () => {
    const offers = parseVendorOffers([
      {
        trader: "54cb57776803fa99248b456e",
        price: 40800,
        priceRUB: 40800,
        currency: "RUB",
      },
    ]);
    expect(offers[0]).toMatchObject({
      vendor: "therapist",
      vendorName: "Therapist",
      priceRub: 40800,
    });
  });
});

describe("parseItemBuyOffers", () => {
  it("merges buyFor and buyFromTrader, first vendor wins", () => {
    const offers = parseItemBuyOffers({
      buyFor: [
        {
          price: 100,
          currency: "RUB",
          priceRUB: 100,
          vendor: { name: "Prapor", normalizedName: "prapor" },
        },
      ],
      buyFromTrader: [
        {
          price: 200,
          currency: "RUB",
          priceRUB: 200,
          trader: { name: "Prapor", normalizedName: "prapor" },
        },
        {
          price: 50,
          currency: "RUB",
          priceRUB: 50,
          trader: { name: "Therapist", normalizedName: "therapist" },
        },
      ],
    });
    expect(offers.map((row) => [row.vendor, row.priceRub])).toEqual([
      ["prapor", 100],
      ["therapist", 50],
    ]);
  });
});

describe("splitVendorOffers", () => {
  it("separates flea from traders", () => {
    const { flea, traders } = splitVendorOffers([
      {
        vendor: "flea-market",
        vendorName: "Flea",
        price: 1,
        currency: "RUB",
        priceRub: 1,
        minLevel: null,
      },
      {
        vendor: "prapor",
        vendorName: "Prapor",
        price: 2,
        currency: "RUB",
        priceRub: 2,
        minLevel: 1,
      },
    ]);
    expect(flea.map((row) => row.vendor)).toEqual(["flea-market"]);
    expect(traders.map((row) => row.vendor)).toEqual(["prapor"]);
  });

  it("namedTraderOffers drops flea and empty vendors", () => {
    expect(
      namedTraderOffers([
        {
          vendor: "flea-market",
          vendorName: "Flea",
          price: 1,
          currency: "RUB",
          priceRub: 1,
          minLevel: null,
        },
        {
          vendor: "",
          vendorName: "—",
          price: 2,
          currency: "RUB",
          priceRub: 2,
          minLevel: null,
        },
        {
          vendor: "prapor",
          vendorName: "Prapor",
          price: 3,
          currency: "RUB",
          priceRub: 3,
          minLevel: 1,
        },
      ]).map((row) => row.vendor),
    ).toEqual(["prapor"]);
  });
});

describe("extractGridPockets", () => {
  it("uses dump coordinates when every pocket has them", () => {
    expect(
      extractGridPockets({
        grids: [
          { width: 4, height: 5, col: 0, row: 0 },
          { width: 1, height: 2, col: 4, row: 0 },
        ],
      }),
    ).toEqual([
      { width: 4, height: 5, col: 0, row: 0 },
      { width: 1, height: 2, col: 4, row: 0 },
    ]);
  });

  it("packs pockets without overlapping when coordinates are missing", () => {
    expect(
      extractGridPockets({
        grids: [
          { width: 4, height: 5, col: 0, row: 0 },
          { width: 1, height: 2 },
        ],
      }),
    ).toEqual([
      { width: 4, height: 5, col: 0, row: 0 },
      { width: 1, height: 2, col: 4, row: 0 },
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
