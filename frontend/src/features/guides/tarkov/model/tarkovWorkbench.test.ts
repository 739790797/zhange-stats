import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  collectSlotIds,
  findSlotNode,
  filterWorkbenchParts,
  formatSignedStat,
  formatWorkbenchErgo,
  pairsFromTree,
  partConflictsWith,
  pairsSignature,
  replacePair,
  replaceSlotInstalled,
  sortWorkbenchParts,
  toggleWorkbenchPartSort,
  workbenchEvoErgoDelta,
  workbenchArmStaminaSeconds,
  workbenchEquipErgoModifier,
  workbenchOverswing,
  clampWorkbenchStrengthLevel,
  clampWorkbenchEquipErgoPenaltyPct,
  formatWorkbenchAccuracyMoa,
  formatWorkbenchArmStamina,
  formatWorkbenchEed,
  formatWorkbenchMuzzleVelocity,
  loadWorkbenchStrengthLevel,
  saveWorkbenchStrengthLevel,
  loadWorkbenchEquipErgoPenaltyPct,
  saveWorkbenchEquipErgoPenaltyPct,
  WORKBENCH_STRENGTH_STORAGE_KEY,
  WORKBENCH_EQUIP_ERGO_PENALTY_STORAGE_KEY,
} from "./tarkovWorkbench";

