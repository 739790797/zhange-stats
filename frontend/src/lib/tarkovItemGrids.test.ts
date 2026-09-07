import { describe, expect, it } from "vitest";
import {
  composeGridOccupancy,
  extractGridPockets,
  gridOccupancyCaption,
  resolveItemGridLayout,
} from "./tarkovItemGrids";

const TACTEC_ID = "5c0e805e86f774683f3dd637";
const HALF_COL_ID = "5c0e746986f7741453628fe5";

describe("extractGridPockets", () => {
  it("prefers mapped layout for a known item id", () => {
    const pockets = extractGridPockets({}, TACTEC_ID);
    expect(pockets).toEqual([
      { row: 0, col: 0, width: 5, height: 5 },
      { row: 5, col: 0, width: 1, height: 2 },
      { row: 5, col: 1, width: 3, height: 2 },
      { row: 5, col: 4, width: 1, height: 2 },
    ]);
  });

  it("keeps half-cell pocket offsets from the map", () => {
    const pockets = extractGridPockets({}, HALF_COL_ID);
    expect(pockets.some((pocket) => pocket.col === 0.5)).toBe(true);
    expect(pockets.some((pocket) => pocket.col === 2.5)).toBe(true);
  });

  it("reuses a unique mapped silhouette when dump pocket sizes match", () => {
    const layout = resolveItemGridLayout({
      grids: [
        { width: 5, height: 5 },
        { width: 1, height: 2 },
        { width: 3, height: 2 },
        { width: 1, height: 2 },
      ],
    });
    expect(layout.kind).toBe("mapped");
    expect(layout.pockets).toEqual(extractGridPockets({}, TACTEC_ID));
  });

  it("does not invent a silhouette when pocket sizes are ambiguous", () => {
    const layout = resolveItemGridLayout({
      grids: [
        { width: 1, height: 1 },
        { width: 1, height: 1 },
        { width: 1, height: 1 },
        { width: 1, height: 1 },
        { width: 1, height: 1 },
        { width: 1, height: 1 },
        { width: 1, height: 2 },
        { width: 1, height: 2 },
        { width: 1, height: 2 },
        { width: 1, height: 2 },
        { width: 1, height: 2 },
        { width: 1, height: 2 },
      ],
    });
    expect(layout.kind).toBe("stacked");
    expect(layout.pockets[0]).toMatchObject({ col: 0, row: 0 });
    const occupied = new Set(
      layout.pockets.map((pocket) => `${pocket.col},${pocket.row}`),
    );
    expect(occupied.size).toBe(layout.pockets.length);
  });
});

describe("composeGridOccupancy", () => {
  it("leaves holes between mapped pockets", () => {
    const occupancy = composeGridOccupancy([
      { col: 0, row: 0, width: 2, height: 1 },
      { col: 1, row: 1, width: 1, height: 1 },
    ]);
    expect(occupancy).not.toBeNull();
    const filled = occupancy!.cells.filter(Boolean).length;
    expect(filled).toBe(12);
    expect(occupancy!.cells[8]).toBe(false);
  });

  it("places half-column pockets without overlapping neighbors", () => {
    const occupancy = composeGridOccupancy(
      extractGridPockets({}, HALF_COL_ID),
    );
    expect(occupancy).not.toBeNull();
    const filled = occupancy!.cells.filter(Boolean).length;
    const expected = extractGridPockets({}, HALF_COL_ID).reduce(
      (sum, pocket) => sum + pocket.width * pocket.height * 4,
      0,
    );
    expect(filled).toBe(expected);
  });
});

describe("gridOccupancyCaption", () => {
  it("lists slot count and pocket sizes", () => {
    expect(
      gridOccupancyCaption(
        [
          { width: 5, height: 7, col: 0, row: 0 },
          { width: 2, height: 2, col: 5, row: 0 },
        ],
        45,
      ),
    ).toBe("39 格 · 容量 45 · 5×7 · 2×2");
  });
});
