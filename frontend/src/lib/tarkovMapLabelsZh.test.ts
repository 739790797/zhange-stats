import { describe, expect, it } from "vitest";
import rawMaps from "@/data/tarkov-dev-maps.json";
import type { TarkovDevMapGroup } from "./tarkovMapImages";
import { hasTarkovMapLabel, tarkovMapLabel } from "./tarkovMapLabelsZh";

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

  it("keeps unknown labels as-is", () => {
    expect(tarkovMapLabel("Unknown Spot")).toBe("Unknown Spot");
    expect(tarkovMapLabel("")).toBe("");
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
