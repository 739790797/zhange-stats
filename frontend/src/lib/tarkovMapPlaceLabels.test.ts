import { describe, expect, it } from "vitest";
import { findInteractiveMap } from "./tarkovMapImages";
import {
  hasCustomMapPlaceLabels,
  resolveMapPlaceLabels,
} from "./tarkovMapPlaceLabels";

function overlayTexts(slug: string): string[] {
  const layer = findInteractiveMap(slug);
  expect(layer).toBeTruthy();
  return resolveMapPlaceLabels(layer!).map((row) => row.text);
}

describe("resolveMapPlaceLabels", () => {
  it("replaces shoreline tarkov.dev labels with the Chinese community overlay", () => {
    const texts = overlayTexts("shoreline");
    expect(hasCustomMapPlaceLabels("shoreline")).toBe(true);
    expect(texts).toEqual(
      expect.arrayContaining([
        "疗养院",
        "行政楼",
        "西楼",
        "东楼",
        "停车场",
        "真别墅",
        "假别墅",
        "蓝铁皮",
        "红白电塔",
        "雷达站",
        "村落",
      ]),
    );
    for (const banned of [
      "Resort",
      "Admin",
      "Cottages",
      "Construction",
      "Radio Tower",
      "北楼",
      "豪宅",
      "工地",
      "无线电塔",
    ]) {
      expect(texts).not.toContain(banned);
    }
    expect(texts.some((text) => /[A-Za-z]/.test(text))).toBe(false);
  });

  it("splits the two cottages west/east and keeps 蓝铁皮 toward the resort", () => {
    const layer = findInteractiveMap("shoreline");
    const byText = new Map(
      resolveMapPlaceLabels(layer!).map((row) => [row.text, row.position]),
    );
    const fake = byText.get("假别墅");
    const real = byText.get("真别墅");
    const blue = byText.get("蓝铁皮");
    expect(fake && real && blue).toBeTruthy();
    // 海岸线 +X 朝西：假别墅在西，真别墅在东，蓝铁皮更靠疗养院。
    expect(fake![0]).toBeGreaterThan(real![0]);
    expect(real![0]).toBeGreaterThan(blue![0]);
  });

  it("still translates other maps from tarkov.dev overlay text", () => {
    expect(hasCustomMapPlaceLabels("customs")).toBe(false);
    const texts = overlayTexts("customs");
    expect(texts).toContain("宿舍");
    expect(texts).toContain("大红房");
    expect(texts).not.toContain("Dorms");
  });
});
