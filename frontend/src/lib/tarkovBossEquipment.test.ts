import { describe, expect, it } from "vitest";
import {
  bossGearAmmoStats,
  bossGearArmorClassLabel,
  bossGearItemLabel,
  groupBossGearSlots,
  mergeBossArmorSlots,
  splitBossGearContains,
} from "./tarkovBossEquipment";

describe("groupBossGearSlots", () => {
  it("splits wear / arms / carry and keeps slot order", () => {
    const grouped = groupBossGearSlots([
      { key: "gun", label: "武器" },
      { key: "headwear", label: "头部装备" },
      { key: "keys", label: "钥匙" },
      { key: "armor", label: "身体护甲" },
      { key: "mystery", label: "未知" },
    ]);
    expect(grouped.map((row) => row.id)).toEqual(["wear", "arms", "carry"]);
    expect(grouped[0]?.slots.map((row) => row.key)).toEqual([
      "headwear",
      "armor",
    ]);
    expect(grouped[1]?.slots.map((row) => row.key)).toEqual(["gun"]);
    expect(grouped[2]?.slots.map((row) => row.key)).toEqual(["keys", "mystery"]);
  });

  it("omits empty groups", () => {
    expect(
      groupBossGearSlots([{ key: "meds", label: "医疗物品" }]).map(
        (row) => row.id,
      ),
    ).toEqual(["carry"]);
  });
});

describe("bossGearItemLabel", () => {
  it("prefers short name only when compact", () => {
    const item = {
      name: "RPK-16 5.45x39 轻机枪",
      short_name: "RPK-16",
      item_id: "rpk",
      count: 1,
    };
    expect(bossGearItemLabel(item)).toBe("RPK-16 5.45x39 轻机枪");
    expect(bossGearItemLabel(item, true)).toBe("RPK-16");
  });

  it("prefixes count when more than one", () => {
    expect(
      bossGearItemLabel({ name: "F-1", short_name: "F-1", count: 3 }),
    ).toBe("3× F-1");
  });
});

describe("mergeBossArmorSlots", () => {
  it("keeps vests and plates in one 身体护甲 slot", () => {
    expect(
      mergeBossArmorSlots([
        {
          key: "armor",
          label: "防弹衣",
          items: [{ item_id: "vest", types: ["armor"] }],
        },
        {
          key: "armorPlate",
          label: "防弹插板",
          items: [{ item_id: "plate", types: ["armorPlate"] }],
        },
        { key: "rig", label: "战术胸挂", items: [{ item_id: "av", types: ["rig"] }] },
      ]),
    ).toEqual([
      {
        key: "armor",
        label: "身体护甲",
        items: [
          { item_id: "vest", types: ["armor"] },
          { item_id: "plate", types: ["armorPlate"] },
        ],
      },
      { key: "rig", label: "战术胸挂", items: [{ item_id: "av", types: ["rig"] }] },
    ]);
  });

  it("renames a plate-only slot back to 身体护甲", () => {
    expect(
      mergeBossArmorSlots([
        {
          key: "armorPlate",
          label: "防弹插板",
          items: [{ item_id: "plate", types: ["armorPlate"] }],
        },
      ]),
    ).toEqual([
      {
        key: "armor",
        label: "身体护甲",
        items: [{ item_id: "plate", types: ["armorPlate"] }],
      },
    ]);
  });
});

describe("bossGearArmorClassLabel", () => {
  it("formats plate class under the name", () => {
    expect(bossGearArmorClassLabel({ armor_class: 4 })).toBe("4级");
    expect(bossGearArmorClassLabel({ armor_class: 5.2 })).toBe("5级");
    expect(bossGearArmorClassLabel({})).toBe("");
    expect(bossGearArmorClassLabel({ armor_class: 0 })).toBe("");
  });
});

describe("splitBossGearContains", () => {
  it("splits magazines, ammo and plates", () => {
    const split = splitBossGearContains([
      { item_id: "mag", kind: "magazine", types: ["mods"] },
      { item_id: "bp", kind: "ammo", types: ["ammo"] },
      { item_id: "plate", kind: "plate", types: ["armorPlate"] },
      { item_id: "odd", types: ["mods"] },
    ]);
    expect(split.magazines.map((row) => row.item_id)).toEqual(["mag"]);
    expect(split.ammo.map((row) => row.item_id)).toEqual(["bp"]);
    expect(split.plates.map((row) => row.item_id)).toEqual(["plate"]);
    expect(split.other.map((row) => row.item_id)).toEqual(["odd"]);
  });

  it("falls back to types when kind is missing", () => {
    const split = splitBossGearContains([{ item_id: "bt", types: ["ammo"] }]);
    expect(split.ammo).toHaveLength(1);
  });
});

describe("bossGearAmmoStats", () => {
  it("keeps missing stats as null", () => {
    expect(bossGearAmmoStats({})).toEqual({
      damage: null,
      penetration: null,
      armorDamage: null,
    });
  });

  it("reads damage / penetration / armor damage", () => {
    expect(
      bossGearAmmoStats({ damage: 52, penetration: 38, armor_damage: 44 }),
    ).toEqual({ damage: 52, penetration: 38, armorDamage: 44 });
  });
});
