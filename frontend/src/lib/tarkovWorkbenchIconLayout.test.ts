import { describe, expect, it } from "vitest";
import {
  collectSlotHotspots,
  layoutWorkbenchIcons,
  nearestWorkbenchSlot,
  slotAnchor,
  workbenchGunArtSource,
} from "./tarkovWorkbenchIconLayout";

describe("tarkovWorkbenchIconLayout", () => {
  it("puts muzzle barrel receiver and stock in different side-view bands", () => {
    const muzzle = slotAnchor("mod_muzzle");
    const barrel = slotAnchor("mod_barrel");
    const grip = slotAnchor("mod_pistol_grip");
    const stock = slotAnchor("mod_stock");
    expect(muzzle.x).toBeLessThan(barrel.x);
    expect(barrel.x).toBeLessThan(50);
    expect(stock.x).toBeGreaterThan(grip.x);
    expect(grip.y).toBeGreaterThan(slotAnchor("mod_scope").y);
  });

  it("walks nested slots including empty ones and offsets duplicate families", () => {
    const collected = collectSlotHotspots([
      {
        id: "slot-stock",
        name: "枪托",
        name_id: "mod_stock",
        required: true,
        installed: null,
        children: [],
      },
      {
        id: "slot-barrel",
        name_id: "mod_barrel",
        installed: { id: "b1", name: "Barrel", icon_link: "https://x/b.png" },
        children: [
          {
            id: "slot-tac-1",
            name_id: "mod_tactical",
            installed: { id: "t1", short_name: "Tac1", icon_link: "https://x/t1.png" },
            children: [],
          },
          {
            id: "slot-muzzle",
            name: "枪口",
            name_id: "mod_muzzle",
            installed: null,
            children: [],
          },
        ],
      },
      {
        id: "slot-tac-2",
        name_id: "mod_tactical_001",
        installed: { id: "t2", short_name: "Tac2", icon_link: "https://x/t2.png" },
        children: [],
      },
    ]);
    expect(collected.map((row) => row.slotId)).toEqual([
      "slot-stock",
      "slot-barrel",
      "slot-tac-1",
      "slot-muzzle",
      "slot-tac-2",
    ]);
    expect(collected.filter((row) => row.empty).map((row) => row.slotId)).toEqual([
      "slot-stock",
      "slot-muzzle",
    ]);
    const laid = layoutWorkbenchIcons(collected);
    const tacs = laid.filter((row) => row.nameId.includes("tactical"));
    expect(tacs).toHaveLength(2);
    expect(tacs[0].x !== tacs[1].x || tacs[0].y !== tacs[1].y).toBe(true);
  });

  it("uses dump gun art: preset when parts installed, receiver image when bare", () => {
    expect(
      workbenchGunArtSource({
        imageLink: "https://cdn/gun-image.webp",
        presetImageLink: "https://cdn/gun-preset.webp",
        hasInstalled: true,
      }),
    ).toBe("https://cdn/gun-preset.webp");
    expect(
      workbenchGunArtSource({
        imageLink: "https://cdn/gun-image.webp",
        presetImageLink: "https://cdn/gun-preset.webp",
        hasInstalled: false,
      }),
    ).toBe("https://cdn/gun-image.webp");
    expect(
      workbenchGunArtSource({
        imageLink: "https://cdn/gun-image.webp",
        presetImageLink: "",
        hasInstalled: true,
      }),
    ).toBe("https://cdn/gun-image.webp");
  });

  it("picks the nearest slot within range and ignores far clicks", () => {
    const pieces = [
      { slotId: "muzzle", x: 10, y: 48 },
      { slotId: "stock", x: 80, y: 48 },
    ];
    expect(nearestWorkbenchSlot(pieces, 12, 50)).toBe("muzzle");
    expect(nearestWorkbenchSlot(pieces, 78, 46)).toBe("stock");
    expect(nearestWorkbenchSlot(pieces, 50, 10)).toBeNull();
  });
});
