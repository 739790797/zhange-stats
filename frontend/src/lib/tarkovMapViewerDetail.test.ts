import { describe, expect, it } from "vitest";
import type { TarkovMapDetail } from "@/api/guidesApi";
import { tarkovMapViewerLayerProps } from "./tarkovMapViewerDetail";

describe("tarkovMapViewerLayerProps", () => {
  it("returns empty layers when detail is missing", () => {
    expect(tarkovMapViewerLayerProps()).toEqual({
      parentSlug: undefined,
      extracts: undefined,
      bosses: undefined,
      spawns: undefined,
      locks: undefined,
      hazards: undefined,
      switches: undefined,
      stationaryWeapons: undefined,
      btrStops: undefined,
      lootContainers: undefined,
      lootLoose: undefined,
      places: undefined,
    });
  });

  it("maps parent slug and marker arrays", () => {
    const detail = {
      parent_slug: "customs",
      extracts: [{ name: "ZB-1011" }],
      places: [{ id: 1, name: "dorms" }],
    } as TarkovMapDetail;
    expect(tarkovMapViewerLayerProps(detail)).toMatchObject({
      parentSlug: "customs",
      extracts: detail.extracts,
      places: detail.places,
    });
  });
});
