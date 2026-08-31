import type { TarkovDevLabel, TarkovDevMapLayer } from "@/lib/tarkovMapImages";
import { tarkovMapLabel } from "@/lib/tarkovMapLabelsZh";

/**
 * 地名层：有自定义表的地图完全弃用 tarkov.dev labels，只画这里的中文点。
 * 坐标仍用同一套游戏 xz（与 maps.json 一致），位置按社区图拆点，不跟上游英文名走。
 */
const CUSTOM_MAP_PLACE_LABELS: Record<string, TarkovDevLabel[]> = {
  shoreline: [
    { text: "疗养院", position: [-258.2, -71.2], size: 100 },
    { text: "行政楼", position: [-252, -146] },
    { text: "西楼", position: [-171, -83] },
    { text: "东楼", position: [-329, -83] },
    { text: "停车场", position: [-85, -32] },
    { text: "假别墅", position: [162, 86] },
    { text: "真别墅", position: [96, 108] },
    { text: "蓝铁皮", position: [52, 134] },
    { text: "红白电塔", position: [-708.9, 93.91] },
    { text: "雷达站", position: [-496, 257] },
    { text: "变电站", position: [-215.8, 178.4] },
    { text: "加油站", position: [-189.3, 420] },
    { text: "沼泽", position: [326, -118.5] },
    { text: "村落", position: [418.4, 118] },
    { text: "小屋", position: [288, 144] },
    { text: "坦克桥", position: [-355, 188] },
    { text: "码头", position: [-338.6, 525] },
    { text: "灯塔", position: [216, 424] },
    { text: "公交站", position: [-96, -6] },
    { text: "地堡", position: [-153, -290] },
    { text: "吊车", position: [-625, 484] },
    { text: "农场", position: [-622, -202] },
  ],
};

function mapPlaceKey(layer: Pick<TarkovDevMapLayer, "key" | "normalizedName">): string {
  return (layer.normalizedName || layer.key || "").trim().toLowerCase();
}

export function hasCustomMapPlaceLabels(mapKey: string): boolean {
  return Object.prototype.hasOwnProperty.call(
    CUSTOM_MAP_PLACE_LABELS,
    (mapKey || "").trim().toLowerCase(),
  );
}

/** 最终画在地图上的地名。有自定义表则不读 tarkov.dev。 */
export function resolveMapPlaceLabels(
  layer: Pick<TarkovDevMapLayer, "key" | "normalizedName" | "labels">,
): TarkovDevLabel[] {
  const key = mapPlaceKey(layer);
  const custom = CUSTOM_MAP_PLACE_LABELS[key];
  if (custom) return custom;
  const out: TarkovDevLabel[] = [];
  for (const label of layer.labels || []) {
    if (!label.position || label.position.length < 2) continue;
    out.push({ ...label, text: tarkovMapLabel(label.text, key) });
  }
  return out;
}
