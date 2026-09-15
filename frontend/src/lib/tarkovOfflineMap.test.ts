import { describe, expect, it } from "vitest";
import { parseOfflineMapId, resolveOfflineLogMapId } from "./tarkovOfflineMap";

describe("parseOfflineMapId", () => {
  it("normalizes known raid-prep maps", () => {
    expect(parseOfflineMapId("factory-night")).toBe("night-factory");
    expect(parseOfflineMapId("customs")).toBe("customs");
    expect(parseOfflineMapId("unknown-place")).toBe("");
  });
});

describe("resolveOfflineLogMapId", () => {
  it("keeps the log map when present", () => {
    expect(
      resolveOfflineLogMapId({
        logMapId: "shoreline",
        offlineMapId: "customs",
        raidMode: "offline",
        phaseKind: "raid_started",
      }),
    ).toBe("shoreline");
  });

  it("uses the hand-picked map for an offline raid without location", () => {
    expect(
      resolveOfflineLogMapId({
        logMapId: "",
        offlineMapId: "customs",
        raidMode: "offline",
        phaseKind: "raid_started",
      }),
    ).toBe("customs");
  });

  it("uses the hand-picked map while loading a map with no location", () => {
    expect(
      resolveOfflineLogMapId({
        logMapId: "",
        offlineMapId: "woods",
        raidMode: "online",
        phaseKind: "map_loading",
      }),
    ).toBe("woods");
  });

  it("does not force the map after raid exit or in the menu", () => {
    expect(
      resolveOfflineLogMapId({
        logMapId: "",
        offlineMapId: "customs",
        raidMode: "offline",
        phaseKind: "raid_exited",
      }),
    ).toBe("");
    expect(
      resolveOfflineLogMapId({
        logMapId: "",
        offlineMapId: "customs",
        raidMode: "online",
        phaseKind: "matching_aborted",
      }),
    ).toBe("");
    expect(
      resolveOfflineLogMapId({
        logMapId: "",
        offlineMapId: "customs",
        raidMode: "",
        phaseKind: "",
      }),
    ).toBe("");
  });
});
