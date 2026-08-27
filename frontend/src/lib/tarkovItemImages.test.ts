import { describe, expect, it } from "vitest";
import {
  hdPreviewUrl,
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
});
