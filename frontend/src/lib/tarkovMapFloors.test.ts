import { describe, expect, it } from "vitest";
import {
  MAP_OFF_LEVEL_OPACITY,
  isSvgBaseFloorGroup,
  mapBaseOffLevel,
  svgFloorGroupClasses,
} from "./tarkovMapFloors";

describe("svgFloorGroupClasses", () => {
  it("keeps the ground group visible when a height floor is selected", () => {
    expect(
      svgFloorGroupClasses({ id: "Ground_Level" }, "Ground_Level", "Second_Floor"),
    ).toEqual({
      "base-layer": true,
      "overlay-layer": false,
      "hidden-layer": false,
    });
  });

  it("treats keep-with-base groups as ground", () => {
    expect(
      isSvgBaseFloorGroup(
        { id: "Roads", keepWithGroup: "Ground_Level" },
        "Ground_Level",
      ),
    ).toBe(true);
    expect(
      svgFloorGroupClasses(
        { id: "Roads", keepWithGroup: "Ground_Level" },
        "Ground_Level",
        "Second_Floor",
      )["hidden-layer"],
    ).toBe(false);
  });

  it("shows only the selected overlay floor", () => {
    expect(
      svgFloorGroupClasses({ id: "Second_Floor" }, "Ground_Level", "Second_Floor"),
    ).toEqual({
      "base-layer": false,
      "overlay-layer": true,
      "hidden-layer": false,
    });
    expect(
      svgFloorGroupClasses({ id: "Third_Floor" }, "Ground_Level", "Second_Floor")[
        "hidden-layer"
      ],
    ).toBe(true);
  });

  it("hides overlay floors on the ground view", () => {
    expect(
      svgFloorGroupClasses({ id: "Second_Floor" }, "Ground_Level", "")[
        "hidden-layer"
      ],
    ).toBe(true);
    expect(mapBaseOffLevel("")).toBe(false);
    expect(mapBaseOffLevel("Second_Floor")).toBe(true);
    expect(mapBaseOffLevel("First_Floor", true)).toBe(false);
    expect(mapBaseOffLevel("Second_Floor", true)).toBe(false);
    expect(MAP_OFF_LEVEL_OPACITY).toBeGreaterThan(0.2);
    expect(MAP_OFF_LEVEL_OPACITY).toBeLessThan(1);
  });
});
