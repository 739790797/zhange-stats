import { describe, expect, it } from "vitest";
import {
  formatArmorMaterial,
  formatArmorSlotLabel,
  formatArmorType,
  formatArmorZoneLabel,
  formatArmorZoneList,
} from "./tarkovArmorLabels";

describe("formatArmorZoneLabel", () => {
  it("maps colliders, plate slots and simplified zones", () => {
    expect(formatArmorZoneLabel("Collider Type RibcageUp")).toBe("上胸");
    expect(formatArmorZoneLabel("Collider Type NeckFront")).toBe("喉咙");
    expect(formatArmorZoneLabel("Front_plate")).toBe("前胸");
    expect(formatArmorZoneLabel("Chest")).toBe("胸部");
    expect(formatArmorZoneLabel("Stomach")).toBe("腹部");
  });

  it("maps plate armor-zone enums without keeping Granit/SAPI codes", () => {
    expect(formatArmorZoneLabel("Armor Zone Plate_Granit_SAPI_chest")).toBe(
      "前胸插板",
    );
    expect(formatArmorZoneLabel("Armor Zone Plate_Granit_SAPI_back")).toBe(
      "后背插板",
    );
    expect(formatArmorZoneLabel("Armor Zone Plate_Granit_SAPI_side_left")).toBe(
      "左侧插板",
    );
    expect(
      formatArmorZoneLabel("Armor Zone Plate_SSAPI_side_left_high"),
    ).toBe("左侧插板（高）");
  });

  it("strips dump prefixes when the token is unknown", () => {
    expect(formatArmorZoneLabel("Collider Type BrandNewHitbox")).toBe(
      "BrandNewHitbox",
    );
  });
});

describe("formatArmorZoneList", () => {
  it("translates, dedupes and keeps order", () => {
    expect(
      formatArmorZoneList([
        "Collider Type RibcageUp",
        "Collider Type RibcageLow",
        "Collider Type RibcageUp",
        "Chest",
      ]),
    ).toBe("上胸 · 下胸 · 胸部");
    expect(formatArmorZoneList(["Chest", "Stomach"])).toBe("胸部 · 腹部");
  });
});

describe("formatArmorSlotLabel / material / type", () => {
  it("maps slot, material id/object and armor type", () => {
    expect(formatArmorSlotLabel("Front_plate")).toBe("前胸");
    expect(formatArmorMaterial("Aramid")).toBe("芳纶");
    expect(formatArmorMaterial("UHMWPE")).toBe("聚乙烯");
    expect(formatArmorMaterial({ id: "combined", name: "Combined" })).toBe(
      "复合材料",
    );
    expect(formatArmorMaterial({ id: "granit", name: "Granit" })).toBe("Granit");
    expect(formatArmorType("Heavy")).toBe("重型");
    expect(formatArmorType("Light")).toBe("轻型");
  });

  it("keeps upstream locale strings instead of the local fallback", () => {
    expect(formatArmorZoneLabel("胸腔上部")).toBe("胸腔上部");
    expect(formatArmorZoneList(["胸腔上部", "胸廓"])).toBe("胸腔上部 · 胸廓");
    expect(formatArmorSlotLabel("前部插板")).toBe("前部插板");
    expect(formatArmorMaterial("芳香族聚酰胺")).toBe("芳香族聚酰胺");
    expect(formatArmorType("轻甲")).toBe("轻甲");
  });
});
