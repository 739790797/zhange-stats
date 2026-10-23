import { describe, expect, it } from "vitest";
import {
  hazardOutlineColor,
  usableOutlinePoints,
} from "./tarkovMapMarkerOutlines";

describe("tarkov map marker outlines", () => {
  it("needs at least three finite x/z points", () => {
    expect(usableOutlinePoints(undefined)).toEqual([]);
    expect(usableOutlinePoints([{ x: 1, z: 2 }, { x: 3, z: 4 }])).toEqual([]);
    expect(
      usableOutlinePoints([
        { x: 1, z: 2 },
        { x: 3, z: 4 },
        { x: 5, z: 6 },
      ]),
    ).toEqual([
      { x: 1, z: 2 },
      { x: 3, z: 4 },
      { x: 5, z: 6 },
    ]);
  });

  it("uses warmer stroke for mortar than mines", () => {
    expect(hazardOutlineColor("mortar")).toBe("#c8932a");
    expect(hazardOutlineColor("minefield")).toBe("#d44a4a");
  });
});
