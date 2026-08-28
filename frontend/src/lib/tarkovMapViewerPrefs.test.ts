import { describe, expect, it } from "vitest";
import { defaultExtractKindFlags } from "./tarkovMapExtracts";
import { defaultSpawnKindFlags } from "./tarkovMapSpawns";
import {
  DEFAULT_TARKOV_MAP_VIEWER_PREFS,
  parseTarkovMapViewerPrefs,
  resolveMapFloor,
  resolveMapStyle,
  withExtractKind,
  withMapFloor,
  withSpawnKind,
} from "./tarkovMapViewerPrefs";

const emptyDefaults = {
  ...DEFAULT_TARKOV_MAP_VIEWER_PREFS,
  floorsByMap: {},
  extractKinds: defaultExtractKindFlags(true),
  spawnKinds: defaultSpawnKindFlags(true),
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
    });
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
