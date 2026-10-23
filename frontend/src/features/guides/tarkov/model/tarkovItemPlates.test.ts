import { describe, expect, it } from "vitest";
import {
  collapsedPresetHref,
  extractPlateTableRows,
  isCollapsedItemPreset,
  plateColumnFilters,
  plateColumnMatch,
  platePresetMarks,
  presetKindFromName,
} from "./tarkovItemPlates";

describe("presetKindFromName", () => {
  it("reads default flag and stripped locale", () => {
    expect(presetKindFromName("TacTec 默认", true)).toBe("default");
    expect(presetKindFromName("TacTec 默认")).toBe("default");
    expect(presetKindFromName("TacTec Stripped")).toBe("stripped");
    expect(presetKindFromName("风暴灰 剥离")).toBe("stripped");
    expect(presetKindFromName("丛林绿")).toBeNull();
  });
});

describe("isCollapsedItemPreset", () => {
  it("collapses rig/armor presets but keeps guns", () => {
    expect(isCollapsedItemPreset(["preset"], ["rig"])).toBe(true);
    expect(isCollapsedItemPreset(["preset"], ["armor"])).toBe(true);
    expect(isCollapsedItemPreset(["preset", "gun"], ["gun"])).toBe(false);
    expect(isCollapsedItemPreset(["preset"], ["gun"])).toBe(false);
    expect(isCollapsedItemPreset(["rig"], ["rig"])).toBe(false);
  });
});

describe("collapsedPresetHref", () => {
  it("sends non-gun presets to the base item page", () => {
    expect(
      collapsedPresetHref({
        id: "preset-1",
        item: { types: ["preset"] },
        properties: {
          baseItem: { id: "rig-1", types: ["rig"] },
        },
      }),
    ).toBe("/guides/tarkov/items/rigs/rig-1");
  });

  it("leaves gun presets on their own page", () => {
    expect(
      collapsedPresetHref({
        id: "preset-g",
        item: { types: ["preset"] },
        properties: {
          baseItem: { id: "gun-1", types: ["gun"] },
        },
      }),
    ).toBeNull();
  });
});

describe("extractPlateTableRows", () => {
  const properties = {
    defaultPreset: {
      id: "p-default",
      name: "胸挂 默认",
      default: true,
      types: ["preset"],
      containsItems: [{ item: { id: "front-a", types: ["armorPlate"] } }],
    },
    presets: [
      {
        id: "p-default",
        name: "胸挂 默认",
        default: true,
        containsItems: [{ item: { id: "front-a", types: ["armorPlate"] } }],
      },
      {
        id: "p-stripped",
        name: "胸挂 Stripped",
        containsItems: [],
      },
    ],
    armorSlots: [
      {
        name: "Front_plate",
        allowedPlates: [
          {
            id: "front-a",
            name: "Granit 4",
            iconLink: "a.webp",
            types: ["armorPlate"],
            class: 5,
            durability: 50,
            weight: 3.3,
            lastLowPrice: 80000,
            armorType: "Heavy",
            material: { id: "granit", name: "Granit" },
            ergoPenalty: -0.025,
            speedPenalty: -0.03,
            turnPenalty: -0.01,
          },
          {
            id: "front-b",
            name: "SAPI",
            types: ["armorPlate"],
            class: 4,
            durability: 40,
            weight: 1.8,
            lastLowPrice: 40000,
            armorType: "Light",
            material: "Aramid",
            ergoPenalty: -0.01,
            speedPenalty: -0.01,
            turnPenalty: 0,
          },
        ],
      },
    ],
  };

  it("flattens slots and tags factory plates", () => {
    const rows = extractPlateTableRows(properties);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({
      id: "front-a",
      slot: "前胸",
      class: 5,
      material: "Granit",
      armorType: "重型",
      ergoPenalty: -0.025,
      badges: ["default"],
      price: 80000,
    });
    expect(rows[1]).toMatchObject({
      material: "芳纶",
      armorType: "轻型",
      turnPenalty: 0,
      badges: [],
    });
  });

  it("builds filter options for slot / class / material / armor type", () => {
    const rows = extractPlateTableRows(properties);
    expect(plateColumnFilters(rows, "slot")).toEqual([
      { text: "前胸", value: "前胸" },
    ]);
    expect(plateColumnFilters(rows, "class").map((row) => row.value)).toEqual([
      "4",
      "5",
    ]);
    expect(plateColumnFilters(rows, "material").map((row) => row.text)).toEqual([
      "芳纶",
      "Granit",
    ]);
    expect(plateColumnMatch(rows[0], "armorType", "重型")).toBe(true);
    expect(plateColumnMatch(rows[1], "armorType", "重型")).toBe(false);
  });

  it("still lists stripped even when it has no plates", () => {
    expect(platePresetMarks(properties).map((row) => row.kind)).toEqual([
      "default",
      "stripped",
    ]);
  });
});
