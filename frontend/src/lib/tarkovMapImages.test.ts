import { describe, expect, it } from "vitest";
import rawMaps from "@/data/tarkov-dev-maps.json";
import {
  findInteractiveMap,
  findRasterMap,
  floorLabel,
  svgFallbackUrl,
  type TarkovDevMapGroup,
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
    expect(findInteractiveMap("factory-night")?.key).toBe("factory");
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
    expect(floorLabel("1st Floor")).toBe("1 层");
    expect(floorLabel("2nd Floor")).toBe("2 层");
    expect(floorLabel("Technical")).toBe("技术层");
    expect(floorLabel("Infirmary")).toBe("医务室");
    expect(floorLabel("Officers' Deck")).toBe("军官甲板");
    expect(svgFallbackUrl("https://assets.tarkov.dev/maps/svg/Woods.svg")).toBe(
      "https://raw.githubusercontent.com/the-hideout/tarkov-dev-svg-maps/refs/heads/main/Woods.svg",
    );
  });

  it("translates every floor/layer name in maps.json", () => {
    const missing: string[] = [];
    for (const group of rawMaps as TarkovDevMapGroup[]) {
      for (const layer of group.maps || []) {
        for (const floor of layer.layers || []) {
          const name = String(floor.name || "").trim();
          if (name && floorLabel(name) === name) missing.push(name);
        }
      }
    }
    expect([...new Set(missing)]).toEqual([]);
  });
});
