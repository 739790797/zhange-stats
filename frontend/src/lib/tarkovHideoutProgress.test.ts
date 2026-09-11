import { describe, expect, it } from "vitest";
import {
  applyHideoutLevel,
  canSetHideoutLevel,
  filledHideoutLevels,
  formatHideoutBonusValue,
  hideoutDefaultLevel,
  indexHideoutStations,
  skillReqMet,
  traderReqMet,
  type HideoutStationSpec,
} from "./tarkovHideoutProgress";

function catalog(): HideoutStationSpec[] {
  return [
    {
      id: "stash",
      slug: "stash",
      levels: [
        { level: 1, station_requirements: [] },
        { level: 2, station_requirements: [{ station_id: "gen", level: 1 }] },
      ],
    },
    {
      id: "gen",
      slug: "generator",
      levels: [
        { level: 1, station_requirements: [] },
        { level: 2, station_requirements: [{ station_id: "stash", level: 2 }] },
      ],
    },
    {
      id: "bench",
      slug: "workbench",
      levels: [
        { level: 1, station_requirements: [{ station_id: "gen", level: 1 }] },
        { level: 2, station_requirements: [{ station_id: "gen", level: 2 }] },
      ],
    },
  ];
}

describe("tarkovHideoutProgress", () => {
  it("defaults stash to 1 and other stations to 0", () => {
    const levels = filledHideoutLevels(catalog(), {});
    expect(levels.stash).toBe(1);
    expect(levels.gen).toBe(0);
    expect(levels.bench).toBe(0);
    expect(hideoutDefaultLevel({ slug: "stash" })).toBe(1);
  });

  it("blocks upgrade until station prereqs hold", () => {
    const stations = catalog();
    const levels = filledHideoutLevels(stations, {});
    const byId = indexHideoutStations(stations);
    expect(canSetHideoutLevel(byId.get("bench"), 1, levels, byId)).toBe(false);
    expect(() => applyHideoutLevel(stations, levels, "bench", 1)).toThrow(
      /前置/,
    );
    const next = applyHideoutLevel(stations, levels, "gen", 1);
    expect(next.gen).toBe(1);
    expect(applyHideoutLevel(stations, next, "bench", 1).bench).toBe(1);
  });

  it("cascades dependents on downgrade", () => {
    const stations = catalog();
    const start = filledHideoutLevels(stations, {
      stash: 2,
      gen: 2,
      bench: 2,
    });
    const mid = applyHideoutLevel(stations, start, "gen", 1);
    expect(mid).toEqual({ stash: 2, gen: 1, bench: 1 });
    expect(applyHideoutLevel(stations, mid, "gen", 0)).toEqual({
      stash: 1,
      gen: 0,
      bench: 0,
    });
  });

  it("clamps stash to at least 1", () => {
    const stations = catalog();
    expect(applyHideoutLevel(stations, { stash: 1 }, "stash", 0).stash).toBe(1);
  });

  it("keeps trader/skill unset until user data exists", () => {
    expect(traderReqMet({ slug: "prapor", level: 2 }, undefined)).toBeNull();
    expect(skillReqMet({ skill_id: "HideoutManagement", level: 5 }, undefined)).toBeNull();
    expect(traderReqMet({ slug: "prapor", level: 2 }, { prapor: 2 })).toBe(true);
    expect(traderReqMet({ slug: "prapor", level: 2 }, { prapor: 1 })).toBe(false);
  });

  it("formats bonus values", () => {
    expect(formatHideoutBonusValue("ExperienceRate", 0.15)).toBe("+15%");
    expect(formatHideoutBonusValue("FuelConsumption", -0.5)).toBe("-50%");
    expect(formatHideoutBonusValue("StashSize", 300)).toBe("+300");
    expect(formatHideoutBonusValue("UnlockArmorRepair", 1)).toBe("解锁");
  });
});
