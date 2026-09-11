import { describe, expect, it } from "vitest";
import {
  categoryGroupKey,
  collectInstalledCategoryIds,
  findGunsmithSpec,
  formatGunsmithConstraint,
  gunsmithLiveCheck,
  isGunsmithConstraintLive,
  isGunsmithObjectiveType,
  isGunsmithTask,
  orderedGunsmithConstraints,
  type GunsmithSpec,
} from "./tarkovWorkbenchGunsmith";

const spec: GunsmithSpec = {
  id: "gs:o1",
  task_id: "gs",
  objective_id: "o1",
  task_name: "Gunsmith - Part 1",
  weapon_id: "gun1",
  constraints: {
    min_ergonomics: 45,
    max_recoil_sum: 800,
    max_weight: 4,
  },
  required_items: [{ id: "grip1", name: "握把" }],
  required_category_groups: [[{ id: "cat-sight", name: "瞄具" }]],
  loadable: true,
};

describe("tarkovWorkbenchGunsmith", () => {
  it("detects buildWeapon objectives", () => {
    expect(isGunsmithObjectiveType("buildWeapon")).toBe(true);
    expect(isGunsmithTask(["shoot", "buildWeapon"])).toBe(true);
    expect(isGunsmithTask(["shoot"])).toBe(false);
  });

  it("formats constraint labels", () => {
    expect(formatGunsmithConstraint("min_ergonomics", 45)).toBe("人机 ≥ 45");
    expect(formatGunsmithConstraint("max_recoil_sum", 800)).toBe("后坐和 ≤ 800");
    expect(formatGunsmithConstraint("min_durability", 60)).toBe("耐久 ≥ 60%");
    expect(formatGunsmithConstraint("max_weight", 4.8)).toBe("重量 ≤ 4.8");
    expect(formatGunsmithConstraint("max_width", 4)).toBe("格仓宽 ≤ 4");
  });

  it("orders dump constraints and marks size/durability as not live", () => {
    expect(isGunsmithConstraintLive("min_ergonomics")).toBe(true);
    expect(isGunsmithConstraintLive("min_durability")).toBe(false);
    expect(
      orderedGunsmithConstraints({
        max_width: 4,
        min_ergonomics: 21,
        min_durability: 60,
      }).map(([key]) => key),
    ).toEqual(["min_durability", "min_ergonomics", "max_width"]);
  });

  it("picks the matching objective or the first row", () => {
    const items = [
      { ...spec, objective_id: "o1" },
      { ...spec, id: "gs:o2", objective_id: "o2", weapon_id: "gun2" },
    ];
    expect(findGunsmithSpec(items, "gs", "o2")?.weapon_id).toBe("gun2");
    expect(findGunsmithSpec(items, "gs")?.objective_id).toBe("o1");
    expect(findGunsmithSpec(items, "missing")).toBeNull();
  });

  it("collects category ids and keys groups", () => {
    expect(
      collectInstalledCategoryIds([
        { category_ids: ["a", ""] },
        { category_ids: ["b"] },
      ]),
    ).toEqual(["a", "b"]);
    expect(categoryGroupKey([{ id: "a" }, { id: "b" }])).toBe("a\0b");
  });

  it("checks live constraints against installed parts", () => {
    const fail = gunsmithLiveCheck(
      spec,
      {
        ergonomics: 20,
        recoil_vertical: 500,
        recoil_horizontal: 400,
        weight: 5,
      },
      ["other"],
      [],
    );
    expect(fail?.ok).toBe(false);
    expect(fail?.missingItemIds).toEqual(["grip1"]);
    expect(fail?.unmetConstraints).toEqual([
      "min_ergonomics",
      "max_recoil_sum",
      "max_weight",
    ]);
    expect(fail?.missingCategoryGroups).toHaveLength(1);

    const ok = gunsmithLiveCheck(
      spec,
      {
        ergonomics: 50,
        recoil_vertical: 300,
        recoil_horizontal: 200,
        weight: 3,
      },
      ["grip1"],
      ["cat-sight"],
    );
    expect(ok?.ok).toBe(true);

    const magCap = gunsmithLiveCheck(
      { ...spec, constraints: { max_mag_capacity: 10 } },
      { mag_capacity: 30 },
      ["grip1"],
      ["cat-sight"],
    );
    expect(magCap?.unmetConstraints).toEqual(["max_mag_capacity"]);

    const notes = gunsmithLiveCheck(
      {
        ...spec,
        constraints: { min_durability: 60, max_width: 3, min_ergonomics: 45 },
      },
      {
        ergonomics: 50,
        recoil_vertical: 0,
        recoil_horizontal: 0,
        weight: 1,
      },
      ["grip1"],
      ["cat-sight"],
    );
    expect(notes?.unmetConstraints).toEqual([]);
  });
});
