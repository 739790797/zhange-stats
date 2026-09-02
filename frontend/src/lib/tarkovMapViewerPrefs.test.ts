import { describe, expect, it } from "vitest";
import { defaultExtractKindFlags } from "./tarkovMapExtracts";
import { defaultTarkovMapKindFlags } from "./tarkovMapMarkers";
import { defaultSpawnKindFlags } from "./tarkovMapSpawns";
import {
  DEFAULT_TARKOV_MAP_VIEWER_PREFS,
  overlayFlagsForMode,
  parseTarkovMapViewerPrefs,
  resolveMapFloor,
  resolveMapStyle,
  withExtractKind,
  withHazardKind,
  withLootContainerKind,
  withMapFloor,
  withSpawnKind,
} from "./tarkovMapViewerPrefs";

const emptyDefaults = {
  ...DEFAULT_TARKOV_MAP_VIEWER_PREFS,
  floorsByMap: {},
  extractKinds: defaultExtractKindFlags(true),
  spawnKinds: defaultSpawnKindFlags(true),
  hazardKinds: defaultTarkovMapKindFlags(),
  lootContainerKinds: defaultTarkovMapKindFlags(),
};

describe("parseTarkovMapViewerPrefs", () => {
  it("returns defaults for empty and invalid payloads", () => {
    expect(parseTarkovMapViewerPrefs(null)).toEqual(emptyDefaults);
    expect(parseTarkovMapViewerPrefs("{")).toEqual(emptyDefaults);
    expect(parseTarkovMapViewerPrefs("[]")).toEqual(emptyDefaults);
  });

  it("keeps valid fields, empty ground floors, and drops junk", () => {
    expect(
      parseTarkovMapViewerPrefs(
        JSON.stringify({
          style: "tile",
          floorsByMap: { customs: "2nd Floor", factory: "", 1: true },
          extractKinds: {
            pmc: true,
            scav: false,
            shared: true,
            transit: false,
          },
          spawnKinds: { pmc: false, scav: true, boss: false },
          showLabels: false,
          showQuests: false,
          extra: 1,
        }),
      ),
    ).toEqual({
      style: "tile",
      floorsByMap: { customs: "2nd Floor", factory: "" },
      extractKinds: {
        pmc: true,
        scav: false,
        shared: true,
        transit: false,
      },
      spawnKinds: { pmc: false, scav: true, boss: false },
      showLabels: false,
      showQuests: false,
      showLocks: true,
      showHazards: true,
      showSwitches: true,
      showStationary: true,
      showBtrStops: true,
      showLootContainers: false,
      hazardKinds: {},
      lootContainerKinds: {},
    });
  });

  it("defaults locks on and loot containers off when old storage omits them", () => {
    const parsed = parseTarkovMapViewerPrefs(
      JSON.stringify({
        style: "svg",
        showLabels: true,
        showQuests: true,
      }),
    );
    expect(parsed.showLocks).toBe(true);
    expect(parsed.showHazards).toBe(true);
    expect(parsed.showSwitches).toBe(true);
    expect(parsed.showStationary).toBe(true);
    expect(parsed.showBtrStops).toBe(true);
    expect(parsed.showLootContainers).toBe(false);
    expect(parsed.hazardKinds).toEqual({});
    expect(parsed.lootContainerKinds).toEqual({});
  });

  it("migrates legacy showExtracts boolean into extractKinds", () => {
    expect(
      parseTarkovMapViewerPrefs(
        JSON.stringify({
          style: "svg",
          showExtracts: false,
          showBosses: true,
          showLabels: true,
          showQuests: true,
        }),
      ).extractKinds,
    ).toEqual(defaultExtractKindFlags(false));
    expect(
      parseTarkovMapViewerPrefs(
        JSON.stringify({ showExtracts: true }),
      ).extractKinds,
    ).toEqual(defaultExtractKindFlags(true));
  });

  it("migrates legacy showBosses into spawnKinds.boss", () => {
    expect(
      parseTarkovMapViewerPrefs(
        JSON.stringify({ showBosses: false }),
      ).spawnKinds,
    ).toEqual({ pmc: true, scav: true, boss: false });
    expect(
      parseTarkovMapViewerPrefs(
        JSON.stringify({ showBosses: true }),
      ).spawnKinds,
    ).toEqual(defaultSpawnKindFlags(true));
  });
});

describe("resolveMapStyle", () => {
  it("uses saved style when the current map supports it", () => {
    expect(resolveMapStyle("tile", true, true)).toBe("tile");
    expect(resolveMapStyle("svg", true, true)).toBe("svg");
  });

  it("falls back when the saved style is missing on this map", () => {
    expect(resolveMapStyle("tile", true, false)).toBe("svg");
    expect(resolveMapStyle("svg", false, true)).toBe("tile");
  });
});

describe("resolveMapFloor", () => {
  it("restores a known floor and treats missing or unknown as ground", () => {
    expect(resolveMapFloor(undefined, ["2nd Floor"])).toBe("");
    expect(resolveMapFloor("", ["2nd Floor"])).toBe("");
    expect(resolveMapFloor("2nd Floor", ["2nd Floor"])).toBe("2nd Floor");
    expect(resolveMapFloor("gone", ["2nd Floor"])).toBe("");
  });
});

describe("withMapFloor", () => {
  it("writes per-map floors without dropping other maps", () => {
    const prev = withMapFloor(emptyDefaults, "customs", "2nd Floor");
    expect(withMapFloor(prev, "factory", "")).toEqual({
      ...emptyDefaults,
      floorsByMap: { customs: "2nd Floor", factory: "" },
    });
    expect(withMapFloor(prev, "", "2nd Floor")).toEqual(prev);
  });
});

describe("withExtractKind", () => {
  it("toggles one extract kind without dropping others", () => {
    expect(withExtractKind(emptyDefaults, "scav", false).extractKinds).toEqual({
      pmc: true,
      scav: false,
      shared: true,
      transit: true,
    });
  });
});

describe("withSpawnKind", () => {
  it("toggles one spawn kind without dropping others", () => {
    expect(withSpawnKind(emptyDefaults, "boss", false).spawnKinds).toEqual({
      pmc: true,
      scav: true,
      boss: false,
    });
  });
});

describe("withHazardKind", () => {
  it("turns on a hazard kind and the parent", () => {
    const off = { ...emptyDefaults, showHazards: false };
    expect(withHazardKind(off, "minefield", true)).toEqual({
      ...off,
      showHazards: true,
      hazardKinds: { minefield: true },
    });
  });
});

describe("withLootContainerKind", () => {
  it("turns on one container kind without enabling others", () => {
    expect(withLootContainerKind(emptyDefaults, "jacket", true)).toEqual({
      ...emptyDefaults,
      showLootContainers: true,
      lootContainerKinds: { jacket: true },
    });
  });
});

describe("overlayFlagsForMode", () => {
  it("keeps only boss markers in spawn overlay mode", () => {
    expect(overlayFlagsForMode(emptyDefaults, "boss-spawns")).toEqual({
      extractKinds: defaultExtractKindFlags(false),
      spawnKinds: { pmc: false, scav: false, boss: true },
      showLabels: false,
      showQuests: false,
      showLocks: false,
      showHazards: false,
      showSwitches: false,
      showStationary: false,
      showBtrStops: false,
      showLootContainers: false,
      hazardKinds: {},
      lootContainerKinds: {},
    });
  });
});