describe("tarkovWorkbench", () => {
  it("signatures ignore pair order", () => {
    expect(
      pairsSignature([
        { slot_id: "stock", item_id: "s1" },
        { slot_id: "grip", item_id: "g1" },
      ]),
    ).toBe("grip:g1,stock:s1");
    expect(pairsSignature([])).toBe("");
  });

  it("walks installed pairs from a slot tree", () => {
    expect(
      pairsFromTree([
        {
          id: "grip",
          name: "握把",
          installed: { id: "g1", name: "Grip" },
          children: [
            {
              id: "rail",
              name: "导轨",
              installed: { id: "r1", name: "Rail" },
              children: [],
            },
          ],
        },
        { id: "stock", name: "枪托", children: [] },
      ]),
    ).toEqual([
      { slot_id: "grip", item_id: "g1" },
      { slot_id: "rail", item_id: "r1" },
    ]);
  });

  it("replaces or clears a slot pair", () => {
    const pairs = [
      { slot_id: "grip", item_id: "g1" },
      { slot_id: "stock", item_id: "s1" },
    ];
    expect(replacePair(pairs, "grip", "g2")).toEqual([
      { slot_id: "stock", item_id: "s1" },
      { slot_id: "grip", item_id: "g2" },
    ]);
    expect(replacePair(pairs, "stock", null)).toEqual([
      { slot_id: "grip", item_id: "g1" },
    ]);
    expect(
      replacePair(
        [
          { slot_id: "grip", item_id: "g1" },
          { slot_id: "rail", item_id: "r1" },
          { slot_id: "stock", item_id: "s1" },
        ],
        "grip",
        "g2",
        ["rail"],
      ),
    ).toEqual([
      { slot_id: "stock", item_id: "s1" },
      { slot_id: "grip", item_id: "g2" },
    ]);
  });

  it("replaces a slot in the tree and drops nested children", () => {
    const tree = [
      {
        id: "grip",
        name: "握把",
        installed: { id: "g1", name: "Grip" },
        children: [
          {
            id: "rail",
            name: "导轨",
            installed: { id: "r1", name: "Rail" },
            children: [],
          },
        ],
      },
    ];
    const next = replaceSlotInstalled(tree, "grip", { id: "g2", name: "Grip 2" });
    expect(next[0].installed?.id).toBe("g2");
    expect(next[0].children).toEqual([]);
    expect(
      replaceSlotInstalled(tree, "rail", null)[0].children?.[0].installed,
    ).toBeNull();
  });

  it("formats signed attachment stats", () => {
    expect(formatSignedStat(0)).toBe("0");
    expect(formatSignedStat(8)).toBe("+8");
    expect(formatSignedStat(-0.08)).toBe("-0.08");
  });

  it("collects slot ids depth-first", () => {
    expect(
      collectSlotIds([
        {
          id: "grip",
          name: "握把",
          children: [{ id: "rail", name: "导轨", children: [] }],
        },
        { id: "stock", name: "枪托" },
      ]),
    ).toEqual(["grip", "rail", "stock"]);
    expect(
      findSlotNode(
        [
          {
            id: "grip",
            name: "握把",
            children: [{ id: "rail", name: "导轨" }],
          },
        ],
        "rail",
      )?.name,
    ).toBe("导轨");
  });

  it("flags parts that conflict with other installed items", () => {
    expect(
      partConflictsWith(
        { id: "grip2", conflicting_ids: ["stock1"] },
        ["grip2", "stock1"],
        "grip2",
      ),
    ).toBe(true);
    expect(
      partConflictsWith(
        { id: "grip2", conflicting_ids: ["stock1"] },
        ["grip2"],
        "grip2",
      ),
    ).toBe(false);
    expect(
      partConflictsWith(
        { id: "stock1" },
        ["grip2", "stock1"],
        "stock1",
        [{ id: "grip2", conflicting_ids: ["stock1"] }],
      ),
    ).toBe(true);
  });

  it("filters parts by name or short name", () => {
    const parts = [
      { id: "a", name: "Geissele Super Precision", short_name: "GSP" },
      { id: "b", name: "Aimpoint Micro H-2", short_name: "H-2" },
    ];
    expect(filterWorkbenchParts(parts, "aim").map((row) => row.id)).toEqual(["b"]);
    expect(filterWorkbenchParts(parts, "gsp").map((row) => row.id)).toEqual(["a"]);
    expect(filterWorkbenchParts(parts, "  ").map((row) => row.id)).toEqual(["a", "b"]);
  });

  it("toggles column sort and sorts by the selected field", () => {
    expect(
      toggleWorkbenchPartSort({ key: "ergonomics", dir: "desc" }, "ergonomics"),
    ).toEqual({ key: "ergonomics", dir: "asc" });
    expect(
      toggleWorkbenchPartSort({ key: "ergonomics", dir: "desc" }, "name"),
    ).toEqual({ key: "name", dir: "asc" });
    const parts = [
      { id: "a", name: "B", ergonomics: 1, recoil_modifier: 0.1, weight: 2, price_rub: 100 },
      { id: "b", name: "A", ergonomics: 8, recoil_modifier: -0.2, weight: 1, price_rub: 50 },
    ];
    expect(
      sortWorkbenchParts(parts, { key: "name", dir: "asc" }).map((row) => row.id),
    ).toEqual(["b", "a"]);
    expect(
      sortWorkbenchParts(parts, { key: "ergonomics", dir: "desc" }).map((row) => row.id),
    ).toEqual(["b", "a"]);
    expect(
      sortWorkbenchParts(parts, { key: "recoil", dir: "asc" }).map((row) => row.id),
    ).toEqual(["b", "a"]);
  });

  it("computes evo ergo delta with the same cap as overswing", () => {
    expect(workbenchEvoErgoDelta(0, 0)).toBe(43.7);
    expect(workbenchEvoErgoDelta(55, 3.179)).toBe(52.9);
    expect(workbenchEvoErgoDelta(10, 20)).toBeLessThan(0);
    expect(workbenchOverswing(10, 20)).toBe(true);
    expect(workbenchOverswing(55, 3.179)).toBe(false);
    expect(workbenchEvoErgoDelta(55, 3.179, -0.15)).toBe(40.0);
    expect(formatWorkbenchErgo(55)).toBe("55");
    expect(formatWorkbenchErgo(67.9)).toBe("67.9");
    expect(formatWorkbenchAccuracyMoa(1.82)).toBe("1.82 MOA");
    expect(formatWorkbenchAccuracyMoa(null)).toBe("—");
    expect(formatWorkbenchArmStamina(35)).toBe("35.0s");
    expect(formatWorkbenchEed(52.9)).toBe("+52.9");
    expect(formatWorkbenchEed(-1.2)).toBe("-1.2");
    expect(formatWorkbenchMuzzleVelocity(900)).toBe("900 m/s");
    expect(formatWorkbenchMuzzleVelocity(null)).toBe("—");
  });

  it("recomputes arm stamina from strength and equipment ergo", () => {
    expect(workbenchArmStaminaSeconds(3.179, 55)).toBe(35.0);
    expect(workbenchArmStaminaSeconds(3.179, 55, 0)).toBe(33.7);
    expect(workbenchArmStaminaSeconds(3.179, 55, 51)).toBe(40.6);
    expect(workbenchArmStaminaSeconds(3.179, 55, 10, -0.15)).toBe(34.8);
    expect(clampWorkbenchStrengthLevel(-4)).toBe(0);
    expect(clampWorkbenchStrengthLevel(99)).toBe(51);
    expect(clampWorkbenchStrengthLevel("nope")).toBe(10);
    expect(clampWorkbenchEquipErgoPenaltyPct(150)).toBe(100);
    expect(workbenchEquipErgoModifier(15)).toBe(-0.15);
  });
});

describe("tarkovWorkbench player prefs", () => {
  const mem = new Map<string, string>();

  beforeEach(() => {
    mem.clear();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => mem.get(key) ?? null,
      setItem: (key: string, value: string) => {
        mem.set(key, value);
      },
      removeItem: (key: string) => {
        mem.delete(key);
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("remembers strength and equipment ergo penalty", () => {
    expect(loadWorkbenchStrengthLevel()).toBe(10);
    expect(loadWorkbenchEquipErgoPenaltyPct()).toBe(0);
    saveWorkbenchStrengthLevel(22);
    saveWorkbenchEquipErgoPenaltyPct(15);
    expect(mem.get(WORKBENCH_STRENGTH_STORAGE_KEY)).toBe("22");
    expect(mem.get(WORKBENCH_EQUIP_ERGO_PENALTY_STORAGE_KEY)).toBe("15");
    expect(loadWorkbenchStrengthLevel()).toBe(22);
    expect(loadWorkbenchEquipErgoPenaltyPct()).toBe(15);
  });
});
