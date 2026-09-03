import { describe, expect, it } from "vitest";
import {
  estimatedCanvasTooltipHeight,
  lootDetailCardOverflowFlip,
  oppositeTooltipSide,
  pickTooltipVerticalSide,
  spawnTooltipSideAfterLayout,
  tooltipBoxesOverlap,
  tooltipOffsetForSide,
  tooltipSideFromClassName,
} from "./tarkovMapTooltip";

describe("tarkov map tooltip side", () => {
  it("keeps the bubble above when there is room", () => {
    expect(
      pickTooltipVerticalSide({
        pointY: 400,
        mapHeight: 600,
        tooltipHeight: 80,
      }),
    ).toBe("top");
  });

  it("flips below when the marker is near the top", () => {
    expect(
      pickTooltipVerticalSide({
        pointY: 40,
        mapHeight: 600,
        tooltipHeight: 96,
      }),
    ).toBe("bottom");
  });

  it("stays above when the marker is near the bottom", () => {
    expect(
      pickTooltipVerticalSide({
        pointY: 560,
        mapHeight: 600,
        tooltipHeight: 96,
      }),
    ).toBe("top");
  });

  it("honors prefer when both sides fit", () => {
    expect(
      pickTooltipVerticalSide({
        pointY: 300,
        mapHeight: 600,
        tooltipHeight: 40,
        prefer: "bottom",
      }),
    ).toBe("bottom");
  });

  it("picks the larger leftover side when neither fits", () => {
    expect(
      pickTooltipVerticalSide({
        pointY: 30,
        mapHeight: 80,
        tooltipHeight: 60,
      }),
    ).toBe("bottom");
    expect(
      pickTooltipVerticalSide({
        pointY: 50,
        mapHeight: 80,
        tooltipHeight: 60,
      }),
    ).toBe("top");
  });

  it("mirrors offset for top vs bottom", () => {
    expect(tooltipOffsetForSide("top", 18)).toEqual([0, -18]);
    expect(tooltipOffsetForSide("bottom", 18)).toEqual([0, 18]);
    expect(oppositeTooltipSide("top")).toBe("bottom");
  });

  it("reads leaflet direction classes", () => {
    expect(tooltipSideFromClassName("leaflet-tooltip leaflet-tooltip-top")).toBe(
      "top",
    );
    expect(
      tooltipSideFromClassName("leaflet-tooltip leaflet-tooltip-bottom spawn"),
    ).toBe("bottom");
    expect(tooltipSideFromClassName("leaflet-tooltip")).toBeNull();
  });

  it("estimates loot icon rows a bit taller than a name chip", () => {
    expect(estimatedCanvasTooltipHeight(`<div class="lootLooseTip"></div>`)).toBe(
      56,
    );
    expect(estimatedCanvasTooltipHeight("<strong>Boss</strong>")).toBe(48);
  });

  it("flips spawn bubbles to the other side of an overlapping quest tip", () => {
    const self = { left: 40, top: 80, right: 200, bottom: 160 };
    const quest = { left: 50, top: 70, right: 220, bottom: 150 };
    expect(tooltipBoxesOverlap(self, quest)).toBe(true);
    expect(
      spawnTooltipSideAfterLayout({
        current: "top",
        self,
        others: [{ box: quest, side: "top", isQuest: true }],
        pointY: 180,
        mapHeight: 600,
        tooltipHeight: 80,
      }),
    ).toBe("bottom");
  });

  it("keeps the spawn side when the quest bubble does not overlap", () => {
    expect(
      spawnTooltipSideAfterLayout({
        current: "top",
        self: { left: 10, top: 10, right: 80, bottom: 40 },
        others: [
          {
            box: { left: 200, top: 10, right: 280, bottom: 40 },
            side: "top",
            isQuest: true,
          },
        ],
        pointY: 50,
        mapHeight: 600,
        tooltipHeight: 40,
      }),
    ).toBe("top");
  });

  it("flips a nested item card when it would leave the map", () => {
    const wrap = { left: 0, top: 0, right: 400, bottom: 300 };
    expect(
      lootDetailCardOverflowFlip(
        { left: 350, top: 40, right: 520, bottom: 100 },
        wrap,
      ),
    ).toEqual({ flipX: true, flipY: false });
    expect(
      lootDetailCardOverflowFlip(
        { left: 20, top: -20, right: 180, bottom: 40 },
        wrap,
      ),
    ).toEqual({ flipX: false, flipY: true });
  });
});
