import { describe, expect, it } from "vitest";
import {
  detectInventoryGrid,
  detectKeyboxGrid,
  groupWordsByRowColumn,
  keyIconBodyRect,
  keyNameBandAdmissible,
  keyNameBandDestRect,
  keyNameBandHasInk,
  keyNameBandRect,
  KEY_NAME_BAND_TARGET_HEIGHT,
  KEY_NAME_BAND_TARGET_WIDTH,
  keyRowSheetChunks,
  keyRowSheetColumnAt,
  keyRowSheetLayout,
} from "./tarkovKeyOcrGrid";
import { describeKeyOcrCell, overlayCellLabel, overlayLabelTop } from "./tarkovKeyOcrOverlay";

function paintGrid(opts: {
  cols: number;
  rows: number;
  cell: number;
  line: number;
  header: number;
  pad: number;
  durabilityAt?: number;
}): { data: Uint8ClampedArray; width: number; height: number } {
  const { cols, rows, cell, line, header, pad, durabilityAt } = opts;
  const width = pad * 2 + cols * cell + (cols + 1) * line;
  const height = header + pad + rows * cell + (rows + 1) * line;
  const data = new Uint8ClampedArray(width * height * 4);
  const set = (x: number, y: number, v: number) => {
    if (x < 0 || y < 0 || x >= width || y >= height) return;
    const i = (y * width + x) * 4;
    data[i] = v;
    data[i + 1] = v;
    data[i + 2] = v;
    data[i + 3] = 255;
  };
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) set(x, y, y < header ? 48 : 18);
  }
  const gridTop = header;
  const gridLeft = pad;
  for (let row = 0; row <= rows; row += 1) {
    const y0 = gridTop + row * (cell + line);
    for (let y = y0; y < y0 + line; y += 1) {
      for (let x = gridLeft; x < gridLeft + cols * cell + (cols + 1) * line; x += 1) {
        set(x, y, 170);
      }
    }
  }
  for (let col = 0; col <= cols; col += 1) {
    const x0 = gridLeft + col * (cell + line);
    for (let x = x0; x < x0 + line; x += 1) {
      for (let y = gridTop; y < gridTop + rows * cell + (rows + 1) * line; y += 1) {
        set(x, y, 170);
      }
    }
  }
  if (durabilityAt != null) {
    for (let row = 0; row < rows; row += 1) {
      const y0 =
        gridTop + line + row * (cell + line) + Math.round(cell * durabilityAt);
      for (let y = y0; y < y0 + 2; y += 1) {
        for (let x = gridLeft; x < gridLeft + cols * cell + (cols + 1) * line; x += 1) {
          set(x, y, 160);
        }
      }
    }
  }
  return { data, width, height };
}

describe("detectInventoryGrid", () => {
  it("finds a regular inventory grid", () => {
    const { data, width, height } = paintGrid({
      cols: 8,
      rows: 5,
      cell: 40,
      line: 2,
      header: 22,
      pad: 6,
    });
    const grid = detectInventoryGrid(data, width, height);
    expect(grid).not.toBeNull();
    expect(grid?.cols).toBe(8);
    expect(grid?.rows).toBe(5);
    expect(grid?.cells.length).toBe(40);
    expect(grid?.cellWidth).toBeGreaterThanOrEqual(38);
    expect(grid?.cellWidth).toBeLessThanOrEqual(44);
  });

  it("finds a 4-column page with larger cells", () => {
    const { data, width, height } = paintGrid({
      cols: 4,
      rows: 4,
      cell: 120,
      line: 3,
      header: 28,
      pad: 8,
    });
    const grid = detectInventoryGrid(data, width, height);
    expect(grid).not.toBeNull();
    expect(grid?.cols).toBe(4);
    expect(grid?.rows).toBe(4);
    expect(grid?.cells.length).toBe(16);
  });

  it("keeps square rows when durability bars add a shorter period", () => {
    const { data, width, height } = paintGrid({
      cols: 8,
      rows: 5,
      cell: 40,
      line: 2,
      header: 22,
      pad: 6,
      durabilityAt: 0.72,
    });
    const grid = detectInventoryGrid(data, width, height);
    expect(grid).not.toBeNull();
    expect(grid?.cols).toBe(8);
    expect(grid?.rows).toBe(5);
    expect(grid?.cells.length).toBe(40);
  });

  it("returns null on empty noise", () => {
    const width = 320;
    const height = 220;
    const data = new Uint8ClampedArray(width * height * 4);
    for (let i = 0; i < data.length; i += 4) {
      data[i] = 20;
      data[i + 1] = 20;
      data[i + 2] = 20;
      data[i + 3] = 255;
    }
    expect(detectInventoryGrid(data, width, height)).toBeNull();
  });

  it("finds oversized cells after detect-scale", () => {
    const painted = paintGrid({
      cols: 10,
      rows: 4,
      cell: 200,
      line: 4,
      header: 30,
      pad: 12,
    });
    expect(detectInventoryGrid(painted.data, painted.width, painted.height)).toBeNull();
    const grid = detectKeyboxGrid(painted.data, painted.width, painted.height);
    expect(grid).not.toBeNull();
    expect(grid?.cols).toBe(10);
    expect(grid?.rows).toBe(4);
    expect(grid?.cellWidth).toBeGreaterThan(180);
  });
});

