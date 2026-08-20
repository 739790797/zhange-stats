import { describe, expect, it } from "vitest";
import type { TarkovAmmoItem } from "@/api/guidesApi";
import {
  ammoScatterAxisMax,
  filterAmmoByIds,
} from "./tarkovAmmoScatter";

function ammo(partial: Partial<TarkovAmmoItem> & Pick<TarkovAmmoItem, "id">): TarkovAmmoItem {
  return {
    name: partial.id,
    short_name: "",
    caliber: "Caliber556x45NATO",
    ammo_type: "bullet",
    damage: 0,
    penetration: 0,
    armor_damage: 0,
    initial_speed: 0,
    accuracy_modifier: 0,
    recoil_modifier: 0,
    light_bleed_modifier: 0,
    heavy_bleed_modifier: 0,
    icon_link: "",
    ...partial,
  };
}

describe("filterAmmoByIds", () => {
  const items = [ammo({ id: "a" }), ammo({ id: "b" }), ammo({ id: "c" })];

  it("keeps only requested ids", () => {
    expect(filterAmmoByIds(items, ["c", "a"]).map((row) => row.id)).toEqual([
      "a",
      "c",
    ]);
  });

  it("ignores blank ids", () => {
    expect(filterAmmoByIds(items, ["", "  "])).toEqual([]);
  });
});

describe("ammoScatterAxisMax", () => {
  it("ceils to the next 10 with a floor of 10", () => {
    expect(ammoScatterAxisMax([])).toEqual({ x: 10, y: 10 });
    expect(
      ammoScatterAxisMax([
        ammo({ id: "a", penetration: 41, damage: 85 }),
        ammo({ id: "b", penetration: 50, damage: 72 }),
      ]),
    ).toEqual({ x: 50, y: 90 });
  });
});
