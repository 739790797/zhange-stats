import { describe, expect, it } from "vitest";
import rawMaps from "@/data/tarkov-dev-maps.json";
import type { TarkovDevMapGroup } from "./tarkovMapImages";
import {
  hasTarkovMapLabel,
  tarkovBossMapLabel,
  tarkovMapLabel,
} from "./tarkovMapLabelsZh";

describe("tarkovMapLabel", () => {
  it("translates iconic place names used on the map overlay", () => {
    expect(tarkovMapLabel("Dorms")).toBe("宿舍");
    expect(tarkovMapLabel("Big Red")).toBe("大红房");
    expect(tarkovMapLabel("Primorsky Ave.")).toBe("滨海大道");
    expect(tarkovMapLabel("Power Station")).toBe("发电站");
    expect(tarkovMapLabel("ТАРЗДРАВ")).toBe("塔尔健康");
    expect(tarkovMapLabel("New Gas Station")).toBe("新加油站");
    expect(tarkovMapLabel("Stronghold")).toBe("要塞");
  });

  it("uses shoreline community names over shared English labels", () => {
    expect(tarkovMapLabel("Resort", "shoreline")).toBe("疗养院");
    expect(tarkovMapLabel("West Wing", "shoreline")).toBe("西楼");
    expect(tarkovMapLabel("East Wing", "shoreline")).toBe("东楼");
    expect(tarkovMapLabel("Admin", "shoreline")).toBe("行政楼");
    expect(tarkovMapLabel("Power Station", "shoreline")).toBe("变电站");
    expect(tarkovMapLabel("Cottages", "shoreline")).toBe("别墅区");
    expect(tarkovMapLabel("Construction", "shoreline")).toBe("蓝铁皮");
    expect(tarkovMapLabel("Radio Tower", "shoreline")).toBe("红白电塔");
    expect(tarkovMapLabel("Scav Island", "shoreline")).toBe("灯塔");
    // shared English stays map-specific elsewhere
    expect(tarkovMapLabel("Power Station", "interchange")).toBe("发电站");
    expect(tarkovMapLabel("Cottages", "lighthouse")).toBe("别墅");
    expect(tarkovMapLabel("Construction", "customs")).toBe("工地");
  });

  it("keeps unknown labels as-is", () => {
    expect(tarkovMapLabel("Unknown Spot")).toBe("Unknown Spot");
    expect(tarkovMapLabel("")).toBe("");
  });

  it("keeps only the boss name before a location suffix", () => {
    expect(tarkovBossMapLabel("Glukhar - Storage Bunker")).toBe("Glukhar");
    expect(tarkovBossMapLabel("Glukhar · Storage Bunker")).toBe("Glukhar");
    expect(tarkovBossMapLabel("Glukhar")).toBe("Glukhar");
    expect(tarkovBossMapLabel("")).toBe("");
  });

  it("covers every overlay label in tarkov-dev-maps.json", () => {
    const missing: string[] = [];
    for (const group of rawMaps as TarkovDevMapGroup[]) {
      for (const layer of group.maps || []) {
        for (const label of layer.labels || []) {
          const text = String(label.text || "").trim();
          if (text && !hasTarkovMapLabel(text)) missing.push(text);
        }
      }
    }
    expect(missing).toEqual([]);
  });
});
