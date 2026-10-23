import { describe, expect, it } from "vitest";
import { ror2ItemDetailHref, ror2ItemDetailKind, ror2ItemRouteId } from "./ror2ItemDetail";

describe("ROR2 item detail routes", () => {
  it("uses stable internal names and preserves list search parameters", () => {
    const item = {
      name: "Fireworks",
      rarity: "Common",
      internal_name: "ITEM_FIREWORKS",
      code: "FIREWORKS",
    };

    expect(ror2ItemDetailKind(item)).toBe("item");
    expect(ror2ItemRouteId(item)).toBe("ITEM_FIREWORKS");
    expect(ror2ItemDetailHref(item, "?cat=Common&q=fireworks")).toBe(
      "/guides/ror2/items/item/ITEM_FIREWORKS?cat=Common&q=fireworks",
    );
  });

  it("distinguishes equipment and falls back to code or encoded source name", () => {
    expect(ror2ItemDetailKind({ rarity: "Elite Equipment" })).toBe("equipment");
    expect(ror2ItemRouteId({ name: "Fuel", code: "EQUIPMENT_FUEL", internal_name: "" })).toBe("EQUIPMENT_FUEL");
    expect(ror2ItemDetailHref({ name: "Old Coin", code: "", internal_name: "", rarity: "Common" })).toBe(
      "/guides/ror2/items/item/Old%20Coin",
    );
  });
});