describe("keyIconBodyRect", () => {
  it("sits below the short-name band and above durability", () => {
    const cell = { col: 0, row: 0, x: 10, y: 20, width: 80, height: 80 };
    const band = keyNameBandRect(cell);
    const body = keyIconBodyRect(cell);
    expect(body.y).toBeGreaterThanOrEqual(band.y + band.height - 4);
    expect(body.y + body.height).toBeLessThan(cell.y + cell.height - 8);
    expect(body.x).toBeGreaterThan(cell.x);
    expect(body.width).toBeLessThan(cell.width);
  });
});

describe("keyNameBandRect", () => {
  it("takes the top of the cell", () => {
    const band = keyNameBandRect({
      col: 0,
      row: 0,
      x: 10,
      y: 20,
      width: 58,
      height: 57,
    });
    expect(band.y).toBe(21);
    expect(band.height).toBeGreaterThanOrEqual(18);
    expect(band.height).toBeLessThanOrEqual(24);
    expect(band.x).toBe(12);
  });

  it("rejects a name band that is too small to recover", () => {
    const band = keyNameBandRect({
      col: 0,
      row: 0,
      x: 0,
      y: 0,
      width: 20,
      height: 20,
    });
    expect(band.height).toBeLessThan(10);
    expect(keyNameBandAdmissible(band)).toBe(false);
  });

  it("fits any admitted band into the same target slot", () => {
    const small = keyNameBandDestRect({ x: 0, y: 0, width: 54, height: 22 });
    const large = keyNameBandDestRect({ x: 0, y: 0, width: 122, height: 48 });
    expect(small.width).toBeLessThanOrEqual(KEY_NAME_BAND_TARGET_WIDTH);
    expect(small.height).toBeLessThanOrEqual(KEY_NAME_BAND_TARGET_HEIGHT);
    expect(large.width).toBeLessThanOrEqual(KEY_NAME_BAND_TARGET_WIDTH);
    expect(large.height).toBeLessThanOrEqual(KEY_NAME_BAND_TARGET_HEIGHT);
  });
});

describe("keyNameBandHasInk", () => {
  it("skips empty dark cells and keeps text", () => {
    const width = 80;
    const height = 40;
    const data = new Uint8ClampedArray(width * height * 4);
    for (let i = 0; i < data.length; i += 4) {
      data[i] = 18;
      data[i + 1] = 18;
      data[i + 2] = 18;
      data[i + 3] = 255;
    }
    const empty = { x: 4, y: 2, width: 70, height: 20 };
    expect(keyNameBandHasInk(data, width, height, empty)).toBe(false);
    for (let y = 6; y < 18; y += 1) {
      for (let x = 10; x < 50; x += 1) {
        const i = (y * width + x) * 4;
        data[i] = 210;
        data[i + 1] = 210;
        data[i + 2] = 210;
      }
    }
    expect(keyNameBandHasInk(data, width, height, empty)).toBe(true);
  });
});

describe("keyOcrOverlay", () => {
  it("marks empty dark bands and keeps inked ones", () => {
    const width = 80;
    const height = 50;
    const data = new Uint8ClampedArray(width * height * 4);
    for (let i = 0; i < data.length; i += 4) {
      data[i] = 18;
      data[i + 1] = 18;
      data[i + 2] = 18;
      data[i + 3] = 255;
    }
    const empty = describeKeyOcrCell(
      { col: 1, row: 2, x: 4, y: 4, width: 70, height: 40 },
      data,
      width,
      height,
    );
    expect(empty.skip).toBe("empty");
    expect(overlayCellLabel(empty)).toBe("");
    expect(overlayLabelTop(empty)).toBe(empty.band.y + empty.band.height + 1);
    for (let y = 6; y < 20; y += 1) {
      for (let x = 10; x < 50; x += 1) {
        const i = (y * width + x) * 4;
        data[i] = 210;
        data[i + 1] = 210;
        data[i + 2] = 210;
      }
    }
    const inked = describeKeyOcrCell(
      { col: 1, row: 2, x: 4, y: 4, width: 70, height: 40 },
      data,
      width,
      height,
    );
    expect(inked.skip).toBeUndefined();
    expect(overlayCellLabel(inked)).toBe("");
    expect(overlayCellLabel({ ...inked, ocrText: "10/10 卡", matchShort: undefined })).toBe(
      "",
    );
    expect(overlayCellLabel({ ...inked, matchShort: "西203" })).toBe("西203");
    expect(overlayLabelTop(inked)).toBe(inked.band.y + inked.band.height + 1);
  });
});

describe("keyRowSheetChunks", () => {
  it("splits an 11-column row into groups of five", () => {
    expect(keyRowSheetChunks(11)).toEqual([
      { start: 0, count: 5 },
      { start: 5, count: 5 },
      { start: 10, count: 1 },
    ]);
  });
});

describe("keyRowSheetLayout", () => {
  it("maps word centers back to columns", () => {
    const layout = keyRowSheetLayout(11);
    expect(layout.columns).toBe(11);
    expect(keyRowSheetColumnAt(layout.cellXs[0] + 20, layout)).toBe(0);
    expect(keyRowSheetColumnAt(layout.cellXs[3] + 40, layout)).toBe(3);
    expect(
      groupWordsByRowColumn(
        [
          { text: "218钥匙", x0: layout.cellXs[0], x1: layout.cellXs[0] + 80 },
          { text: "Goshan", x0: layout.cellXs[4], x1: layout.cellXs[4] + 90 },
        ],
        layout,
      )[0],
    ).toBe("218钥匙");
    expect(
      groupWordsByRowColumn(
        [{ text: "Goshan", x0: layout.cellXs[4], x1: layout.cellXs[4] + 90 }],
        layout,
      )[4],
    ).toBe("Goshan");
  });
});
