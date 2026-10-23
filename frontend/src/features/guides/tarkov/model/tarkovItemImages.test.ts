import { describe, expect, it } from "vitest";
import {
  collectionItemImageUrl,
  handbookCategoryIconUrl,
  hdPreviewUrl,
  inspectImageUrl,
  inventoryThumbUrl,
  transparentThumbUrl,
} from "./tarkovItemImages";

describe("tarkov item image urls", () => {
  it("rewrites cdn suffixes to inventory / inspect variants", () => {
    const base = "https://assets.tarkov.dev/abc-base-image.webp";
    expect(inventoryThumbUrl(base)).toBe(
      "https://assets.tarkov.dev/abc-icon.webp",
    );
    expect(transparentThumbUrl("https://assets.tarkov.dev/abc-icon.webp")).toBe(
      "https://assets.tarkov.dev/abc-base-image.webp",
    );
    expect(hdPreviewUrl("https://assets.tarkov.dev/abc-icon.webp?x=1")).toBe(
      "https://assets.tarkov.dev/abc-512.webp?x=1",
    );
  });

  it("falls back to cdn icon when only the item id is known", () => {
    expect(inventoryThumbUrl("", "5910922b86f7747d96753483")).toBe(
      "https://assets.tarkov.dev/5910922b86f7747d96753483-icon.webp",
    );
    expect(inventoryThumbUrl(null, "not-an-id")).toBe("");
    expect(inventoryThumbUrl("")).toBe("");
  });

  it("inspectImageUrl prefers 512 then falls back to item id", () => {
    expect(
      inspectImageUrl({
        iconLink: "https://assets.tarkov.dev/abc-icon.webp",
      }),
    ).toBe("https://assets.tarkov.dev/abc-512.webp");
    expect(inspectImageUrl({}, "5910922b86f7747d96753483")).toBe(
      "https://assets.tarkov.dev/5910922b86f7747d96753483-512.webp",
    );
    expect(inspectImageUrl({})).toBe("");
  });

  it("uses 512px assets for collection tiles", () => {
    expect(
      collectionItemImageUrl("https://assets.tarkov.dev/abc-icon.webp"),
    ).toBe("https://assets.tarkov.dev/abc-512.webp");
    expect(collectionItemImageUrl("", "5910922b86f7747d96753483")).toBe(
      "https://assets.tarkov.dev/5910922b86f7747d96753483-512.webp",
    );
    expect(collectionItemImageUrl("", "not-an-id")).toBe("");
  });

  it("builds handbook category icon urls", () => {
    expect(handbookCategoryIconUrl("5b5f731a86f774093e6cb4f9")).toBe(
      "https://assets.tarkov.dev/handbook-category-5b5f731a86f774093e6cb4f9-icon.webp",
    );
    expect(handbookCategoryIconUrl("not-an-id")).toBe("");
    expect(handbookCategoryIconUrl("")).toBe("");
  });
});
