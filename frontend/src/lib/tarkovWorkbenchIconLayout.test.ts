import { describe, expect, it } from "vitest";
import {
  collectWorkbenchGridSlots,
  layoutWorkbenchGrid,
  slotFamily,
  workbenchGunArtSource,
  WORKBENCH_GUN_COL,
  WORKBENCH_STOCK_COL,
} from "./tarkovWorkbenchIconLayout";

describe("tarkovWorkbenchIconLayout", () => {
  it("maps nameId to slot families", () => {
    expect(slotFamily("mod_muzzle")).toBe("muzzle");
    expect(slotFamily("mod_tactical_001")).toBe("tactical");
    expect(slotFamily("mod_sight_rear")).toBe("rear_sight");
    expect(slotFamily("mod_pistol_grip")).toBe("pistol_grip");
    expect(slotFamily("mod_reciever")).toBe("receiver");
  });

  it("puts muzzle barrel and stock around the gun row", () => {
    const { cells, gunRow } = layoutWorkbenchGrid(
      collectWorkbenchGridSlots([
        { id: "slot-muzzle", name: "枪口", name_id: "mod_muzzle", children: [] },
        { id: "slot-barrel", name: "枪管", name_id: "mod_barrel", children: [] },
        { id: "slot-stock", name: "枪托", name_id: "mod_stock", children: [] },
        {
          id: "slot-mag",
          name: "弹匣",
          name_id: "mod_magazine",
          children: [],
        },
        {
          id: "slot-sight",
          name: "照门",
          name_id: "mod_sight_rear",
          children: [],
        },
      ]),
    );
    const byId = Object.fromEntries(cells.map((row) => [row.slotId, row]));
    expect(byId["slot-muzzle"].extras).toBe(false);
    expect(byId["slot-barrel"].extras).toBe(false);
    expect(byId["slot-muzzle"].col).toBeLessThan(byId["slot-barrel"].col!);
    expect(byId["slot-barrel"].col).toBeLessThan(WORKBENCH_GUN_COL);
    expect(byId["slot-stock"].col).toBe(WORKBENCH_STOCK_COL);
    expect(byId["slot-muzzle"].row).toBe(gunRow);
    expect(byId["slot-stock"].row).toBe(gunRow);
    expect(byId["slot-sight"].row).toBeLessThan(gunRow);
    expect(byId["slot-mag"].row).toBeGreaterThan(gunRow);
  });

  it("walks nested slots including empty ones and keeps children near the parent", () => {
    const collected = collectWorkbenchGridSlots([
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
    const { cells, gunRow } = layoutWorkbenchGrid(collected);
    const barrel = cells.find((row) => row.slotId === "slot-barrel")!;
    const nestedTac = cells.find((row) => row.slotId === "slot-tac-1")!;
    const nestedMuzzle = cells.find((row) => row.slotId === "slot-muzzle")!;
    expect(barrel.extras).toBe(false);
    expect(nestedTac.extras).toBe(false);
    expect(nestedMuzzle.extras).toBe(false);
    expect(nestedMuzzle.col).toBeLessThan(barrel.col!);
    expect(nestedMuzzle.row).toBe(gunRow);
    expect(barrel.row).toBe(gunRow);
    expect(nestedTac.col).toBe(barrel.col);
    expect(nestedTac.row).toBeLessThan(barrel.row!);
  });

  it("lays nested M4 barrel chain on the gun row instead of a left column", () => {
    const { cells, gunRow } = layoutWorkbenchGrid(
      collectWorkbenchGridSlots([
        {
          id: "slot-receiver",
          name: "机匣",
          name_id: "mod_reciever",
          installed: { id: "upper", short_name: "M4A1" },
          children: [
            {
              id: "slot-barrel",
              name: "枪管",
              name_id: "mod_barrel",
              installed: { id: "barrel", short_name: "14.5" },
              children: [
                {
                  id: "slot-gas",
                  name: "导气管",
                  name_id: "mod_gas_block",
                  installed: { id: "gas", short_name: "A2" },
                  children: [],
                },
                {
                  id: "slot-muzzle",
                  name: "枪口",
                  name_id: "mod_muzzle",
                  installed: { id: "muzzle", short_name: "USGI" },
                  children: [],
                },
              ],
            },
            {
              id: "slot-handguard",
              name: "护木",
              name_id: "mod_handguard",
              installed: { id: "hg", short_name: "M4" },
              children: [],
            },
            {
              id: "slot-sight",
              name: "照门",
              name_id: "mod_sight_rear",
              children: [],
            },
          ],
        },
        {
          id: "slot-stock",
          name: "枪托",
          name_id: "mod_stock",
          installed: { id: "stock", short_name: "M4SS" },
          children: [],
        },
        {
          id: "slot-grip",
          name: "手枪握把",
          name_id: "mod_pistol_grip",
          children: [],
        },
        {
          id: "slot-mag",
          name: "弹匣",
          name_id: "mod_magazine",
          children: [],
        },
        {
          id: "slot-charge",
          name: "拉机柄",
          name_id: "mod_charge",
          children: [],
        },
      ]),
    );
    const byId = Object.fromEntries(cells.map((row) => [row.slotId, row]));
    const left = [
      byId["slot-muzzle"],
      byId["slot-gas"],
      byId["slot-barrel"],
      byId["slot-handguard"],
      byId["slot-receiver"],
    ];
    for (const cell of left) {
      expect(cell.extras).toBe(false);
      expect(cell.row).toBe(gunRow);
    }
    expect(left.map((row) => row.col)).toEqual(
      [...left.map((row) => row.col)].sort((a, b) => (a || 0) - (b || 0)),
    );
    expect(byId["slot-receiver"].col).toBe(WORKBENCH_GUN_COL - 1);
    expect(byId["slot-stock"].col).toBe(WORKBENCH_STOCK_COL);
    expect(byId["slot-stock"].row).toBe(gunRow);
    expect(byId["slot-sight"].row).toBeLessThan(gunRow);
    expect(byId["slot-sight"].col).toBeGreaterThan(WORKBENCH_GUN_COL);
    expect(byId["slot-mag"].row).toBeGreaterThan(gunRow);
    expect(byId["slot-grip"].row).toBeGreaterThan(gunRow);
    expect(byId["slot-charge"].col).toBe(WORKBENCH_STOCK_COL);
    expect(byId["slot-charge"].row).toBeLessThan(gunRow);
  });

  it("sends unnamed extras like trigger below the grid", () => {
    const { cells } = layoutWorkbenchGrid(
      collectWorkbenchGridSlots([
        { id: "slot-stock", name_id: "mod_stock", children: [] },
        { id: "slot-trigger", name_id: "mod_trigger", children: [] },
      ]),
    );
    const trigger = cells.find((row) => row.slotId === "slot-trigger")!;
    expect(trigger.extras).toBe(true);
    expect(trigger.col).toBeNull();
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
});
