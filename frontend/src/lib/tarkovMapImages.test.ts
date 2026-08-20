import { describe, expect, it } from "vitest";
import {
  findInteractiveMap,
  findRasterMap,
  floorLabel,
  svgFallbackUrl,
} from "@/lib/tarkovMapImages";

describe("tarkov map images", () => {
  it("resolves interactive customs with svg and tiles", () => {
    const layer = findInteractiveMap("customs");
    expect(layer?.key).toBe("customs");
    expect(layer?.svgPath).toContain("Customs.svg");
    expect(layer?.tilePath).toContain("customs_0.16");
    expect(layer?.bounds?.length).toBe(2);
  });

  it("uses factory interactive for night-factory alt map", () => {
    const layer = findInteractiveMap("night-factory", "factory");
    expect(layer?.key).toBe("factory");
    expect(layer?.svgPath).toContain("Factory.svg");
  });

  it("resolves lab alias via parent/group", () => {
    const layer = findInteractiveMap("lab");
    expect(layer?.tilePath).toContain("labs_v4");
  });

  it("falls back to 2d raster when asked", () => {
    const raster = findRasterMap("customs");
    expect(raster?.url).toBe("https://tarkov.dev/maps/customs-2d.jpg");
  });

  it("maps floor names and svg github fallback", () => {
    expect(floorLabel("2nd Floor")).toBe("2 层");
    expect(svgFallbackUrl("https://assets.tarkov.dev/maps/svg/Woods.svg")).toBe(
      "https://raw.githubusercontent.com/the-hideout/tarkov-dev-svg-maps/refs/heads/main/Woods.svg",
    );
  });
});
