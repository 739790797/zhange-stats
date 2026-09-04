import type { TarkovMapDetail } from "@/api/guidesApi";

/** 把地图详情里的标点层展开成 MapViewer / LiveMap 的 props。 */
export function tarkovMapViewerLayerProps(detail?: TarkovMapDetail | null) {
  return {
    parentSlug: detail?.parent_slug || undefined,
    extracts: detail?.extracts,
    bosses: detail?.bosses,
    spawns: detail?.spawns,
    locks: detail?.locks,
    hazards: detail?.hazards,
    switches: detail?.switches,
    stationaryWeapons: detail?.stationary_weapons,
    btrStops: detail?.btr_stops,
    lootContainers: detail?.loot_containers,
    lootLoose: detail?.loot_loose,
    places: detail?.places,
  };
}
